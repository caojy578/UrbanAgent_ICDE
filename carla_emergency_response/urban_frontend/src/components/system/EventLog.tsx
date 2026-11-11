import { useMemo } from 'react';
import { useSystemStore } from '@/store/useSystemStore';
import { Panel } from '@/components/primitives/Panel';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/cn';
import { useFadeMask } from '@/hooks/useFadeMask';
import { ScrollFade } from '@/components/primitives/ScrollFade';
import type { Severity } from '@/types';

const tone: Record<Severity, string> = {
  info: 'text-fg-3',
  ok: 'text-ok',
  warn: 'text-warn',
  danger: 'text-danger',
};

function fmt(ts: number) {
  const d = new Date(ts);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(
    2,
    '0',
  )}:${String(d.getSeconds()).padStart(2, '0')}`;
}

export function EventLog() {
  const allEvents = useSystemStore((s) => s.events);
  const events = useMemo(
    () => allEvents.filter((e) => e.source === 'SCENARIO'),
    [allEvents],
  );
  const fade = useFadeMask<HTMLDivElement>();
  return (
    <Panel
      tag="LOG"
      title="事件日志"
      collapsible
      state="live"
      className="flex-1 min-h-0"
      actions={
        <span className="font-mono text-2xs text-fg-3 tnum">{events.length}</span>
      }
    >
      <div className="relative h-full">
      <div
        ref={fade.ref}
        className="h-full px-4 pt-1 pb-1 overflow-auto"
        style={{
          overscrollBehavior: 'contain',
        }}
      >
        <AnimatePresence initial={false}>
          {events
            .slice()
            .reverse()
            .map((e) => (
              <motion.div
                key={e.id}
                layout
                initial={{ opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.24 }}
                className="flex items-baseline gap-2 h-[22px]"
              >
                <span className="font-mono text-2xs text-fg-4 tnum w-[60px] shrink-0">
                  {fmt(e.timestamp)}
                </span>
                <span
                  className={cn(
                    'font-mono text-2xs uppercase tracking-[0.06em] w-[60px] shrink-0',
                    tone[e.severity],
                  )}
                >
                  {e.source}
                </span>
                <span className="text-xs text-fg-2 truncate">{e.message}</span>
              </motion.div>
            ))}
        </AnimatePresence>
      </div>
        <ScrollFade top={fade.top} bottom={fade.bottom} />
      </div>
    </Panel>
  );
}
