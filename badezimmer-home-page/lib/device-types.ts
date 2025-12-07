// Type definitions based on your proto schema
export enum DeviceKind {
  UNKNOWN_KIND = 0,
  SENSOR_KIND = 1,
  ACTUATOR_KIND = 2,
}

export enum DeviceStatus {
  UNKNOWN_DEVICE_STATUS = 0,
  OFFLINE_DEVICE_STATUS = 1,
  ONLINE_DEVICE_STATUS = 2,
  ERROR_DEVICE_STATUS = 3,
}

export enum DeviceCategory {
  UNKNOWN_CATEGORY = 0,
  LIGHT_LAMP = 1,
  FART_DETECTOR = 2,
  TOILET = 3,
}

export interface ConnectedDevice {
  id: string
  device_name: string
  kind: DeviceKind
  status: DeviceStatus
  ips: string[]
  port: number
  properties: Record<string, string>
  category: DeviceCategory
  transport_protocol: number
}

export const deviceCategoryNames: Record<DeviceCategory, string> = {
  [DeviceCategory.UNKNOWN_CATEGORY]: "Unknown",
  [DeviceCategory.LIGHT_LAMP]: "Light Lamp",
  [DeviceCategory.FART_DETECTOR]: "Fart Detector",
  [DeviceCategory.TOILET]: "Toilet",
}

export const deviceStatusColors: Record<DeviceStatus, string> = {
  [DeviceStatus.UNKNOWN_DEVICE_STATUS]: "bg-gray-600",
  [DeviceStatus.OFFLINE_DEVICE_STATUS]: "bg-red-600",
  [DeviceStatus.ONLINE_DEVICE_STATUS]: "bg-green-600",
  [DeviceStatus.ERROR_DEVICE_STATUS]: "bg-yellow-600",
}

export const deviceStatusLabels: Record<DeviceStatus, string> = {
  [DeviceStatus.UNKNOWN_DEVICE_STATUS]: "Unknown",
  [DeviceStatus.OFFLINE_DEVICE_STATUS]: "Disconnected",
  [DeviceStatus.ONLINE_DEVICE_STATUS]: "Online",
  [DeviceStatus.ERROR_DEVICE_STATUS]: "Error",
}
