import { useTelemetryStore } from '@/store/useTelemetryStore';
import { useSystemStore } from '@/store/useSystemStore';

let timer: ReturnType<typeof setInterval> | null = null;

const drift = (v: number, range: number, min = 0, max = 100) =>
  Math.max(min, Math.min(max, v + (Math.random() - 0.5) * range));

export function startMockBridge(intervalMs = 800) {
  if (timer) return;
  useSystemStore.getState().setSource('mock');
  useSystemStore.getState().setConnection('offline');

  timer = setInterval(() => {
    const t = useTelemetryStore.getState();
    t.ingest({
      uav: {
        ...t.uav,
        altitude: drift(t.uav.altitude, 0.6, 80, 180),
        speed: drift(t.uav.speed, 0.4, 0, 60),
        battery: Math.max(0, t.uav.battery - 0.01),
        link: { ...t.uav.link, latency: drift(t.uav.link.latency, 2, 5, 60) },
      },
      ugv: {
        ...t.ugv,
        speed: drift(t.ugv.speed, 0.4, 0, 60),
        heading: drift(t.ugv.heading, 1, 0, 360),
        link: { ...t.ugv.link, latency: drift(t.ugv.link.latency, 2, 5, 60) },
      },
      city: {
        ...t.city,
        vehicles: Math.round(drift(t.city.vehicles, 6, 800, 1800)),
        pedestrians: Math.round(drift(t.city.pedestrians, 80, 30000, 60000)),
      },
    });

    const sys = useSystemStore.getState();
    const fps = Math.round(drift(sys.metrics.fps, 1, 50, 62));
    sys.setMetrics({
      cpu: drift(sys.metrics.cpu, 2, 20, 95),
      gpu: drift(sys.metrics.gpu, 2, 30, 98),
      mem: drift(sys.metrics.mem, 1, 30, 90),
      net: drift(sys.metrics.net, 3, 5, 90),
    });
    sys.pushFps(fps);
  }, intervalMs);
}

export function stopMockBridge() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}
