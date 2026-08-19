import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '')
  const apiTarget = env.VITE_API_TARGET || 'http://127.0.0.1:8000'

  return {
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/pdfjs-dist')) return 'vendor-pdf'
          if (
            id.includes('node_modules/markdown-it') ||
            id.includes('node_modules/markdown-it-katex') ||
            id.includes('node_modules/katex') ||
            id.includes('node_modules/highlight.js') ||
            id.includes('node_modules/dompurify')
          ) {
            return 'vendor-markdown'
          }
        },
      },
    },
  },
  }
})
