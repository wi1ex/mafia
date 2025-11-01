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
      <div class="bell" ref="bellEl">
        <button @click.stop="onToggleNotifs" :aria-expanded="nb_open" aria-label="Уведомления">
          <img :src="iconNotifBell" alt="bells" />
          <span v-if="notif.unread > 0">{{ notif.unread < 100 ? notif.unread : '∞' }}</span>
        </button>

        <Notifs
          v-model:open="nb_open"
          :anchor="bellEl"
        />
      </div>

      <router-link to="/profile" class="profile-link" aria-label="Профиль">
        <img v-minio-img="{ key: user.user?.avatar_name ? `avatars/${user.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Аватар" />
        <span aria-live="polite">{{ user.user?.username || 'User' }}</span>
      </router-link>

      <button class="btn" type="button" @click="logout">Выйти</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, nextTick, ref } from 'vue'
import { useAuthStore, useUserStore, useNotifStore } from '@/store'
import Notifs from '@/components/Notifs.vue'

import defaultAvatar from "@/assets/svg/defaultAvatar.svg"
import iconNotifBell from "@/assets/svg/notifBell.svg"

const auth = useAuthStore()
const user = useUserStore()
const notif = useNotifStore()

const nb_open = ref(false)
const bellEl = ref<HTMLElement | null>(null)

function onToggleNotifs() {
  nb_open.value = !nb_open.value
}

const BOT = import.meta.env.VITE_TG_BOT_NAME as string || ''
const BUILD = import.meta.env.VITE_BUILD_ID as string || ''
const SIZE: 'large' | 'medium' | 'small' = 'large'
let TG_LIB_ONCE = false

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

watch(() => auth.isAuthed, async ok => {
  if (ok) {
    notif.ensureWS()
    await notif.fetchAll()
  }
})

onMounted(async () => {
  if (!auth.isAuthed && !auth.foreignActive) {
    await nextTick()
    mountTGWidget()
  }
  if (auth.isAuthed) {
    notif.ensureWS()
    await notif.fetchAll()
  }
})

onBeforeUnmount(() => { delete (window as any).__tg_cb__ })
</script>

<style scoped lang="scss">
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
  .user {
    display: flex;
    align-items: center;
    gap: 10px;
    .bell {
      position: relative;
      border-radius: 5px;
      button {
        display: flex;
        position: relative;
        align-items: center;
        justify-content: center;
        padding: 0 10px;
        height: 40px;
        border-radius: 5px;
        border: none;
        background-color: $dark;
        font-size: 16px;
        cursor: pointer;
        img {
          width: 24px;
          height: 24px;
        }
        span {
          display: flex;
          align-items: center;
          justify-content: center;
          position: absolute;
          top: 5px;
          right: 5px;
          width: 17px;
          height: 17px;
          border-radius: 50%;
          background-color: $red;
          color: $fg;
          font-size: 12px;
          font-family: Manrope-Medium;
          line-height: 1;
        }
      }
    }
    .profile-link {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 10px;
      gap: 5px;
      height: 40px;
      border-radius: 5px;
      background-color: $lead;
      text-decoration: none;
      img {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        object-fit: cover;
      }
      span {
        color: $fg;
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
