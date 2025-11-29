import logging
import socket
import asyncio
import random
import collections
from typing import Optional, List, Dict, Deque, Tuple

import asyncudp

from badezimmer import (
    MDNSQueryRequest,
    MDNSQueryResponse,
    MDNSQuestion,
    MDNSType,
    MDNSRecord,
    MDNSPointerRecord,
    MDNS,
    TransportProtocol,
)
from badezimmer.logger import setup_logger
from badezimmer.tcp import (
    prepare_protobuf_request,
    get_protobuf_data,
)
from badezimmer.info import (
    DEFAULT_TTL,
    EntryRecord,
    MDNSServiceInfo,
    current_time_millis,
    generate_domain_name,
)

logger = logging.getLogger(__name__)
setup_logger(logger)

_MULTICAST_IP = "224.0.0.251"
MULTICAST_PORT = 5369
RANDOM_SEED = 42069
SERVICE_DISCOVERY_TYPE = "_services._dns-sd._udp.local"


class NonUniqueNameException(Exception):
    pass


class BadezimmerServiceListener:
    def add_service(self, mdns: "BadezimmerMDNS", info: MDNSServiceInfo) -> None: ...
    def remove_service(self, mdns: "BadezimmerMDNS", info: MDNSServiceInfo) -> None: ...
    def update_service(self, mdns: "BadezimmerMDNS", info: MDNSServiceInfo) -> None: ...


