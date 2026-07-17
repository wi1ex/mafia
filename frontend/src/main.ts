import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import minioImg from './services/minioImg'
import { installPwaTracking } from './services/pwa'
import { installVersionWatcher } from './services/version'
import './styles/main.scss'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.directive('minio-img', minioImg)
installPwaTracking()
installVersionWatcher(import.meta.env.VITE_BUILD_ID as string || '')

app.mount('#app')

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).catch(() => {})
  })
}
