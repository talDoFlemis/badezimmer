import logging
import re

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
import asyncio
import random
import time
import threading

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
        self.expires_at = record.ttl + current_time_millis()

    def expired(self) -> bool:
        return self.expires_at < current_time_millis()


class MDNSServiceInfo:
    def __init__(
        self,
        name: str,
        type: str,
        port: int,
        kind: DeviceKind,
        category: DeviceCategory,
        properties: dict[str, str],
        ttl: int = DEFAULT_TTL,
        allow_name_change: bool = True,
    ):
        self.name = name
        self.type = type
        self.category = category
        self.port = port
        self.properties = properties
        self.kind = kind
        self.ttl = ttl
        self.allow_name_change = allow_name_change
        self.ips = get_all_ips_strings_for_adapters()

    def to_records(self) -> list[MDNSRecord]:
        records = []
        ptr_record = MDNSRecord(
            name=self.type,
            ttl=self.ttl,
            cache_flush=False,
            ptr_record=MDNSPointerRecord(name=self.name, domain_name=self.name),
        )
        records.append(ptr_record)

        domain_name = generate_domain_name(self.type, self.name)

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
        srv_record = MDNSRecord(
            name=domain_name,
            ttl=self.ttl,
            cache_flush=True,
            srv_record=MDNSSRVRecord(
                name=domain_name_parts[-1],
                protocol=domain_name_parts[-2],
                service=domain_name_parts[-3],
                instance=domain_name_parts[-4],
                port=self.port,
                target=domain_name,
            ),
        )
        records.append(srv_record)

        txt_record_entries: dict[str, str] = {}

        txt_record_entries["kind"] = DeviceKind.Name(self.kind.numerator)
        txt_record_entries["category"] = DeviceCategory.Name(self.category.numerator)
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
        self.cache: dict[str, list[EntryRecord]] = {}
        self.services: dict[str, MDNSServiceInfo] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None

    async def register_service(self, info: MDNSServiceInfo):
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
            logger.info("Tiebreaking attempt", extra={"attempt": current_attempt + 1})

            while await self.__check_if_service_is_defined(
                entry_name=info.type, instance_name=current_instance_name
            ):
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
        self.services[info.name] = info

    async def __broadcast_service(self, info: MDNSServiceInfo) -> None:
        records = info.to_records()
        ptr_record = records[0]
        additional_records = records[1:]

        response = MDNSQueryResponse(
            answer=ptr_record, additional_records=additional_records
        )

        packet = MDNS(transaction_id=0x0000, query_response=response)

        raw_bytes = prepare_protobuf_request(packet)
        sock = await asyncudp.create_socket(remote_addr=(_MULTICAST_IP, MULTICAST_PORT))
        sock.sendto(raw_bytes)

    async def __query_service(
        self, type_: str, query_timeout_in_millis: int
    ) -> MDNSQueryResponse | None:
        question = MDNSQuestion(name=type_, type=MDNSType.MDNS_PTR)
        query = MDNSQueryRequest(questions=[question])

        packet = MDNS(transaction_id=0x0000, query_request=query)

        raw_bytes = prepare_protobuf_request(packet)

        try:
            logger.debug("Sending query request to multicast address")

            sock = await asyncudp.create_socket(
                remote_addr=(_MULTICAST_IP, MULTICAST_PORT)
            )
            sock.sendto(raw_bytes)

            try:
                async with asyncio.timeout(query_timeout_in_millis / 1000):
                    resp_raw_bytes = await sock.recvfrom()
                proto_bytes = get_protobuf_data(resp_raw_bytes)
            except TimeoutError:
                logger.error("Timeout while waiting for response on send query")
                return None

            packet = MDNS()
            packet.ParseFromString(proto_bytes)

            if packet.WhichOneof("data") != "query_response":
                raise ValueError("Invalid packet received")

            response = packet.query_response

            # Add answers to cache
            self.__add_entry_record(type_, response.answer)
            [
                self.__add_entry_record(type_, record)
                for record in response.additional_records
            ]

        except Exception as e:
            logger.error(f"Error sending query request to multicast address: {e}")
            raise

        return None

    async def __check_if_service_is_defined(
        self, entry_name: str, instance_name: str
    ) -> bool:
        entry_records = self.cache.get(entry_name)

        if entry_records is None:
            return False

        for entry_record in reversed(entry_records):
            if (
                entry_record.record.WhichOneof("record") != "ptr_record"
                or entry_record.expired()
            ):
                continue

            ptr_record = entry_record.record.ptr_record

            domain_name = generate_domain_name(entry_name, instance_name)
            if ptr_record.domain_name == domain_name:
                return True

        return False

    def __add_entry_record(self, entry_name: str, record: MDNSRecord) -> None:
        self.cache.setdefault(entry_name, []).append(EntryRecord(record))


def generate_domain_name(entry: str, instance_name: str) -> str:
    return f"{instance_name}.{entry}"
