import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import compression from 'vite-plugin-compression'

const vendorChunkRules: Array<[string, string]> = [
  ['/node_modules/vue/', 'vue-vendor'],
  ['/node_modules/@vue/', 'vue-vendor'],
  ['/node_modules/vue-router/', 'vue-vendor'],
  ['/node_modules/pinia/', 'vue-vendor'],

  ['/node_modules/axios/', 'http-vendor'],
  ['/node_modules/follow-redirects/', 'http-vendor'],
  ['/node_modules/form-data/', 'http-vendor'],
  ['/node_modules/proxy-from-env/', 'http-vendor'],

  ['/node_modules/socket.io-client/', 'socket-vendor'],
  ['/node_modules/socket.io-parser/', 'socket-vendor'],
  ['/node_modules/engine.io-client/', 'socket-vendor'],
  ['/node_modules/engine.io-parser/', 'socket-vendor'],
  ['/node_modules/@socket.io/', 'socket-vendor'],
  ['/node_modules/debug/', 'socket-vendor'],
  ['/node_modules/ms/', 'socket-vendor'],
  ['/node_modules/ws/', 'socket-vendor'],
  ['/node_modules/xmlhttprequest-ssl/', 'socket-vendor'],

  ['/node_modules/livekit-client/', 'rtc-vendor'],
  ['/node_modules/@livekit/', 'rtc-vendor'],
  ['/node_modules/@bufbuild/', 'rtc-vendor'],
  ['/node_modules/events/', 'rtc-vendor'],
  ['/node_modules/jose/', 'rtc-vendor'],
  ['/node_modules/loglevel/', 'rtc-vendor'],
  ['/node_modules/sdp-transform/', 'rtc-vendor'],
  ['/node_modules/tslib/', 'rtc-vendor'],
  ['/node_modules/typed-emitter/', 'rtc-vendor'],
  ['/node_modules/webrtc-adapter/', 'rtc-vendor'],
]

function vendorChunkFor(id: string): string | undefined {
  return vendorChunkRules.find(([needle]) => id.includes(needle))?.[1]
}

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
          return vendorChunkFor(normalized)
        },
      },
    },
  },
})
