import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from zeroconf import (
    IPVersion,
    ServiceBrowser,
    ServiceInfo,
    ServiceListener,
    Zeroconf,
)

import lightlamp
from badezimmer import (
    Color,
    ConnectedDevice,
    DeviceKind,
    DeviceStatus,
    LightLampActionRequest,
    SendActuatorCommandRequest,
    SendActuatorCommandResponse,
    setup_logger,
)
from badezimmer.tcp import send_request
from typing import Optional

setup_logger()
logger = logging.getLogger(__name__)

zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

devices: dict[str, ConnectedDevice] = {}


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
        id=info.name,
        device_name=info.name,
        kind=str_to_device_kind(type_),
        status=DeviceStatus.ONLINE_DEVICE_STATUS,
        port=info.port,
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

        devices[device.id] = device
        logger.info(
            "Service updated",
            extra={
                "id": device.id,
                "device_name": device.device_name,
                "ips": device.ips,
                "kind": device.kind,
                "port": info.port,
                "properties": info.decoded_properties,
            },
        )

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            logger.info(
                "Service removed, but no info available", extra={"service_name": name}
            )
            return

        del devices[info.name]

        logger.info("Service removed", extra={"service_name": name})

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
    services = [lightlamp.SERVICE_TYPE]
    logger.info("found services", extra={"services": services})
    ServiceBrowser(zeroconf, services, listener)


async def startup_job():
    logger.info("Running startup job: Initializing resources...")
    await discovery_services_job()
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


class ConnectedDeviceResponse(BaseModel):
    id: str
    device_name: str
    kind: str
    status: str
    ips: list[str]


@app.get("/devices")
def list_devices() -> list[ConnectedDeviceResponse]:
    return [
        ConnectedDeviceResponse(
            id=device.id,
            device_name=device.device_name,
            kind=DeviceKind.Name(device.kind.numerator),
            status=DeviceStatus.Name(device.status.numerator),
            ips=list(device.ips),
        )
        for device in devices.values()
    ]


class UpdateLightRequest(BaseModel):
    turn_on: Optional[bool]
    brightness: int | None = None
    color: int | None = None


class UpdateLightResponse(BaseModel):
    message: str


@app.patch("/devices/light/{device_id}")
async def update_light(device_id: str, request_body: UpdateLightRequest):
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Item not found")

    device = devices[device_id]

    request = LightLampActionRequest(
        turn_on=request_body.turn_on,
        brightness=request_body.brightness,
        color=Color(value=request_body.color),
    )

    response_bytes = await send_request(
        list(device.ips),
        device.port,
        SendActuatorCommandRequest(device_id=device.id, light_action=request),
    )

    response = SendActuatorCommandResponse.FromString(response_bytes)

    return UpdateLightResponse(message=response.message)


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
        app="gateway:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True,
        log_config=log_config,
    )
