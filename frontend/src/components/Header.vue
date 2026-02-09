<template>
  <header class="bar">
    <div class="links">
      <router-link class="btn" :to="{ name: 'home' }" aria-label="DECEIT.games">
        <span data-nosnippet>deceit.games v0.10.6b</span>
<!--        <span>deceit.games {{ BUILD }}</span>-->
      </router-link>
      <router-link class="btn" :to="{ name: 'rules' }" aria-label="Правила">
        <img :src="iconInfo" alt="" aria-hidden="true" />
        <span data-nosnippet>Правила</span>
      </router-link>
      <button class="btn" type="button" @click="openInstall" :aria-expanded="installOpen" aria-haspopup="dialog" aria-label="Установить">
        <img :src="iconInstall" alt="" aria-hidden="true" />
      </button>
      <button class="btn" type="button" @click="openSupport" :aria-expanded="supportOpen" aria-haspopup="dialog" aria-label="Поддержать">
        <img :src="iconCard" alt="" aria-hidden="true" />
      </button>
      <router-link v-if="user.user?.role === 'admin'" class="btn" :to="{ name: 'admin' }" aria-label="Админ-панель">
        <span data-nosnippet>Админ-панель</span>
      </router-link>
    </div>

    <div v-if="!auth.isAuthed && !auth.foreignActive" class="auth-actions">
      <button class="btn" type="button" @click="openAuth('login')">
        <span>Войти в аккаунт</span>
      </button>
    </div>
    <div v-else-if="!auth.isAuthed && auth.foreignActive" class="btn">
      <span>Вы уже авторизованы в соседней вкладке</span>
    </div>
    <div v-else class="user">
      <div class="bell" ref="updatesEl">
        <button @click.stop="onToggleUpdates" :aria-expanded="updates_open" aria-label="Обновления">
          <img :src="iconUpdates" alt="updates" />
          <span v-if="updates.unread > 0">{{ updates.unread < 100 ? updates.unread : '∞' }}</span>
        </button>
        <Updates
          v-model:open="updates_open"
          :anchor="updatesEl"
        />
      </div>

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

      <div class="bell" ref="friendsEl">
        <button @click.stop="onToggleFriends" :aria-expanded="friends_open" aria-label="??????">
          <img :src="iconFriends" alt="friends" />
          <span v-if="friends.incomingCount > 0">{{ friends.incomingCount < 100 ? friends.incomingCount : '∞' }}</span>
        </button>
        <FriendsPanel
          v-model:open="friends_open"
          :anchor="friendsEl"
        />
      </div>

      <div class="user-menu" ref="userMenuEl">
        <button class="btn" type="button" @click.stop="onToggleUserMenu" :aria-expanded="um_open" aria-haspopup="true">
          <img v-minio-img="{ key: user.user?.avatar_name ? `avatars/${user.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Аватар" />
          <span aria-live="polite">{{ user.user?.username || 'User' }}</span>
          <img class="arrow" :src="iconArrowDown" alt="arrow" :style="{ transform: um_open ? 'rotate(180deg)' : 'none'}" />
        </button>

        <Transition name="user-menu">
          <div v-if="um_open" class="user-menu-dropdown" role="menu">
            <router-link to="/profile" class="user-menu-item" role="menuitem" @click="closeUserMenu">
              <img :src="iconProfile" alt="profile" />
              <span>Личный кабинет</span>
            </router-link>
            <div class="border-line"></div>
            <button type="button" class="user-menu-item" role="menuitem" @click="onLogoutClick">
              <img :src="iconLogout" alt="logout" />
              <span>Выйти</span>
            </button>
          </div>
        </Transition>
      </div>
    </div>
  </header>
  <div v-if="sanctionBanner" class="sanction-banner" :class="`sanction-banner--${sanctionBanner.kind}`">
    <span>{{ sanctionBanner.text }}</span>
  </div>
  <div v-if="verificationBanner" class="sanction-banner sanction-banner--suspend">
    <span>Чтобы входить в комнаты требуется верификация.</span>
    <a v-if="botName" :href="botLink" target="_blank" rel="noopener noreferrer">Как пройти верификацию?</a>
  </div>
  <div v-if="registrationInfoBanner" class="sanction-banner sanction-banner--suspend">
    <span>Если у Вас ранее уже был аккаунт, используйте "Сбросить пароль" в</span>
    <a v-if="botName" :href="botLink" target="_blank" rel="noopener noreferrer">Telegram-боте</a>
  </div>
  <AppModal v-model:open="installOpen" />
  <SupportModal v-model:open="supportOpen" :support-link="supportLink" />
  <AuthModal v-model:open="authOpen" :mode="authMode" />
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, ref, computed } from 'vue'
import { useAuthStore, useUserStore, useNotifStore, useUpdatesStore, useFriendsStore } from '@/store'
import Notifs from '@/components/Notifs.vue'
import Updates from '@/components/Updates.vue'
import FriendsPanel from '@/components/FriendsPanel.vue'
import AppModal from '@/components/AppModal.vue'
import AuthModal from '@/components/AuthModal.vue'
import SupportModal from '@/components/SupportModal.vue'

import defaultAvatar from "@/assets/svg/defaultAvatar.svg"
import iconNotifBell from "@/assets/svg/notifBell.svg"
import iconInfo from "@/assets/svg/info.svg"
import iconUpdates from "@/assets/svg/updates.svg"
import iconFriends from "@/assets/svg/friends.svg"
import iconCard from "@/assets/svg/card.svg"
import iconInstall from "@/assets/svg/install.svg"
import iconLogout from '@/assets/svg/leave.svg'
import iconProfile from "@/assets/svg/profile.svg"
import iconArrowDown from '@/assets/svg/arrowDown.svg'

