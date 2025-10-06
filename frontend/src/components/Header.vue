<template>
  <header class="bar" role="banner">
    <div class="brand" aria-label="Mafia">Mafia</div>

    <div v-if="!auth.isAuthed && !auth.foreignActive" class="login-box">
      <div id="tg-login" />
    </div>
    <div v-else-if="!auth.isAuthed && auth.foreignActive" class="login-box note">
      <span>Вы уже авторизованы в соседней вкладке</span>
    </div>

    <div v-else class="user">
      <img :src="auth.user?.photo_url || defaultAvatar" alt="Аватар" class="avatar" loading="lazy" referrerpolicy="no-referrer" />
      <span class="nick" aria-live="polite">{{ auth.user?.username || 'User' }}</span>
      <button class="btn" type="button" @click="logout">Выйти</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useAuthStore } from '@/store'

import defaultAvatar from "@/assets/svg/defaultAvatar.svg"

const auth = useAuthStore()

const BOT = import.meta.env.VITE_TG_BOT_NAME as string | undefined
const SIZE: 'large'|'medium'|'small' = 'large'

declare global { interface Window { __tg_cb__?: (u:any) => void } }

async function logout() { try { await auth.logout() } catch {} }

function mountTGWidget() {
  if (!BOT) return
  const box = document.getElementById('tg-login')
  if (!box) return
  box.innerHTML = ''
  document.querySelector('script[data-tg-widget="1"]')?.remove()
  window.__tg_cb__ = async (u:any) => { await auth.signInWithTelegram(u) }

  const s = document.createElement('script')
  s.async = true
  s.src = 'https://telegram.org/js/telegram-widget.js?19'
  s.dataset.telegramLogin = BOT
  s.dataset.size = SIZE
  s.dataset.userpic = 'true'
  s.dataset.onauth = '__tg_cb__(user)'
  s.setAttribute('data-tg-widget', '1')
  box.appendChild(s)
}

watch([() => auth.isAuthed, () => auth.foreignActive], async () => {
  if (!auth.isAuthed && !auth.foreignActive) {
    await nextTick()
    mountTGWidget()
  } else {
    document.getElementById('tg-login')?.replaceChildren()
  }
}, { flush: 'post' })

onMounted(async () => {
  if (!auth.isAuthed && !auth.foreignActive) {
    await nextTick()
    mountTGWidget()
  }
})

onBeforeUnmount(() => {
  delete window.__tg_cb__
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
  }
  .note {
    color: $muted;
    max-width: 460px;
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
    }
    .nick {
      color: $fg;
    }
    .btn {
      padding: 6px 10px;
      border-radius: 8px;
      cursor: pointer;
    }
  }
}
</style>
