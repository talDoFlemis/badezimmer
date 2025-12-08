package main

import (
	"context"
	"encoding/binary"
	"fmt"
	"log"
	"math/rand"
	"net"
	"sync"
	"syscall"
	"time"

	"github.com/talDoFlemis/badezimmer/go-water-leak/badezimmer"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/timestamppb"
)

const (
	MulticastIP   = "224.0.0.251"
	MulticastPort = 5369
	DefaultTTL    = 4500
	ServiceDiscoveryType = "_services._dns-sd._udp.local"
	
	// SO_REUSEPORT for Linux
	SO_REUSEPORT = 15
)

type MDNSServiceInfo struct {
	Name       string
	Type       string
	Port       int32
	Kind       badezimmer.DeviceKind
	Category   badezimmer.DeviceCategory
	Protocol   badezimmer.TransportProtocol
	Properties map[string]string
	Addresses  []string
	TTL        int32
}

type BadezimmerMDNS struct {
	conn              *net.UDPConn
	registeredServices map[string]*MDNSServiceInfo // key: domain_name
	sentPackets       [][]byte
	sentPacketsMu     sync.Mutex
	ctx               context.Context
	cancel            context.CancelFunc
	wg                sync.WaitGroup
}

func NewBadezimmerMDNS() *BadezimmerMDNS {
	ctx, cancel := context.WithCancel(context.Background())
	return &BadezimmerMDNS{
		registeredServices: make(map[string]*MDNSServiceInfo),
		sentPackets:        make([][]byte, 0, 50),
		ctx:                ctx,
		cancel:             cancel,
	}
}

func (m *BadezimmerMDNS) Start() error {
	addr := &net.UDPAddr{
		IP:   net.ParseIP("0.0.0.0"),
		Port: MulticastPort,
	}

	// Create a listening connection with SO_REUSEPORT to allow multiple processes
	lc := net.ListenConfig{
		Control: func(network, address string, c syscall.RawConn) error {
			var opErr error
			err := c.Control(func(fd uintptr) {
				// Enable SO_REUSEADDR
				opErr = syscall.SetsockoptInt(int(fd), syscall.SOL_SOCKET, syscall.SO_REUSEADDR, 1)
				if opErr != nil {
					return
				}
				// Enable SO_REUSEPORT to allow multiple processes to bind to the same port
				opErr = syscall.SetsockoptInt(int(fd), syscall.SOL_SOCKET, SO_REUSEPORT, 1)
			})
			if err != nil {
				return err
			}
			return opErr
		},
	}

	packetConn, err := lc.ListenPacket(context.Background(), "udp4", addr.String())
	if err != nil {
		return fmt.Errorf("failed to listen UDP: %w", err)
	}

	conn, ok := packetConn.(*net.UDPConn)
	if !ok {
		return fmt.Errorf("failed to cast to UDPConn")
	}

	m.conn = conn

	// Join multicast group
	multicastIP := net.ParseIP(MulticastIP)
	
	err = conn.SetReadBuffer(65536)
	if err != nil {
		return fmt.Errorf("failed to set read buffer: %w", err)
	}

	// Get socket file descriptor and set multicast options
	file, err := conn.File()
	if err != nil {
		return fmt.Errorf("failed to get socket file: %w", err)
	}
	defer file.Close()

	fd := int(file.Fd())
	
	// Join multicast group using IP_ADD_MEMBERSHIP
	mreq := &syscall.IPMreq{
		Multiaddr: [4]byte{multicastIP[0], multicastIP[1], multicastIP[2], multicastIP[3]},
		Interface: [4]byte{0, 0, 0, 0}, // Use default interface
	}
	
	if err := syscall.SetsockoptIPMreq(fd, syscall.IPPROTO_IP, syscall.IP_ADD_MEMBERSHIP, mreq); err != nil {
		log.Printf("Warning: failed to join multicast group: %v", err)
	} else {
		log.Printf("Joined multicast group %s", MulticastIP)
	}

	log.Printf("BadezimmerMDNS listening on %s:%d", MulticastIP, MulticastPort)

	// Start receive loop
	m.wg.Add(1)
	go m.recvLoop()

	// Start renovation loop
	m.wg.Add(1)
	go m.renovateLoop()

	return nil
}

