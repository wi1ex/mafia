import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/pages/Home.vue'
import Room from '@/pages/Room.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Home },
    { path: '/room/:id', component: Room },
  ],
})
