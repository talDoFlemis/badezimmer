import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
from pythonjsonlogger import jsonlogger
from typing import Union
from zeroconf import (
    IPVersion,
    ServiceBrowser,
    ServiceListener,
    Zeroconf,
    ZeroconfServiceTypes,
)
from badezimmer import setup_logger

setup_logger()
logger = logging.getLogger(__name__)

zeroconf = Zeroconf()


class GatewayListener(ServiceListener):
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service {name} updated")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service {name} removed")

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            print(f"Service {name} added, but no info available")
            return

        addresses = info.ip_addresses_by_version(IPVersion.V4Only)
        for addr in addresses:
            print(f"Service {name} added, address: {str(addr)}")


async def discovery_services_job() -> None:
    listener = GatewayListener()
    browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)


async def startup_job():
    logger.info("Running startup job: Initializing resources...")
    await discovery_services_job()
    print("\n".join(ZeroconfServiceTypes.find()))
    logger.info("Startup job completed.")


async def shutdown_job():
    logger.info("Running shutdown job: Cleaning up resources...")
    global zeroconf
    zeroconf.close()
    logger.info("Shutdown job completed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await discovery_services_job()
    yield
    await shutdown_job()


app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"status": "Healthy"}


if __name__ == "__main__":
    import uvicorn

    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "fmt": "%(asctime)s %(levelname)s %(message)s %(name)s",
                "rename_fields": {"levelname": "severity", "asctime": "timestamp"},
            },
        },
        "handlers": {
            "default": {
                "formatter": "json",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
        },
    }

    uvicorn.run(
        app="gateway.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True,
        log_config=log_config,
    )
