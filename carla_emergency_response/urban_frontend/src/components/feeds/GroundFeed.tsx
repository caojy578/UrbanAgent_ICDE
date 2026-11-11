import { Panel } from '@/components/primitives/Panel';
import { Stat } from '@/components/primitives/Stat';
import { Button } from '@/components/primitives/Button';
import { useTelemetryStore } from '@/store/useTelemetryStore';
import { VideoSurface } from './VideoSurface';
import { CornersOut } from '@phosphor-icons/react';
import { useFullscreen } from '@/hooks/useFullscreen';

const DEFAULT_URL = import.meta.env.VITE_UGV_FEED_URL ?? '/media/ground.mp4';

const obstacleTone = {
  safe: 'ok',
  warn: 'warn',
  block: 'danger',
} as const;

const obstacleLabel = {
  safe: '安全',
  warn: '警戒',
  block: '阻塞',
} as const;

export function GroundFeed() {
  const ugv = useTelemetryStore((s) => s.ugv);
  const { toggle } = useFullscreen();

  return (
    <Panel
      id="panel-ground"
      tag="GROUND"
      title="无人车视角"
      subtitle={ugv.id}
      state="live"
      collapsible
      actions={
        <Button
          variant="ghost"
          size="sm"
          aria-label="全屏"
          onClick={() => toggle('panel-ground')}
        >
          <CornersOut size={12} />
        </Button>
      }
      bodyClassName="flex flex-col"
      className="flex-1 min-h-0"
    >
      <div className="relative flex-1 min-h-0">
        <VideoSurface variant="ground" label={ugv.id} defaultUrl={DEFAULT_URL} />
      </div>
      <div className="grid grid-cols-4 gap-3 px-4 py-3 border-t border-hairline">
        <Stat label="SPD" value={ugv.speed.toFixed(1)} unit="km/h" size="sm" />
        <Stat label="HDG" value={`${Math.round(ugv.heading)}°`} size="sm" />
        <Stat
          label="OBS"
          value={obstacleLabel[ugv.obstacle]}
          size="sm"
          tone={obstacleTone[ugv.obstacle]}
        />
        <Stat
          label="LINK"
          value={ugv.link.latency.toFixed(0)}
          unit="ms"
          size="sm"
          tone={ugv.link.latency > 40 ? 'warn' : 'ok'}
        />
      </div>
    </Panel>
  );
}
