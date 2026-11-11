import { Panel } from '@/components/primitives/Panel';
import { useSystemStore } from '@/store/useSystemStore';
import { NumberFlow } from '@/components/primitives/NumberFlow';
import { cn } from '@/lib/cn';

interface BarProps {
  label: string;
  value: number;
  tone?: 'accent' | 'ok' | 'warn';
}

function Bar({ label, value, tone = 'accent' }: BarProps) {
  const colorMap = {
    accent: 'bg-accent',
    ok: 'bg-ok',
    warn: 'bg-warn',
  };
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-2xs uppercase tracking-[0.08em] text-fg-3">
          {label}
        </span>
        <span className="font-mono text-xs text-fg-1 tnum">
          <NumberFlow value={value} decimals={0} />%
        </span>
      </div>
      <div className="h-[3px] rounded-full bg-surface-3 overflow-hidden">
        <div
          className={cn('h-full transition-all duration-360 ease-spring', colorMap[tone])}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

export function Telemetry() {
  const sys = useSystemStore((s) => s.metrics);
  return (
    <Panel
      tag="SYS"
      title="系统遥测"
      collapsible
      state="live"
      className="shrink-0"
      actions={
        <span className="font-mono text-2xs text-fg-2 tnum">
          <NumberFlow value={sys.fps} /> fps
        </span>
      }
    >
      <div className="px-4 py-2 grid grid-cols-2 gap-x-4 gap-y-2">
        <Bar label="CPU" value={sys.cpu} />
        <Bar label="GPU" value={sys.gpu} />
        <Bar label="MEM" value={sys.mem} tone="ok" />
        <Bar label="NET" value={sys.net} />
      </div>
    </Panel>
  );
}
