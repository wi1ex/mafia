import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/pages/Home.vue'
import Room from '@/pages/Room.vue'
import { useAuthStore } from '@/store'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: Home, meta: { title: 'Mafia' } },
    { path: '/room/:id(\\d+)', name: 'room', component: Room, meta: { requiresAuth: true, title: 'Комната' } },
    { path: '/:pathMatch(.*)*', redirect: { name: 'home' } },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach(async (to) => {
  if (!to.meta.requiresAuth) return true
  if (!/^\d+$/.test(String(to.params.id || ''))) return { name: 'home' }
  const auth = useAuthStore()
  if (!auth.ready) await auth.init()
  return auth.isAuthed ? true : { name: 'home' }
})


router.afterEach((to) => {
  const base = 'Mafia'
  const t = to.meta?.title as string | undefined
  const id = to.name === 'room' ? String(to.params.id || '') : ''
  document.title = t ? `${t}${id ? ' #' + id : ''} — ${base}` : base
})

export default router
