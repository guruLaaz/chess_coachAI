import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  define: {
    __VUE_PROD_DEVTOOLS__: true,
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/u': 'http://localhost:8000',
      '/analyze': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/assets': 'http://localhost:8000',
    }
  },
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  }
})
