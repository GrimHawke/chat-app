import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const API_SERVER_TARGET = process.env.API_SERVER_TARGET || 'localhost:5000';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: API_SERVER_TARGET,
        changeOrigin: true,
      },
    },
  }
})
