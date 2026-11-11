import { create } from 'zustand';
import type { CityMetrics, UavTelemetry, UgvTelemetry } from '@/types';

interface TelemetryState {
  uav: UavTelemetry;
  ugv: UgvTelemetry;
  city: CityMetrics;
  setUav: (patch: Partial<UavTelemetry>) => void;
  setUgv: (patch: Partial<UgvTelemetry>) => void;
  setCity: (patch: Partial<CityMetrics>) => void;
  ingest: (data: { uav?: Partial<UavTelemetry>; ugv?: Partial<UgvTelemetry>; city?: Partial<CityMetrics> }) => void;
}

export const useTelemetryStore = create<TelemetryState>((set) => ({
  uav: {
    id: 'UAV-01',
    altitude: 128.4,
    speed: 32.1,
    heading: 47,
    battery: 87,
    gps: { lat: 31.2304, lng: 121.4737 },
    link: { latency: 12, quality: 0.92 },
  },
  ugv: {
    id: 'UGV-02',
    speed: 28.6,
    heading: 312,
    road: '中环路 · E 段',
    obstacle: 'safe',
    battery: 73,
    link: { latency: 18, quality: 0.88 },
  },
  city: {
    vehicles: 1284,
    pedestrians: 45621,
    intersections: 'normal',
    aqi: 35,
    alerts: 3,
  },
  setUav: (patch) => set((s) => ({ uav: { ...s.uav, ...patch } })),
  setUgv: (patch) => set((s) => ({ ugv: { ...s.ugv, ...patch } })),
  setCity: (patch) => set((s) => ({ city: { ...s.city, ...patch } })),
  ingest: ({ uav, ugv, city }) =>
    set((s) => ({
      uav: uav ? { ...s.uav, ...uav } : s.uav,
      ugv: ugv ? { ...s.ugv, ...ugv } : s.ugv,
      city: city ? { ...s.city, ...city } : s.city,
    })),
}));
