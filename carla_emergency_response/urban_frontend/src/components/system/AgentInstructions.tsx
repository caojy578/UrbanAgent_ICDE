import { useMemo } from 'react';
import { useSystemStore } from '@/store/useSystemStore';
import { Panel } from '@/components/primitives/Panel';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/cn';
import { useFadeMask } from '@/hooks/useFadeMask';
import { ScrollFade } from '@/components/primitives/ScrollFade';

type Action = 'accept' | 'reject';

interface Parsed {
  action: Action;
  target: string | null;
  kind: string | null;
  rest: string;
}

const INSTRUCTION_RE = /^(accept|reject)\s/i;

function parseInstruction(message: string): Parsed | null {
  const m = INSTRUCTION_RE.exec(message);
  if (!m) return null;
  const action = m[1].toLowerCase() as Action;

  const tokens = message.trim().split(/\s+/);
  // tokens[0] = action; tokens[1] is task id only when it has no '=' (e.g. ta-xxx)
  const startIndex = tokens[1] && !tokens[1].includes('=') ? 2 : 1;

  let target: string | null = null;
  let kind: string | null = null;
  const others: string[] = [];
  for (const tok of tokens.slice(startIndex)) {
    const eq = tok.indexOf('=');
    if (eq <= 0) {
      others.push(tok);
      continue;
    }
    const key = tok.slice(0, eq);
    const val = tok.slice(eq + 1);
    if (key === 'target') target = val;
    else if (key === 'kind') kind = val;
    else others.push(tok);
  }
  return { action, target, kind, rest: others.join(' ') };
}

function fmt(ts: number) {
  const d = new Date(ts);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(
    2,
    '0',
  )}:${String(d.getSeconds()).padStart(2, '0')}`;
}

interface Row {
  id: string;
  timestamp: number;
  action: Action;
  target: string | null;
  kind: string | null;
  rest: string;
}

export function AgentInstructions() {
  const events = useSystemStore((s) => s.events);
  const fade = useFadeMask<HTMLDivElement>();

  const rows = useMemo<Row[]>(() => {
    const out: Row[] = [];
    for (const e of events) {
      if (e.source !== 'AGENT') continue;
      const parsed = parseInstruction(e.message);
      if (!parsed) continue;
      out.push({
        id: e.id,
        timestamp: e.timestamp,
        action: parsed.action,
        target: parsed.target,
        kind: parsed.kind,
        rest: parsed.rest,
      });
    }
    return out;
  }, [events]);

  return (
    <Panel
      tag="AGENT"
      title="智能体指令"
      collapsible
      state="live"
      className="flex-1 min-h-0"
      actions={
        <span className="font-mono text-2xs text-fg-3 tnum">{rows.length}</span>
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
          {rows.length === 0 ? (
            <div className="flex items-center h-[22px] font-mono text-2xs text-fg-4">
              暂无 UrbanAgent 调度指令
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {rows
                .slice()
                .reverse()
                .map((r) => (
                  <motion.div
                    key={r.id}
                    layout
                    initial={{ opacity: 0, x: -4 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.24 }}
                    className="flex items-baseline gap-1.5 h-[22px] font-mono text-2xs"
                  >
                    <span className="text-fg-4 tnum w-[60px] shrink-0">
                      {fmt(r.timestamp)}
                    </span>
                    <span className="text-fg-3 shrink-0">UrbanAgent</span>
                    <span className="text-fg-4 shrink-0">-&gt;</span>
                    <span className="text-fg-2 w-[64px] shrink-0 truncate">
                      {r.target ?? '—'}
                    </span>
                    <span
                      className={cn(
                        'uppercase tracking-[0.06em] w-[34px] shrink-0',
                        r.action === 'accept' ? 'text-ok' : 'text-danger',
                      )}
                    >
                      {r.action === 'accept' ? 'ACK' : 'REJ'}
                    </span>
                    <span className="text-fg-2 truncate">
                      {r.kind ?? r.rest ?? '—'}
                    </span>
                  </motion.div>
                ))}
            </AnimatePresence>
          )}
        </div>
        <ScrollFade top={fade.top} bottom={fade.bottom} />
      </div>
    </Panel>
  );
}
