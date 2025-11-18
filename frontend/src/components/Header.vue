<template>
  <header class="bar">
    <router-link class="btn" :to="{ name: 'home' }" aria-label="DECEIT.games">DECEIT.games (v{{ BUILD }})</router-link>

    <div v-if="!auth.isAuthed && !auth.foreignActive">
      <div id="tg-login" />
    </div>
    <div v-else-if="!auth.isAuthed && auth.foreignActive" class="btn">
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

      <div class="user-menu" ref="userMenuEl">
        <button class="btn" type="button" @click.stop="onToggleUserMenu" :aria-expanded="um_open" aria-haspopup="true">
          <img v-minio-img="{ key: user.user?.avatar_name ? `avatars/${user.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Аватар" />
          <span aria-live="polite">{{ user.user?.username || 'User' }}</span>
          <img :src="iconArrowDown" alt="arrow" :style="{ transform: um_open ? 'rotate(180deg)' : 'none'}" />
        </button>

        <Transition name="user-menu">
          <div v-if="um_open" class="user-menu-dropdown" role="menu">
            <router-link to="/profile" class="user-menu-item" role="menuitem" @click="closeUserMenu">
              <img :src="iconProfile" alt="profile" />
              <span>Профиль</span>
            </router-link>
            <button type="button" class="user-menu-item" role="menuitem" @click="onLogoutClick">
              <img :src="iconLogout" alt="logout" />
              <span>Выйти</span>
            </button>
          </div>
        </Transition>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, nextTick, ref } from 'vue'
import { useAuthStore, useUserStore, useNotifStore } from '@/store'
import Notifs from '@/components/Notifs.vue'

import defaultAvatar from "@/assets/svg/defaultAvatar.svg"
import iconNotifBell from "@/assets/svg/notifBell.svg"
import iconLogout from '@/assets/svg/leave.svg'
import iconProfile from "@/assets/svg/profile.svg"
import iconArrowDown from '@/assets/svg/arrowDown.svg'

const auth = useAuthStore()
const user = useUserStore()
const notif = useNotifStore()

const nb_open = ref(false)
const bellEl = ref<HTMLElement | null>(null)
const um_open = ref(false)
const userMenuEl = ref<HTMLElement | null>(null)

function onToggleNotifs() {
  nb_open.value = !nb_open.value
}
function onToggleUserMenu() {
  um_open.value = !um_open.value
}
function closeUserMenu() {
  um_open.value = false
}
async function onLogoutClick() {
  closeUserMenu()
  await logout()
}
function onGlobalPointerDown(e: PointerEvent) {
  if (!um_open.value) return
  const target = e.target as Node | null
  if (target && userMenuEl.value && userMenuEl.value.contains(target)) return
  um_open.value = false
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
  finally { alert('Для "полного" выхода из аккаунта нажмите в Telegram "Terminate session" для этого сайта') }
}

function mountTGWidget() {
  if (!BOT) return
  const box = document.getElementById('tg-login')
  if (!box || box.children.length) return
  window.__tg_cb__ = async (u: any) => {
    const prevUid = Number(localStorage.getItem('user:lastUid') || 0)
    const nextUid = Number(u?.id || 0)
    const userChanged = prevUid !== nextUid
    try { auth.wipeLocalForNewLogin?.({ userChanged }) } catch {}
    await auth.signInWithTelegram(u)
    try { localStorage.setItem('user:lastUid', String(nextUid)) } catch {}
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
  document.addEventListener('pointerdown', onGlobalPointerDown)
})

onBeforeUnmount(() => {
  delete (window as any).__tg_cb__
  document.removeEventListener('pointerdown', onGlobalPointerDown)
})
</script>

<style scoped lang="scss">
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
  width: calc(100% - 20px);
  min-height: 60px;
  height: 60px;
  max-height: 60px;
  .btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 10px;
    gap: 5px;
    height: 40px;
    border: none;
    border-radius: 5px;
    background-color: $graphite;
    color: $fg;
    font-size: 16px;
    font-family: Manrope-Medium;
    line-height: 1;
    text-decoration: none;
    cursor: pointer;
    img {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      object-fit: cover;
    }
    .arrow {
      margin-left: 5px;
      width: 16px;
      height: 16px;
      border-radius: 0;
      object-fit: none;
      transition: transform 0.25s ease-in-out;
    }
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
        border: none;
        border-radius: 5px;
        background-color: $graphite;
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
    .user-menu {
      position: relative;
      .user-menu-dropdown {
        position: absolute;
        right: 0;
        top: 50px;
        min-width: 200px;
        max-width: 200px;
        border-radius: 5px;
        background-color: $graphite;
        box-shadow: 3px 3px 5px rgba($black, 0.25);
        z-index: 20;
        .user-menu-item {
          display: flex;
          align-items: center;
          padding: 0;
          gap: 5px;
          width: 200px;
          height: 50px;
          border: none;
          background: none;
          text-decoration: none;
          cursor: pointer;
          transition: background-color 0.25s ease-in-out;
          img {
            margin-left: 15px;
            width: 20px;
            height: 20px;
          }
          span {
            height: 18px;
            color: $fg;
            font-size: 16px;
            font-family: Manrope-Medium;
            line-height: 1;
          }
          &:hover {
            background-color: $lead;
          }
        }
      }
    }
  }
}

.user-menu-enter-active,
.user-menu-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}
.user-menu-enter-from,
.user-menu-leave-to {
  opacity: 0;
  transform: translateY(-30px);
}
</style>
