import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import compression from 'vite-plugin-compression'

export default defineConfig({
  plugins: [
    vue(),
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
  build: {
    sourcemap: false,
    rolldownOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.replace(/\\/g, '/')

          if (normalized.includes('/node_modules/livekit-client/')) {
            return 'room-rtc-vendor'
          }

          if (normalized.includes('/src/composables/rtc.ts')) {
            return 'room-rtc'
          }

          if (
            normalized.includes('/src/composables/roomGame.ts')
            || normalized.includes('/src/components/RoomTile.vue')
          ) {
            return 'room-game'
          }

          if (
            normalized.includes('/src/components/RoomSetting.vue')
            || normalized.includes('/src/components/GameParamsModal.vue')
            || normalized.includes('/src/components/GameParamsForm.vue')
            || normalized.includes('/src/components/FriendsPanel.vue')
          ) {
            return 'room-panels'
          }
        },
      },
    },
  },
})
