import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

type Tone = 'neutral' | 'accent' | 'ok' | 'warn' | 'danger';

const tones: Record<Tone, string> = {
  neutral: 'bg-surface-3 text-fg-2 border-hairline',
  accent: 'bg-accent/10 text-accent border-accent/20',
  ok: 'bg-ok/10 text-ok border-ok/20',
  warn: 'bg-warn/10 text-warn border-warn/20',
  danger: 'bg-danger/10 text-danger border-danger/20',
};

export function Badge({
  children,
  tone = 'neutral',
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center h-5 px-1.5 rounded',
        'font-mono text-2xs uppercase tracking-[0.08em] tnum',
        'border',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
