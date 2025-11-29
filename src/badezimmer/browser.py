from ast import List
import logging
from badezimmer import setup_logger
from badezimmer.mdns import (
    BadezimmerMDNS,
    BadezimmerServiceListener,
    SERVICE_DISCOVERY_TYPE,
)
from badezimmer.info import MDNSServiceInfo
import asyncio

logger = logging.getLogger(__name__)
setup_logger(logger)


class BadezimmerServiceBrowser(BadezimmerServiceListener):
    def __init__(
        self,
        mdns: BadezimmerMDNS,
        service_types: list[str],
        listener: BadezimmerServiceListener,
    ):
        self.mdns = mdns
        self.service_types = set(service_types)
        self.delegate_listener = listener
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        await self.mdns.start()
        self._started = True

        self.mdns.add_listener(self)

        await self._replay_cache()

        for svc_type in self.service_types:
            asyncio.create_task(
                self.mdns._query_service(svc_type, self.mdns.query_timeout_ms)
            )

    async def _replay_cache(self) -> None:
        """Looks through existing MDNS cache and triggers add_service for matches."""
        for svc_type in self.service_types:
            # Check if this type exists in the MDNS PTR records
            if svc_type in self.mdns.ptr_records:
                for domain_name, entry in self.mdns.ptr_records[svc_type].items():
                    if not entry.expired():
                        # We need to use the internal helper to reconstruct the full object
                        info = self.mdns._reconstruct_info_from_cache(
                            svc_type, domain_name
                        )
                        if info:
                            self.delegate_listener.add_service(self.mdns, info)

    def add_service(self, mdns: BadezimmerMDNS, info: MDNSServiceInfo) -> None:
        if (
            SERVICE_DISCOVERY_TYPE in self.service_types
            or info.type in self.service_types
        ):
            self.delegate_listener.add_service(mdns, info)

    def remove_service(self, mdns: BadezimmerMDNS, info: MDNSServiceInfo) -> None:
        if (
            SERVICE_DISCOVERY_TYPE in self.service_types
            or info.type in self.service_types
        ):
            self.delegate_listener.remove_service(mdns, info)

    def update_service(self, mdns: BadezimmerMDNS, info: MDNSServiceInfo) -> None:
        if (
            SERVICE_DISCOVERY_TYPE in self.service_types
            or info.type in self.service_types
        ):
            self.delegate_listener.update_service(mdns, info)
