import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/store'

const BASE_TITLE = 'Mafia'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/pages/Home.vue'),
    meta: { title: BASE_TITLE },
  },
  {
    path: '/room/:id(\\d+)',
    name: 'room',
    component: () => import('@/pages/Room.vue'),
    meta: { requiresAuth: true, title: 'Комната' },
    props: (route) => ({ id: Number(route.params.id) }),
  },
  { path: '/:pathMatch(.*)*', redirect: { name: 'home' } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

function setTitle(to: any): void {
  const t = to.meta?.title as string | undefined
  const id = to.name === 'room' ? String(to.params.id ?? '') : ''
  document.title = t ? `${t}${id ? ` #${id}` : ''} — ${BASE_TITLE}` : BASE_TITLE
}

router.beforeEach(async (to) => {
  if (!to.meta?.requiresAuth) return true

  const id = Number(to.params.id)
  if (!Number.isFinite(id) || id <= 0) return { name: 'home' }

  const auth = useAuthStore()
  if (!auth.ready) await auth.init()

  return auth.isAuthed ? true : { name: 'home' }
})

router.afterEach((to) => setTitle(to))

router.onError((err) => {
  console.error('[router]', err)
  router.replace({ name: 'home' }).catch(() => {})
})

export default router
