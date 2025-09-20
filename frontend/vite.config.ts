import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import compression from 'vite-plugin-compression'

export default defineConfig({
  plugins: [
    vue(),
    compression({ algorithm: 'brotliCompress' }),
    compression({ algorithm: 'gzip' }),
  ],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/styles/variables" as *;`,
      },
    },
  },
  build: { sourcemap: false },
})
