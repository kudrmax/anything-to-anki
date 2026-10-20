/// <reference types="vitest/config" />
import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import type { IncomingMessage } from 'http'

const BACKEND = 'http://localhost:17833'
/** Префиксы API backend: всё, что web запрашивает у сервера. */
const BACKEND_PREFIXES = [
  '/api', '/sources', '/collections', '/phrases', '/words', '/known-words', '/unknown-words',
  '/vocabulary', '/export', '/anki', '/stats', '/media',
]

export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom' },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: Object.fromEntries(BACKEND_PREFIXES.map(prefix => [prefix, {
      target: BACKEND,
      // Переход браузера на страницу (/sources/7/review, /export?scope=…) остаётся SPA.
      bypass: (req: IncomingMessage) => (req.headers.accept?.includes('text/html') ? '/index.html' : undefined),
    }])),
  },
})
