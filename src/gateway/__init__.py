from asyncio import futures
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import struct
from pydantic import BaseModel

from badezimmer import (
    Color,
    ConnectedDevice,
    DeviceKind,
    DeviceStatus,
    LightLampActionRequest,
    SinkActionRequest,
    SendActuatorCommandRequest,
    SendActuatorCommandResponse,
    BadezimmerRequest,
    BadezimmerResponse,
    ErrorDetails,
    ErrorCode,
    DeviceCategory,
    setup_logger,
    ListConnectedDevicesRequest,
    ListConnectedDevicesResponse,
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
import base64

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

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
    ],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["grpc-status", "grpc-message"],  # Required for gRPC-Web
)


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


class UpdateSinkRequest(BaseModel):
    turn_on: Optional[bool]


class UpdateLightResponse(BaseModel):
    message: str


class UpdateSinkResponse(BaseModel):
    message: str


@app.patch("/devices/light/{device_id}")
async def update_light(device_id: str, request_body: UpdateLightRequest):
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Item not found")

    device = devices[device_id]

    request = BadezimmerRequest(
        send_actuator_command=SendActuatorCommandRequest(
            device_id=device.id,
            light_action=LightLampActionRequest(
                turn_on=request_body.turn_on,
                brightness=request_body.brightness,
                color=Color(value=request_body.color),
            ),
        ),
    )

    response_bytes = await send_request(list(device.ips), device.port, request=request)

    response = BadezimmerResponse.FromString(response_bytes)
    if response.WhichOneof("response") == "error":
        error = response.error
        raise HTTPException(
            status_code=500,
            detail=f"Error from device: {error.code} - {error.message}",
        )

    return UpdateLightResponse(message=response.send_actuator_command_response.message)


@app.patch("/devices/sink/{device_id}")
async def update_sink(device_id: str, request_body: UpdateSinkRequest):
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Item not found")

    device = devices[device_id]

    request = BadezimmerRequest(
        send_actuator_command=SendActuatorCommandRequest(
            device_id=device.id,
            sink_action=SinkActionRequest(
                turn_on=request_body.turn_on,
            ),
        ),
    )

    response_bytes = await send_request(list(device.ips), device.port, request=request)

    response = BadezimmerResponse.FromString(response_bytes)
    if response.WhichOneof("response") == "error":
        error = response.error
        raise HTTPException(
            status_code=500,
            detail=f"Error from device: {error.code} - {error.message}",
        )

    return UpdateSinkResponse(message=response.send_actuator_command_response.message)


@app.post("/badezimmer.BadezimmerService/ListConnectedDevices")
async def grpc_list_connected_devices(request: Request):
    """Handle gRPC-Web request for listing connected devices"""
    try:
        # Read the request body
        body = await request.body()

        # Decode based on content-type (text or binary)
        content_type = request.headers.get("content-type", "")

        if "application/grpc-web-text" in content_type:
            # Base64 decode for text mode
            body = base64.b64decode(body)

        # gRPC-Web adds a 5-byte prefix: 1 byte compression flag + 4 bytes length
        if len(body) >= 5:
            compression_flag = body[0]
            message_length = struct.unpack(">I", body[1:5])[0]
            body = body[5 : 5 + message_length]

        # Parse the protobuf request
        grpc_request = ListConnectedDevicesRequest.FromString(body)

        # Build the response
        response = ListConnectedDevicesResponse()
        for device in devices.values():
            response.devices.append(device)

        # Serialize the response
        response_bytes = response.SerializeToString()

        # Add gRPC-Web framing: 1 byte (no compression) + 4 bytes length + message
        framed_response = (
            bytes([0]) + struct.pack(">I", len(response_bytes)) + response_bytes
        )

        # Encode for gRPC-Web text mode if needed
        if "application/grpc-web-text" in content_type:
            framed_response = base64.b64encode(framed_response)
            content_type_response = "application/grpc-web-text"
        else:
            content_type_response = "application/grpc-web+proto"

        # Return with proper gRPC-Web headers
        return Response(
            content=framed_response,
            media_type=content_type_response,
            headers={
                "grpc-status": "0",
                "grpc-message": "",
            },
        )
    except Exception as e:
        logger.error(f"gRPC-Web error: {e}", exc_info=True)
        return Response(
            content=b"",
            status_code=500,
            headers={
                "grpc-status": "13",
                "grpc-message": str(e),
            },
        )


