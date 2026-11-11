import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Warning, X } from '@phosphor-icons/react';
import { Button } from '@/components/primitives/Button';

interface Props {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'danger';
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = '确认',
  cancelLabel = '取消',
  variant = 'default',
  busy = false,
  onConfirm,
  onCancel,
}: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
      if (e.key === 'Enter') onConfirm();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onCancel, onConfirm]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={onCancel}
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
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Warning
                  size={14}
                  weight="duotone"
                  className={variant === 'danger' ? 'text-danger' : 'text-accent'}
                />
                <span className="font-mono text-2xs uppercase tracking-[0.16em] text-fg-2">
                  {title}
                </span>
              </div>
              <button
                onClick={onCancel}
                className="size-6 inline-flex items-center justify-center text-fg-3 hover:text-fg-1 hover:bg-surface-2 rounded transition-colors duration-140"
                aria-label="关闭"
              >
                <X size={12} />
              </button>
            </div>
            <p className="text-xs leading-relaxed text-fg-2 mb-5">{description}</p>
            <div className="flex items-center justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
                {cancelLabel}
              </Button>
              <Button
                variant={variant === 'danger' ? 'danger' : 'primary'}
                size="sm"
                onClick={onConfirm}
                disabled={busy}
              >
                {confirmLabel}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
