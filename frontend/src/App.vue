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
import { onMounted, onBeforeUnmount, watchEffect, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store'
import { useUserStore } from '@/store'
import { useNotifStore } from '@/store'
import { useSettingsStore } from '@/store'
import { alertDialog } from '@/services/confirm'
import Header from '@/components/Header.vue'
import Toast from '@/components/Toasts.vue'
import Confirms from '@/components/Confirms.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const user = useUserStore()
const settings = useSettingsStore()

let onSanctionsUpdate: ((e: any) => void) | null = null
let onSanctionAlert: ((e: any) => void) | null = null

const isRoom = computed(() => route.name === 'room')

watchEffect(() => {
  if (route.meta?.requiresAuth && !auth.isAuthed) {
    router.replace({ name: 'home' }).catch(() => {})
  }
})
watchEffect(() => {
  if (auth.isAuthed) user.ensureClock()
})

onMounted(async () => {
  settings.ensureWS()
  try { await settings.fetchPublic() } catch {}
  await auth.init()
  if (auth.isAuthed) {
    try { await user.fetchMe() } catch {}
    user.ensureClock()
    const notif = useNotifStore()
    notif.ensureWS()
    try { await notif.fetchAll() } catch {}
  }
  onSanctionsUpdate = (e: any) => {
    const p = e?.detail || {}
    user.setSanctions({
      timeout_until: p.timeout_until ?? null,
      suspend_until: p.suspend_until ?? null,
      ban_active: p.ban_active ?? false,
    })
  }
  onSanctionAlert = (e: any) => {
    const p = e?.detail || {}
    if (p.kind !== 'sanction') return
    const title = p.title ? String(p.title) : 'Уведомление'
    const text = p.text ? String(p.text) : ''
    void alertDialog({ title, text })
  }
  window.addEventListener('auth-sanctions_update', onSanctionsUpdate)
  window.addEventListener('auth-notify', onSanctionAlert)
})

onBeforeUnmount(() => {
  if (onSanctionsUpdate) window.removeEventListener('auth-sanctions_update', onSanctionsUpdate)
  if (onSanctionAlert) window.removeEventListener('auth-notify', onSanctionAlert)
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
