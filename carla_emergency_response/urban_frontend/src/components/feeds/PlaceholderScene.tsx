import { cn } from '@/lib/cn';

interface Props {
  variant?: 'aerial' | 'ground' | 'city';
  label?: string;
  className?: string;
}

export function PlaceholderScene({ variant = 'aerial', label, className }: Props) {
  return (
    <div className={cn('relative w-full h-full overflow-hidden bg-canvas', className)}>
      <svg
        viewBox="0 0 800 450"
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 w-full h-full"
      >
        <defs>
          <linearGradient id={`grad-${variant}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(248 245 238)" />
            <stop offset="60%" stopColor="rgb(242 239 232)" />
            <stop offset="100%" stopColor="rgb(237 233 224)" />
          </linearGradient>
          <pattern id={`grid-${variant}`} width="32" height="32" patternUnits="userSpaceOnUse">
            <path
              d="M 32 0 L 0 0 0 32"
              fill="none"
              stroke="rgb(0 0 0 / 0.06)"
              strokeWidth="1"
            />
          </pattern>
        </defs>
        <rect width="800" height="450" fill={`url(#grad-${variant})`} />
        <rect width="800" height="450" fill={`url(#grid-${variant})`} />

        {/* Isometric city silhouette — hairline */}
        <g
          transform="translate(120 120)"
          stroke="rgb(0 0 0 / 0.22)"
          strokeWidth="0.8"
          fill="none"
          strokeLinejoin="round"
        >
          <path d="M40 240 L40 140 L120 100 L120 200 Z" />
          <path d="M120 200 L120 100 L200 60 L200 160 Z" />
          <path d="M200 160 L200 60 L280 100 L280 200 Z" />
          <path d="M280 200 L280 100 L360 140 L360 240 Z" />
          <path d="M360 240 L360 140 L440 100 L440 200 Z" />
          <path d="M440 200 L440 100 L520 60 L520 160 Z" />
          <path d="M520 160 L520 60 L600 100 L600 200 Z" />
          {/* Ground plane */}
          <path d="M0 240 L640 240" />
          <path d="M0 250 L640 250" opacity="0.4" />
        </g>

        {/* Single moving sweep line */}
        <line
          x1="0"
          x2="800"
          y1="225"
          y2="225"
          stroke="rgb(142 122 92 / 0.30)"
          strokeWidth="1"
          strokeDasharray="2 6"
        >
          <animate
            attributeName="y1"
            values="100;360;100"
            dur="9s"
            repeatCount="indefinite"
          />
          <animate
            attributeName="y2"
            values="100;360;100"
            dur="9s"
            repeatCount="indefinite"
          />
        </line>
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-2xs uppercase tracking-[0.24em] text-fg-3">
          AWAITING FEED
        </span>
        {label && (
          <span className="mt-1 font-mono text-2xs tnum text-fg-4">· {label} ·</span>
        )}
      </div>
    </div>
  );
}
