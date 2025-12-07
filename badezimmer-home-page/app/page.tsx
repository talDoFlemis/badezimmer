"use client";

import { useState, useEffect } from "react";
import {
  type ConnectedDevice,
  DeviceCategory,
  DeviceStatus,
} from "@/lib/device-types";
import { DeviceGrid } from "@/components/device-grid";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Loader2, RefreshCw, Wifi, WifiOff } from "lucide-react";
import { listConnectedDevices, getEventStream } from "@/lib/grpc-client";

export default function Home() {
  const [devices, setDevices] = useState<ConnectedDevice[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isConnected, setIsConnected] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchDevices = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const devicesList = await listConnectedDevices();

      // Convert protobuf objects to plain JavaScript objects
      const formattedDevices: ConnectedDevice[] = devicesList.map(
        (device: any) => ({
          id: device.getId(),
          device_name: device.getDeviceName(),
          kind: device.getKind(),
          status: device.getStatus(),
          ips: device.getIpsList(),
          port: device.getPort(),
          properties: device.getPropertiesMap().toObject(),
          category: device.getCategory(),
          transport_protocol: device.getTransportProtocol(),
        }),
      );

      setDevices(formattedDevices);
      setIsConnected(true);
      setLastUpdate(new Date());
    } catch (err) {
      console.error("Failed to fetch devices:", err);
      setError(
        err instanceof Error ? err.message : "Failed to connect to gateway",
      );
      setIsConnected(false);
      setDevices([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch
    fetchDevices();

    // Set up event stream for real-time updates
    const cleanup = getEventStream(
      () => {
        // onOpen callback
        setIsConnected(true);
        console.log("Connected to device event stream");
      },
      (err) => {
        // onError callback
        console.error("Event stream error:", err);
        setIsConnected(false);
        setError("Lost connection to gateway");
      },
      (device) => {
        // onDeviceEvent callback
        setDevices((prevDevices) => {
          // Find if device already exists
          const existingIndex = prevDevices.findIndex(
            (d) => d.id === device.id,
          );

          if (existingIndex >= 0) {
            // Update existing device
            const newDevices = [...prevDevices];
            newDevices[existingIndex] = device;
            return newDevices;
          } else {
            // Add new device
            return [...prevDevices, device];
          }
        });
        setLastUpdate(new Date());
      },
    );

    return () => {
      if (cleanup) cleanup();
    };
  }, []);

  const handleRefresh = async () => {
    await fetchDevices();
  };

  const onlineDevices = devices.filter((d) => d.status === 2).length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">Badezimmer</h1>
              <p className="text-slate-400">Smart Bathroom Monitor Gateway</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-4 py-2 bg-slate-800 rounded-lg border border-slate-700">
                {isConnected ? (
                  <>
                    <Wifi className="w-4 h-4 text-green-500" />
                    <span className="text-sm text-slate-300">Connected</span>
                  </>
                ) : (
                  <>
                    <WifiOff className="w-4 h-4 text-red-500" />
                    <span className="text-sm text-slate-300">Disconnected</span>
                  </>
                )}
              </div>
              <Button
                onClick={handleRefresh}
                disabled={isLoading}
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4 mr-2" />
                )}
                Refresh
              </Button>
            </div>
          </div>

          {/* Status Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="bg-slate-800 border-slate-700">
              <div className="p-4">
                <p className="text-slate-400 text-sm mb-1">Total Devices</p>
                <p className="text-3xl font-bold text-white">
                  {devices.length}
                </p>
              </div>
            </Card>
            <Card className="bg-slate-800 border-slate-700">
              <div className="p-4">
                <p className="text-slate-400 text-sm mb-1">Online</p>
                <p className="text-3xl font-bold text-green-400">
                  {onlineDevices}
                </p>
              </div>
            </Card>
            <Card className="bg-slate-800 border-slate-700">
              <div className="p-4">
                <p className="text-slate-400 text-sm mb-1">Last Updated</p>
                <p className="text-sm text-slate-300">
                  {lastUpdate ? lastUpdate.toLocaleTimeString() : "—"}
                </p>
              </div>
            </Card>
          </div>
        </div>

        {/* Device Grid */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-white mb-4">
            Connected Devices
          </h2>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            </div>
          ) : (
            <DeviceGrid devices={devices} />
          )}
        </div>

        {/* Footer Info */}
        <div className="text-center text-slate-500 text-sm py-4 border-t border-slate-700">
          <p>
            Connecting via gRPC Web over TCP • Gateway:{" "}
            {process.env.NEXT_PUBLIC_GATEWAY_HOST || "http://localhost:8080"}
          </p>
        </div>
      </div>
    </div>
  );
}
