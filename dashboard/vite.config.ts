import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // File-change events don't cross Docker bind mounts on Windows/macOS,
    // so the container enables polling via VITE_USE_POLLING=true.
    watch: { usePolling: process.env.VITE_USE_POLLING === 'true' },
  },
})
