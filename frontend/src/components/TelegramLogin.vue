<template>
  <div id="tg-login" />
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/store'

const BOT = import.meta.env.VITE_TG_BOT_NAME
const SIZE: 'large'|'medium'|'small' = 'large'
const auth = useAuthStore()

declare global {
  interface Window {
    __mafia_tg_cb__?: (u: any) => void
  }
}

onMounted(() => {
  if (!BOT) return
  if (document.querySelector('script[data-tg-widget="1"]')) return
  window.__mafia_tg_cb__ = async (u: any) => {
    await auth.signInWithTelegram(u)
  }
  const s = document.createElement('script')
  s.async = true
  s.src = 'https://telegram.org/js/telegram-widget.js?19'
  s.dataset.telegramLogin = BOT
  s.dataset.size = SIZE
  s.dataset.userpic = 'true'
  s.dataset.onauth = '__mafia_tg_cb__(user)'
  s.setAttribute('data-tg-widget', '1')
  document.getElementById('tg-login')?.appendChild(s)
})

onBeforeUnmount(() => {
  delete window.__mafia_tg_cb__
})
</script>
