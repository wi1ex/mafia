/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_TG_BOT_NAME?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
