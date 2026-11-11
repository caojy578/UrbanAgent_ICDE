import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return (
      <input
        ref={ref}
        className={cn(
          'flex h-9 w-full rounded px-3',
          'bg-surface-2 text-sm text-fg-1 placeholder:text-fg-3',
          'border border-hairline',
          'transition-all duration-140 ease-spring',
          'hover:border-white/10',
          'focus:outline-none focus:border-accent/40 focus:bg-surface-1',
          'disabled:opacity-40',
          className,
        )}
        {...rest}
      />
    );
  },
);
