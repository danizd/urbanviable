import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './',
  envPrefix: ['VITE_', 'REACT_APP_'],
  build: {
    outDir: 'build',
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/tiles': {
        target: 'http://127.0.0.1:8080/data',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/tiles/, ''),
      },
      '/api/status': {
        target: 'http://127.0.0.1:8081',
        changeOrigin: true,
        rewrite: () => '/last_update.json',
      },
    },
  },
});