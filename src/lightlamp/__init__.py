import logging
from zeroconf import (
    IPVersion,
    Zeroconf,
    ServiceInfo,
)
from badezimmer import (
    setup_logger,
    SendActuatorCommandResponse,
    SendActuatorCommandRequest,
    DeviceKind,
    DeviceCategory,
)
import badezimmer
from badezimmer.tcp import (
    get_random_available_tcp_port,
    get_all_ips_for_adapters,
    handle_request,
)

from badezimmer.mdns import MDNSServiceInfo, BadezimmerMDNS
import asyncio
from zeroconf import Zeroconf

SERVICE_TYPE = "_lightlamp._tcp.local."
DESCRIPTION = "A smart light lamp device"
PROPERTIES: dict[str | bytes, str | bytes | None] = {
    "kind": DeviceKind.Name(DeviceKind.ACTUATOR_KIND.numerator),
    "category": DeviceCategory.Name(DeviceCategory.LIGHT_LAMP.numerator),
    "is_on": "false",
    "brightness": "0",
    "color": "0xFFFFFF",
}

setup_logger()
logger = logging.getLogger(__name__)

# zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

info = ServiceInfo(
    SERVICE_TYPE,
    f"Light Lamp.{SERVICE_TYPE}",
    addresses=get_all_ips_for_adapters(),
    port=0,
    properties=PROPERTIES,
)


async def execute(request: SendActuatorCommandRequest) -> SendActuatorCommandResponse:
    response = SendActuatorCommandResponse()
    field = request.WhichOneof("action")

    if field != "light_action":
        response.message = f"Unknown action {field} for action"
        return response

    light_action = request.light_action

    global state
    msg = ""

    if light_action.turn_on and PROPERTIES["is_on"] != "true":
        PROPERTIES["is_on"] = "true"
        msg += "Light turned ON. "
    if light_action.turn_on is False and PROPERTIES["is_on"] == "true":
        PROPERTIES["is_on"] = "false"
        msg += "Light turned OFF. "
    if light_action.brightness != PROPERTIES["brightness"]:
        PROPERTIES["brightness"] = str(light_action.brightness)
        msg += f"Brightness set to {light_action.brightness}. "
    if light_action.color.value != PROPERTIES["color"]:
        PROPERTIES["color"] = str(light_action.color.value)
        msg += f"Color set to #{light_action.color.value:06X}. "
    else:
        msg += "No change. "

    info._set_properties(PROPERTIES)
    # zeroconf.update_service(info)

    return SendActuatorCommandResponse(message=msg.strip())


async def register(port: int):
    logger.info(
        "Registering service with Zeroconf...",
        extra={
            "port": port,
            "service_type": SERVICE_TYPE,
            "properties": PROPERTIES,
        },
    )

    info.port = port
    # zeroconf.register_service(info, allow_name_change=True)
    logger.info("Service registered.")


async def main_server(port: int):
    server = await asyncio.start_server(handle_request(execute), "0.0.0.0", port)
    logger.info("Starting Light Lamp service...", extra={"port": port})
    # await register(port)
    mdns = BadezimmerMDNS()
    another_info = MDNSServiceInfo(
        name="tubias",
        type="tubias._tcp.local",
        port=port,
        kind=DeviceKind.SENSOR_KIND,
        category=DeviceCategory.LIGHT_LAMP,
        properties={"is_on": "false", "brightness": "0", "color": "0xFFFFFF"},
    )
    await mdns.register_service(another_info)
    logger.info("Registered")

    try:
        async with server:
            await server.serve_forever()
    except Exception as e:
        logger.error(f"Server error: {e}")
    except asyncio.CancelledError:
        logger.info("Task cancelled. Performing cleanup...")
        logger.info("Unregistering service...")
        # zeroconf.unregister_service(info)
        logger.info("Service unregistered.")


def main():
    port = get_random_available_tcp_port()
    try:
        asyncio.run(main_server(port))
    except KeyboardInterrupt:
        logger.info("Server stopped manually.")


if __name__ == "__main__":
    main()
