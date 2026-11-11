import { useMemo, useState } from 'react';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { ShortcutHint } from '@/components/layout/ShortcutHint';
import { AerialFeed } from '@/components/feeds/AerialFeed';
import { GroundFeed } from '@/components/feeds/GroundFeed';
import { CityBirdView } from '@/components/feeds/CityBirdView';
import { FleetStatus } from '@/components/system/FleetStatus';
import { Telemetry } from '@/components/system/Telemetry';
import { EventLog } from '@/components/system/EventLog';
import { AgentInstructions } from '@/components/system/AgentInstructions';
import { ErrorBoundary } from '@/components/system/ErrorBoundary';
import { useBridge } from '@/hooks/useBridge';
import { useFullscreen } from '@/hooks/useFullscreen';
import { useKeyboardShortcuts, type Shortcut } from '@/hooks/useKeyboardShortcuts';

export default function App() {
  useBridge();
  const { toggle, exit, activeId } = useFullscreen();
  const [hintOpen, setHintOpen] = useState(false);

  const shortcuts = useMemo<Shortcut[]>(
    () => [
      {
        combo: '1',
        description: '全屏无人机视角',
        handler: () => toggle('panel-aerial'),
      },
      {
        combo: '2',
        description: '全屏无人车视角',
        handler: () => toggle('panel-ground'),
      },
      {
        combo: '3',
        description: '全屏 3D 鸟瞰图',
        handler: () => toggle('panel-city'),
      },
      {
        combo: 'Esc',
        description: '退出全屏 / 关闭面板',
        handler: () => {
          if (hintOpen) {
            setHintOpen(false);
            return;
          }
          if (activeId) exit();
        },
      },
      {
        combo: 'Ctrl+/',
        description: '聚焦指令输入框',
        handler: () => {
          const input = document.querySelector<HTMLInputElement>(
            '#panel-command input[type="text"]',
          );
          input?.focus();
        },
      },
      {
        combo: 'Shift+/',
        description: '快捷键面板',
        handler: () => setHintOpen((v) => !v),
      },
    ],
    [toggle, exit, activeId, hintOpen],
  );

  useKeyboardShortcuts(shortcuts);

  return (
    <ErrorBoundary>
      <div className="h-screen w-screen flex flex-col bg-canvas bg-grain">
        <Header onShowShortcuts={() => setHintOpen(true)} />
        <main
          className="flex-1 min-h-0 grid gap-2 p-2"
          style={{ gridTemplateColumns: '22% 1fr 22%' }}
        >
          <section className="flex flex-col gap-2 min-h-0">
            <AerialFeed />
            <GroundFeed />
          </section>

          <section className="min-h-0 flex flex-col gap-2">
            <CityBirdView />
          </section>

          <section className="flex flex-col gap-2 min-h-0">
            <FleetStatus />
            <Telemetry />
            <AgentInstructions />
            <EventLog />
          </section>
        </main>
        <Footer />
        <ShortcutHint open={hintOpen} onClose={() => setHintOpen(false)} />
      </div>
    </ErrorBoundary>
  );
}
