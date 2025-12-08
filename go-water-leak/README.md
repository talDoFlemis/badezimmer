# Go Water Leak Detector

A water leak detection device implementation in Go for the Badezimmer IoT system.

## Features

- Custom mDNS protocol implementation for service discovery
- TCP server for communication with the gateway
- Random leak data generation (severity and location)
- Automatic service registration and TTL renewal

## Building

```bash
go build -o water-leak .
```

## Running

```bash
./water-leak
```

The service will automatically:
1. Get a random available TCP port
2. Register itself via mDNS as a water leak sensor
3. Start the TCP server
4. Generate random leak data every 10 seconds

## Configuration

- `PORT` environment variable: Set a specific TCP port (optional)

## Docker

Build the Docker image:

```bash
docker build -f ../Dockerfile.water-leak -t water-leak ..
```

Run the container:

```bash
docker run --rm water-leak
```

## Protocol

The device uses the Badezimmer protobuf protocol defined in `../proto/badezimmer.proto`.

### mDNS Service

- Service Type: `_waterleak._tcp.local.`
- Device Kind: `SENSOR_KIND`
- Properties:
  - `severity`: 0-10 (leak severity level)
  - `location`: BATHROOM, KITCHEN, BASEMENT, LAUNDRY_ROOM, or GARAGE
