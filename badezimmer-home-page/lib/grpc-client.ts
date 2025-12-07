import { BadezimmerServicePromiseClient } from "../generated/badezimmer_grpc_web_pb";
const messages = require("../generated/badezimmer_pb");
import { type ConnectedDevice as DeviceType } from "@/lib/device-types";

const gatewayHost =
  process.env.NEXT_PUBLIC_GATEWAY_HOST || "http://localhost:8000";

export const badezimmerClient = new BadezimmerServicePromiseClient(
  gatewayHost,
  null,
  null,
);

export const {
  ListConnectedDevicesRequest,
  SendActuatorCommandRequest,
  LightLampActionRequest,
  SinkActionRequest,
  Color,
  DeviceKind,
  DeviceCategory,
  DeviceStatus,
  TransportProtocol,
  ConnectedDevice,
} = messages;

export const listConnectedDevices = async (
  filterKind?: number,
  filterName?: string,
) => {
  const request = new ListConnectedDevicesRequest();

  if (filterKind !== undefined) {
    request.setFilterKind(filterKind);
  }

  try {
    const response = await badezimmerClient.listConnectedDevices(request, {});
    return response.getDevicesList();
  } catch (error) {
    console.error("Error listing devices:", error);
    throw error;
  }
};

export const sendActuatorCommand = async (
  deviceId: string,
  action?: any,
) => {
  const request = new SendActuatorCommandRequest();
  request.setDeviceId(deviceId);

  if (action instanceof LightLampActionRequest) {
    request.setLightAction(action)
  } else if (action instanceof SinkActionRequest) {
    request.setSinkAction(action)
  }

  try {
    const response = await badezimmerClient.sendActuatorCommand(request, {});
    return response.getMessage();
  } catch (error) {
    console.error("Error sending command:", error);
    throw error;
  }
};

export const getEventStream = (
  onOpen: () => void,
  onError: (err: any) => void,
  onDeviceEvent: (device: DeviceType) => void,
) => {
  const eventSource = new EventSource(`${gatewayHost}/devices/events`);

  eventSource.onopen = () => {
    console.log("Event stream opened.");
    onOpen();
  };

  eventSource.onerror = (err) => {
    console.error("Event stream error:", err);
    onError(err);
  };

  eventSource.onmessage = (event) => {
    try {
      const binaryString = atob(event.data);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const device = ConnectedDevice.deserializeBinary(bytes);
      const realDevice: DeviceType = {
        id: device.getId(),
        device_name: device.getDeviceName(),
        kind: device.getKind(),
        status: device.getStatus(),
        ips: device.getIpsList(),
        port: device.getPort(),
        properties: device.getPropertiesMap().toObject(),
        category: device.getCategory(),
        transport_protocol: device.getTransportProtocol(),
      };

      onDeviceEvent(realDevice);
    } catch (error) {
      console.error("Error parsing device event:", error);
      onError(error);
    }
  };

  // Return cleanup function
  return () => {
    eventSource.close();
  };
};
