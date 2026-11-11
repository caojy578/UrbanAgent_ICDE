import { Panel } from '@/components/primitives/Panel';
import { Stat } from '@/components/primitives/Stat';
import { Button } from '@/components/primitives/Button';
import { useTelemetryStore } from '@/store/useTelemetryStore';
import { VideoSurface } from './VideoSurface';
import { CornersOut } from '@phosphor-icons/react';
import { useFullscreen } from '@/hooks/useFullscreen';

const DEFAULT_URL = import.meta.env.VITE_UAV_FEED_URL ?? '/media/aerial.mp4';

export function AerialFeed() {
  const uav = useTelemetryStore((s) => s.uav);
  const { toggle } = useFullscreen();

  return (
    <Panel
      id="panel-aerial"
      tag="AERIAL"
      title="无人机视角"
      subtitle={uav.id}
      state="live"
      collapsible
      actions={
        <Button
          variant="ghost"
          size="sm"
          aria-label="全屏"
          onClick={() => toggle('panel-aerial')}
        >
          <CornersOut size={12} />
        </Button>
      }
      bodyClassName="flex flex-col"
      className="flex-1 min-h-0"
    >
      <div className="relative flex-1 min-h-0">
        <VideoSurface variant="aerial" label={uav.id} defaultUrl={DEFAULT_URL} />
      </div>
      <div className="grid grid-cols-4 gap-3 px-4 py-3 border-t border-hairline">
        <Stat label="ALT" value={uav.altitude.toFixed(1)} unit="m" size="sm" />
        <Stat label="SPD" value={uav.speed.toFixed(1)} unit="km/h" size="sm" />
        <Stat
          label="BAT"
          value={uav.battery.toFixed(0)}
          unit="%"
          size="sm"
          tone={uav.battery < 25 ? 'warn' : 'default'}
        />
        <Stat
          label="LINK"
          value={uav.link.latency.toFixed(0)}
          unit="ms"
          size="sm"
          tone={uav.link.latency > 40 ? 'warn' : 'ok'}
        />
      </div>
    </Panel>
  );
}