func (m *BadezimmerMDNS) Close() error {
	m.cancel()
	
	// Send goodbye packets for all registered services
	for _, info := range m.registeredServices {
		goodbyeInfo := *info
		goodbyeInfo.TTL = 0
		m.broadcastService(&goodbyeInfo)
		log.Printf("Sent goodbye packet for service: %s", info.Name)
	}

	if m.conn != nil {
		m.conn.Close()
	}
	
	m.wg.Wait()
	return nil
}

func (m *BadezimmerMDNS) RegisterService(info *MDNSServiceInfo) error {
	log.Printf("Registering service: %s on port %d", info.Name, info.Port)
	
	// Add random delay
	time.Sleep(time.Duration(150+rand.Intn(100)) * time.Millisecond)
	
	domainName := generateDomainName(info.Type, info.Name)
	m.registeredServices[domainName] = info
	
	// Broadcast service
	return m.broadcastService(info)
}

func (m *BadezimmerMDNS) UnregisterService(info *MDNSServiceInfo) error {
	log.Printf("Unregistering service: %s", info.Name)
	
	domainName := generateDomainName(info.Type, info.Name)
	delete(m.registeredServices, domainName)
	
	// Send goodbye packet
	goodbyeInfo := *info
	goodbyeInfo.TTL = 0
	return m.broadcastService(&goodbyeInfo)
}

func (m *BadezimmerMDNS) UpdateService(info *MDNSServiceInfo) error {
	log.Printf("Updating service: %s", info.Name)
	
	domainName := generateDomainName(info.Type, info.Name)
	m.registeredServices[domainName] = info
	
	return m.broadcastService(info)
}

func (m *BadezimmerMDNS) recvLoop() {
	defer m.wg.Done()
	
	buffer := make([]byte, 65536)
	for {
		select {
		case <-m.ctx.Done():
			return
		default:
		}
		
		m.conn.SetReadDeadline(time.Now().Add(1 * time.Second))
		n, addr, err := m.conn.ReadFromUDP(buffer)
		if err != nil {
			if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
				continue
			}
			log.Printf("Error reading from UDP: %v", err)
			continue
		}
		
		data := buffer[:n]
		
		// Skip our own packets
		if m.isSentPacket(data) {
			continue
		}
		
		log.Printf("Received packet from %s (%d bytes)", addr.IP, n)
		m.handlePacket(data, addr)
	}
}

func (m *BadezimmerMDNS) renovateLoop() {
	defer m.wg.Done()
	
	// Renovate at 75% of TTL
	renovationInterval := time.Duration(float64(DefaultTTL) * 0.75) * time.Second
	ticker := time.NewTicker(renovationInterval)
	defer ticker.Stop()
	
	for {
		select {
		case <-m.ctx.Done():
			return
		case <-ticker.C:
			count := 0
			for _, info := range m.registeredServices {
				if err := m.broadcastService(info); err != nil {
					log.Printf("Error renovating service %s: %v", info.Name, err)
				} else {
					count++
				}
			}
			if count > 0 {
				log.Printf("TTL renovation cycle completed (%d services)", count)
			}
		}
	}
}

func (m *BadezimmerMDNS) handlePacket(data []byte, addr *net.UDPAddr) {
	protoBytes, err := getProtobufData(data)
	if err != nil {
		log.Printf("Error extracting protobuf data: %v", err)
		return
	}
	
	packet := &badezimmer.MDNS{}
	if err := proto.Unmarshal(protoBytes, packet); err != nil {
		log.Printf("Error unmarshaling MDNS packet: %v", err)
		return
	}
	
	switch packet.GetData().(type) {
	case *badezimmer.MDNS_QueryRequest:
		m.handleQuery(packet.GetQueryRequest(), addr)
	case *badezimmer.MDNS_QueryResponse:
		// We could handle responses here if needed
		log.Printf("Received query response from %s", addr.IP)
	}
}

