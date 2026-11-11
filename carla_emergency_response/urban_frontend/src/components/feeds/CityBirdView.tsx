import { Panel } from '@/components/primitives/Panel';
import { Button } from '@/components/primitives/Button';
import { Badge } from '@/components/primitives/Badge';
import { NumberFlow } from '@/components/primitives/NumberFlow';
import { useTelemetryStore } from '@/store/useTelemetryStore';
import { VideoSurface } from './VideoSurface';
import { CornersOut, Compass } from '@phosphor-icons/react';
import { useState } from 'react';
import { cn } from '@/lib/cn';
import { useFullscreen } from '@/hooks/useFullscreen';

const layers = ['Vehicles', 'Pedestrians', 'Signals', 'Heatmap'] as const;
type Layer = (typeof layers)[number];

const DEFAULT_URL = import.meta.env.VITE_CITY_FEED_URL ?? '/media/city.mp4';

export function CityBirdView() {
  const city = useTelemetryStore((s) => s.city);
  const [active, setActive] = useState<Layer[]>(['Vehicles', 'Signals']);
  const { toggle: toggleFs } = useFullscreen();

  const toggle = (l: Layer) =>
    setActive((s) => (s.includes(l) ? s.filter((x) => x !== l) : [...s, l]));

  return (
    <Panel
      id="panel-city"
      tag="MAP-3D"
      title="3D 鸟瞰图"
      subtitle="城市数字孪生"
      state="live"
      variant="feature"
      actions={
        <>
          <div className="flex items-center gap-1 mr-2">
            {layers.map((l) => {
              const on = active.includes(l);
              return (
                <button
                  key={l}
                  onClick={() => toggle(l)}
                  title={l}
                  className={cn(
                    'h-6 px-2 rounded font-mono text-2xs uppercase tracking-[0.08em] transition-all duration-140 ease-spring',
                    on
                      ? 'bg-accent/12 text-accent border border-accent/30'
                      : 'text-fg-3 border border-transparent hover:text-fg-1 hover:bg-surface-2',
                  )}
                >
                  {l}
                </button>
              );
            })}
          </div>
          <Badge tone="accent">UE4 PIXEL STREAM</Badge>
          <Button
            variant="ghost"
            size="sm"
            aria-label="全屏"
            onClick={() => toggleFs('panel-city')}
          >
            <CornersOut size={12} />
          </Button>
        </>
      }
      className="flex-1 min-h-0"
      bodyClassName="flex flex-col"
    >
      <div className="relative flex-1 min-h-0">
        <VideoSurface variant="city" defaultUrl={DEFAULT_URL} />
        {/* compass — only floats over the video itself */}
        <div className="absolute top-4 left-4 size-10 glass rounded-full flex items-center justify-center">
          <Compass size={20} weight="duotone" className="text-fg-2" />
        </div>
      </div>

      {/* bottom data strip — sits in the panel chrome, matches panel bg */}
      <div className="px-6 py-3 border-t border-hairline flex items-center gap-8 font-mono shrink-0">
        <div className="flex items-baseline gap-2">
          <span className="text-2xs uppercase text-fg-3 tracking-[0.08em]">Vehicles</span>
          <span className="text-base text-fg-1 tnum">
            <NumberFlow value={city.vehicles} />
          </span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xs uppercase text-fg-3 tracking-[0.08em]">Pedestrians</span>
          <span className="text-base text-fg-1 tnum">
            <NumberFlow value={city.pedestrians} />
          </span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xs uppercase text-fg-3 tracking-[0.08em]">AQI</span>
          <span className="text-base text-ok tnum">{city.aqi}</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xs uppercase text-fg-3 tracking-[0.08em]">Alerts</span>
          <span className="text-base text-warn tnum">{city.alerts}</span>
        </div>
        <div className="ml-auto text-2xs uppercase tracking-[0.08em] text-fg-3">
          31.2304° N · 121.4737° E
        </div>
      </div>
    </Panel>
  );
}
