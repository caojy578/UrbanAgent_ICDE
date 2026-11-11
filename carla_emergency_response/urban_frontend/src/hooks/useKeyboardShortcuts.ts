import { useEffect } from 'react';

export interface Shortcut {
  /** Key combo, e.g. "1", "Esc", "Ctrl+/", "Space". */
  combo: string;
  description: string;
  handler: (e: KeyboardEvent) => void;
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return (
    tag === 'INPUT' ||
    tag === 'TEXTAREA' ||
    tag === 'SELECT' ||
    target.isContentEditable
  );
}

function matches(combo: string, e: KeyboardEvent): boolean {
  const parts = combo.split('+').map((p) => p.trim().toLowerCase());
  const key = parts.pop();
  const wantCtrl = parts.includes('ctrl');
  const wantShift = parts.includes('shift');
  const wantAlt = parts.includes('alt');
  const wantMeta = parts.includes('meta') || parts.includes('cmd');

  const actual = e.key.toLowerCase();
  const norm = actual === ' ' ? 'space' : actual === 'escape' ? 'esc' : actual;

  return (
    key === norm &&
    e.ctrlKey === wantCtrl &&
    e.shiftKey === wantShift &&
    e.altKey === wantAlt &&
    e.metaKey === wantMeta
  );
}

export function useKeyboardShortcuts(shortcuts: Shortcut[]) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // allow Esc and Ctrl+/ even while typing
      const allowWhileTyping = ['esc', 'ctrl+/'];
      const isTyping = isTypingTarget(e.target);

      for (const s of shortcuts) {
        const lower = s.combo.toLowerCase();
        if (isTyping && !allowWhileTyping.includes(lower)) continue;
        if (matches(s.combo, e)) {
          e.preventDefault();
          s.handler(e);
          return;
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [shortcuts]);
}
