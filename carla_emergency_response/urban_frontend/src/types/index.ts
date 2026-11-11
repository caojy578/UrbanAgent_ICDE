export type ConnectionState = 'live' | 'reconnecting' | 'offline';

export type Severity = 'info' | 'ok' | 'warn' | 'danger';

export interface AgentSummary {
  id: string;
  kind: 'uav' | 'ugv';
  state: ConnectionState;
  battery?: number;
  signal: number;
}

export interface UavTelemetry {
  id: string;
  altitude: number;
  speed: number;
  heading: number;
  battery: number;
  gps: { lat: number; lng: number };
  link: { latency: number; quality: number };
}

export interface UgvTelemetry {
  id: string;
  speed: number;
  heading: number;
  road: string;
  obstacle: 'safe' | 'warn' | 'block';
  battery: number;
  link: { latency: number; quality: number };
}

export interface CityMetrics {
  vehicles: number;
  pedestrians: number;
  intersections: 'normal' | 'congested';
  aqi: number;
  alerts: number;
}

export interface SystemMetrics {
  cpu: number;
  gpu: number;
  mem: number;
  net: number;
  fps: number;
  fpsHistory: number[];
}

export interface CommandRecord {
  id: string;
  timestamp: number;
  direction: 'out' | 'ack' | 'reject' | 'system' | 'warn';
  target: string;
  text: string;
  latencyMs?: number;
}

export type Priority = 'normal' | 'high' | 'urgent';
