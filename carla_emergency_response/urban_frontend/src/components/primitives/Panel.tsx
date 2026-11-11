import { motion } from 'framer-motion';
import { CaretDown } from '@phosphor-icons/react';
import { useState, type ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { StatusDot } from './StatusDot';
import type { ConnectionState } from '@/types';

interface PanelProps {
  /** DOM id — required for fullscreen + keyboard shortcuts. */
  id?: string;
  tag?: string;
  title: string;
  subtitle?: string;
  state?: ConnectionState;
  collapsible?: boolean;
  defaultOpen?: boolean;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  variant?: 'default' | 'feature';
}

export function Panel({
  id,
  tag,
  title,
  subtitle,
  state,
  collapsible = false,
  defaultOpen = true,
  actions,
  children,
  className,
  bodyClassName,
  variant = 'default',
}: PanelProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <motion.section
      id={id}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.36, ease: [0.32, 0.72, 0, 1] }}
      className={cn(
        'flex flex-col rounded-lg overflow-hidden',
        'bg-surface-1 shadow-panel',
        'transition-shadow duration-240 ease-spring',
        'hover:shadow-panel-elevated',
        'fullscreen:rounded-none fullscreen:shadow-none',
        variant === 'feature' && 'bg-surface-1/80',
        className,
        // Collapsed panels should shrink to header-only, not eat remaining flex space
        !open && '!flex-none',
      )}
    >
      <header className="flex items-center justify-between gap-3 px-4 h-9 shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          {tag && (
            <span className="font-mono text-2xs uppercase text-fg-3 tracking-[0.08em] tnum">
              {tag}
            </span>
          )}
          <h2 className="text-sm font-medium text-fg-1 truncate">{title}</h2>
          {subtitle && <span className="text-2xs text-fg-3 truncate">· {subtitle}</span>}
          {state && <StatusDot state={state} className="ml-1" />}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {actions}
          {collapsible && (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-label={open ? '折叠' : '展开'}
              className={cn(
                'flex items-center justify-center size-6 rounded text-fg-3',
                'hover:bg-surface-3 hover:text-fg-1 transition-colors duration-140',
              )}
            >
              <CaretDown
                size={12}
                weight="bold"
                className={cn(
                  'transition-transform duration-240 ease-spring',
                  !open && '-rotate-90',
                )}
              />
            </button>
          )}
        </div>
      </header>

      {open && (
        <div className={cn('flex-1 min-h-0 overflow-hidden', bodyClassName)}>
          {children}
        </div>
      )}
    </motion.section>
  );
}
