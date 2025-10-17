import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import minioImg from './services/minioImg'
import './styles/main.scss'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.directive('minio-img', minioImg)

// const BUILD = import.meta.env.VITE_BUILD_ID as string || ''
// async function pollVersion() {
//   try {
//     const r = await fetch('/version.txt', { cache: 'no-store' })
//     const v = (await r.text()).trim()
//     if (v && v !== BUILD) location.reload()
//   } catch {}
// }
// void pollVersion()
// setInterval(pollVersion, 60_000)
// document.addEventListener('visibilitychange', () => { if (!document.hidden) pollVersion() })
// window.addEventListener('online', () => { pollVersion() })
// router.onError((err: unknown) => {
//   const msg = String((err as any)?.message || '')
//   if (/ChunkLoadError|Loading chunk \d+ failed|Failed to fetch dynamically imported module/i.test(msg)) {
//     location.reload()
//   }
// })

app.mount('#app')