func (m *BadezimmerMDNS) handleQuery(query *badezimmer.MDNSQueryRequest, addr *net.UDPAddr) {
	var ptrRecords []*badezimmer.MDNSRecord
	var additionalRecords []*badezimmer.MDNSRecord
	
	for _, question := range query.Questions {
		if question.Name == ServiceDiscoveryType {
			// Respond with all our registered services
			for _, info := range m.registeredServices {
				records := infoToRecords(info)
				if len(records) > 0 {
					ptrRecords = append(ptrRecords, records[0])
					additionalRecords = append(additionalRecords, records[1:]...)
				}
			}
		} else {
			// Check if this question matches any of our registered services
			for _, info := range m.registeredServices {
				if info.Type == question.Name {
					records := infoToRecords(info)
					if len(records) > 0 {
						ptrRecords = append(ptrRecords, records[0])
						additionalRecords = append(additionalRecords, records[1:]...)
					}
				}
			}
		}
	}
	
	if len(ptrRecords) > 0 {
		response := &badezimmer.MDNSQueryResponse{
			Answers:           ptrRecords,
			AdditionalRecords: additionalRecords,
		}
		m.sendResponse(response)
	}
}

func (m *BadezimmerMDNS) broadcastService(info *MDNSServiceInfo) error {
	records := infoToRecords(info)
	if len(records) == 0 {
		return fmt.Errorf("no records generated for service")
	}
	
	response := &badezimmer.MDNSQueryResponse{
		Answers:           []*badezimmer.MDNSRecord{records[0]},
		AdditionalRecords: records[1:],
	}
	
	return m.sendResponse(response)
}

func (m *BadezimmerMDNS) sendResponse(response *badezimmer.MDNSQueryResponse) error {
	packet := &badezimmer.MDNS{
		TransactionId: rand.Uint32(),
		Timestamp:     timestamppb.Now(),
		Data:          &badezimmer.MDNS_QueryResponse{QueryResponse: response},
	}
	
	return m.sendPacket(packet)
}

func (m *BadezimmerMDNS) sendPacket(packet *badezimmer.MDNS) error {
	rawBytes, err := prepareProtobufRequest(packet)
	if err != nil {
		return fmt.Errorf("failed to prepare packet: %w", err)
	}
	
	m.addSentPacket(rawBytes)
	
	addr := &net.UDPAddr{
		IP:   net.ParseIP(MulticastIP),
		Port: MulticastPort,
	}
	
	_, err = m.conn.WriteToUDP(rawBytes, addr)
	if err != nil {
		return fmt.Errorf("failed to send packet: %w", err)
	}
	
	log.Printf("Sent packet (%d bytes, txid: %d)", len(rawBytes), packet.TransactionId)
	return nil
}

func (m *BadezimmerMDNS) addSentPacket(data []byte) {
	m.sentPacketsMu.Lock()
	defer m.sentPacketsMu.Unlock()
	
	// Keep last 50 packets
	if len(m.sentPackets) >= 50 {
		m.sentPackets = m.sentPackets[1:]
	}
	m.sentPackets = append(m.sentPackets, data)
}

func (m *BadezimmerMDNS) isSentPacket(data []byte) bool {
	m.sentPacketsMu.Lock()
	defer m.sentPacketsMu.Unlock()
	
	for _, sent := range m.sentPackets {
		if bytesEqual(sent, data) {
			return true
		}
	}
	return false
}

func prepareProtobufRequest(msg proto.Message) ([]byte, error) {
	serialized, err := proto.Marshal(msg)
	if err != nil {
		return nil, err
	}
	
	length := uint32(len(serialized))
	lengthPrefix := make([]byte, 4)
	binary.BigEndian.PutUint32(lengthPrefix, length)
	
	return append(lengthPrefix, serialized...), nil
}

