<template>
  <header class="bar">
    <div class="brand" aria-label="Mafia">DECEIT.games (v{{ BUILD }})</div>

    <div v-if="!auth.isAuthed && !auth.foreignActive">
      <div id="tg-login" />
    </div>
    <div v-else-if="!auth.isAuthed && auth.foreignActive" class="brand">
      <span>Вы уже авторизованы в соседней вкладке</span>
    </div>

    <div v-else class="user">
      <NotifsBell />
      <router-link to="/profile" class="profile-link" aria-label="Профиль">
        <img v-minio-img="{ key: user.user?.avatar_name ? `avatars/${user.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Аватар" />
        <span class="nick" aria-live="polite">{{ user.user?.username || 'User' }}</span>
      </router-link>
      <button class="btn" type="button" @click="logout">Выйти</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, nextTick, ref } from 'vue'
import { useAuthStore, useUserStore } from '@/store'
import NotifsBell from '@/components/NotifsBell.vue'

import defaultAvatar from "@/assets/svg/defaultAvatar.svg"

const auth = useAuthStore()
const user  = useUserStore()

let TG_LIB_ONCE = false
const BOT = import.meta.env.VITE_TG_BOT_NAME as string || ''
const BUILD = import.meta.env.VITE_BUILD_ID as string || ''
const SIZE: 'large' | 'medium' | 'small' = 'large'

declare global {
  interface Window { __tg_cb__?: (u: any) => void }
}

async function logout() {
  try { await auth.logout() }
  finally { alert('Для "полного" выхода из аккаунта нажмите в Telegram "Terminate session" для этой сессии') }
}

function mountTGWidget() {
  if (!BOT) return
  const box = document.getElementById('tg-login')
  if (!box || box.children.length) return
  window.__tg_cb__ = async (u: any) => {
    try { auth.wipeLocalForNewLogin() } catch {}
    await auth.signInWithTelegram(u)
  }
  const s = document.createElement('script')
  s.async = true
  s.src = 'https://telegram.org/js/telegram-widget.js?19'
  s.dataset.telegramLogin = BOT
  s.dataset.size = SIZE
  s.dataset.userpic = 'true'
  s.dataset.onauth = '__tg_cb__(user)'
  s.setAttribute('data-tg-widget', TG_LIB_ONCE ? '0' : '1')
  TG_LIB_ONCE = true
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
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
  width: calc(100% - 20px);
  height: 60px;
  .brand {
    display: flex;
    align-items: center;
    padding: 0 10px;
    height: 40px;
    border-radius: 5px;
    background-color: $dark;
    color: $fg;
    font-size: 16px;
  }
  .note {
    max-width: 460px;
    color: $fg;
  }
  .user {
    display: flex;
    align-items: center;
    gap: 10px;
    .profile-link {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 10px;
      gap: 5px;
      height: 40px;
      border-radius: 5px;
      background-color: $fg;
      text-decoration: none;
      img {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        object-fit: cover;
      }
      .nick {
        color: $bg;
        font-size: 16px;
      }
    }
    .btn {
      padding: 0 10px;
      height: 40px;
      border-radius: 5px;
      border: none;
      background-color: $dark;
      color: $fg;
      font-size: 16px;
      cursor: pointer;
    }
  }
}
</style>
