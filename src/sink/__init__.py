import logging
import signal
import sys
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
    name="Sink",
    type_="_sink._tcp.local.",
    port=0,
    kind=DeviceKind.ACTUATOR_KIND,
    category=DeviceCategory.SINK,
    protocol=TransportProtocol.TCP_PROTOCOL,
    properties={
        "is_on": "false",
        "water_consumed_in_litters": "0"
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
    if field != "sink_action":
        response.error = ErrorDetails(
            code=ErrorCode.INVALID_COMMAND,
            message=f"Unsupported actuator command type: {field}",
            metadata={"field": field},
        )
        return response

    sink_action = actuator_cmd.sink_action

    global state
    msg = ""

    if sink_action.turn_on and info.properties["is_on"] != "true":
        info.properties["is_on"] = "true"
        msg += "Sink turned ON. "
    if sink_action.turn_on is False and info.properties["is_on"] == "true":
        info.properties["is_on"] = "false"
        msg += "Sink turned OFF. "
    elif sink_action.turn_on and info.properties["is_on"] == "true":
        msg += "Sink already ON. "

    if not msg:
        msg = "No change. "

    await mdns.update_service(info)
    return BadezimmerResponse(
        send_actuator_command_response=SendActuatorCommandResponse(message=msg.strip())
    )


async def update_water_consumption():
    """Continuously updates water consumption while sink is on"""
    while True:
        if info.properties["is_on"] == "true":
            water_consumed = int(info.properties["water_consumed_in_litters"])
            water_consumed += 5
            info.properties["water_consumed_in_litters"] = str(water_consumed)
            logger.info(f"Water consumed: {water_consumed}L")
            await mdns.update_service(info)
        
        await asyncio.sleep(3.0)


async def main_server(port: int):
    server = await asyncio.start_server(handle_request(execute), "0.0.0.0", port)
    logger.info("Starting Sink service...", extra={"port": port})
    info.port = port
    await mdns.start()
    await mdns.register_service(info)

    water_task = asyncio.create_task(update_water_consumption())

    try:
        await server.serve_forever()
    finally:
        water_task.cancel()
        try:
            await water_task
        except asyncio.CancelledError:
            logger.info("Water consumption task stopped.")
        server.close()
        await mdns.unregister_service(info)
        await mdns.close()


def _handle_signal(signum, frame):
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    port = get_random_available_tcp_port()

    try:
        asyncio.run(main_server(port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
