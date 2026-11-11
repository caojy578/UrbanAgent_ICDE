import { create } from 'zustand';
import type { ConnectionState, Severity, SystemMetrics } from '@/types';

export interface LogEvent {
  id: string;
  timestamp: number;
  severity: Severity;
  source: string;
  message: string;
}

interface SystemState {
  connection: ConnectionState;
  source: 'live' | 'mock';
  metrics: SystemMetrics;
  events: LogEvent[];
  setConnection: (c: ConnectionState) => void;
  setSource: (s: 'live' | 'mock') => void;
  setMetrics: (patch: Partial<SystemMetrics>) => void;
  pushFps: (fps: number) => void;
  pushEvent: (e: Omit<LogEvent, 'id' | 'timestamp'>) => void;
}

const seedFps = Array.from({ length: 60 }, (_, i) =>
  Math.round(58 + Math.sin(i / 4) * 2 + (Math.random() - 0.5) * 1.2),
);

export const useSystemStore = create<SystemState>((set) => ({
  connection: 'offline',
  source: 'mock',
  metrics: {
    cpu: 0,
    gpu: 0,
    mem: 0,
    net: 0,
    fps: 0,
    fpsHistory: seedFps,
  },
  events: [
    {
      id: 'e0',
      timestamp: Date.now() - 240_000,
      severity: 'info',
      source: 'BRIDGE',
      message: '指挥中心已启动',
    },
    {
      id: 'e1',
      timestamp: Date.now() - 230_000,
      severity: 'ok',
      source: 'BRIDGE',
      message: 'WebRTC 信令通道已建立',
    },
    {
      id: 'e2',
      timestamp: Date.now() - 210_000,
      severity: 'info',
      source: 'CARLA',
      message: '加载场景 Town10HD · LOD-5',
    },
    {
      id: 'e3',
      timestamp: Date.now() - 180_000,
      severity: 'ok',
      source: 'AGENT',
      message: 'UAV-01 / UAV-02 / UGV-01 在线',
    },
    {
      id: 'e4',
      timestamp: Date.now() - 130_000,
      severity: 'warn',
      source: 'NET',
      message: 'UAV-03 信号 -82 dBm,启动重连',
    },
    {
      id: 'e5',
      timestamp: Date.now() - 90_000,
      severity: 'info',
      source: 'BRIDGE',
      message: 'telemetry 推送 50Hz',
    },
    {
      id: 'e6',
      timestamp: Date.now() - 45_000,
      severity: 'danger',
      source: 'GUARD',
      message: 'UAV-04 进入限飞区,指令拒绝',
    },
    {
      id: 'e7',
      timestamp: Date.now() - 12_000,
      severity: 'ok',
      source: 'AGENT',
      message: 'UGV-02 路径规划完成 · WP-12',
    },
  ],
  setConnection: (connection) => set({ connection }),
  setSource: (source) => set({ source }),
  setMetrics: (patch) => set((s) => ({ metrics: { ...s.metrics, ...patch } })),
  pushFps: (fps) =>
    set((s) => ({
      metrics: {
        ...s.metrics,
        fps,
        fpsHistory: [...s.metrics.fpsHistory.slice(1), fps],
      },
    })),
  pushEvent: (e) =>
    set((s) => ({
      events: [
        ...s.events,
        { ...e, id: `e${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, timestamp: Date.now() },
      ].slice(-200),
    })),
}));