class BadezimmerMDNS:
    def __init__(
        self,
        interval_between_tiebreaking_ms: float = 100.0,
        tiebreaking_attempts: int = 3,
        query_timeout_ms: int = 200,
        tiebreaking_max_drift_ms: float = 25.0,
        random_seed: int = RANDOM_SEED,
        automatic_cleanup: bool = True,
        interval_between_cleanup_seconds: float = 60,
        automatic_renovation: bool = True,
        interval_between_renovation_seconds: float = 60,
        health_check_timeout: float = 1.0,
        excluded_ip_prefixes: Optional[Tuple[str, ...]] = None,
    ):
        self.interval_tiebreaking_ms = interval_between_tiebreaking_ms
        self.tiebreaking_attempts = tiebreaking_attempts
        self.query_timeout_ms = query_timeout_ms
        self.tiebreaking_drift_ms = tiebreaking_max_drift_ms
        self.random = random.Random(random_seed)
        self.automatic_cleanup = automatic_cleanup
        self.interval_between_cleanup_seconds = interval_between_cleanup_seconds
        self.automatic_renovation = automatic_renovation
        self.interval_between_renovation_seconds = interval_between_renovation_seconds
        self.health_check_timeout = health_check_timeout
        self.excluded_ip_prefixes = excluded_ip_prefixes or (
            "127.",
            "172.17.",
            "172.18.",
            "172.19.",
            "172.20.",
            "172.21.",
            "172.22.",
        )

        self.registered_services: Dict[str, List[str]] = {}
        self.ptr_records: Dict[str, Dict[str, EntryRecord]] = {}
        self.non_ptr_records: Dict[str, Dict[str, List[EntryRecord]]] = {}
        self.listeners: List[BadezimmerServiceListener] = []

        self.sock: Optional[asyncudp.Socket] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._renovate_task: Optional[asyncio.Task] = None
        self._sent_packets: Deque[bytes] = collections.deque(maxlen=50)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self) -> None:
        if self.sock is not None:
            return

        self.sock = await asyncudp.create_socket(
            local_addr=("0.0.0.0", MULTICAST_PORT),
            reuse_port=True,
        )
        sock_obj = self.sock._transport.get_extra_info("socket")
        mreq = socket.inet_aton(_MULTICAST_IP) + socket.inet_aton("0.0.0.0")
        sock_obj.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        self._recv_task = asyncio.create_task(self._recv_loop())

        if self.automatic_cleanup:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        if self.automatic_renovation:
            self._renovate_task = asyncio.create_task(self._renovate_loop())

        logger.info(
            "BadezimmerMDNS listening",
            extra={"multicast_ip": _MULTICAST_IP, "port": MULTICAST_PORT},
        )

    async def close(self) -> None:
        # Unregister all local services on close by sending goodbye packets
        for svc_type, domains in list(self.registered_services.items()):
            for domain in domains:
                # Reconstruct info from cache to send a proper goodbye
                info = self._reconstruct_info_from_cache(svc_type, domain)
                if info:
                    # Set TTL to 0 for goodbye packet
                    info.ttl = 0
                    await self._broadcast_service(info)
                    logger.debug(
                        "Sent goodbye packet for service",
                        extra={"service_name": info.name, "type": svc_type},
                    )

        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
            self._recv_task = None

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        if self._renovate_task:
            self._renovate_task.cancel()
            try:
                await self._renovate_task
            except asyncio.CancelledError:
                pass
            self._renovate_task = None

        if self.sock:
            self.sock.close()
            self.sock = None

    def add_listener(self, listener: BadezimmerServiceListener) -> None:
        self.listeners.append(listener)

    def _notify_listeners_safe(self, callback) -> None:
        """Notify all listeners with error protection to prevent one failure from affecting others."""
        for listener in self.listeners:
            try:
                callback(listener)
            except Exception:
                logger.exception(
                    "Error notifying listener",
                    extra={"listener": listener.__class__.__name__},
                )

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired cache entries and check service connectivity."""
        while True:
            try:
                await asyncio.sleep(self.interval_between_cleanup_seconds)

                expired_services = []
                services_to_check = []

                # 1. Collect expired services and services needing health checks
                for service_type in list(self.ptr_records.keys()):
                    for domain_name in list(self.ptr_records[service_type].keys()):
                        entry = self.ptr_records[service_type][domain_name]

                        # Skip our own registered services
                        if domain_name in self.registered_services.get(
                            service_type, []
                        ):
                            continue

                        if entry.expired():
                            expired_services.append((service_type, domain_name))
                        else:
                            # Queue services for connectivity checks
                            info = self._reconstruct_info_from_cache(
                                service_type, domain_name
                            )
                            if info:
                                services_to_check.append(
                                    (service_type, domain_name, info)
                                )

                # 2. Check connectivity in parallel
                unresponsive_services = []
                if services_to_check:
                    check_tasks = [
                        self._check_service_alive(info)
                        for _, _, info in services_to_check
                    ]
                    results = await asyncio.gather(*check_tasks, return_exceptions=True)

                    for (service_type, domain_name, info), is_alive in zip(
                        services_to_check, results
                    ):
                        # Handle exceptions as service down
                        if isinstance(is_alive, Exception) or not is_alive:
                            unresponsive_services.append((service_type, domain_name))

                # 3. Remove expired services and notify listeners
                for service_type, domain_name in expired_services:
                    existing_info = self._reconstruct_info_from_cache(
                        service_type, domain_name
                    )
                    await self._remove_from_cache(service_type, domain_name)

                    if existing_info:
                        logger.debug(
                            "Removing expired service from cache",
                            extra={
                                "service_name": existing_info.name,
                                "type": service_type,
                                "domain": domain_name,
                            },
                        )
                        self._notify_listeners_safe(
                            lambda l: l.remove_service(self, existing_info)
                        )

                # 4. Remove unresponsive services
                for service_type, domain_name in unresponsive_services:
                    existing_info = self._reconstruct_info_from_cache(
                        service_type, domain_name
                    )
                    await self._remove_from_cache(service_type, domain_name)

                    if existing_info:
                        logger.debug(
                            "Removing unresponsive service",
                            extra={
                                "service_name": existing_info.name,
                                "type": service_type,
                                "domain": domain_name,
                            },
                        )
                        self._notify_listeners_safe(
                            lambda l: l.remove_service(self, existing_info)
                        )

                if expired_services or unresponsive_services:
                    logger.debug(
                        "Cleanup cycle completed",
                        extra={
                            "expired_count": len(expired_services),
                            "unresponsive_count": len(unresponsive_services),
                        },
                    )

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in cleanup loop")
                await asyncio.sleep(1)

    async def _check_service_alive(self, info: MDNSServiceInfo) -> bool:
        """Check if a service is alive by attempting to connect to its TCP port."""
        if not info.addresses or info.port == 0:
            return False

        # Only check TCP services (UDP health checks are unreliable)
        if info.protocol != TransportProtocol.TCP_PROTOCOL:
            return True

        # Try to connect to available addresses
        for address in info.addresses:
            # Skip excluded IP prefixes
            if address.startswith(self.excluded_ip_prefixes):
                continue

            try:
                conn = asyncio.open_connection(address, info.port)
                reader, writer = await asyncio.wait_for(
                    conn, timeout=self.health_check_timeout
                )
                writer.close()
                await writer.wait_closed()
                logger.debug(
                    "Service connectivity check passed",
                    extra={
                        "service_name": info.name,
                        "address": address,
                        "port": info.port,
                        "protocol": "TCP",
                    },
                )
                return True
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                # Expected errors for unavailable services
                continue
            except Exception:
                # Unexpected errors - log but continue checking other addresses
                logger.exception(
                    "Unexpected error checking service connectivity",
                    extra={
                        "service_name": info.name,
                        "address": address,
                        "port": info.port,
                    },
                )
                continue

        # If we couldn't connect to any address, service is down
        logger.debug(
            "Service connectivity check failed",
            extra={
                "service_name": info.name,
                "addresses": info.addresses,
                "port": info.port,
            },
        )
        return False

    async def _renovate_loop(self) -> None:
        """Periodically re-broadcast registered services to renovate their TTL on the network."""
        while True:
            try:
                # Renovate at 75% of TTL interval
                renovation_interval = DEFAULT_TTL * 0.75
                await asyncio.sleep(renovation_interval)

                services_renovated = 0

                # Re-broadcast all registered services
                for service_type, domain_list in list(self.registered_services.items()):
                    for domain_name in domain_list:
                        # Reconstruct service info from cache
                        info = self._reconstruct_info_from_cache(
                            service_type, domain_name
                        )
                        if info:
                            await self._broadcast_service(info)
                            services_renovated += 1

                if services_renovated > 0:
                    logger.debug(
                        "TTL renovation cycle completed",
                        extra={"services_renovated": services_renovated},
                    )

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in TTL renovation loop")
                await asyncio.sleep(1)

    async def _recv_loop(self) -> None:
        while True:
            try:
                if self.sock is None:
                    break
                data, addr = await self.sock.recvfrom()
                if data in self._sent_packets:
                    continue
                logger.debug(
                    "Received packet",
                    extra={"size_bytes": len(data), "source": addr[0], "port": addr[1]},
                )
                await self._handle_packet(data, addr)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in MDNS receive loop")
                await asyncio.sleep(0.1)

    def _send_packet(self, packet: MDNS) -> None:
        if self.sock is None:
            return
        packet.transaction_id = random.randint(1, 65535)
        packet.timestamp.GetCurrentTime()
        raw_bytes = prepare_protobuf_request(packet)
        self._sent_packets.append(raw_bytes)
        logger.debug(
            "Sending packet",
            extra={
                "size_bytes": len(raw_bytes),
                "transaction_id": packet.transaction_id,
            },
        )
        try:
            self.sock.sendto(raw_bytes, (_MULTICAST_IP, MULTICAST_PORT))
        except Exception:
            logger.exception("Failed to send MDNS packet")

    async def _handle_packet(self, data: bytes, addr: Tuple[str, int]) -> None:
        try:
            proto_bytes = get_protobuf_data(data)
            packet = MDNS()
            packet.ParseFromString(proto_bytes)

            payload_type = packet.WhichOneof("data")
            if payload_type == "query_request":
                await self._handle_query(packet.query_request, addr)
            elif payload_type == "query_response":
                await self._handle_response(packet.query_response, addr)
        except Exception:
            logger.exception("Failed to handle packet")

    async def _handle_query(
        self, query: MDNSQueryRequest, addr: Tuple[str, int]
    ) -> None:
        ptr_records: List[MDNSRecord] = []
        additional_records: List[MDNSRecord] = []

        for question in query.questions:
            if question.name == SERVICE_DISCOVERY_TYPE:
                for domain_list in self.registered_services.values():
                    for domain in domain_list:
                        svc_type = domain.split(".", 1)[1]
                        if (
                            svc_type in self.ptr_records
                            and domain in self.ptr_records[svc_type]
                        ):
                            ptr_records.append(
                                self.ptr_records[svc_type][domain].record
                            )
                            if domain in self.non_ptr_records:
                                for entries in self.non_ptr_records[domain].values():
                                    additional_records.extend(e.record for e in entries)

            elif question.name in self.registered_services:
                records_map = self.ptr_records.get(question.name, {})
                ptr_records.extend(e.record for e in records_map.values())
                for registered_domain in self.registered_services[question.name]:
                    if registered_domain in self.non_ptr_records:
                        for entries in self.non_ptr_records[registered_domain].values():
                            additional_records.extend(e.record for e in entries)

        if ptr_records:
            response = MDNSQueryResponse(
                answers=ptr_records, additional_records=additional_records
            )
            await self._send_response(response)

    async def _send_response(self, response: MDNSQueryResponse) -> None:
        packet = MDNS(query_response=response)
        self._send_packet(packet)

    async def _handle_response(
        self, response: MDNSQueryResponse, addr: Tuple[str, int]
    ) -> None:
        all_records = list(response.answers) + list(response.additional_records)

        # Split into active records and goodbye records (TTL=0)
        active_records = [r for r in all_records if r.ttl > 0]
        expired_records = [r for r in all_records if r.ttl == 0]

        # Handle New/Updates
        if active_records:
            infos = MDNSServiceInfo.from_records(active_records)
            if infos:
                for info in infos:
                    is_new = await self._cache_service(info)
                    if is_new:
                        self._notify_listeners_safe(lambda l: l.add_service(self, info))
                    else:
                        self._notify_listeners_safe(
                            lambda l: l.update_service(self, info)
                        )

        # Parsing expired records is tricky because a goodbye packet
        # often only contains the PTR, not the full SRV/TXT needed to reconstruct MDNSServiceInfo.
        # We must look up the *existing* cache to notify listeners who exactly is leaving.
        if expired_records:
            for rec in expired_records:
                if rec.WhichOneof("record") == "ptr_record":
                    domain_name = rec.ptr_record.domain_name
                    service_type = rec.name

                    # Look up full info from our cache before deleting it
                    existing_info = self._reconstruct_info_from_cache(
                        service_type, domain_name
                    )

                    if existing_info:
                        await self._remove_from_cache(service_type, domain_name)
                        self._notify_listeners_safe(
                            lambda l: l.remove_service(self, existing_info)
                        )

    def _reconstruct_info_from_cache(
        self, service_type: str, domain_name: str
    ) -> Optional[MDNSServiceInfo]:
        if (
            service_type not in self.ptr_records
            or domain_name not in self.ptr_records[service_type]
        ):
            return None

        # Reconstruct records list to use standard parsing logic
        records = [self.ptr_records[service_type][domain_name].record]

        if domain_name in self.non_ptr_records:
            for entries in self.non_ptr_records[domain_name].values():
                records.extend([e.record for e in entries])

        infos = MDNSServiceInfo.from_records(records)
        return infos[0] if infos else None

    async def register_service(self, info: MDNSServiceInfo) -> None:
        logger.info(
            "Registering service",
            extra={"service_name": info.name, "type": info.type, "port": info.port},
        )
        await asyncio.sleep(self.random.randint(150, 250) / 1000)
        self.registered_services.setdefault(info.type, [])
        await self._tiebreaker(info)

        full_domain = generate_domain_name(info.type, info.name)
        self.registered_services[info.type].append(full_domain)

        await self._cache_service(info, force_insert=True)
        await self._broadcast_service(info)

    async def unregister_service(self, info: MDNSServiceInfo) -> None:
        logger.info(
            "Unregistering service",
            extra={"service_name": info.name, "type": info.type},
        )

        domain_name = generate_domain_name(info.type, info.name)

        # 1. Check if we actually own this service
        if (
            info.type not in self.registered_services
            or domain_name not in self.registered_services[info.type]
        ):
            logger.warning(
                "Attempted to unregister unknown service",
                extra={
                    "service_name": info.name,
                    "type": info.type,
                    "domain": domain_name,
                },
            )
            return

        # 2. Modify info to have TTL=0 (Goodbye Packet)
        goodbye_info = info
        goodbye_info.ttl = 0

        # 3. Broadcast Goodbye
        await self._broadcast_service(goodbye_info)

        # 4. Cleanup Local State
        self.registered_services[info.type].remove(domain_name)
        if not self.registered_services[info.type]:
            del self.registered_services[info.type]

        await self._remove_from_cache(info.type, domain_name)

        # 5. Notify Listeners (Optional: usually listeners only care about remote removals,
        # but consistency is good)
        self._notify_listeners_safe(lambda l: l.remove_service(self, info))

    async def update_service(self, info: MDNSServiceInfo) -> None:
        """Updates service details and broadcasts the change."""
        logger.info(
            "Updating service", extra={"service_name": info.name, "type": info.type}
        )

        domain_name = generate_domain_name(info.type, info.name)
        if (
            info.type not in self.registered_services
            or domain_name not in self.registered_services[info.type]
        ):
            logger.warning(
                "Cannot update non-registered service",
                extra={
                    "service_name": info.name,
                    "type": info.type,
                    "domain": domain_name,
                },
            )
            return

        # 1. Update Local Cache
        await self._cache_service(info, force_insert=True)

        # 2. Broadcast Announcement (Flush Cache on other devices)
        # Note: If only TXT record changes, we could send just that,
        # but sending full record set is safer.
        await self._broadcast_service(info)

        # 3. Notify Listeners
        self._notify_listeners_safe(lambda l: l.update_service(self, info))

    async def _tiebreaker(self, info: MDNSServiceInfo) -> None:
        current_attempt = 0
        next_instance_num = 2
        while current_attempt < self.tiebreaking_attempts:
            is_conflict = await self._is_service_defined(info.type, info.name)
            if is_conflict:
                if not info.allow_name_change:
                    raise NonUniqueNameException(f"Name '{info.name}' is taken")
                info.name = f"{info.name.split('-')[0]}-{next_instance_num}"
                next_instance_num += 1
                current_attempt = 0
                continue
            await self._query_service(info.type, self.query_timeout_ms)
            drift = self.random.random() * self.tiebreaking_drift_ms
            await asyncio.sleep((self.interval_tiebreaking_ms + drift) / 1000)
            current_attempt += 1

    async def _cache_service(
        self, info: MDNSServiceInfo, force_insert: bool = False
    ) -> bool:
        """
        Stores service records. Returns True if this is a NEW service, False if update.
        """
        domain_name = generate_domain_name(info.type, info.name)

        # Check uniqueness to determine if this is an Add or Update
        is_existing = (
            info.type in self.ptr_records and domain_name in self.ptr_records[info.type]
        )

        is_own_service = domain_name in self.registered_services.get(info.type, [])
        if is_own_service and not force_insert:
            return False

        # Update PTR
        ptr_entry = EntryRecord(
            MDNSRecord(
                name=info.type,
                ttl=info.ttl,
                ptr_record=MDNSPointerRecord(name=info.type, domain_name=domain_name),
            )
        )
        self.ptr_records.setdefault(info.type, {})[domain_name] = ptr_entry

        # Update Non-PTR
        records = info.to_records()
        if domain_name not in self.non_ptr_records:
            self.non_ptr_records[domain_name] = {}

        # Clear old non-ptr records for this domain to ensure clean update
        self.non_ptr_records[domain_name].clear()

        for rec in records:
            field = rec.WhichOneof("record")
            if field != "ptr_record":
                self.non_ptr_records[domain_name].setdefault(field, []).append(
                    EntryRecord(rec)
                )

        return not is_existing

    async def _remove_from_cache(self, service_type: str, domain_name: str) -> None:
        """Removes all records associated with a service instance."""
        # Remove PTR
        if service_type in self.ptr_records:
            if domain_name in self.ptr_records[service_type]:
                del self.ptr_records[service_type][domain_name]
            if not self.ptr_records[service_type]:
                del self.ptr_records[service_type]

        # Remove SRV/TXT/A
        if domain_name in self.non_ptr_records:
            del self.non_ptr_records[domain_name]

    async def _broadcast_service(self, info: MDNSServiceInfo) -> None:
        records = info.to_records()
        if not records:
            return
        response = MDNSQueryResponse(
            answers=[records[0]], additional_records=records[1:]
        )
        await self._send_response(response)

    async def _query_service(self, type_: str, timeout_ms: int) -> None:
        question = MDNSQuestion(name=type_, type=MDNSType.MDNS_PTR)
        query = MDNSQueryRequest(questions=[question])
        self._send_packet(MDNS(query_request=query))

    async def _is_service_defined(self, entry_name: str, instance_name: str) -> bool:
        records = self.ptr_records.get(entry_name, {})
        target_domain = generate_domain_name(entry_name, instance_name)
        if target_domain not in records:
            return False
        return not records[target_domain].expired()
