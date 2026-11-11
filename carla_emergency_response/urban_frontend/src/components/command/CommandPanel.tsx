import { Panel } from '@/components/primitives/Panel';
import { Button } from '@/components/primitives/Button';
import { Input } from '@/components/primitives/Input';
import { useCommandStore } from '@/store/useCommandStore';
import { dispatchCommand } from '@/services/commandApi';
import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/cn';
import { ArrowRight, Check, Warning, X, Terminal, CaretDown } from '@phosphor-icons/react';
import type { CommandRecord, Priority } from '@/types';
import { motion, AnimatePresence } from 'framer-motion';

const targets = ['ALL', 'UAV', 'UGV', 'UAV-01', 'UAV-02', 'UGV-01', 'UGV-02'] as const;
const priorities: Priority[] = ['normal', 'high', 'urgent'];
const quickCmds = [
  { label: '返回基地', cmd: 'return-to-base' },
  { label: '悬停待命', cmd: 'hold' },
  { label: '开始巡逻', cmd: 'patrol' },
  { label: '数据采集', cmd: 'collect' },
];
const dangerCmds = [
  { label: '紧急停止', cmd: 'estop' },
  { label: '安全撤离', cmd: 'evacuate' },
];

function fmtTime(ts: number) {
  const d = new Date(ts);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(
    2,
    '0',
  )}:${String(d.getSeconds()).padStart(2, '0')}`;
}

function DirectionIcon({ direction }: { direction: CommandRecord['direction'] }) {
  switch (direction) {
    case 'out':
      return <ArrowRight size={11} weight="bold" className="text-accent" />;
    case 'ack':
      return <Check size={11} weight="bold" className="text-ok" />;
    case 'reject':
      return <X size={11} weight="bold" className="text-danger" />;
    case 'warn':
      return <Warning size={11} weight="bold" className="text-warn" />;
    case 'system':
      return <Terminal size={11} weight="bold" className="text-fg-3" />;
  }
}

export function CommandPanel() {
  const history = useCommandStore((s) => s.history);
  const inputHistory = useCommandStore((s) => s.inputHistory);
  const pushInputHistory = useCommandStore((s) => s.pushInputHistory);

  const [target, setTarget] = useState<(typeof targets)[number]>('ALL');
  const [priority, setPriority] = useState<Priority>('normal');
  const [text, setText] = useState('');
  const [historyIdx, setHistoryIdx] = useState(-1);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [quickOpen, setQuickOpen] = useState(false);
  const streamRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    streamRef.current?.scrollTo({
      top: streamRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [history.length]);

  const send = (raw: string) => {
    const cmd = raw.trim();
    if (!cmd) return;
    dispatchCommand(cmd, target, priority);
    pushInputHistory(cmd);
    setText('');
    setHistoryIdx(-1);
  };

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      send(text);
      return;
    }
    if (e.key === 'ArrowUp' && inputHistory.length > 0) {
      e.preventDefault();
      const next = Math.min(historyIdx + 1, inputHistory.length - 1);
      setHistoryIdx(next);
      setText(inputHistory[next] ?? '');
    }
    if (e.key === 'ArrowDown' && historyIdx >= 0) {
      e.preventDefault();
      const next = historyIdx - 1;
      setHistoryIdx(next);
      setText(next < 0 ? '' : (inputHistory[next] ?? ''));
    }
  };

  const handleDanger = (cmd: { label: string; cmd: string }) => {
    if (confirming === cmd.cmd) {
      send(cmd.cmd);
      setConfirming(null);
    } else {
      setConfirming(cmd.cmd);
      setTimeout(() => setConfirming((c) => (c === cmd.cmd ? null : c)), 2400);
    }
  };

  return (
    <Panel
      id="panel-command"
      tag="CMD"
      title="智能体指令"
      collapsible
      state="live"
      bodyClassName="flex flex-col"
      className="flex-1 min-h-0"
    >
      <div className="px-4 py-3 flex items-center gap-2 border-b border-hairline shrink-0">
        <select
          value={target}
          onChange={(e) => setTarget(e.target.value as typeof target)}
          className="flex-1 h-8 px-2 rounded bg-surface-2 border border-hairline text-xs text-fg-1 font-mono tnum focus:outline-none focus:border-accent/40 transition-colors duration-140"
        >
          {targets.map((t) => (
            <option key={t} value={t}>
              {t === 'ALL' ? '全体智能体' : t}
            </option>
          ))}
        </select>
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value as Priority)}
          className="h-8 px-2 rounded bg-surface-2 border border-hairline text-xs text-fg-1 font-mono uppercase tracking-[0.06em] focus:outline-none focus:border-accent/40 transition-colors duration-140"
        >
          {priorities.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </div>

      <div className="border-b border-hairline shrink-0">
        <button
          type="button"
          onClick={() => setQuickOpen((v) => !v)}
          className="w-full px-4 h-8 flex items-center justify-between text-fg-3 hover:text-fg-1 transition-colors duration-140"
        >
          <span className="font-mono text-2xs uppercase tracking-[0.08em]">Quick Actions</span>
          <CaretDown
            size={11}
            weight="bold"
            className={cn(
              'transition-transform duration-240 ease-spring',
              !quickOpen && '-rotate-90',
            )}
          />
        </button>
        {quickOpen && (
          <div className="px-4 pb-3 pt-1 flex flex-wrap gap-1.5">
            {quickCmds.map((q) => (
              <Button key={q.cmd} onClick={() => send(q.cmd)}>
                {q.label}
              </Button>
            ))}
            {dangerCmds.map((q) => (
              <Button
                key={q.cmd}
                variant="danger"
                onClick={() => handleDanger(q)}
                className={cn(confirming === q.cmd && 'animate-pulse')}
              >
                {confirming === q.cmd ? `确认 ${q.label}?` : q.label}
              </Button>
            ))}
          </div>
        )}
      </div>

      <div ref={streamRef} className="flex-1 min-h-0 overflow-auto px-4 py-3 space-y-1.5">
        <AnimatePresence initial={false}>
          {history.map((c) => (
            <motion.div
              key={c.id}
              layout
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.24, ease: [0.32, 0.72, 0, 1] }}
              className="flex items-baseline gap-2 group"
            >
              <span className="font-mono text-2xs text-fg-4 tnum shrink-0 w-[60px]">
                {fmtTime(c.timestamp)}
              </span>
              <span className="shrink-0 translate-y-px">
                <DirectionIcon direction={c.direction} />
              </span>
              <span
                className={cn(
                  'font-mono text-2xs uppercase tracking-[0.06em] tnum w-[60px] shrink-0',
                  c.direction === 'out' && 'text-accent',
                  c.direction === 'ack' && 'text-ok',
                  c.direction === 'warn' && 'text-warn',
                  c.direction === 'reject' && 'text-danger',
                  c.direction === 'system' && 'text-fg-3',
                )}
              >
                {c.target}
              </span>
              <span className="text-xs text-fg-2 truncate">{c.text}</span>
              {c.latencyMs !== undefined && (
                <span className="font-mono text-2xs text-fg-4 tnum ml-auto shrink-0">
                  {c.latencyMs}ms
                </span>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      <div className="px-4 py-3 border-t border-hairline flex gap-2 shrink-0">
        <Input
          placeholder="输入指令,Enter 发送,↑↓ 历史..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKey}
          className="font-mono"
        />
        <Button variant="primary" size="md" onClick={() => send(text)}>
          发送
        </Button>
      </div>
    </Panel>
  );
}
