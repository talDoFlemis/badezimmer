package main

import (
	"context"
	"encoding/binary"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/talDoFlemis/badezimmer/go-water-leak/badezimmer"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/emptypb"
)

const (
	randomSeed                     = 42069
	intervalBetweenLeaksInSeconds  = 10.0
)

var (
	possibleSeverities = []string{"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}
	possibleLocations  = []string{"BATHROOM"}
)

type WaterLeakDetector struct {
	mdns *BadezimmerMDNS
	info *MDNSServiceInfo
	ctx  context.Context
	cancel context.CancelFunc
}

func NewWaterLeakDetector(port int32) *WaterLeakDetector {
	ctx, cancel := context.WithCancel(context.Background())
	
	rand.Seed(randomSeed)
	
	info := &MDNSServiceInfo{
		Name:     "Aliexpress Water Leak Detector",
		Type:     "_waterleak._tcp.local.",
		Port:     port,
		Kind:     badezimmer.DeviceKind_SENSOR_KIND,
		Category: badezimmer.DeviceCategory_WATER_LEAK,
		Protocol: badezimmer.TransportProtocol_TCP_PROTOCOL,
		Properties: map[string]string{
			"severity": possibleSeverities[rand.Intn(len(possibleSeverities))],
			"location": possibleLocations[rand.Intn(len(possibleLocations))],
		},
		Addresses: getLocalIPv4Addresses(),
		TTL:       DefaultTTL,
	}
	
	return &WaterLeakDetector{
		mdns:   NewBadezimmerMDNS(),
		info:   info,
		ctx:    ctx,
		cancel: cancel,
	}
}

func (w *WaterLeakDetector) Start() error {
	// Start MDNS
	if err := w.mdns.Start(); err != nil {
		return fmt.Errorf("failed to start MDNS: %w", err)
	}
	
	// Register service
	if err := w.mdns.RegisterService(w.info); err != nil {
		return fmt.Errorf("failed to register service: %w", err)
	}
	
	// Start TCP server
	listener, err := net.Listen("tcp", fmt.Sprintf("0.0.0.0:%d", w.info.Port))
	if err != nil {
		return fmt.Errorf("failed to start TCP server: %w", err)
	}
	
	log.Printf("Starting Water Leak Detector service on port %d", w.info.Port)
	
	// Start random data generator
	go w.generateRandomData()
	
	// Accept connections
	go func() {
		for {
			conn, err := listener.Accept()
			if err != nil {
				select {
				case <-w.ctx.Done():
					return
				default:
					log.Printf("Error accepting connection: %v", err)
					continue
				}
			}
			go w.handleConnection(conn)
		}
	}()
	
	return nil
}

func (w *WaterLeakDetector) Stop() error {
	log.Println("Stopping Water Leak Detector service...")
	w.cancel()
	
	// Unregister service
	if err := w.mdns.UnregisterService(w.info); err != nil {
		log.Printf("Error unregistering service: %v", err)
	}
	
	// Close MDNS
	if err := w.mdns.Close(); err != nil {
		log.Printf("Error closing MDNS: %v", err)
	}
	
	log.Println("Service stopped")
	return nil
}

func (w *WaterLeakDetector) generateRandomData() {
	ticker := time.NewTicker(time.Duration(intervalBetweenLeaksInSeconds) * time.Second)
	defer ticker.Stop()
	
	for {
		select {
		case <-w.ctx.Done():
			return
		case <-ticker.C:
			w.info.Properties["severity"] = possibleSeverities[rand.Intn(len(possibleSeverities))]
			w.info.Properties["location"] = possibleLocations[rand.Intn(len(possibleLocations))]
			
			if err := w.mdns.UpdateService(w.info); err != nil {
				log.Printf("Error updating service: %v", err)
			}
		}
	}
}

func (w *WaterLeakDetector) handleConnection(conn net.Conn) {
	defer conn.Close()
	
	addr := conn.RemoteAddr()
	log.Printf("Connected by %s", addr)
	
	for {
		// Read length prefix
		lengthBuf := make([]byte, 4)
		if _, err := io.ReadFull(conn, lengthBuf); err != nil {
			if err != io.EOF {
				log.Printf("Error reading length prefix: %v", err)
			}
			return
		}
		
		messageLength := binary.BigEndian.Uint32(lengthBuf)
		if messageLength == 0 || messageLength > 64*1024 {
			log.Printf("Invalid message length: %d", messageLength)
			return
		}
		
		// Read message
		messageBuf := make([]byte, messageLength)
		if _, err := io.ReadFull(conn, messageBuf); err != nil {
			log.Printf("Error reading message: %v", err)
			return
		}
		
		// Parse request
		request := &badezimmer.BadezimmerRequest{}
		if err := proto.Unmarshal(messageBuf, request); err != nil {
			log.Printf("Error unmarshaling request: %v", err)
			return
		}
		
		// Execute request
		response := w.executeRequest(request)
		
		// Send response
		responseBytes, err := proto.Marshal(response)
		if err != nil {
			log.Printf("Error marshaling response: %v", err)
			return
		}
		
		responseLengthBuf := make([]byte, 4)
		binary.BigEndian.PutUint32(responseLengthBuf, uint32(len(responseBytes)))
		
		if _, err := conn.Write(responseLengthBuf); err != nil {
			log.Printf("Error writing response length: %v", err)
			return
		}
		
		if _, err := conn.Write(responseBytes); err != nil {
			log.Printf("Error writing response: %v", err)
			return
		}
	}
}

func (w *WaterLeakDetector) executeRequest(request *badezimmer.BadezimmerRequest) *badezimmer.BadezimmerResponse {
	// For now, just return empty response for all requests
	return &badezimmer.BadezimmerResponse{
		Response: &badezimmer.BadezimmerResponse_Empty{
			Empty: &emptypb.Empty{},
		},
	}
}

func getRandomAvailableTCPPort() (int32, error) {
	listener, err := net.Listen("tcp", ":0")
	if err != nil {
		return 0, err
	}
	defer listener.Close()
	
	addr := listener.Addr().(*net.TCPAddr)
	return int32(addr.Port), nil
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lshortfile)
	
	// Check for port from environment variable
	var port int32
	if portStr := os.Getenv("PORT"); portStr != "" {
		portInt, err := strconv.Atoi(portStr)
		if err != nil {
			log.Fatalf("Invalid PORT environment variable: %v", err)
		}
		port = int32(portInt)
	} else {
		// Get random available port
		var err error
		port, err = getRandomAvailableTCPPort()
		if err != nil {
			log.Fatalf("Failed to get available port: %v", err)
		}
	}
	
	detector := NewWaterLeakDetector(port)
	
	if err := detector.Start(); err != nil {
		log.Fatalf("Failed to start detector: %v", err)
	}
	
	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	
	<-sigChan
	
	if err := detector.Stop(); err != nil {
		log.Fatalf("Error stopping detector: %v", err)
	}
}
