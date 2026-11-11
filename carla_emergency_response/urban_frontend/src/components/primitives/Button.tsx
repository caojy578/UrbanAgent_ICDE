import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

type Variant = 'default' | 'primary' | 'ghost' | 'danger';
type Size = 'sm' | 'md';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variants: Record<Variant, string> = {
  default:
    'bg-surface-2 text-fg-1 hover:bg-surface-3 active:bg-surface-3/80 border border-hairline',
  primary:
    'bg-accent text-white hover:bg-accent/90 active:bg-accent/80 shadow-[inset_0_1px_0_0_rgb(255_255_255_/_0.18)]',
  ghost: 'bg-transparent text-fg-2 hover:bg-surface-2 hover:text-fg-1',
  danger:
    'bg-danger/10 text-danger hover:bg-danger/16 border border-danger/24 hover:border-danger/40',
};

const sizes: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-xs gap-1.5',
  md: 'h-8 px-3 text-xs gap-2',
};

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = 'default', size = 'sm', className, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center rounded',
        'font-medium tracking-tight whitespace-nowrap',
        'transition-all duration-140 ease-spring',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
});
