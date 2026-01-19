import { createRouter, createWebHistory, type RouteRecordRaw, type RouteLocationNormalized } from 'vue-router'
import { useAuthStore, useUserStore } from '@/store'

const BASE_TITLE = 'Deceit'
const BASE_DESCRIPTION = 'Играйте в мафию онлайн бесплатно, общайтесь в комнатах с трансляциями'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/pages/Home.vue'),
  },
  {
    path: '/rules',
    name: 'rules',
    component: () => import('@/pages/Rules.vue'),
    meta: { title: 'Правила', robots: 'noindex, nofollow' },
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/pages/Profile.vue'),
    meta: { requiresAuth: true, title: 'Профиль', robots: 'noindex, nofollow' },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/pages/Admin.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Админ-панель', robots: 'noindex, nofollow' },
  },
  {
    path: '/room/:id(\\d+)',
    name: 'room',
    component: () => import('@/pages/Room.vue'),
    meta: { requiresAuth: true, title: 'Комната', robots: 'noindex, nofollow' },
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

function ensureMeta(name: string, content: string): void {
  let el = document.querySelector(`meta[name="${name}"]`) as HTMLMetaElement | null
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute('name', name)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

function ensureCanonical(href: string): void {
  let el = document.querySelector('link[rel="canonical"]') as HTMLLinkElement | null
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', 'canonical')
    document.head.appendChild(el)
  }
  el.setAttribute('href', href)
}

function setMeta(to: RouteLocationNormalized): void {
  const description = (to.meta?.description as string | undefined) ?? BASE_DESCRIPTION
  const robots = (to.meta?.robots as string | undefined) ?? 'index, follow'
  ensureMeta('description', description)
  ensureMeta('robots', robots)
  const base = window.location?.origin || ''
  ensureCanonical(base ? `${base}${to.path}` : to.path)
}

router.beforeEach(async (to) => {
  if (!to.meta?.requiresAuth) return true

  const auth = useAuthStore()
  if (!auth.ready) await auth.init()
  if (!auth.isAuthed) return { name: 'home' }

  if (to.meta?.requiresAdmin) {
    const user = useUserStore()
    if (!user.user) {
      try { await user.fetchMe() } catch {}
    }
    if (user.user?.role !== 'admin') return { name: 'home' }
  }

  if (to.name === 'room') {
    const id = Number(to.params.id)
    if (!Number.isFinite(id) || id <= 0) return { name: 'home' }
  }
  return true
})

router.afterEach((to) => {
  setTitle(to)
  setMeta(to)
})

router.onError((err) => {
  const msg = String(err?.message || '')
  if (/Loading chunk \d+ failed|ChunkLoadError|Failed to fetch dynamically imported module/.test(msg)) {
    location.reload()
    return
  }
  router.replace({ name: 'home' }).catch(() => {})
})

export default router