func getProtobufData(data []byte) ([]byte, error) {
	if len(data) < 4 {
		return nil, fmt.Errorf("data too short for length prefix")
	}
	
	messageLength := binary.BigEndian.Uint32(data[:4])
	if uint32(len(data)-4) < messageLength {
		return nil, fmt.Errorf("data shorter than expected message length")
	}
	
	return data[4 : 4+messageLength], nil
}

func generateDomainName(serviceType, instanceName string) string {
	return fmt.Sprintf("%s.%s", instanceName, serviceType)
}

func infoToRecords(info *MDNSServiceInfo) []*badezimmer.MDNSRecord {
	var records []*badezimmer.MDNSRecord
	domainName := generateDomainName(info.Type, info.Name)
	
	// 1. PTR Record
	ptrRecord := &badezimmer.MDNSRecord{
		Name:       info.Type,
		Ttl:        info.TTL,
		CacheFlush: false,
		Record: &badezimmer.MDNSRecord_PtrRecord{
			PtrRecord: &badezimmer.MDNSPointerRecord{
				Name:       info.Type,
				DomainName: domainName,
			},
		},
	}
	records = append(records, ptrRecord)
	
	// 2. A Records
	for _, ip := range info.Addresses {
		aRecord := &badezimmer.MDNSRecord{
			Name:       domainName,
			Ttl:        info.TTL,
			CacheFlush: true,
			Record: &badezimmer.MDNSRecord_ARecord{
				ARecord: &badezimmer.MDNSARecord{
					Name:    domainName,
					Address: ip,
				},
			},
		}
		records = append(records, aRecord)
	}
	
	// 3. SRV Record
	service := "_http"
	if parts := splitServiceType(info.Type); len(parts) > 0 {
		service = parts[0]
	}
	
	srvRecord := &badezimmer.MDNSRecord{
		Name:       domainName,
		Ttl:        info.TTL,
		CacheFlush: true,
		Record: &badezimmer.MDNSRecord_SrvRecord{
			SrvRecord: &badezimmer.MDNSSRVRecord{
				Name:     info.Name,
				Protocol: info.Protocol,
				Service:  service,
				Instance: info.Name,
				Port:     info.Port,
				Target:   domainName,
			},
		},
	}
	records = append(records, srvRecord)
	
	// 4. TXT Record
	txtEntries := make(map[string]string)
	txtEntries["kind"] = info.Kind.String()
	txtEntries["category"] = info.Category.String()
	for k, v := range info.Properties {
		txtEntries[k] = v
	}
	
	txtRecord := &badezimmer.MDNSRecord{
		Name:       domainName,
		Ttl:        info.TTL,
		CacheFlush: true,
		Record: &badezimmer.MDNSRecord_TxtRecord{
			TxtRecord: &badezimmer.MDNSTextRecord{
				Name:    domainName,
				Entries: txtEntries,
			},
		},
	}
	records = append(records, txtRecord)
	
	return records
}

func splitServiceType(serviceType string) []string {
	result := []string{}
	for i := 0; i < len(serviceType); i++ {
		if serviceType[i] == '.' {
			result = append(result, serviceType[:i])
			break
		}
	}
	return result
}

func getLocalIPv4Addresses() []string {
	var addresses []string
	
	ifaces, err := net.Interfaces()
	if err != nil {
		return addresses
	}
	
	excludedPrefixes := []string{"127.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22."}
	
	for _, iface := range ifaces {
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		
		for _, addr := range addrs {
			var ip net.IP
			switch v := addr.(type) {
			case *net.IPNet:
				ip = v.IP
			case *net.IPAddr:
				ip = v.IP
			}
			
			if ip == nil || ip.To4() == nil {
				continue
			}
			
			ipStr := ip.String()
			excluded := false
			for _, prefix := range excludedPrefixes {
				if len(ipStr) >= len(prefix) && ipStr[:len(prefix)] == prefix {
					excluded = true
					break
				}
			}
			
			if !excluded {
				addresses = append(addresses, ipStr)
			}
		}
	}
	
	return addresses
}

func bytesEqual(a, b []byte) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
