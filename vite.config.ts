import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import svgr from 'vite-plugin-svgr';
import path from 'path';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  optimizeDeps: {
    exclude: ['format', 'editor.all'],
    include: ['monaco-editor/editor/editor.api'],
    force: true,
  },
  plugins: [
    react(),
    svgr(),
    tailwindcss(),
  ],
  resolve: {
    alias: [
      { find: '@', replacement: path.resolve(__dirname, './src') },
      { find: 'shared', replacement: path.resolve(__dirname, './shared') },
      { find: 'worker', replacement: path.resolve(__dirname, './worker') },
    ],
  },
  define: {
    'process.env.NODE_ENV': JSON.stringify(
      process.env.NODE_ENV || 'development',
    ),
  },
  server: {
    allowedHosts: true,
  },
  cacheDir: 'node_modules/.vite',
});
