<template>
  <div v-if="sanctionBanner" class="sanction-banner" :class="`sanction-banner--${sanctionBanner.kind}`">
    <span>{{ sanctionBanner.text }}</span>
  </div>
  <div v-if="verificationBanner" class="sanction-banner sanction-banner--verif">
    <UiIcon class="banner-icon" :icon="iconWarning" />
    <span>Без верификации аккаунт будет удален через <span class="verification-hour-badge">1</span> час.</span>
    <span class="verification-divider" aria-hidden="true"></span>
    <span>Пройдите верификацию через</span>
    <a v-if="botName" :href="botLink" target="_blank" rel="noopener noreferrer">
      <img :src="iconTelegram" alt="" />
      TG-бота
    </a>
  </div>
  <div v-if="adminBannerText" class="sanction-banner sanction-banner--admin">
    <span>{{ adminBannerText }}</span>
    <a v-if="adminBannerLink" :href="adminBannerLink" target="_blank" rel="noopener noreferrer">
      {{ adminBannerLink }}
    </a>
  </div>
  <header class="bar">
    <div class="links">
      <router-link class="home" :to="{ name: 'home' }" aria-label="DECEIT.games">
        <img :src="iconLogo" alt="" aria-hidden="true" />
<!--        <span data-nosnippet>{{ BUILD }}</span>-->
      </router-link>
      <div class="pages">
        <router-link class="page" :to="{ name: 'rules' }" aria-label="Правила">
          <UiIcon class="page-icon" :icon="iconInfo" />
          <span data-nosnippet>Правила</span>
        </router-link>
        <router-link v-if="showHistoryButton" class="page" :to="{ name: 'history' }" aria-label="История игр">
          <UiIcon class="page-icon" :icon="iconGamesHistory" />
          <span data-nosnippet>История игр</span>
        </router-link>
        <router-link v-if="user.user?.role === 'admin'" class="page" :to="{ name: 'admin' }" aria-label="Админ-панель">
          <UiIcon class="page-icon" :icon="iconJudge" />
          <span data-nosnippet>Админ-панель</span>
        </router-link>
        <router-link v-if="user.user?.role === 'moder'" class="page" :to="{ name: 'moderation' }" aria-label="Модерация">
          <UiIcon class="page-icon" :icon="iconJudge" />
          <span data-nosnippet>Модерация</span>
        </router-link>
      </div>
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

      <div v-if="showFriendsButton" class="bell" ref="friendsEl">
        <button @click.stop="onToggleFriends" :aria-expanded="friends_open" aria-label="Друзья">
          <img :src="iconFriends" alt="friends" />
          <span v-if="friends.incomingCount > 0">{{ friends.incomingCount < 100 ? friends.incomingCount : '∞' }}</span>
        </button>
        <FriendsPanel
          v-model:open="friends_open"
          :anchor="friendsEl"
          mode="header"
        />
      </div>

      <div v-if="showGlobalChatButton" class="bell">
        <button @click.stop="toggleGlobalChat" :aria-expanded="chat.open" aria-label="Общий чат">
          <img :src="iconChat" alt="chat" />
          <span v-if="chat.unread > 0">{{ chat.unread < 100 ? chat.unread : '∞' }}</span>
        </button>
      </div>

      <div class="user-menu" ref="userMenuEl">
        <button class="btn" :class="{ 'has-profile-theme': hasUserMenuProfileTheme }" type="button" :style="userMenuButtonStyle" @click.stop="onToggleUserMenu" :aria-expanded="um_open" aria-haspopup="true">
          <img v-minio-img="{ key: user.user?.avatar_name ? `avatars/${user.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Аватар" class="avatar" />
          <div v-if="userMenuProfileIconSrcs.length" class="profile-theme-icons" aria-hidden="true">
            <img v-for="badgeSrc in userMenuProfileIconSrcs" :key="badgeSrc" class="profile-theme-icon" :src="badgeSrc" alt="" />
          </div>
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
  <AuthModal v-model:open="authOpen" :mode="authMode" />
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, ref, computed } from 'vue'
import { useAuthStore, useUserStore, useNotifStore, useUpdatesStore, useFriendsStore, useSettingsStore, useGlobalChatStore } from '@/store'
import Notifs from '@/components/Notifs.vue'
import Updates from '@/components/Updates.vue'
import FriendsPanel from '@/components/FriendsPanel.vue'
import AuthModal from '@/components/AuthModal.vue'
import UiIcon from '@/components/UiIcon.vue'

