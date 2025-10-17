interface ImportMetaEnv {
  readonly VITE_TG_BOT_NAME: string
  readonly VITE_BUILD_ID: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
