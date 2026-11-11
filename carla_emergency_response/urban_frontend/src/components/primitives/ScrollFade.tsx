import { cn } from '@/lib/cn';

interface Props {
  top?: boolean;
  bottom?: boolean;
  className?: string;
}

/**
 * Tiny edge indicators that hint at hidden scroll content without
 * ever covering it. Two thin (4px) shadow strips positioned below
 * and above the scroll container — they don't sit on top of any row,
 * so the last/first row is always pixel-perfect.
 *
 * Render outside the scroll container, inside a flex parent.
 */
export function ScrollFade({ top, bottom, className }: Props) {
  return (
    <>
      {top && (
        <div
          className={cn(
            'pointer-events-none absolute left-0 right-0 top-0 h-1',
            'bg-gradient-to-b from-black/10 to-transparent',
            className,
          )}
        />
      )}
      {bottom && (
        <div
          className={cn(
            'pointer-events-none absolute left-0 right-0 bottom-0 h-1',
            'bg-gradient-to-t from-black/10 to-transparent',
            className,
          )}
        />
      )}
    </>
  );
}
