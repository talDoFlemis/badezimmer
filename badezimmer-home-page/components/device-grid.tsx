"use client"

import type { ConnectedDevice } from "@/lib/device-types"
import { DeviceCard } from "./device-card"

export function DeviceGrid({ devices }: { devices: ConnectedDevice[] }) {
  if (devices.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-400">No devices connected yet.</p>
        <p className="text-slate-500 text-sm mt-2">Devices will appear here once they connect to the gateway.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {devices.map((device) => (
        <DeviceCard key={device.id} device={device} />
      ))}
    </div>
  )
}
