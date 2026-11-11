import { emitCommand } from './socket';
import { useCommandStore } from '@/store/useCommandStore';
import { useSystemStore } from '@/store/useSystemStore';
import type { Priority } from '@/types';

export function dispatchCommand(text: string, target: string, priority: Priority) {
  const record = useCommandStore.getState().send(text, target, priority);
  const sys = useSystemStore.getState();
  const ok = emitCommand({ id: record.id, target, priority, text });

  if (!ok) {
    // Mock mode: synthesize an ack after a small delay so UI flows feel real.
    const fake = 180 + Math.round(Math.random() * 140);
    setTimeout(() => {
      useCommandStore.getState().ack(record.id, fake, target === 'ALL' ? 'UAV-01' : target);
    }, fake);
    if (sys.source !== 'mock') {
      sys.pushEvent({
        severity: 'warn',
        source: 'BRIDGE',
        message: '后端未连接 · 指令以模拟模式回放',
      });
    }
  }
  return record;
}
