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
body {
  margin: 0;
  background-color: $bg;
  color: $fg;
  font-family: 'Manrope-Medium';
  user-select: none;
}
#app{
  display: flex;
  flex-direction: column;
  width: 100vw;
  height: 100dvh;
}

.rotate-overlay {
  display: none;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($black, 0.8);
  backdrop-filter: blur(5px);
  text-align: center;
  color: $fg;
  z-index: 9999;
}
.rotate-box {
  max-width: 600px;
  font-size: 20px;
}
@media (orientation: portrait) {
  .rotate-overlay {
    display: flex;
  }
}
</style>