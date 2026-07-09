import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite 配置:开发时将 /api 代理到后端 FastAPI
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
