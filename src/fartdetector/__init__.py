import logging
from badezimmer import (
    setup_logger,
    DeviceKind,
    DeviceCategory,
    TransportProtocol,
    BadezimmerRequest,
    BadezimmerResponse,
    Empty,
)
from badezimmer.tcp import (
    get_random_available_tcp_port,
    handle_request,
)
from badezimmer.mdns import BadezimmerMDNS, MDNSServiceInfo
import random
import asyncio
import signal
import sys

random_seed = 42069
random.seed(random_seed)

possible_severities = [str(i) for i in range(0, 11)]
possible_diets = ["HIGH_FIBER", "HIGH_PROTEIN", "VEGAN", "KETO", "STANDARD"]
interval_between_farts_in_seconds = 10.0


logger = logging.getLogger(__name__)
setup_logger(logger)
mdns = BadezimmerMDNS()

info = MDNSServiceInfo(
    name="Shopee Fart Detector",
    type_="_fartdetector._tcp.local.",
    port=0,
    kind=DeviceKind.SENSOR_KIND,
    category=DeviceCategory.FART_DETECTOR,
    protocol=TransportProtocol.TCP_PROTOCOL,
    properties={
        "severity": random.choice(possible_severities),
        "diet": random.choice(possible_diets),
    },
)


async def execute(_request: BadezimmerRequest) -> BadezimmerResponse:
    return BadezimmerResponse(empty=Empty())


async def generate_random_data():
    while True:
        info.properties["diet"] = random.choice(possible_diets)
        info.properties["severity"] = random.choice(possible_severities)
        await mdns.update_service(info)
        await asyncio.sleep(interval_between_farts_in_seconds)


async def main_server(port: int):
    server = await asyncio.start_server(handle_request(execute), "0.0.0.0", port)
    logger.info("Starting Light Lamp service...", extra={"port": port})
    info.port = port
    await mdns.start()
    await mdns.register_service(info)

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
        await mdns.unregister_service(info)
        await mdns.close()
        logger.info("Service unregistered.")


def _handle_signal(signum, frame):
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    port = get_random_available_tcp_port()
    try:
        asyncio.run(main_server(port))
    except KeyboardInterrupt:
        logger.info("Server stopped manually.")


if __name__ == "__main__":
    main()
