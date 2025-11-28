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
from badezimmer.tcp import (
    get_random_available_tcp_port,
    get_all_ips_for_adapters,
    handle_request,
)
import random
import asyncio

random_seed = 42069
random.seed(random_seed)

possible_severities = [str(i) for i in range(0, 11)]
possible_diets = ["HIGH_FIBER", "HIGH_PROTEIN", "VEGAN", "KETO", "STANDARD"]
interval_between_farts_in_seconds = 10.0

SERVICE_TYPE = "_fartdetector._tcp.local."
DESCRIPTION = "A fart detector device"
PROPERTIES: dict[str | bytes, str | bytes | None] = {
    "kind": DeviceKind.Name(DeviceKind.SENSOR_KIND.numerator),
    "category": DeviceCategory.Name(DeviceCategory.FART_DETECTOR.numerator),
    "severity": random.choice(possible_severities),
    "diet": random.choice(possible_diets),
}


setup_logger()
logger = logging.getLogger(__name__)

zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

info = ServiceInfo(
    SERVICE_TYPE,
    f"Shopee Fart Detector.{SERVICE_TYPE}",
    addresses=get_all_ips_for_adapters(),
    port=0,
    properties=PROPERTIES,
)


async def execute(_request: SendActuatorCommandRequest) -> SendActuatorCommandResponse:
    return SendActuatorCommandResponse(message="No actuator commands supported.")


async def generate_random_data():
    while True:
        PROPERTIES["diet"] = random.choice(possible_diets)
        PROPERTIES["severity"] = random.choice(possible_severities)
        info._set_properties(PROPERTIES)
        zeroconf.update_service(info)
        await asyncio.sleep(interval_between_farts_in_seconds)


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
    zeroconf.register_service(info, allow_name_change=True)
    logger.info("Service registered.")


async def main_server(port: int):
    server = await asyncio.start_server(handle_request(execute), "0.0.0.0", port)
    logger.info("Starting Light Lamp service...", extra={"port": port})
    await register(port)

    # Start the random data generation task
    data_task = asyncio.create_task(generate_random_data())

    try:
        async with server:
            await server.serve_forever()
    except Exception as e:
        logger.error(f"Server error: {e}")
    except asyncio.CancelledError:
        logger.info("Task cancelled. Performing cleanup...")
    finally:
        # Cancel the data generation task
        data_task.cancel()
        try:
            await data_task
        except asyncio.CancelledError:
            logger.info("Data generation task stopped.")
        logger.info("Unregistering service...")
        zeroconf.unregister_service(info)
        logger.info("Service unregistered.")


def main():
    port = get_random_available_tcp_port()
    try:
        asyncio.run(main_server(port))
    except KeyboardInterrupt:
        logger.info("Server stopped manually.")


if __name__ == "__main__":
    main()
