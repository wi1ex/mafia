<template>
  <div id="tg-login" />
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/store'

const BOT = import.meta.env.VITE_TG_BOT_NAME
const SIZE: 'large'|'medium'|'small'='large'

const auth = useAuthStore()

declare global {
  interface Window {
    telegramAuthCallback?: (u: any)=>void
  }
}

onMounted(() => {
  window.telegramAuthCallback = async (u: any) => {
    await auth.signInWithTelegram(u)
  }
  const s = document.createElement('script')
  s.async = true
  s.src = 'https://telegram.org/js/telegram-widget.js?19'
  s.setAttribute('data-telegram-login', BOT)
  s.setAttribute('data-size', SIZE)
  s.setAttribute('data-userpic', 'true')
  s.setAttribute('data-onauth', 'telegramAuthCallback(user)')
  document.getElementById('tg-login')?.appendChild(s)
})

onBeforeUnmount(() => {
  delete window.telegramAuthCallback
})
</script>

<style lang="scss" scoped>

</style>
