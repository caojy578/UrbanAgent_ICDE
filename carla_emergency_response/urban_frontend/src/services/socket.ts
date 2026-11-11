import { io, type Socket } from 'socket.io-client';
import { useSystemStore } from '@/store/useSystemStore';
import { useTelemetryStore } from '@/store/useTelemetryStore';
import { useCommandStore } from '@/store/useCommandStore';

let socket: Socket | null = null;

export interface ConnectOptions {
  url: string;
  /** When true, do not bind handlers — useful for one-shot pings. */
  passive?: boolean;
}

export function getSocket(): Socket | null {
  return socket;
}

export function connect(opts: ConnectOptions) {
  if (socket) return socket;
  const sys = useSystemStore.getState();
  sys.setConnection('reconnecting');

  socket = io(opts.url, {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 8000,
    timeout: 6000,
    autoConnect: true,
  });

  if (opts.passive) return socket;

  socket.on('connect', () => {
    useSystemStore.getState().setMetrics({ cpu: 0, gpu: 0, mem: 0, net: 0, fps: 0 });
    useSystemStore.getState().setConnection('live');
    useSystemStore.getState().setSource('live');
    useSystemStore.getState().pushEvent({
      severity: 'ok',
      source: 'BRIDGE',
      message: `已连接 ${opts.url}`,
    });
  });

  socket.on('disconnect', (reason) => {
    useSystemStore.getState().setConnection('reconnecting');
    useSystemStore.getState().pushEvent({
      severity: 'warn',
      source: 'BRIDGE',
      message: `连接断开 · ${reason}`,
    });
  });

  socket.on('connect_error', (err) => {
    useSystemStore.getState().setConnection('reconnecting');
    useSystemStore.getState().pushEvent({
      severity: 'danger',
      source: 'BRIDGE',
      message: `连接错误 · ${err.message}`,
    });
  });

  socket.on('state_update', (payload: Record<string, unknown>) => {
    useTelemetryStore.getState().ingest(payload);
  });

  socket.on(
    'system_metrics',
    (m: { cpu?: number; gpu?: number; mem?: number; net?: number; fps?: number }) => {
      const store = useSystemStore.getState();
      store.setMetrics({
        cpu: m.cpu ?? 0,
        gpu: m.gpu ?? 0,
        mem: m.mem ?? 0,
        net: m.net ?? 0,
      });
      if (typeof m.fps === 'number') store.pushFps(m.fps);
    },
  );

  socket.on(
    'event_log',
    (e: { severity?: 'info' | 'ok' | 'warn' | 'danger'; source?: string; message: string }) => {
      useSystemStore.getState().pushEvent({
        severity: e.severity ?? 'info',
        source: e.source ?? 'AGENT',
        message: e.message,
      });
    },
  );

  socket.on(
    'agent_ack',
    (a: { id: string; target?: string; latency_ms?: number }) => {
      useCommandStore.getState().ack(a.id, a.latency_ms ?? 0, a.target);
    },
  );

  socket.on('agent_reject', (a: { id: string; reason: string; target?: string }) => {
    useCommandStore.getState().reject(a.id, a.reason, a.target);
  });

  return socket;
}

export function disconnect() {
  socket?.disconnect();
  socket = null;
  useSystemStore.getState().setConnection('offline');
  useSystemStore.getState().setSource('mock');
}

export function emitCommand(payload: {
  id: string;
  target: string;
  priority: string;
  text: string;
}) {
  if (!socket || !socket.connected) return false;
  socket.emit('agent_command', payload);
  return true;
}