import defaultAvatar from "@/assets/svg/defaultAvatar.svg"
import iconLogo from '@/assets/svg/iconLogo.svg'
import iconNotifBell from "@/assets/svg/notifBell.svg"
import iconTelegram from "@/assets/svg/iconTelegram.svg"
import iconWarning from "@/assets/svg/iconWarning.svg"
import iconInfo from "@/assets/svg/iconInfo.svg"
import iconGamesHistory from "@/assets/svg/iconHistory.svg"
import iconUpdates from "@/assets/svg/updates.svg"
import iconFriends from "@/assets/svg/friends.svg"
import iconChat from "@/assets/svg/chat.svg"
import iconLogout from '@/assets/svg/leave.svg'
import iconProfile from "@/assets/svg/profile.svg"
import iconArrowDown from '@/assets/svg/arrowDown.svg'
import iconJudge from '@/assets/svg/iconJudge.svg'
import { buildProfileThemeStyle } from '@/constants/profileThemes'
import { getProfileThemeBadgeSources } from '@/constants/profileThemeIcons'

const auth = useAuthStore()
const user = useUserStore()
const notif = useNotifStore()
const updates = useUpdatesStore()
const friends = useFriendsStore()
const settings = useSettingsStore()
const chat = useGlobalChatStore()

const nb_open = ref(false)
const bellEl = ref<HTMLElement | null>(null)
const friends_open = ref(false)
const friendsEl = ref<HTMLElement | null>(null)
const updates_open = ref(false)
const updatesEl = ref<HTMLElement | null>(null)
const um_open = ref(false)
const userMenuEl = ref<HTMLElement | null>(null)
const authOpen = ref(false)
const authMode = ref<'login' | 'register'>('login')
const BUILD = (import.meta.env.VITE_BUILD_ID as string || '').trim() || 'BUILD'
const botName = (import.meta.env.VITE_TG_BOT_NAME as string || '').trim()
const botLink = botName ? `https://t.me/${botName}` : 'https://t.me'
const userMenuButtonStyle = computed(() => buildProfileThemeStyle(user.activeProfileThemeColor))
const hasUserMenuProfileTheme = computed(() => Boolean(user.activeProfileThemeColor))
const userMenuProfileIconSrcs = computed(() => getProfileThemeBadgeSources(user.activeProfileThemeIcon, user.user?.role))

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
    return { kind: 'suspend', text: `Отстранение от игр: ${formatRemaining(user.suspendRemainingMs)}` }
  }
  return null
})

const verificationBanner = computed(() => {
  return auth.ready
    && settings.ready
    && settings.verificationRestrictions
    && auth.isAuthed
    && Boolean(user.user)
    && !user.telegramVerified
})

const canUseVerifiedFeatures = computed(() => {
  if (!auth.ready || !settings.ready || !auth.isAuthed) return false
  if (!user.user) return false
  return !(settings.verificationRestrictions && !user.telegramVerified)
})

const showHistoryButton = computed(() => {
  return canUseVerifiedFeatures.value
})

const showFriendsButton = computed(() => {
  return canUseVerifiedFeatures.value
})

const showGlobalChatButton = computed(() => {
  if (!canUseVerifiedFeatures.value) return false
  if (!settings.chatOpenEnabled) return false
  return !(user.banActive || user.timeoutActive || user.inActiveGameAsPlayer)
})

const adminBannerText = computed(() => {
  if (!settings.ready) return ''
  const text = String(settings.adminBannerText || '').trim()
  if (!text || text === '0') return ''
  return text
})

const adminBannerLink = computed(() => {
  if (!settings.ready || !adminBannerText.value) return ''
  const link = String(settings.adminBannerLink || '').trim()
  if (!link || link === '0') return ''
  return link
})

