import time
from typing import Dict, List, Optional, Union
from badezimmer.badezimmer_pb2 import TransportProtocol
from badezimmer.tcp import (
    get_all_ips_strings_for_adapters,
)


def current_time_millis() -> float:
    return time.monotonic() * 1000


def generate_domain_name(service_type: str, instance_name: str) -> str:
    return f"{instance_name}.{service_type}"


from badezimmer import (
    DeviceCategory,
    DeviceKind,
    MDNSRecord,
    MDNSPointerRecord,
    MDNSARecord,
    MDNSSRVRecord,
    MDNSTextRecord,
    MDNS,
)

DEFAULT_TTL = 4500


class EntryRecord:
    def __init__(self, record: MDNSRecord):
        self.record = record
        # Note: If TTL is 0, this is immediately expired
        self.expires_at = (record.ttl * 1000) + current_time_millis()

    def expired(self) -> bool:
        return self.expires_at < current_time_millis()


class MDNSServiceInfo:
    def __init__(
        self,
        name: str,
        type_: str,
        port: int,
        kind: Union[DeviceKind, int],
        category: Union[DeviceCategory, int],
        protocol: Union[int, TransportProtocol],
        properties: Dict[str, str],
        addresses: Optional[List[str]] = None,
        ttl: int = DEFAULT_TTL,
        allow_name_change: bool = True,
    ):
        self.name = name
        self.type = type_
        self.port = port
        self.kind = kind
        self.category = category
        self.properties = properties
        self.addresses = addresses or get_all_ips_strings_for_adapters()
        self.ttl = ttl
        self.allow_name_change = allow_name_change
        self.protocol = protocol

    def to_records(self) -> List[MDNSRecord]:
        records = []
        domain_name = generate_domain_name(self.type, self.name)

        # 1. PTR
        ptr_record = MDNSRecord(
            name=self.type,
            ttl=self.ttl,
            cache_flush=False,
            ptr_record=MDNSPointerRecord(name=self.type, domain_name=domain_name),
        )
        records.append(ptr_record)

        # 2. A Records
        for ip in self.addresses:
            records.append(
                MDNSRecord(
                    name=domain_name,
                    ttl=self.ttl,
                    cache_flush=True,
                    a_record=MDNSARecord(name=domain_name, address=ip),
                )
            )

        # 3. SRV
        try:
            parts = self.type.split(".")
            service = parts[0] if len(parts) > 0 else "_http"
        except IndexError:
            service = "_unknown"

        srv_record = MDNSRecord(
            name=domain_name,
            ttl=self.ttl,
            cache_flush=True,
            srv_record=MDNSSRVRecord(
                name=self.name,
                protocol=TransportProtocol.Name(self.protocol),
                service=service,
                instance=self.name,
                port=self.port,
                target=domain_name,
            ),
        )
        records.append(srv_record)

        # 4. TXT
        txt_entries = {
            "kind": DeviceKind.Name(self.kind),
            "category": DeviceCategory.Name(self.category),
            **self.properties,
        }

        txt_record = MDNSRecord(
            name=domain_name,
            ttl=self.ttl,
            cache_flush=True,
            txt_record=MDNSTextRecord(name=domain_name, entries=txt_entries),
        )
        records.append(txt_record)
        return records

    @staticmethod
    def from_records(records: List[MDNSRecord]) -> Optional[List["MDNSServiceInfo"]]:
        if not records:
            return None

        ptr_map: Dict[str, List[MDNSPointerRecord]] = {}
        srv_map: Dict[str, MDNSSRVRecord] = {}
        txt_map: Dict[str, MDNSTextRecord] = {}
        a_map: Dict[str, List[MDNSARecord]] = {}

        for r in records:
            field = r.WhichOneof("record")
            if field == "ptr_record":
                ptr_map.setdefault(r.ptr_record.domain_name, []).append(r.ptr_record)
            elif field == "srv_record":
                srv_map[r.name] = r.srv_record
            elif field == "txt_record":
                txt_map[r.name] = r.txt_record
            elif field == "a_record":
                a_map.setdefault(r.name, []).append(r.a_record)

        infos = []
        all_ptrs = [p for sublist in ptr_map.values() for p in sublist]

        for ptr in all_ptrs:
            full_domain_name = ptr.domain_name
            instance_name = full_domain_name.split(".")[0]

            info = MDNSServiceInfo(
                name=instance_name,
                type_=ptr.name,
                port=0,
                kind=DeviceKind.UNKNOWN_KIND,
                category=DeviceCategory.UNKNOWN_CATEGORY,
                properties={},
                addresses=[],
                protocol=TransportProtocol.UNKNOWN_PROTOCOL,
            )

            if full_domain_name in a_map:
                info.addresses = [rec.address for rec in a_map[full_domain_name]]
            if full_domain_name in srv_map:
                info.port = srv_map[full_domain_name].port
                info.protocol = srv_map[full_domain_name].protocol.numerator
            if full_domain_name in txt_map:
                info.properties = dict(txt_map[full_domain_name].entries)
                try:
                    info.kind = DeviceKind.Value(
                        info.properties.get("kind", "UNKNOWN_KIND")
                    )
                    info.category = DeviceCategory.Value(
                        info.properties.get("category", "UNKNOWN_CATEGORY")
                    )
                except ValueError:
                    pass

            infos.append(info)

        return infos if infos else None
