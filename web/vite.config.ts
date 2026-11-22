import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  base: '/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  build: {
    outDir: '../public',
    emptyOutDir: true,
    // Nothing becomes a data: URI; the CSP would block it.
    assetsInlineLimit: 0,
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