function onToggleNotifs() {
  const next = !nb_open.value
  closeHeaderPanels({ keepNotifs: true })
  nb_open.value = next
}
function onToggleUpdates() {
  const next = !updates_open.value
  closeHeaderPanels({ keepUpdates: true })
  updates_open.value = next
}
function onToggleFriends() {
  if (!showFriendsButton.value) {
    friends_open.value = false
    return
  }
  const next = !friends_open.value
  closeHeaderPanels({ keepFriends: true })
  friends_open.value = next
}
function toggleGlobalChat() {
  if (chat.open) {
    chat.closePanel()
    return
  }
  closeHeaderPanels({ keepChat: true })
  chat.openPanel()
}
function onToggleUserMenu() {
  const next = !um_open.value
  closeHeaderPanels({ keepUserMenu: true })
  um_open.value = next
}
function closeUserMenu() {
  um_open.value = false
}
function closeHeaderPanels(options: {
  keepChat?: boolean
  keepNotifs?: boolean
  keepUpdates?: boolean
  keepFriends?: boolean
  keepUserMenu?: boolean
  keepAuth?: boolean
} = {}) {
  if (!options.keepNotifs) nb_open.value = false
  if (!options.keepUpdates) updates_open.value = false
  if (!options.keepFriends) friends_open.value = false
  if (!options.keepUserMenu) um_open.value = false
  if (!options.keepAuth) authOpen.value = false
  if (!options.keepChat && chat.open) {
    chat.closePanel()
  }
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

async function syncFriendsAccess() {
  if (!showFriendsButton.value) {
    friends_open.value = false
    return
  }
  friends.ensureWS()
  await friends.fetchIncomingCount()
}

watch(() => auth.isAuthed, async ok => {
  if (ok) {
    notif.ensureWS()
    await notif.fetchAll()
    updates.ensureWS()
    await updates.fetchAll()
    await syncFriendsAccess()
  }
})

watch(showFriendsButton, ok => {
  if (!ok) {
    friends_open.value = false
    return
  }
  void syncFriendsAccess()
})

onMounted(async () => {
  if (auth.isAuthed) {
    notif.ensureWS()
    await notif.fetchAll()
    updates.ensureWS()
    await updates.fetchAll()
    await syncFriendsAccess()
  }
  document.addEventListener('pointerdown', onGlobalPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onGlobalPointerDown)
})

function openAuth(mode: 'login' | 'register') {
  closeHeaderPanels({ keepAuth: true })
  authMode.value = mode
  authOpen.value = true
}
</script>

<style scoped lang="scss">
.sanction-banner {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  height: 40px;
  border-radius: 0 0 16px 16px;
  .page-icon {
    --ui-icon-width: 24px;
    --ui-icon-height: 24px;
    --ui-icon-color: #{$neutral-white};
  }
  span {
    color: $neutral-white;
    font-family: Hauora-Medium;
    font-size: 16px;
    line-height: 16px;
    letter-spacing: -0.32px;
  }
  a {
    display: flex;
    align-items: center;
    gap: 8px;
    color: $neutral-white;
    font-size: 16px;
    line-height: 16px;
    letter-spacing: -0.32px;
    font-family: Hauora-Bold;
    text-decoration-line: underline;
    text-decoration-style: solid;
    text-decoration-skip-ink: auto;
    text-decoration-thickness: 1.28px;
    text-underline-offset: 2.56px;
    text-underline-position: from-font;
    img {
      width: 24px;
      height: 24px;
    }
  }
  &.sanction-banner--ban {
    background-color: $red-500;
  }
  &.sanction-banner--timeout {
    background-color: $orange-500;
    .page-icon {
      --ui-icon-color: #{$neutral-900};
    }
    span {
      color: $neutral-900;
    }
  }
  &.sanction-banner--suspend {
    background-color: $yellow-500;
    .page-icon {
      --ui-icon-color: #{$neutral-900};
    }
    span {
      color: $neutral-900;
    }
  }
  &.sanction-banner--verif {
    background-color: $red-500;
    .verification-hour-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 8px 4px;
      width: 28px;
      height: 28px;
      border-radius: 6px;
      background-color: rgba($neutral-black, 0.4);
      font-family: Hauora-Bold;
    }
    .verification-divider {
      display: block;
      width: 1px;
      height: 28px;
      background-color: rgba($neutral-white, 0.4);
    }
  }
  &.sanction-banner--admin {
    background-color: $lead;
  }
}
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 10px 0;
  padding: 0 40px;
  height: 64px;
  min-height: 64px;
  max-height: 64px;
  .links {
    display: flex;
    align-items: center;
    gap: 24px;
    .home {
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 16px;
      border-radius: 16px;
      background-color: $soft-purple-900;
      img {
        width: 115px;
        height: 32px;
      }
    }
    .pages {
      display: flex;
      align-items: center;
      gap: 12px;
      .page {
        display: flex;
        align-items: center;
        padding: 0 16px;
        gap: 8px;
        height: 64px;
        border-radius: 16px;
        text-decoration: none;
        transition: background-color 0.25s ease-in-out;
        .page-icon {
          --ui-icon-width: 24px;
          --ui-icon-height: 24px;
          --ui-icon-color: #{$neutral-300};
        }
        &:hover .page-icon,
        &:focus-visible .page-icon,
        &:active .page-icon {
          --ui-icon-color: #{$neutral-white};
        }
        span {
          color: $neutral-300;
          font-family: Hauora-Regular;
          font-size: 18px;
          line-height: 20px;
          letter-spacing: -0.36px;
        }
        &:hover {
          background-color: $soft-purple-900;
        }
      }
    }
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
    background-color: var(--user-theme-bg, $graphite);
    text-decoration: none;
    cursor: pointer;
    transition: background-color 0.25s ease-in-out;
    &:hover {
      background-color: var(--user-theme-bg-hover, $lead);
    }
    span {
      color: $fg;
      font-size: 16px;
      font-family: Manrope-Medium;
      line-height: 1;
    }
    img {
      height: 24px;
      object-fit: cover;
    }
    .avatar {
      border-radius: 50%;
      aspect-ratio: 1;
    }
    .profile-theme-icon {
      width: 24px;
      height: 24px;
      border-radius: 0;
      object-fit: contain;
    }
    .profile-theme-icons {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      flex: 0 0 auto;
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
      > .btn.has-profile-theme {
        position: relative;
        overflow: hidden;
        isolation: isolate;
        &::before {
          content: '';
          position: absolute;
          inset: 0;
          border-radius: inherit;
          background:
            radial-gradient(circle at top, rgba($white, 0.1) 0%, rgba($white, 0) 50%),
            rgba($white, 0.05);
          opacity: 0;
          pointer-events: none;
          transition: opacity 0.25s ease-in-out;
          z-index: 0;
        }
        &:hover::before,
        &:focus-visible::before {
          opacity: 1;
        }
        > * {
          position: relative;
          z-index: 1;
        }
      }
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
  .sanction-banner {
    font-size: 12px;
    font-weight: normal;
    letter-spacing: 0.25px;
  }
  .bar {
    min-height: 50px;
    height: 50px;
    max-height: 50px;
    .links {
      gap: 5px;
    }
    .btn {
      padding: 0 8px;
      gap: 3px;
      height: 30px;
      span {
        font-size: 12px;
      }
      img {
        height: 16px;
      }
      .profile-theme-icon {
        width: 16px;
        height: 16px;
      }
      .profile-theme-icons {
        gap: 3px;
      }
      .arrow {
        margin-left: 3px;
        width: 10px;
        height: 10px;
      }
    }
    .user {
      gap: 5px;
      .bell {
        button {
          padding: 0 8px;
          height: 30px;
          img {
            width: 16px;
            height: 16px;
          }
          span {
            width: 11px;
            height: 11px;
            font-size: 8px;
            line-height: 0.8;
          }
        }
      }
      .user-menu {
        .user-menu-dropdown {
          top: 40px;
          min-width: 150px;
          max-width: 150px;
          .user-menu-item {
            height: 30px;
            img {
              margin-left: 10px;
              width: 16px;
              height: 16px;
            }
            span {
              height: 14px;
              font-size: 12px;
            }
          }
        }
      }
    }
  }
}
</style>
