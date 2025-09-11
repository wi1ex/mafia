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

router.beforeEach((to) => {
  if (to.meta.requiresAuth) {
    const id = String(to.params.id || '')
    const isNumber = /^\d+$/.test(id)
    const auth = useAuthStore()
    if (!isNumber || !auth.isAuthed) return { name: 'home' }
  }
  return true
})

router.afterEach((to) => {
  const base = 'Mafia'
  const t = to.meta?.title as string | undefined
  const id = to.name === 'room' ? String(to.params.id || '') : ''
  document.title = t ? `${t}${id ? ' #' + id : ''} — ${base}` : base
})

export default router