@app.post("/badezimmer.BadezimmerService/SendActuatorCommand")
async def grpc_send_actuator_command(request: Request):
    """Handle gRPC-Web request for sending actuator commands"""
    try:
        # Read the request body
        body = await request.body()

        # Decode based on content-type
        content_type = request.headers.get("content-type", "")

        if "application/grpc-web-text" in content_type:
            body = base64.b64decode(body)

        # gRPC-Web adds a 5-byte prefix: 1 byte compression flag + 4 bytes length
        if len(body) >= 5:
            compression_flag = body[0]
            message_length = struct.unpack(">I", body[1:5])[0]
            body = body[5 : 5 + message_length]

        # Parse the protobuf request
        grpc_request = SendActuatorCommandRequest.FromString(body)

        # Find the device
        device_id = grpc_request.device_id
        if device_id not in devices:
            error_trailer = b"grpc-status:5\r\ngrpc-message:Device not found\r\n"
            framed_error = (
                bytes([0x80]) + struct.pack(">I", len(error_trailer)) + error_trailer
            )

            if "application/grpc-web-text" in content_type:
                framed_error = base64.b64encode(framed_error)

            return Response(
                content=framed_error,
                status_code=200,
                headers={
                    "grpc-status": "5",
                    "grpc-message": "Device not found",
                    "content-type": content_type,
                },
            )

        device = devices[device_id]

        # Create the internal request
        badezimmer_request = BadezimmerRequest(send_actuator_command=grpc_request)

        # Send to device
        response_bytes = await send_request(
            list(device.ips), device.port, request=badezimmer_request
        )
        badezimmer_response = BadezimmerResponse.FromString(response_bytes)

        # Check for errors
        if badezimmer_response.WhichOneof("response") == "error":
            error = badezimmer_response.error
            error_msg = f"{error.code} - {error.message}"
            error_trailer = f"grpc-status:13\r\ngrpc-message:{error_msg}\r\n".encode()
            framed_error = (
                bytes([0x80]) + struct.pack(">I", len(error_trailer)) + error_trailer
            )

            if "application/grpc-web-text" in content_type:
                framed_error = base64.b64encode(framed_error)

            return Response(
                content=framed_error,
                status_code=200,
                headers={
                    "grpc-status": "13",
                    "grpc-message": error_msg,
                    "content-type": content_type,
                },
            )

        # Build response
        response = badezimmer_response.send_actuator_command_response
        response_bytes = response.SerializeToString()

        # Add gRPC-Web framing
        framed_response = (
            bytes([0]) + struct.pack(">I", len(response_bytes)) + response_bytes
        )

        # Add trailers
        trailer_data = b"grpc-status:0\r\ngrpc-message:\r\n"
        framed_response += (
            bytes([0x80]) + struct.pack(">I", len(trailer_data)) + trailer_data
        )

        # Encode for gRPC-Web text mode if needed
        if "application/grpc-web-text" in content_type:
            framed_response = base64.b64encode(framed_response)
            content_type_response = "application/grpc-web-text"
        else:
            content_type_response = "application/grpc-web+proto"

        return Response(
            content=framed_response,
            media_type=content_type_response,
            headers={
                "grpc-status": "0",
                "grpc-message": "",
            },
        )
    except Exception as e:
        logger.error(f"gRPC-Web error: {e}", exc_info=True)
        error_trailer = f"grpc-status:13\r\ngrpc-message:{str(e)}\r\n".encode()
        framed_error = (
            bytes([0x80]) + struct.pack(">I", len(error_trailer)) + error_trailer
        )

        if "application/grpc-web-text" in request.headers.get("content-type", ""):
            framed_error = base64.b64encode(framed_error)

        return Response(
            content=framed_error,
            status_code=200,
            headers={
                "grpc-status": "13",
                "grpc-message": str(e),
                "content-type": (
                    "application/grpc-web-text"
                    if "text" in request.headers.get("content-type", "")
                    else "application/grpc-web+proto"
                ),
            },
        )


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
