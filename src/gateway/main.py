from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
from zeroconf import (
    IPVersion,
    ServiceBrowser,
    ServiceInfo,
    ServiceListener,
    Zeroconf,
    ZeroconfServiceTypes,
)
from badezimmer import setup_logger, ConnectedDevice, DeviceStatus, DeviceKind

setup_logger()
logger = logging.getLogger(__name__)

zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

devices = {}


def str_to_device_kind(kind_str: str) -> DeviceKind:
    parts = kind_str.split(".")
    if len(parts) != 5:
        return DeviceKind.UNKNOWN_KIND

    # Format is _category._kind._badezimmer._protocol._domain.
    kind = parts[1]
    if kind == "sensor":
        return DeviceKind.SENSOR_KIND
    elif kind == "actuator":
        return DeviceKind.ACTUATOR_KIND
    else:
        return DeviceKind.UNKNOWN_KIND


def generate_connected_device_from_info(
    type_: str, info: ServiceInfo
) -> ConnectedDevice:
    return ConnectedDevice(
        id=info.key,
        device_name=info.name,
        kind=str_to_device_kind(type_),
        status=DeviceStatus.ONLINE_DEVICE_STATUS,
        ips=[str(addr) for addr in info.parsed_addresses(version=IPVersion.V4Only)],
    )


class GatewayListener(ServiceListener):
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            logger.info(
                "Service updated, but no info available", extra={"service_name": name}
            )
            return

        device = generate_connected_device_from_info(
            type_=type_,
            info=info,
        )

        device.id = info.key

        devices[device.id] = device
        logger.info(
            "Service updated",
            extra={
                "id": device.id,
                "device_name": device.device_name,
                "ips": device.ips,
                "kind": device.kind,
            },
        )

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            logger.info(
                "Service removed, but no info available", extra={"service_name": name}
            )
            return

        del devices[info.key]

        logger.info(f"Service removed", extra={"service_name": name})

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)

        if info is None:
            logger.info(
                "Service added, but no info available", extra={"service_name": name}
            )
            return

        device = generate_connected_device_from_info(
            type_=type_,
            info=info,
        )

        logger.info(
            "Discovered new device",
            extra={
                "id": device.id,
                "device_name": device.device_name,
                "ips": device.ips,
                "kind": device.kind,
                "port": info.port,
                "properties": info.decoded_properties,
            },
        )
        devices[device.id] = device


async def discovery_services_job() -> None:
    listener = GatewayListener()
    ServiceBrowser(zeroconf, "_http._tcp.local.", listener)


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
async def lifespan(_app: FastAPI):
    await discovery_services_job()
    yield
    await shutdown_job()


app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"status": "Healthy"}


def main():
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
            "uvicorn.access": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
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
