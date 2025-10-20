<template>
  <Header v-if="!isRoom" />
  <div class="rotate-overlay">
    <div class="rotate-box">Поверните устройство в горизонтальную ориентацию</div>
  </div>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted, watchEffect, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store'
import { useUserStore } from '@/store'
import Header from '@/components/Header.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const user = useUserStore()

const isRoom = computed(() => route.name === 'room')

watchEffect(() => {
  if (route.meta?.requiresAuth && !auth.isAuthed) {
    router.replace({ name: 'home' }).catch(() => {})
  }
})

onMounted(async () => {
  await auth.init()
  if (auth.isAuthed) { try { await user.fetchMe() } catch {} }
})
</script>


<style lang="scss" scoped>
.rotate-overlay {
  display: none;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: $black;
  text-align: center;
  color: $white;
  z-index: 9999;
  padding: calc(env(safe-area-inset-top, 0px) + 16px)
           calc(env(safe-area-inset-right, 0px) + 16px)
           calc(env(safe-area-inset-bottom, 0px) + 16px)
           calc(env(safe-area-inset-left, 0px) + 16px);
}
.rotate-box {
  max-width: 420px;
}
@media (orientation: portrait) {
  .rotate-overlay {
    display: flex;
  }
}
</style>