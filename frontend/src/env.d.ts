/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TG_BOT_NAME: string
  readonly VITE_BUILD_ID: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module '@livekit/throws-transformer/throws' {
  export type Throws<T, _E = never> = T
}

declare module 'sdp-transform' {
  export type MediaAttributes = Record<string, any>
}
