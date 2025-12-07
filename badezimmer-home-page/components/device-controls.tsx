"use client"

import type { ConnectedDevice } from "@/lib/device-types"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { useState } from "react"
import { Lightbulb, Power } from "lucide-react"
import { sendActuatorCommand, LightLampActionRequest } from "@/lib/grpc-client"

export function DeviceControls({ device }: { device: ConnectedDevice }) {
  const [brightness, setBrightness] = useState([50])
  const [isOn, setIsOn] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const handleBrightnessChange = async (value: number[]) => {
    setBrightness(value)
    
    if (!isOn) return
    
    try {
      setIsLoading(true)
      const lightAction = new LightLampActionRequest()
      lightAction.setTurnOn(true)
      lightAction.setBrightness(value[0])
      
      await sendActuatorCommand(device.id, lightAction)
    } catch (error) {
      console.error('Failed to update brightness:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleToggle = async () => {
    const newState = !isOn
    setIsOn(newState)
    
    try {
      setIsLoading(true)
      const lightAction = new LightLampActionRequest()
      lightAction.setTurnOn(newState)
      
      if (newState) {
        lightAction.setBrightness(brightness[0])
      }
      
      await sendActuatorCommand(device.id, lightAction)
    } catch (error) {
      console.error('Failed to toggle light:', error)
      // Revert state on error
      setIsOn(!newState)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-4 pt-2 border-t border-slate-700">
      <div className="flex items-center gap-2">
        <Button
          onClick={handleToggle}
          size="sm"
          variant={isOn ? "default" : "outline"}
          className={isOn ? "bg-blue-600 hover:bg-blue-700" : "border-slate-600 text-slate-300"}
        >
          <Power className="w-4 h-4 mr-2" />
          {isOn ? "On" : "Off"}
        </Button>
      </div>

      {isOn && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Lightbulb className="w-4 h-4 text-yellow-400" />
            <span className="text-xs text-slate-400">Brightness</span>
            <span className="ml-auto text-xs text-slate-300 font-semibold">{brightness[0]}%</span>
          </div>
          <Slider
            value={brightness}
            onValueChange={handleBrightnessChange}
            min={0}
            max={100}
            step={1}
            className="w-full"
          />
        </div>
      )}
    </div>
  )
}
