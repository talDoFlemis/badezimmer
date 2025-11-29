import logging
import re
import socket
import asyncio
import random
import time
import threading
import collections

import asyncudp
from zeroconf import (
    IPVersion,
    Zeroconf,
)

from badezimmer import (
    DeviceCategory,
    DeviceKind,
    MDNSQueryRequest,
    MDNSQueryResponse,
    MDNSQuestion,
    MDNSType,
    MDNSRecord,
    MDNSPointerRecord,
    MDNSARecord,
    MDNSSRVRecord,
    MDNSTextRecord,
    MDNS,
)
from badezimmer.logger import setup_logger
from badezimmer.tcp import (
    prepare_protobuf_request,
    get_protobuf_data,
    get_all_ips_strings_for_adapters,
)

setup_logger()
logger = logging.getLogger(__name__)
zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

_MULTICAST_IP = "224.0.0.251"
MULTICAST_PORT = 5369
RANDOM_SEED = 42069
DEFAULT_TTL = 4500
SERVICE_DISCOVERY_TYPE = "_services._dns-sd._udp.local"


class NonUniqueNameException(Exception):
    """Exception when the name is already registered."""


def current_time_millis() -> float:
    return time.monotonic() * 1000


class EntryRecord:
    def __init__(self, record: MDNSRecord):
        self.record = record
        self.expires_at = (record.ttl * 1000) + current_time_millis()

    def expired(self) -> bool:
        return self.expires_at < current_time_millis()


def generate_domain_name(entry: str, instance_name: str) -> str:
    return f"{instance_name}.{entry}"


class MDNSServiceInfo:
    def __init__(
        self,
        name: str,
        type: str,
        port: int,
        kind: DeviceKind | int,
        category: DeviceCategory | int,
        properties: dict[str, str],
        addresses: list[str] | None = None,
        ttl: int = DEFAULT_TTL,
        allow_name_change: bool = True,
    ):
        self.name = name
        self.type = type
        self.category = category
        self.port: int = port
        self.properties = properties
        self.kind = kind
        self.ttl = ttl
        self.allow_name_change = allow_name_change
        if addresses is not None:
            self.ips = addresses
        else:
            self.ips = get_all_ips_strings_for_adapters()

    def to_records(self) -> list[MDNSRecord]:
        records = []

        domain_name = generate_domain_name(self.type, self.name)

        ptr_record = MDNSRecord(
            name=self.type,
            ttl=self.ttl,
            cache_flush=False,
            ptr_record=MDNSPointerRecord(name=self.type, domain_name=domain_name),
        )
        records.append(ptr_record)

        # Add IPs as A records
        for ip in self.ips:
            record = MDNSRecord(
                name=domain_name,
                ttl=self.ttl,
                cache_flush=True,
                a_record=MDNSARecord(name=domain_name, address=ip),
            )
            records.append(record)

        domain_name_parts = domain_name.split(".")
        srv_name = domain_name_parts[-1]
        protocol = domain_name_parts[-2]
        service = domain_name_parts[-3]
        instance = domain_name_parts[-4]

        srv_record = MDNSRecord(
            name=domain_name,
            ttl=self.ttl,
            cache_flush=True,
            srv_record=MDNSSRVRecord(
                name=srv_name,
                protocol=protocol,
                service=service,
                instance=instance,
                port=self.port,
                target=domain_name,
            ),
        )

        records.append(srv_record)

        txt_record_entries: dict[str, str] = {}

        txt_record_entries["kind"] = DeviceKind.Name(self.kind)
        txt_record_entries["category"] = DeviceCategory.Name(self.category)
        for key, value in self.properties.items():
            txt_record_entries[key] = value

        txt_record = MDNSRecord(
            name=domain_name,
            ttl=self.ttl,
            cache_flush=True,
            txt_record=MDNSTextRecord(
                name=domain_name,
                entries=txt_record_entries,
            ),
        )
        records.append(txt_record)
        return records

    @staticmethod
    def from_records(
        records: list[MDNSRecord],
    ) -> "list[MDNSServiceInfo] | None":
        if len(records) == 0:
            return None

        ptr_records: dict[str, list[MDNSPointerRecord]] = {}
        srv_records: dict[str, MDNSSRVRecord] = {}
        txt_records: dict[str, MDNSTextRecord] = {}
        a_records: dict[str, list[MDNSARecord]] = {}

        for entry in records:
            if entry.WhichOneof("record") == "ptr_record":
                ptr_records.setdefault(entry.ptr_record.domain_name, []).append(
                    entry.ptr_record
                )

        for record in records:
            if ptr_records.get(record.name) is None:
                continue

            field = record.WhichOneof("record")
            if field not in ["srv_record", "txt_record", "a_record"]:
                continue

            if field == "srv_record":
                srv_records[record.name] = record.srv_record
            elif field == "txt_record":
                txt_records[record.name] = record.txt_record
            elif field == "a_record":
                a_records.setdefault(record.name, []).append(record.a_record)

        infos = []

        for record in [
            record for records_list in ptr_records.values() for record in records_list
        ]:
            entry_name = record.domain_name
            instance_name = entry_name.split(".")[0]

            info = MDNSServiceInfo(
                name=instance_name,
                type=record.name,
                port=0,
                kind=DeviceKind.UNKNOWN_KIND,
                category=DeviceCategory.UNKNOWN_CATEGORY,
                properties={},
            )

            for ips in a_records.get(entry_name, []):
                info.ips.append(ips.address)

            if entry_name in srv_records:
                info.port = srv_records[entry_name].port

            for key, value in txt_records[entry_name].entries.items():
                info.properties[key] = value
                continue

            kind_str = info.properties.get("kind", "UNKNOWN_KIND")
            category_str = info.properties.get("category", "UNKNOWN_CATEGORY")

            try:
                info.kind = DeviceKind.Value(kind_str)
            except ValueError:
                info.kind = DeviceKind.UNKNOWN_KIND

            try:
                info.category = DeviceCategory.Value(category_str)
            except ValueError:
                info.category = DeviceCategory.UNKNOWN_CATEGORY

            except Exception as e:
                logger.debug(f"Failed to parse service info from records: {e}")
                continue

            infos.append(info)

        return infos


