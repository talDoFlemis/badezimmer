import logging
import random
import signal
from datetime import datetime
from sys import deactivate_stack_trampoline

from google.protobuf.empty_pb2 import Empty
from badezimmer import (
    setup_logger,
    DeviceKind,
    DeviceCategory,
    TransportProtocol,
    BadezimmerRequest,
    BadezimmerResponse,
)
from badezimmer.tcp import (
    get_random_available_tcp_port,
    handle_request,
)

from badezimmer.mdns import MDNSServiceInfo, BadezimmerMDNS
import asyncio

random_seed = 42069
random.seed(random_seed)

possible_weights_in_kilos = [str(i) for i in range(50, 120)]
possible_materials = ["SOLID", "LIQUID"]
possible_solid_material_weights_in_grams = [str(i) for i in range(100, 201)]
possible_bowl_cleaner_levels = [str(i) for i in range(1, 11)]
interval_between_use_in_seconds = 5.0
clogged_flush_probability = 1/3


logger = logging.getLogger(__name__)
setup_logger(logger)
mdns = BadezimmerMDNS()

info = MDNSServiceInfo(
    name="Inteligent Toilet",
    type_="_toilet._tcp.local.",
    port=0,
    kind=DeviceKind.SENSOR_KIND,
    category=DeviceCategory.TOILET,
    protocol=TransportProtocol.TCP_PROTOCOL,
    properties={
        "clogged": "false",
        "weight_on": "",
        "material_in": "",
        "solid_material_weight": "",
        "bowl_cleaner_level": "10.0",
        "water_consumption_today_liters": "0",
        "flushed": "true",
        "last_flushed": "",
    },
)

mdns = BadezimmerMDNS()


async def execute(request: BadezimmerRequest) -> BadezimmerResponse:
    return BadezimmerResponse(empty=Empty())

async def generate_random_data():
    while True:
        if info.properties["flushed"] == "false" and info.properties["material_in"] == "SOLID":
            if int(info.properties["solid_material_weight"]) > 150:
                if random.random() < clogged_flush_probability:
                    logger.info("Toilet flushed while clogged")
                    info.properties["clogged"] = "false"
                    info.properties["flushed"] = "true"
                    info.properties["last_flushed"] = datetime.now().isoformat()
                    
                    current_consumption = float(info.properties["water_consumption_today_liters"])
                    current_consumption += 6.0
                    info.properties["water_consumption_today_liters"] = str(current_consumption)
                else:
                    logger.info("Toilet flush failed - still clogged")
                    info.properties["flushed"] = "false"
                    await mdns.update_service(info)
                    await asyncio.sleep(interval_between_use_in_seconds)
            else:
                info.properties["flushed"] = "true"
                info.properties["last_flushed"] = datetime.now().isoformat()
                info.properties["material_in"] = ""
                info.properties["solid_material_weight"] = ""

        if info.properties["clogged"] == "true":
            if random.random() < clogged_flush_probability:
                logger.info("Toilet flushed while clogged")
                info.properties["clogged"] = "false"
                info.properties["flushed"] = "true"
                info.properties["last_flushed"] = datetime.now().isoformat()
                
                current_consumption = float(info.properties["water_consumption_today_liters"])
                current_consumption += 6.0
                info.properties["water_consumption_today_liters"] = str(current_consumption)
            else:
                logger.info("Toilet flush failed - still clogged")
                info.properties["flushed"] = "false"
                await mdns.update_service(info)
                await asyncio.sleep(interval_between_use_in_seconds)
                return
            continue

        info.properties["material_in"] = random.choice(possible_materials)
        info.properties["weight_on"] = random.choice(possible_weights_in_kilos)
        
        flushed = random.choice(["true", "false"])
        info.properties["flushed"] = flushed
        
        if info.properties["material_in"] == "SOLID":
            solid_material_weight = random.choice(possible_solid_material_weights_in_grams)
            info.properties["solid_material_weight"] = solid_material_weight
            
            if int(solid_material_weight) > 150:
                info.properties["clogged"] = "true"
                logger.info("Toilet clogged due to heavy solid material")
                current_level = float(info.properties["bowl_cleaner_level"])
                current_level *= 0.3
                current_level = max(1.0, current_level)
                info.properties["bowl_cleaner_level"] = str(int(current_level))
            else:
                info.properties["clogged"] = "false"
        else:
            info.properties["clogged"] = "false"
            info.properties["solid_material_weight"] = ""
            
            current_level = float(info.properties["bowl_cleaner_level"])
            current_level *= 1.1
            current_level = min(10.0, current_level)
            info.properties["bowl_cleaner_level"] = str(float(current_level))
        
        if flushed == "true":
            current_consumption = int(info.properties["water_consumption_today_liters"])
            current_consumption += 6
            current_clean_level = float(info.properties["bowl_cleaner_level"])
            current_clean_level *= 1.2
            current_clean_level = min(10.0, current_clean_level)
            info.properties["water_consumption_today_liters"] = str(current_consumption)
            info.properties["last_flushed"] = datetime.now().isoformat()
            logger.info("Toilet flushed")
        else:
            current_level = float(info.properties["bowl_cleaner_level"])
            current_level *= 0.8
            current_level = max(1.0, current_level)
            info.properties["bowl_cleaner_level"] = str(float(current_level))
        
        await mdns.update_service(info)
        await asyncio.sleep(interval_between_use_in_seconds)

async def main_server(port: int):
    server = await asyncio.start_server(handle_request(execute), "0.0.0.0", port)
    logger.info("Starting Inteligent Toilet service...", extra={"port": port})
    info.port = port
    await mdns.start()
    await mdns.register_service(info)

    data_task = asyncio.create_task(generate_random_data())

    try:
        async with server:
            await server.serve_forever()
    except Exception as e:
        logger.error(f"Server error: {e}")
    except asyncio.CancelledError:
        logger.info("Task cancelled. Performing cleanup...")
    finally:
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
