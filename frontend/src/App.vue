<template>
  <div id="desktop-scale-root" class="desktop-scale-root" :style="desktopScaleStyle">
    <Header v-if="!isRoom" />
    <div class="rotate-overlay">
      <div data-nosnippet>Поверните устройство</div>
    </div>
    <router-view :key="routerViewKey" />
    <Chat />
    <Confirms />
    <Toast />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, watchEffect, computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store'
import { useUserStore } from '@/store'
import { useNotifStore } from '@/store'
import { useGlobalChatStore } from '@/store'
import { useSettingsStore } from '@/store'
import { alertDialog } from '@/services/confirm'

import Header from '@/components/Header.vue'
import Toast from '@/components/Toasts.vue'
import Confirms from '@/components/Confirms.vue'
import Chat from '@/components/Chat.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const user = useUserStore()
const chat = useGlobalChatStore()
const settings = useSettingsStore()

const DESKTOP_DESIGN_WIDTH = 1700
const DESKTOP_BREAKPOINT = 1280
const viewport = ref({ width: window.innerWidth, height: window.innerHeight })
const desktopScale = computed(() => (
  viewport.value.width >= DESKTOP_BREAKPOINT
    ? Math.min(1, viewport.value.width / DESKTOP_DESIGN_WIDTH)
    : 1
))
const desktopScaleStyle = computed(() => {
  const scale = desktopScale.value
  const { width, height } = viewport.value
  return {
    '--desktop-scale': String(scale),
    '--app-viewport-width': `${width / scale}px`,
    '--app-viewport-height': `${height / scale}px`,
  }
})

let onSanctionsUpdate: ((e: any) => void) | null = null
let onTelegramVerified: ((e: any) => void) | null = null
let onAdminNotify: ((e: any) => void) | null = null
let onUserGameParticipationChanged: ((e: any) => void) | null = null
let onProfileSync: ((e: any) => void) | null = null

const isRoom = computed(() => route.name === 'room')
const routerViewKey = computed(() => {
  if (route.name === 'room') return `room:${String(route.params.id ?? '')}`
  return route.name ? `route:${String(route.name)}` : route.fullPath
})

function updateViewport() {
  viewport.value = { width: window.innerWidth, height: window.innerHeight }
}

watchEffect(() => {
  document.body.classList.toggle('room-touch-manipulation', isRoom.value)
})

watchEffect(() => {
  if (route.meta?.requiresAuth && !auth.isAuthed) {
    router.replace({ name: 'home' }).catch(() => {})
  }
  if (
    route.meta?.requiresVerification
    && auth.isAuthed
    && settings.ready
    && settings.verificationRestrictions
    && Boolean(user.user)
    && !user.telegramVerified
  ) {
    router.replace({ name: 'home' }).catch(() => {})
  }
})

watchEffect(() => {
  if (auth.isAuthed) user.ensureClock()
})

watch(() => auth.isAuthed, (isAuthed) => {
  if (!isAuthed) {
    chat.clearUnreadCount()
    return
  }
  chat.ensureUnreadSync()
  chat.syncUnreadFromProfile()
})

onMounted(async () => {
  window.addEventListener('resize', updateViewport)
  onSanctionsUpdate = (e: any) => {
    const p = e?.detail || {}
    user.setSanctions({
      timeout_until: p.timeout_until ?? null,
      suspend_until: p.suspend_until ?? null,
      ban_active: p.ban_active ?? false,
    })
  }
  window.addEventListener('auth-sanctions_update', onSanctionsUpdate)
  onUserGameParticipationChanged = (e: any) => {
    const detail = e?.detail || {}
    const inActiveGameAsPlayer = Boolean(detail.in_active_game_as_player ?? detail.in_active_game_as_alive_player)
    user.setInActiveGameAsPlayer(inActiveGameAsPlayer)
  }
  window.addEventListener('auth-user_game_participation_changed', onUserGameParticipationChanged)
  onProfileSync = (e: any) => {
    const payload = e?.detail
    if (!auth.isAuthed || !payload) return
    user.applyProfile(payload)
    chat.syncUnreadFromProfile()
  }
  window.addEventListener('auth-profile_sync', onProfileSync)
  onTelegramVerified = (e: any) => {
    if (!auth.isAuthed) return
    const payloadUserId = Number(e?.detail?.user_id || 0)
    if (payloadUserId > 0 && user.user?.id && payloadUserId !== user.user.id) return
    const wasVerified = user.telegramVerified
    user.setTelegramVerified(true)
    user.fetchMe().catch(() => {})
    if (!wasVerified) void alertDialog('Аккаунт успешно верифицирован.')
    const onProfile = route.name === 'profile'
    const tab = typeof route.query?.tab === 'string' ? route.query.tab : ''
    if (!onProfile) {
      router.push({ name: 'profile', query: { tab: 'profile' } }).catch(() => {})
      return
    }
    if (tab !== 'profile') {
      router.replace({ query: { ...route.query, tab: 'profile' } }).catch(() => {})
    }
  }
  window.addEventListener('auth-telegram_verified', onTelegramVerified)
  onAdminNotify = (e: any) => {
    const p = e?.detail
    if (!p || p.kind !== 'admin_action') return
    const title = typeof p.title === 'string' && p.title.trim() ? p.title : 'Сообщение'
    const text = typeof p.text === 'string' && p.text.trim() ? p.text : ''
    void alertDialog({ title, text })
    if (auth.isAuthed) user.fetchMe().catch(() => {})
  }
  window.addEventListener('auth-notify', onAdminNotify)
  settings.ensureWS()
  try { await settings.fetchPublic() } catch {}
  await auth.init()
  if (auth.isAuthed) {
    if (!user.user) {
      try { await user.fetchMe() } catch {}
    }
    chat.ensureUnreadSync()
    chat.syncUnreadFromProfile()
    user.ensureClock()
    const notif = useNotifStore()
    notif.ensureWS()
    try { await notif.fetchAll() } catch {}
  } else {
    chat.clearUnreadCount()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewport)
  document.body.classList.remove('room-touch-manipulation')
  if (onSanctionsUpdate) window.removeEventListener('auth-sanctions_update', onSanctionsUpdate)
  if (onUserGameParticipationChanged) window.removeEventListener('auth-user_game_participation_changed', onUserGameParticipationChanged)
  if (onProfileSync) window.removeEventListener('auth-profile_sync', onProfileSync)
  if (onTelegramVerified) window.removeEventListener('auth-telegram_verified', onTelegramVerified)
  if (onAdminNotify) window.removeEventListener('auth-notify', onAdminNotify)
})
</script>

<style lang="scss" scoped>
.desktop-scale-root {
  display: flex;
  flex-direction: column;
  width: var(--app-viewport-width);
  height: var(--app-viewport-height);
  overflow: hidden;
  transform: scale(var(--desktop-scale));
  transform-origin: top left;
}
.rotate-overlay {
  display: none;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($neutral-800, 0.2);
  backdrop-filter: blur(12px);
  color: $neutral-100;
  font-family: Hauora-Regular;
  font-size: 16px;
  line-height: 22px;
  letter-spacing: -0.32px;
  z-index: 9999;
}

@media (orientation: portrait) {
  .rotate-overlay {
    display: flex;
  }
}

@media (max-width: 1700px) {

}

@media (max-width: 1200px) {

}

</style>
