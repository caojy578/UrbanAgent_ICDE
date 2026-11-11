import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: 'rgb(var(--bg-canvas) / <alpha-value>)',
        surface: {
          1: 'rgb(var(--bg-surface-1) / <alpha-value>)',
          2: 'rgb(var(--bg-surface-2) / <alpha-value>)',
          3: 'rgb(var(--bg-surface-3) / <alpha-value>)',
        },
        fg: {
          1: 'rgb(var(--fg-1) / <alpha-value>)',
          2: 'rgb(var(--fg-2) / <alpha-value>)',
          3: 'rgb(var(--fg-3) / <alpha-value>)',
          4: 'rgb(var(--fg-4) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'rgb(var(--accent) / <alpha-value>)',
          soft: 'rgb(var(--accent) / 0.10)',
        },
        ok: 'rgb(var(--state-ok) / <alpha-value>)',
        warn: 'rgb(var(--state-warn) / <alpha-value>)',
        danger: 'rgb(var(--state-danger) / <alpha-value>)',
        hairline: 'rgb(0 0 0 / 0.08)',
      },
      fontFamily: {
        sans: [
          'Inter',
          '"Source Han Sans SC"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          'system-ui',
          'sans-serif',
        ],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        '2xs': ['11px', { lineHeight: '1.4', letterSpacing: '0.04em' }],
        xs: ['12px', { lineHeight: '1.5' }],
        sm: ['13px', { lineHeight: '1.5' }],
        base: ['16px', { lineHeight: '1.5' }],
        lg: ['24px', { lineHeight: '1.2', letterSpacing: '-0.01em' }],
        xl: ['32px', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
        '2xl': ['48px', { lineHeight: '1', letterSpacing: '-0.03em' }],
      },
      spacing: {
        '0.5': '2px',
        1: '4px',
        2: '8px',
        3: '12px',
        4: '16px',
        5: '20px',
        6: '24px',
        8: '32px',
        12: '48px',
        16: '64px',
      },
      borderRadius: {
        none: '0',
        sm: '4px',
        DEFAULT: '6px',
        md: '8px',
        lg: '10px',
        xl: '14px',
        full: '9999px',
      },
      boxShadow: {
        panel:
          '0 0 0 1px rgb(0 0 0 / 0.06), 0 1px 2px rgb(0 0 0 / 0.04), 0 8px 24px -6px rgb(0 0 0 / 0.06)',
        'panel-elevated':
          '0 0 0 1px rgb(0 0 0 / 0.08), 0 2px 4px rgb(0 0 0 / 0.05), 0 16px 40px -8px rgb(0 0 0 / 0.10)',
        ring: '0 0 0 1px rgb(var(--accent) / 0.55), 0 0 0 4px rgb(var(--accent) / 0.16)',
      },
      transitionTimingFunction: {
        spring: 'cubic-bezier(0.32, 0.72, 0, 1)',
      },
      transitionDuration: {
        140: '140ms',
        240: '240ms',
        360: '360ms',
      },
      keyframes: {
        breathe: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.55' },
        },
        sweep: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        riseIn: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        breathe: 'breathe 2.4s ease-in-out infinite',
        sweep: 'sweep 1.6s linear infinite',
        riseIn: 'riseIn 360ms cubic-bezier(0.32, 0.72, 0, 1) both',
      },
    },
  },
  plugins: [],
} satisfies Config;
