import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies /api to the FastAPI backend, so the frontend fetches
// same-origin relative URLs (no CORS, no hardcoded backend host in the code).
export default defineConfig({
  plugins: [react()],
  // Recharts is pre-bundled separately by Vite; dedupe keeps a single React
  // runtime so its hooks share the app's React (avoids "invalid hook call").
  resolve: {
    dedupe: ['react', 'react-dom'],
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'recharts'],
  },
  server: {
    port: 5173,
    proxy: {
      // ws: true so the /api/ws WebSocket is proxied to FastAPI too
      '/api': { target: 'http://127.0.0.1:8000', ws: true },
    },
  },
})
