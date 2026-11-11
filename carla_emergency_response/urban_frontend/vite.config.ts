import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const bridgeUrl = env.VITE_BRIDGE_URL || 'http://localhost:5000';

  return {
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': { target: bridgeUrl, changeOrigin: true },
      '/video_feed': { target: bridgeUrl, changeOrigin: true },
      '/scenario': { target: bridgeUrl, changeOrigin: true },
      '/webrtc': { target: bridgeUrl, changeOrigin: true },
      '/socket.io': { target: bridgeUrl, changeOrigin: true, ws: true },
    },
  },
  build: {
    target: 'es2022',
    sourcemap: false,
    cssCodeSplit: true,
    reportCompressedSize: false,
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom'],
          motion: ['framer-motion'],
          icons: ['@phosphor-icons/react'],
          net: ['socket.io-client'],
          state: ['zustand'],
        },
      },
    },
  },
  };
});
