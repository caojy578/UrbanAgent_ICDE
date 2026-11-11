import { useEffect } from 'react';
import { connect, disconnect, getSocket } from '@/services/socket';
import { startMockBridge, stopMockBridge } from '@/services/mockBridge';
import { useSystemStore } from '@/store/useSystemStore';

const SOCKET_URL = import.meta.env.VITE_SOCKET_URL ?? '';

/**
 * Try the live backend; if it doesn't connect within `probeMs`, run mock bridge.
 * If it later connects, mock auto-stops.
 */
export function useBridge(probeMs = 1500) {
  useEffect(() => {
    let mockOn = false;

    // Empty VITE_SOCKET_URL → same-origin; dev proxy / prod nginx forwards /socket.io to the bridge.
    connect({ url: SOCKET_URL || window.location.origin });

    const probe = setTimeout(() => {
      const s = getSocket();
      if (!s || !s.connected) {
        startMockBridge();
        mockOn = true;
      }
    }, probeMs);

    const unsub = useSystemStore.subscribe((state, prev) => {
      if (state.connection === 'live' && prev.connection !== 'live' && mockOn) {
        stopMockBridge();
        mockOn = false;
      }
      if (state.connection !== 'live' && prev.connection === 'live') {
        startMockBridge();
        mockOn = true;
      }
    });

    return () => {
      clearTimeout(probe);
      unsub();
      stopMockBridge();
      disconnect();
    };
  }, [probeMs]);
}
