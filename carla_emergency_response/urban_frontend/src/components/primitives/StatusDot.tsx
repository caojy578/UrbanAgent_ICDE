import { cn } from '@/lib/cn';
import type { ConnectionState } from '@/types';

interface Props {
  state: ConnectionState;
  className?: string;
}

const colorMap: Record<ConnectionState, string> = {
  live: 'bg-ok shadow-[0_0_0_3px_rgb(96_122_88_/_0.22)]',
  reconnecting: 'bg-warn shadow-[0_0_0_3px_rgb(168_130_70_/_0.22)] animate-breathe',
  offline: 'bg-fg-4',
};

export function StatusDot({ state, className }: Props) {
  return (
    <span
      className={cn(
        'inline-block size-1.5 rounded-full transition-colors duration-240 ease-spring',
        colorMap[state],
        state === 'live' && 'animate-breathe',
        className,
      )}
    />
  );
}
