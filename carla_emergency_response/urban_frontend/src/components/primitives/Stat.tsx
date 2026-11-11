import { motion } from 'framer-motion';
import { cn } from '@/lib/cn';
import type { ReactNode } from 'react';

interface Props {
  label: string;
  value: ReactNode;
  unit?: string;
  hint?: ReactNode;
  align?: 'left' | 'right';
  size?: 'sm' | 'md' | 'lg';
  tone?: 'default' | 'ok' | 'warn' | 'danger' | 'accent';
  className?: string;
}

const sizeMap = {
  sm: { v: 'text-sm', l: 'text-2xs' },
  md: { v: 'text-base', l: 'text-2xs' },
  lg: { v: 'text-lg', l: 'text-2xs' },
};

const toneMap = {
  default: 'text-fg-1',
  ok: 'text-ok',
  warn: 'text-warn',
  danger: 'text-danger',
  accent: 'text-accent',
};

export function Stat({
  label,
  value,
  unit,
  hint,
  align = 'left',
  size = 'md',
  tone = 'default',
  className,
}: Props) {
  return (
    <div className={cn('flex flex-col', align === 'right' && 'items-end', className)}>
      <span className="font-mono text-2xs uppercase tracking-[0.08em] text-fg-3">{label}</span>
      <div className="flex items-baseline gap-1 mt-0.5">
        <motion.span
          key={String(value)}
          initial={{ opacity: 0.4, y: -2 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.24, ease: [0.32, 0.72, 0, 1] }}
          className={cn(
            'font-mono font-medium tnum tracking-tight',
            sizeMap[size].v,
            toneMap[tone],
          )}
        >
          {value}
        </motion.span>
        {unit && (
          <span className="font-mono text-2xs text-fg-3 tnum">{unit}</span>
        )}
      </div>
      {hint && <span className="text-2xs text-fg-3 mt-0.5">{hint}</span>}
    </div>
  );
}
