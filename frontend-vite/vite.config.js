import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';

export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      // Two entries: the cockpit window and the Alt+Space overlay window.
      input: {
        main: 'index.html',
        overlay: 'overlay.html',
      },
    },
  },
});
