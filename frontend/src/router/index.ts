import { createRouter, createWebHistory, type RouteRecordRaw, type RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/store'

const BASE_TITLE = 'Deceit'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/pages/Home.vue'),
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/pages/Profile.vue'),
    meta: { requiresAuth: true, title: 'Профиль' },
  },
  {
    path: '/room/:id(\\d+)',
    name: 'room',
    component: () => import('@/pages/Room.vue'),
    meta: { requiresAuth: true, title: 'Комната' },
  },
  { path: '/:pathMatch(.*)*', redirect: { name: 'home' } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

function setTitle(to: RouteLocationNormalized): void {
  const t = (to.meta?.title as string | undefined) ?? ''
  const id = to.name === 'room' ? String(to.params.id ?? '') : ''
  document.title = t ? `${t}${id ? ` #${id}` : ''}` : BASE_TITLE
}

router.beforeEach(async (to) => {
  if (!to.meta?.requiresAuth) return true

  const auth = useAuthStore()
  if (!auth.ready) await auth.init()
  if (!auth.isAuthed) return { name: 'home' }

  if (to.name === 'room') {
    const id = Number(to.params.id)
    if (!Number.isFinite(id) || id <= 0) return { name: 'home' }
  }
  return true
})

router.afterEach((to) => setTitle(to))

router.onError((err) => {
  const msg = String(err?.message || '')
  if (/Loading chunk \d+ failed|ChunkLoadError|Failed to fetch dynamically imported module/.test(msg)) {
    location.reload()
    return
  }
  router.replace({ name: 'home' }).catch(() => {})
})

export default router