const auth = useAuthStore()
const user = useUserStore()
const notif = useNotifStore()
const updates = useUpdatesStore()
const friends = useFriendsStore()

const nb_open = ref(false)
const bellEl = ref<HTMLElement | null>(null)
const friends_open = ref(false)
const friendsEl = ref<HTMLElement | null>(null)
const updates_open = ref(false)
const updatesEl = ref<HTMLElement | null>(null)
const um_open = ref(false)
const userMenuEl = ref<HTMLElement | null>(null)
const installOpen = ref(false)
const supportOpen = ref(false)
const authOpen = ref(false)
const authMode = ref<'login' | 'register'>('login')
const botName = (import.meta.env.VITE_TG_BOT_NAME as string || '').trim()
const botLink = botName ? `https://t.me/${botName}` : 'https://t.me'
const supportLink = 'https://t.me/tribute/app?startapp=dCvc'

type SanctionBanner = { kind: 'ban' | 'timeout' | 'suspend'; text: string }

function formatRemaining(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  const hh = String(hours).padStart(2, '0')
  const mm = String(minutes).padStart(2, '0')
  const ss = String(seconds).padStart(2, '0')
  const base = `${hh}:${mm}:${ss}`
  return days > 0 ? `${days}д ${base}` : base
}

const sanctionBanner = computed<SanctionBanner | null>(() => {
  if (!auth.isAuthed) return null
  if (user.banActive) {
    return { kind: 'ban', text: 'Аккаунт забанен' }
  }
  if (user.timeoutRemainingMs > 0) {
    return { kind: 'timeout', text: `Таймаут: ${formatRemaining(user.timeoutRemainingMs)}` }
  }
  if (user.suspendRemainingMs > 0) {
    return { kind: 'suspend', text: `Ограничение доступа к играм: ${formatRemaining(user.suspendRemainingMs)}` }
  }
  return null
})

const verificationBanner = computed(() => auth.ready && auth.isAuthed && Boolean(user.user) && !user.telegramVerified)
const registrationInfoBanner = computed(() => auth.ready && !auth.isAuthed && !auth.foreignActive)

function onToggleNotifs() {
  updates_open.value = false
  friends_open.value = false
  nb_open.value = !nb_open.value
}
function onToggleUpdates() {
  nb_open.value = false
  friends_open.value = false
  updates_open.value = !updates_open.value
}
function onToggleFriends() {
  nb_open.value = false
  updates_open.value = false
  friends_open.value = !friends_open.value
}
function onToggleUserMenu() {
  um_open.value = !um_open.value
}
function closeUserMenu() {
  um_open.value = false
}
function openInstall() {
  installOpen.value = true
}
function openSupport() {
  supportOpen.value = true
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


async function logout() {
  try { await auth.logout() }
  finally {}
}

watch(() => auth.isAuthed, async ok => {
  if (ok) {
    notif.ensureWS()
    await notif.fetchAll()
    updates.ensureWS()
    await updates.fetchAll()
    friends.ensureWS()
    await friends.fetchIncomingCount()
  }
})

onMounted(async () => {
  if (auth.isAuthed) {
    notif.ensureWS()
    await notif.fetchAll()
    updates.ensureWS()
    await updates.fetchAll()
    friends.ensureWS()
    await friends.fetchIncomingCount()
  }
  document.addEventListener('pointerdown', onGlobalPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onGlobalPointerDown)
})

function openAuth(mode: 'login' | 'register') {
  authMode.value = mode
  authOpen.value = true
}
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
  .links {
    display: flex;
    align-items: center;
    gap: 10px;
  }
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
    text-decoration: none;
    cursor: pointer;
    transition: background-color 0.25s ease-in-out;
    &:hover {
      background-color: $lead;
    }
    span {
      color: $fg;
      font-size: 16px;
      font-family: Manrope-Medium;
      line-height: 1;
    }
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
  .auth-actions {
    display: flex;
    align-items: center;
    gap: 10px;
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
        transition: background-color 0.25s ease-in-out;
        &:hover {
          background-color: $lead;
        }
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
        .border-line {
          border-bottom: 1px solid $grey;
        }
        .user-menu-item {
          display: flex;
          align-items: center;
          padding: 0;
          gap: 5px;
          width: 200px;
          height: 50px;
          border: none;
          border-radius: 5px;
          background: none;
          text-decoration: none;
          cursor: pointer;
          transition: background-color 0.25s ease-in-out;
          &:hover {
            background-color: $lead;
          }
          img {
            margin-left: 15px;
            width: 24px;
            height: 24px;
          }
          span {
            height: 18px;
            color: $fg;
            font-size: 16px;
            font-family: Manrope-Medium;
            line-height: 1;
          }
        }
      }
    }
  }
}
.sanction-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 10px 10px;
  padding: 10px 0;
  border-radius: 5px;
  color: $bg;
  font-weight: bold;
  letter-spacing: 1px;
  gap: 5px;
  a {
    color: $black;
    text-decoration: underline;
  }
  &.sanction-banner--ban {
    background-color: $red;
  }
  &.sanction-banner--timeout {
    background-color: $orange;
  }
  &.sanction-banner--suspend {
    background-color: $yellow;
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

@media (max-width: 1280px) {
  .bar {
    .btn {
      span {
        font-size: 14px;
      }
      img {
        width: 20px;
        height: 20px;
      }
      .arrow {
        width: 14px;
        height: 14px;
      }
    }
    .user {
      .bell {
        button {
          img {
            width: 20px;
            height: 20px;
          }
        }
      }
    }
  }
  .sanction-banner {
    font-size: 12px;
    font-weight: normal;
    letter-spacing: 0.25px;
  }
}
</style>
