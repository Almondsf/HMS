import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    // Open http://<hospital>.localhost:5173 (e.g. main.localhost); *.localhost is allowed by default.
    // Bind IPv4 explicitly: on Windows "localhost" can mean IPv6 only, while browsers send
    // *.localhost to 127.0.0.1, so the page would fail to load.
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
})
