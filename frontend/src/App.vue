<template>
  <Header v-if="!isRoom" />
  <div class="rotate-overlay">
    <div class="rotate-box" data-nosnippet>Поверните устройство</div>
  </div>
  <router-view />
  <Confirms />
  <Toast />
</template>

<script setup lang="ts">
import { onMounted, watchEffect, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store'
import { useUserStore } from '@/store'
import { useNotifStore } from '@/store'
import { useSettingsStore } from '@/store'
import Header from '@/components/Header.vue'
import Toast from '@/components/Toasts.vue'
import Confirms from '@/components/Confirms.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const user = useUserStore()
const settings = useSettingsStore()

const isRoom = computed(() => route.name === 'room')

watchEffect(() => {
  if (route.meta?.requiresAuth && !auth.isAuthed) {
    router.replace({ name: 'home' }).catch(() => {})
  }
})

onMounted(async () => {
  settings.ensureWS()
  try { await settings.fetchPublic() } catch {}
  await auth.init()
  if (auth.isAuthed) {
    try { await user.fetchMe() } catch {}
    const notif = useNotifStore()
    notif.ensureWS()
    try { await notif.fetchAll() } catch {}
  }
})
</script>

<style lang="scss" scoped>
.rotate-overlay {
  display: none;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($black, 0.75);
  backdrop-filter: blur(5px);
  text-align: center;
  color: $fg;
  z-index: 9999;
}
.rotate-box {
  max-width: 600px;
}
@media (orientation: portrait) {
  .rotate-overlay {
    display: flex;
  }
}
</style>
