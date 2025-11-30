import logging
from badezimmer import (
    setup_logger,
    SendActuatorCommandResponse,
    SendActuatorCommandRequest,
    DeviceKind,
    DeviceCategory,
    TransportProtocol,
    BadezimmerRequest,
    BadezimmerResponse,
    ErrorDetails,
    ErrorCode,
)
from badezimmer.tcp import (
    get_random_available_tcp_port,
    handle_request,
)

from badezimmer.mdns import MDNSServiceInfo, BadezimmerMDNS
import asyncio

logger = logging.getLogger(__name__)
setup_logger(logger)

info = MDNSServiceInfo(
    name="Light Lamp",
    type_="_lightlamp._tcp.local.",
    port=0,
    kind=DeviceKind.ACTUATOR_KIND,
    category=DeviceCategory.LIGHT_LAMP,
    protocol=TransportProtocol.TCP_PROTOCOL,
    properties={
        "is_on": "false",
        "brightness": "0",
        "color": "0xFFFFFF",
    },
)

mdns = BadezimmerMDNS()


async def execute(request: BadezimmerRequest) -> BadezimmerResponse:
    response = BadezimmerResponse()
    field = request.WhichOneof("request")
    if field != "send_actuator_command":
        response.error = ErrorDetails(
            code=ErrorCode.INVALID_COMMAND,
            message=f"Unsupported request type: {field}",
            metadata={"field": field},
        )
        return response

    actuator_cmd = request.send_actuator_command
    field = actuator_cmd.WhichOneof("action")
    if field != "light_action":
        response.error = ErrorDetails(
            code=ErrorCode.INVALID_COMMAND,
            message=f"Unsupported actuator command type: {field}",
            metadata={"field": field},
        )
        return response

    light_action = actuator_cmd.light_action

    global state
    msg = ""

    if light_action.turn_on and info.properties["is_on"] != "true":
        info.properties["is_on"] = "true"
        msg += "Light turned ON. "
    if light_action.turn_on is False and info.properties["is_on"] == "true":
        info.properties["is_on"] = "false"
        msg += "Light turned OFF. "
    if light_action.brightness != info.properties["brightness"]:
        info.properties["brightness"] = str(light_action.brightness)
        msg += f"Brightness set to {light_action.brightness}. "
    if light_action.color.value != info.properties["color"]:
        info.properties["color"] = str(light_action.color.value)
        msg += f"Color set to #{light_action.color.value:06X}. "
    else:
        msg += "No change. "

    await mdns.update_service(info)

    return BadezimmerResponse(
        send_actuator_command_response=SendActuatorCommandResponse(message=msg.strip())
    )


async def main_server(port: int):
    server = await asyncio.start_server(handle_request(execute), "0.0.0.0", port)
    logger.info("Starting Light Lamp service...", extra={"port": port})
    info.port = port
    await mdns.start()
    await mdns.register_service(info)

    try:
        await server.serve_forever()
    except Exception as e:
        logger.error(f"Server error: {e}")
    except asyncio.CancelledError:
        logger.info("Task cancelled. Performing cleanup...")
        logger.info("Unregistering service...")
        await mdns.unregister_service(info)
        await mdns.close()
        logger.info("Service unregistered.")


def main():
    port = get_random_available_tcp_port()
    try:
        asyncio.run(main_server(port))
    except KeyboardInterrupt:
        logger.info("Server stopped manually.")


if __name__ == "__main__":
    main()
