import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from badezimmer import (
    Color,
    ConnectedDevice,
    DeviceKind,
    DeviceStatus,
    LightLampActionRequest,
    SendActuatorCommandRequest,
    SendActuatorCommandResponse,
    DeviceCategory,
    setup_logger,
)
from badezimmer.badezimmer_pb2 import TransportProtocol
from badezimmer.mdns import (
    BadezimmerServiceListener,
    BadezimmerMDNS,
    SERVICE_DISCOVERY_TYPE,
)
from badezimmer.info import MDNSServiceInfo
from badezimmer.browser import BadezimmerServiceBrowser
from badezimmer.tcp import send_request
from typing import Optional

logger = logging.getLogger(__name__)
setup_logger(logger)
mdns = BadezimmerMDNS()

devices: dict[str, ConnectedDevice] = {}


def generate_connected_device_from_info(info: MDNSServiceInfo) -> ConnectedDevice:
    return ConnectedDevice(
        id=f"{info.name}@{info.type}:{info.port}",
        device_name=info.name,
        port=info.port,
        status=DeviceStatus.Name(DeviceStatus.ONLINE_DEVICE_STATUS.numerator),
        kind=DeviceKind.Name(info.kind),
        category=DeviceCategory.Name(info.category),
        properties=info.properties,
        ips=info.addresses,
        transport_protocol=TransportProtocol.Name(info.protocol),
    )


class GatewayListener(BadezimmerServiceListener):
    def update_service(self, mdns: BadezimmerMDNS, info: MDNSServiceInfo) -> None:
        device = generate_connected_device_from_info(info=info)
        devices[device.id] = device

        logger.info(
            "Updating device",
            extra={
                "device_id": device.id,
                "device_name": device.device_name,
                "ips": device.ips,
                "port": device.port,
                "properties": device.properties,
                "status": DeviceStatus.Name(device.status),
                "kind": DeviceKind.Name(device.kind),
                "category": DeviceCategory.Name(device.category),
                "protocol": TransportProtocol.Name(device.transport_protocol),
            },
        )

    def add_service(self, mdns: BadezimmerMDNS, info: MDNSServiceInfo) -> None:
        device = generate_connected_device_from_info(info=info)

        devices[device.id] = device
        logger.info(
            "Discovered new device",
            extra={
                "id": device.id,
                "device_name": device.device_name,
                "ips": device.ips,
                "port": device.port,
                "properties": device.properties,
                "status": DeviceStatus.Name(device.status),
                "kind": DeviceKind.Name(device.kind),
                "category": DeviceCategory.Name(device.category),
                "protocol": TransportProtocol.Name(device.transport_protocol),
            },
        )

    def remove_service(self, mdns: BadezimmerMDNS, info: MDNSServiceInfo) -> None:
        device = generate_connected_device_from_info(info=info)
        del devices[device.id]
        logger.info("Removed device", extra={"device_id": device.id})


async def discovery_services_job() -> None:
    listener = GatewayListener()
    browser = BadezimmerServiceBrowser(
        mdns=mdns, service_types=[SERVICE_DISCOVERY_TYPE], listener=listener
    )
    await mdns.start()
    await browser.start()


async def startup_job():
    logger.info("Running startup job: Initializing resources...")
    await discovery_services_job()
    logger.info("Startup job completed.")


async def shutdown_job():
    logger.info("Running shutdown job: Cleaning up resources...")
    global mdns
    await mdns.close()
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
    category: str
    kind: str
    status: str
    ips: list[str]
    properties: dict[str, str]
    port: int


@app.get("/devices")
def list_devices() -> list[ConnectedDeviceResponse]:
    return [
        ConnectedDeviceResponse(
            id=device.id,
            device_name=device.device_name,
            kind=DeviceKind.Name(device.kind.numerator),
            category=DeviceCategory.Name(device.category.numerator),
            status=DeviceStatus.Name(device.status.numerator),
            ips=list(device.ips),
            properties=dict(device.properties),
            port=device.port,
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


if __name__ == "__main__":
    main()