class BadezimmerServiceListener:
    def add_service(self, mdns: "BadezimmerMDNS", info: MDNSServiceInfo) -> None: ...
    def remove_service(self, mdns: "BadezimmerMDNS", info: MDNSServiceInfo) -> None: ...
    def update_service(self, mdns: "BadezimmerMDNS", info: MDNSServiceInfo) -> None: ...


class BadezimmerMDNS:
    def __init__(
        self,
        interval_between_tiebreaking_in_millis: float = 100.0,
        tiebreaking_attempts: int = 3,
        query_timeout_in_millis: int = 200,
        tiebreaking_max_drift_in_millis: float = 25.0,
        random_seed: int = RANDOM_SEED,
    ):
        self.interval_between_tiebreaking_in_millis = (
            interval_between_tiebreaking_in_millis
        )
        self.tiebreaking_attempts = tiebreaking_attempts
        self.query_timeout_in_millis = query_timeout_in_millis
        self.tiebreaking_max_drift_in_millis = tiebreaking_max_drift_in_millis
        self.random = random.Random(random_seed)
        self.ptr_records: dict[str, list[EntryRecord]] = {}
        self.non_ptr_records: dict[str, dict[MDNSType, list[EntryRecord]]] = {}
        self.listeners: list[BadezimmerServiceListener] = []
        self.sock: asyncudp.Socket | None = None
        self._recv_task: asyncio.Task | None = None
        self._sent_packets: collections.deque = collections.deque(maxlen=50)

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        future = asyncio.run_coroutine_threadsafe(self._start_async(), self._loop)
        try:
            future.result(timeout=1)
        except Exception as e:
            logger.error(f"Failed to start async loop: {e}")

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def add_listener(self, listener: BadezimmerServiceListener) -> None:
        self.listeners.append(listener)

    async def _start_async(self) -> None:
        if self.sock is None:
            self.sock = await asyncudp.create_socket(
                local_addr=("0.0.0.0", MULTICAST_PORT),
                reuse_port=True,
            )
            # Join multicast group
            sock_obj = self.sock._transport.get_extra_info("socket")
            sock_obj.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_ADD_MEMBERSHIP,
                socket.inet_aton(_MULTICAST_IP) + socket.inet_aton("0.0.0.0"),
            )
            self._recv_task = asyncio.create_task(self._recv_loop())
            logger.info("BadezimmerMDNS started listening on multicast port")

    async def close(self) -> None:
        if self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self._close_internal(), self._loop
            )
            try:
                await asyncio.wrap_future(future)
            except Exception as e:
                logger.error(f"Error during close: {e}")

            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread.is_alive():
            self._thread.join()

    async def _close_internal(self) -> None:
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self.sock:
            self.sock.close()

    async def _recv_loop(self) -> None:
        while True:
            try:
                if self.sock is None:
                    break
                data, addr = await self.sock.recvfrom()

                # Ignore own packets
                if data in self._sent_packets:
                    continue

                # Ignore own packets if possible, or handle them gracefully
                # For now, we process everything
                await self._handle_packet(data, addr)
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")

    def _send_packet(self, packet: MDNS) -> None:
        if self.sock is None:
            return

        # Assign a random transaction ID to ensure uniqueness of the packet
        # This helps distinguishing our packet from others even if payload is similar
        packet.transaction_id = self.random.randint(1, 65535)

        raw_bytes = prepare_protobuf_request(packet)
        self._sent_packets.append(raw_bytes)
        self.sock.sendto(raw_bytes, (_MULTICAST_IP, MULTICAST_PORT))

    async def _handle_packet(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            proto_bytes = get_protobuf_data(data)
            packet = MDNS()
            packet.ParseFromString(proto_bytes)

            if packet.WhichOneof("data") == "query_request":
                await self._handle_query(packet.query_request, addr)
            elif packet.WhichOneof("data") == "query_response":
                await self._handle_response(packet.query_response, addr)
        except Exception as e:
            logger.debug(f"Failed to handle packet from {addr}: {e}")

    async def _handle_query(
        self, query: MDNSQueryRequest, addr: tuple[str, int]
    ) -> None:
        ptr_records: list[MDNSRecord] = []

        for question in query.questions:
            if question.name == SERVICE_DISCOVERY_TYPE:
                records = [
                    entry.record
                    for entries in self.ptr_records.values()
                    for entry in entries
                ]
                ptr_records.extend(records)
            else:
                records = self.ptr_records.get(question.name)
                if records is None:
                    continue

                ptr_records.extend([entry.record for entry in records])

        if len(ptr_records) == 0:
            return

        additional_records: list[MDNSRecord] = []

        for record in ptr_records:
            non_ptr_records_entries = self.non_ptr_records.get(
                record.ptr_record.domain_name, {}
            )
            additional_records.extend(
                [
                    entry.record
                    for entries in non_ptr_records_entries.values()
                    for entry in entries
                ]
            )

        await self._send_response(
            MDNSQueryResponse(
                answers=ptr_records, additional_records=additional_records
            )
        )

    async def _send_response(self, response: MDNSQueryResponse) -> None:
        packet = MDNS(query_response=response)
        self._send_packet(packet)

    async def _handle_response(
        self, response: MDNSQueryResponse, addr: tuple[str, int]
    ) -> None:
        records: list[MDNSRecord] = []
        records.extend(response.answers)
        records.extend(response.additional_records)

        infos = MDNSServiceInfo.from_records(records)
        if infos is None:
            return

        for info in infos:
            await self.__add_service(info)

        for listener in self.listeners:
            for info in infos:
                listener.update_service(self, info)

    async def register_service(self, info: MDNSServiceInfo):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop == self._loop:
            await self._register_service_impl(info)
        else:
            future = asyncio.run_coroutine_threadsafe(
                self._register_service_impl(info), self._loop
            )
            await asyncio.wrap_future(future)

    async def _register_service_impl(self, info: MDNSServiceInfo):
        logger.debug(
            "Registering service with on Badezimmer Network...",
            extra={
                "service_name": info.name,
                "service_type": info.type,
                "port": info.port,
                "properties": info.properties,
            },
        )

        logger.debug(
            "Sleeping before registering service to avoid thundering herd",
            extra={"info": info},
        )
        await asyncio.sleep(self.random.randint(150, 250) / 1000)
        await self.__tiebreaker(info)
        await self.__add_service(info)
        await self.__broadcast_service(info)

    async def __tiebreaker(self, info: MDNSServiceInfo) -> None:
        logger.debug("Tiebreaking...", extra={"type": info.type})

        current_attempt = 0
        next_instance_number = 2
        current_instance_name = info.name
        now = next_time = current_time_millis()

        while current_attempt < self.tiebreaking_attempts:
            logger.info(
                "Tiebreaking attempt",
                extra={
                    "attempt": current_attempt + 1,
                    "current_name": current_instance_name,
                },
            )

            while await self.__check_if_service_is_defined(
                entry_name=info.type, instance_name=current_instance_name
            ):
                logger.info(
                    "Service name conflict detected during tiebreaking",
                    extra={
                        "service_type": info.type,
                        "service_name": current_instance_name,
                    },
                )
                if not info.allow_name_change:
                    logger.exception(
                        "Service is already defined checking if allow_name_change"
                    )
                    raise NonUniqueNameException

                current_instance_name = f"{info.name}-{next_instance_number}"
                next_instance_number += 1

                # Reset attempt counter
                current_attempt = 0
                next_time = now

            logger.debug("Service is defined")

            if now < next_time:
                await asyncio.sleep(next_time - now)
                now = current_time_millis()
                continue

            # Do another query to check if the service is defined until the max attempts is reached
            await self.__query_service(info.type, self.query_timeout_in_millis)

            current_attempt += 1
            next_time += (self.interval_between_tiebreaking_in_millis / 1000) + (
                self.random.random() * self.tiebreaking_max_drift_in_millis / 1000
            )

        info.name = current_instance_name

        logger.debug(
            "Tiebreaking resolved with success",
            extra={"type": info.type, "service_name": info.name},
        )

    async def __add_service(self, info: MDNSServiceInfo) -> None:
        self.ptr_records.setdefault(info.type, []).append(
            EntryRecord(
                MDNSRecord(
                    name=info.type,
                    ttl=info.ttl,
                    cache_flush=False,
                    ptr_record=MDNSPointerRecord(
                        name=info.type,
                        domain_name=generate_domain_name(info.type, info.name),
                    ),
                )
            )
        )

        domain_name = generate_domain_name(info.type, info.name)

        if self.non_ptr_records.get(domain_name) is None:
            self.non_ptr_records[domain_name] = {}

        for record in info.to_records()[1:]:
            field = record.WhichOneof("record")
            self.non_ptr_records[domain_name].setdefault(field, []).append(
                EntryRecord(record)
            )

    async def __broadcast_service(self, info: MDNSServiceInfo) -> None:
        records = info.to_records()
        ptr_record = records[0]
        additional_records = records[1:]

        response = MDNSQueryResponse(
            answers=[ptr_record], additional_records=additional_records
        )

        packet = MDNS(query_response=response)
        self._send_packet(packet)

    async def __query_service(
        self, type_: str, query_timeout_in_millis: int
    ) -> MDNSQueryResponse | None:
        question = MDNSQuestion(name=type_, type=MDNSType.MDNS_PTR)
        query = MDNSQueryRequest(questions=[question])

        packet = MDNS(query_request=query)

        try:
            logger.debug("Sending query request to multicast address")
            self._send_packet(packet)
            await asyncio.sleep(query_timeout_in_millis / 1000)

        except Exception as e:
            logger.error(f"Error sending query request to multicast address: {e}")
            raise

        return None

    async def __check_if_service_is_defined(
        self, entry_name: str, instance_name: str
    ) -> bool:
        entry_records = self.ptr_records.get(entry_name)

        if entry_records is None:
            return False

        for entry_record in reversed(entry_records):
            if entry_record.expired():
                continue

            ptr_record = entry_record.record.ptr_record

            domain_name = generate_domain_name(entry_name, instance_name)
            if ptr_record.domain_name == domain_name:
                return True

        return False
