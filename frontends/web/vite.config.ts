import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/sources':     'http://localhost:17833',
      '/candidates':  'http://localhost:17833',
      '/known-words': 'http://localhost:17833',
      '/settings':    'http://localhost:17833',
      '/anki':        'http://localhost:17833',
      '/stats':       'http://localhost:17833',
    },
  },
})
