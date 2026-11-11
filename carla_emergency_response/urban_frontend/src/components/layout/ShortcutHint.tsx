import { motion, AnimatePresence } from 'framer-motion';
import { Keyboard, X } from '@phosphor-icons/react';
import { cn } from '@/lib/cn';

interface ShortcutItem {
  combo: string[];
  description: string;
}

const items: ShortcutItem[] = [
  { combo: ['1'], description: '全屏 · 无人机视角' },
  { combo: ['2'], description: '全屏 · 无人车视角' },
  { combo: ['3'], description: '全屏 · 3D 鸟瞰图' },
  { combo: ['Esc'], description: '退出全屏 / 取消' },
  { combo: ['Ctrl', '/'], description: '聚焦指令输入框' },
  { combo: ['↑', '↓'], description: '指令历史' },
  { combo: ['?'], description: '显示 / 隐藏快捷键面板' },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export function ShortcutHint({ open, onClose }: Props) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex items-center justify-center bg-canvas/70 backdrop-blur-sm"
        >
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.24, ease: [0.32, 0.72, 0, 1] }}
            onClick={(e) => e.stopPropagation()}
            className="w-[420px] rounded-lg bg-surface-1 shadow-panel-elevated p-5"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Keyboard size={14} weight="duotone" className="text-accent" />
                <span className="font-mono text-2xs uppercase tracking-[0.16em] text-fg-2">
                  键盘快捷键
                </span>
              </div>
              <button
                onClick={onClose}
                className="size-6 inline-flex items-center justify-center text-fg-3 hover:text-fg-1 hover:bg-surface-2 rounded transition-colors duration-140"
              >
                <X size={12} />
              </button>
            </div>
            <div className="space-y-2">
              {items.map((it) => (
                <div
                  key={it.description}
                  className="flex items-center justify-between gap-4 px-2 py-1.5 rounded hover:bg-surface-2 transition-colors duration-140"
                >
                  <span className="text-xs text-fg-2">{it.description}</span>
                  <div className="flex items-center gap-1">
                    {it.combo.map((k, i) => (
                      <Kbd key={i}>{k}</Kbd>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex items-center justify-center min-w-[20px] h-6 px-1.5 rounded',
        'bg-surface-3 border border-hairline shadow-[inset_0_-1px_0_rgb(0_0_0_/_0.4)]',
        'font-mono text-2xs text-fg-1',
      )}
    >
      {children}
    </span>
  );
}

