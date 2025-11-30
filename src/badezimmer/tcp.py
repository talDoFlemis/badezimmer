import socket
from google.protobuf import message
import ifaddr
import asyncio
from badezimmer import (
    setup_logger,
    BadezimmerRequest,
    BadezimmerResponse,
    ErrorDetails,
    ErrorCode,
)
import logging
from typing import Callable, Coroutine, Any

from badezimmer.badezimmer_pb2 import SendActuatorCommandResponse

logger = logging.getLogger(__name__)
setup_logger(logger)


def get_all_ips_for_adapters() -> list[bytes]:
    """
    Retrieves all IPv4 addresses associated with the machine's network adapters.
    """
    ips = set()
    adapters = ifaddr.get_adapters()

    for adapter in adapters:
        for ip in adapter.ips:
            if ip.is_IPv4 and ip.ip not in ips:
                ips.add(socket.inet_aton(str(ip.ip)))

    return list(ips)


def get_all_ips_strings_for_adapters() -> list[str]:
    """
    Retrieves all IPv4 addresses associated with the machine's network adapters.
    """
    ips = set()
    adapters = ifaddr.get_adapters()

    for adapter in adapters:
        for ip in adapter.ips:
            if ip.is_IPv4 and ip.ip not in ips:
                ips.add(str(ip.ip))

    return list(ips)


def get_random_available_tcp_port():
    """
    Finds a random, available TCP port by binding a socket to port 0
    and then retrieving the assigned port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def prepare_protobuf_request(message: message.Message) -> bytes:
    """
    Prepares a Protobuf message for sending over TCP by serializing it
    and prefixing it with its length as a 4-byte big-endian integer.
    """
    serialized_message = message.SerializeToString()
    message_length = len(serialized_message)
    length_prefix = message_length.to_bytes(4, byteorder="big")
    return length_prefix + serialized_message


def get_protobuf_data(data: bytes) -> bytes:
    """
    Parses a Protobuf message from received TCP data by extracting the length prefix
    and deserializing the message.
    """
    if len(data) < 4:
        raise ValueError("Data is too short to contain length prefix")

    message_length = int.from_bytes(data[:4], byteorder="big")
    if len(data) - 4 < message_length:
        raise ValueError("Data is shorter than expected message length")

    serialized_message = data[4 : 4 + message_length]
    return serialized_message


def handle_request(
    fn: Callable[
        [BadezimmerRequest], Coroutine[Any, Any, BadezimmerResponse]
    ],
):
    async def inner(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        logger.info(f"Connected by {addr}")

        while True:
            data = await reader.read(64 * 1024)

            if not data:
                logger.debug(f"No data received. Closing connection with {addr!r}")
                break

            logger.debug(f"Received {len(data)} bytes from {addr!r}")
            response = BadezimmerResponse()

            try:
                proto_raw = get_protobuf_data(data)
                request = BadezimmerRequest.FromString(proto_raw)
                response = await fn(request)
            except Exception as e:
                logger.exception(f"Error processing request from {addr!r}")
                response = BadezimmerResponse(error=ErrorDetails(code=ErrorCode.UNKNOWN_ERROR, message=str(e)))

            logger.debug("Response", extra={"response": response})
            response_bytes = prepare_protobuf_request(response)

            writer.write(response_bytes)
            await writer.drain()
            logger.debug("Sent bytes", extra={"bytes_sent": len(response_bytes)})

        logger.debug(f"Client {addr!r} disconnected")
        writer.close()
        await writer.wait_closed()

    return inner


async def send_request(ips: list[str], port: int, request: message.Message) -> bytes:
    """
    Sends a Protobuf request to a specified IP and port over TCP
    and returns the raw response data.
    """
    for ip in ips:
        try:
            reader, writer = await asyncio.open_connection(ip, port)
            logger.info(f"Connected to server at {ip}:{port}")

            request_bytes = prepare_protobuf_request(request)
            writer.write(request_bytes)
            await writer.drain()
            logger.info(f"Sent {len(request_bytes)} bytes to {ip}:{port}")

            data = await reader.read(64 * 1024)
            logger.info(f"Received {len(data)} bytes from {ip}:{port}")

            writer.close()
            await writer.wait_closed()

            proto_data = get_protobuf_data(data)
            return proto_data
        except (ConnectionRefusedError, asyncio.TimeoutError) as e:
            logger.warning(
                f"Could not connect to {ip}:{port}. Trying next IP if available."
            )
            continue

    raise ConnectionError(f"Could not connect to any provided IPs on port {port}")
