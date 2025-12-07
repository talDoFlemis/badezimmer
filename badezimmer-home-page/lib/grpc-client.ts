import { BadezimmerServicePromiseClient } from '../generated/badezimmer_grpc_web_pb'
const messages = require('../generated/badezimmer_pb')

const gatewayHost = process.env.NEXT_PUBLIC_GATEWAY_HOST || "http://localhost:8000"

export const badezimmerClient = new BadezimmerServicePromiseClient(gatewayHost, null, null)

export const {
  ListConnectedDevicesRequest,
  SendActuatorCommandRequest,
  LightLampActionRequest,
  Color,
  DeviceKind,
  DeviceCategory,
  DeviceStatus,
  TransportProtocol
} = messages

export const listConnectedDevices = async (filterKind?: number, filterName?: string) => {
  const request = new ListConnectedDevicesRequest()
  
  if (filterKind !== undefined) {
    request.setFilterKind(filterKind)
  }
  
  if (filterName) {
    request.setFilterName(filterName)
  }
  
  try {
    const response = await badezimmerClient.listConnectedDevices(request, {})
    return response.getDevicesList()
  } catch (error) {
    console.error('Error listing devices:', error)
    throw error
  }
}

export const sendActuatorCommand = async (deviceId: string, lightAction?: any) => {
  const request = new SendActuatorCommandRequest()
  request.setDeviceId(deviceId)
  
  if (lightAction) {
    request.setLightAction(lightAction)
  }
  
  try {
    const response = await badezimmerClient.sendActuatorCommand(request, {})
    return response.getMessage()
  } catch (error) {
    console.error('Error sending command:', error)
    throw error
  }
}
