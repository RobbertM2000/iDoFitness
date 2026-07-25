import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies /api to Flask (port 5000) so cookies work
// without CORS issues during local development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
})
