<template>
  <header class="bar" role="banner">
    <div class="brand" aria-label="Mafia">Mafia</div>

    <div v-if="!auth.isAuthed" class="login-box">
      <div id="tg-login" />
    </div>

    <div v-else class="user">
      <img v-if="auth.avatarUrl" :src="auth.avatarUrl" alt="Аватар" class="avatar" loading="lazy" referrerpolicy="no-referrer" />
      <div v-else class="avatar placeholder" aria-hidden="true" />
      <span class="nick" aria-live="polite">{{ auth.displayName }}</span>
      <button class="btn btn-ghost" type="button" @click="logout">Выйти</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/store'

const auth = useAuthStore()

const BOT = import.meta.env.VITE_TG_BOT_NAME as string | undefined
const SIZE: 'large'|'medium'|'small' = 'large'

declare global {
  interface Window { __mafia_tg_cb__?: (u:any) => void }
}

async function logout() { try { await auth.logout() } catch {} }

onMounted(() => {
  if (!BOT || auth.isAuthed) return
  if (document.querySelector('script[data-tg-widget="1"]')) return

  window.__mafia_tg_cb__ = async (u:any) => { await auth.signInWithTelegram(u) }

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

<style lang="scss" scoped>
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  .brand {
    color: $fg;
    font-weight: 700;
    letter-spacing: 0.5px;
  }
  .user {
    display: flex;
    align-items: center;
    gap: 10px;
    .avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      object-fit: cover;
      background: #0b0f14;
    }
    .placeholder {
      background: #334155;
    }
    .nick {
      color: $fg;
    }
    .btn {
      padding: 6px 10px;
      border: 0;
      border-radius: 8px;
      cursor: pointer;
      transition: opacity 0.2s ease;
    }
    .btn-ghost {
      background: #334155;
      color: #7795d2;
    }
  }
}
</style>
