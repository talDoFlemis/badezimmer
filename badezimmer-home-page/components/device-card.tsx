"use client"

import {
  type ConnectedDevice,
  deviceCategoryNames,
  deviceStatusColors,
  deviceStatusLabels,
  DeviceCategory,
} from "@/lib/device-types"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Lightbulb, Wind, Droplet } from "lucide-react"
import { DeviceControls } from "./device-controls"

export function DeviceCard({ device }: { device: ConnectedDevice }) {
  const getCategoryIcon = (category: DeviceCategory) => {
    switch (category) {
      case DeviceCategory.LIGHT_LAMP:
        return <Lightbulb className="w-5 h-5" />
      case DeviceCategory.FART_DETECTOR:
        return <Wind className="w-5 h-5" />
      case DeviceCategory.TOILET:
        return <Droplet className="w-5 h-5" />
      default:
        return <Droplet className="w-5 h-5" />
    }
  }

  console.log(device.properties)

  const categoryIcon = getCategoryIcon(device.category)

  return (
    <Card className="bg-slate-800 border-slate-700 hover:border-slate-600 transition-colors">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <div className="text-blue-400">{categoryIcon}</div>
              <CardTitle className="text-lg text-white">{device.device_name}</CardTitle>
            </div>
            <CardDescription className="text-slate-400">{deviceCategoryNames[device.category]}</CardDescription>
          </div>
          <Badge className={`${deviceStatusColors[device.status]} text-white border-0`}>
            {deviceStatusLabels[device.status]}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Device ID:</span>
            <span className="text-slate-200 font-mono text-xs">{device.id.slice(0, 8)}...</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Status:</span>
            <span className="text-slate-200">{deviceStatusLabels[device.status]}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">IP Addresses:</span>
            <div className="text-right">
              {device.ips.slice(0, 3).map((ip, idx) => (
                <div key={idx} className="text-slate-200">{ip}</div>
              ))}
              {device.ips.length === 0 && <span className="text-slate-200">N/A</span>}
            </div>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Port:</span>
            <span className="text-slate-200">{device.port}</span>
          </div>
          
          {/* Device Properties */}
          {Object.keys(device.properties).length > 0 && (
            <div className="pt-2 border-t border-slate-700">
              <span className="text-slate-400 block mb-2">Properties:</span>
              <div className="space-y-1 pl-2">
                {Object.keys(device.properties)
                  .filter((key) => key !== 'category')
                  .map((key) => (
                    <div key={key} className="flex justify-between">
                      <span className="text-slate-500 text-xs">{key}:</span>
                      <span className="text-slate-300 text-xs">{device.properties[key]}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>

        {device.category === DeviceCategory.LIGHT_LAMP && <DeviceControls device={device} />}
      </CardContent>
    </Card>
  )
}
