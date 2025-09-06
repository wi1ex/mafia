import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/pages/Home.vue'
import Room from '@/pages/Room.vue'
import { useAuthStore } from '@/store'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Home, meta: { title: 'Mafia' } },
    { path: '/room/:id(\\d+)', component: Room, meta: { requiresAuth: true, title: 'Комната' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior(){ return { top: 0 } }
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  // если нужен доступ — должен быть токен
  if (to.meta.requiresAuth && !auth.accessToken) {
    return { path: '/' }
  }
  return true
})

export default router
