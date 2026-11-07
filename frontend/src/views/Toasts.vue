<template>
  <Teleport to="#desktop-teleport-root">
  <div class="toasts" @transitionend="onTransEnd">
    <div v-for="t in items" :key="t.key" class="toast" :data-key="t.key" :class="[toastAppearance(t.kind).tone, { closing: t._closing }]">
      <UiIcon class="toast-icon" :icon="toastAppearance(t.kind).icon" />
      <div class="toast-div">
        <header>
          <span>{{ t.title }}</span>
          <button @click="closeManual(t)">
            <UiIcon class="btn-icon" :icon="iconClose" />
          </button>
        </header>

        <div class="user">
          <div class="meta" :class="{ 'has-theme-color': hasToastUserThemeColor(t.user), 'meta--subscription-gift': t.kind === 'subscription_gift' }" :style="toastUserNickStyle(t.user)">
            <button v-if="t.user" class="user-profile-trigger" type="button" @click.stop="openToastUserMiniProfile(t.user)"
                    :disabled="!canOpenToastUserMiniProfile(t.user)" :aria-label="`Открыть мини-профиль пользователя ${toastUserName(t.user)}`" aria-haspopup="dialog">
              <img v-minio-img="{ key: t.user.avatar_name ? `avatars/${t.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
              <div v-if="toastUserThemeIconSrcs(t.user).length" class="profile-theme-icons" aria-hidden="true">
                <img v-for="badgeSrc in toastUserThemeIconSrcs(t.user)" :key="`${t.user.id}-${badgeSrc}`" class="profile-theme-icon" :src="badgeSrc" alt="" />
              </div>
              <span class="nick">{{ toastUserName(t.user) }}</span>
            </button>
            <div v-if="t.details" class="sanction-text">
              <p class="sanction-text__lead">{{ t.text }}</p>
              <p class="sanction-text__details">{{ t.details }}</p>
            </div>
            <p v-else-if="t.text">{{ t.text }}</p>
          </div>
          <div v-if="t.actions && t.actions.length" class="actions">
            <UiButton
              v-for="a in t.actions"
              :key="a.label"
              class="action"
              :variant="a.style === 'neutral' ? 'white' : 'green'"
              size="middle"
              :text="a.label"
              :disabled="t._actionBusy"
              @click="runAction(t, a)"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
  </Teleport>

  <MiniProfile
    v-model:open="miniProfileOpen"
    :user-id="miniProfileUserId"
    :initial-profile="miniProfileInitial"
    show-stats-button
  />
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useNotifStore, useUserStore, inferFriendApiAction, resolveFriendsApiError } from '@/store'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId } from '@/services/miniProfile'
import type { ToastAction, ToastPayload, ToastUser } from '@/services/toast'
import { getProfileThemeOption } from '@/constants/profileThemes'
import { getProfileThemeBadgeSources } from '@/constants/profileIcons'

import MiniProfile from '@/views/MiniProfile.vue'
import UiIcon from '@/components/UiIcon.vue'
import UiButton from '@/components/UiButton.vue'

import defaultAvatar from '@/assets/svg/iconDefaultAvatarBlack.svg'
import iconClose from '@/assets/svg/iconClose.svg'
import iconCheckCircle from '@/assets/svg/iconCheckCircle.svg'
import iconInfo from '@/assets/svg/iconInfo.svg'
import iconDanger from '@/assets/svg/iconDanger.svg'
import iconAddFriends from '@/assets/svg/iconAddFriends.svg'
import iconInFriends from '@/assets/svg/iconInFriends.svg'
import iconLeave from '@/assets/svg/iconLeave.svg'
import iconPresent from '@/assets/svg/iconPresent.svg'
import toastSoundUrl from '@/assets/audio/short.mp3'

const router = useRouter()
const notif = useNotifStore()
const userStore = useUserStore()
const TOAST_TTL_MS = 30000
const toastSoundAudio = new Audio(toastSoundUrl)
toastSoundAudio.preload = 'auto'

function playToastSound(): void {
  try { toastSoundAudio.currentTime = 0 } catch {}
  const result = toastSoundAudio.play()
  if (result && typeof result.catch === 'function') result.catch(() => {})
}

type ToastItem = ToastPayload & {
  key: number
  _actionBusy?: boolean
  _closing?: boolean
}
type ToastToneClass = 'tone-yellow' | 'tone-orange' | 'tone-red' | 'tone-green' | 'tone-blue'
type ToastAppearance = { tone: ToastToneClass; icon: string }

const items = ref<ToastItem[]>([])
const miniProfileOpen = ref(false)
const miniProfileUserId = ref<number | null>(null)
const miniProfileInitial = ref<ToastUser | null>(null)

const hasToastUserThemeColor = (user?: ToastUser) => Boolean(getProfileThemeOption(user?.theme_color))
const toastUserNickStyle = (user?: ToastUser) => {
  const option = getProfileThemeOption(user?.theme_color)
  return option ? { '--toast-user-nick-theme': option.bg } : {}
}
const toastUserThemeIconSrcs = (user: ToastUser) => (
  getProfileThemeBadgeSources(user.theme_icon, user.role, { roleBadgeVariant: 'black', userId: user.id })
)
const toastUserName = (toastUser: ToastUser) => toastUser.username || `user${toastUser.id}`

function canOpenToastUserMiniProfile(toastUser?: ToastUser): boolean {
  return canOpenMiniProfileTarget({
    targetId: toastUser?.id,
    viewerId: normalizeMiniProfileUserId(userStore.user?.id),
    viewerRole: userStore.user?.role,
    targetRole: toastUser?.role,
  })
}

function openToastUserMiniProfile(toastUser?: ToastUser): void {
  if (!toastUser || !canOpenToastUserMiniProfile(toastUser)) return
  const userId = normalizeMiniProfileUserId(toastUser.id)
  if (userId <= 0) return
  miniProfileUserId.value = userId
  miniProfileInitial.value = toastUser
  miniProfileOpen.value = true
}

async function close(target: ToastItem | number) {
  const key = typeof target === 'number' ? target : target.key
  items.value = items.value.filter(x => x.key !== key)
}

async function closeManual(t: ToastItem){
  if (t.kind === 'room_request' && t.user?.id && t.room_id) {
    try {
      window.dispatchEvent(new CustomEvent('room-app-seen', { detail: { room_id: t.room_id, user_id: t.user.id } }))
    } catch {}
  }
  try { if (t.id && t.kind !== 'room_request') await notif.markReadVisible([t.id]) } catch {}
  t._closing = true
  setTimeout(() => { void close(t.key) }, 300)
}

async function runAction(t: ToastItem, action: ToastAction) {
  if (t._actionBusy) return
  t._actionBusy = true
  let actionOk = false
  try {
    if (!action) return
    if (action.kind === 'route') {
      await router.push(action.to)
    } else {
      const m = (action.method || 'post').toLowerCase()
      await (api as any)[m](action.url, action.body)
    }
    actionOk = true
  } catch (e: any) {
    if (action.kind === 'api') {
      const friendAction = inferFriendApiAction(action.url, action.method)
      if (friendAction !== 'unknown') {
        void alertDialog(resolveFriendsApiError(e, friendAction))
      } else {
        void alertDialog('Не удалось выполнить действие')
      }
    } else {
      void alertDialog('Не удалось перейти по ссылке')
    }
  } finally {
    t._actionBusy = false
    if (actionOk) await closeManual(t)
  }
}

function onTransEnd(e: TransitionEvent) {
  const el = e.target as HTMLElement
  if (!el.classList.contains('toast')) return
  const k = Number(el.dataset.key)
  const t = items.value.find(x => x.key === k)
  if (t && t._closing) { void close(t) }
}

function onApproved(e: any) {
  const p = e?.detail || {}
  const rid = Number(p.room_id)
  const uid = Number(p.user_id)
  if (!Number.isFinite(rid) || !Number.isFinite(uid)) return
  const targets = items.value.filter(t => t.kind === 'room_request' && t.room_id === rid && t.user?.id === uid)
  for (const t of targets) {
    t._closing = true
    setTimeout(() => { void close(t.key) }, 250)
  }
}

const defaultToastAppearance: ToastAppearance = { tone: 'tone-blue', icon: iconInfo }
const toastAppearances = new Map<string, ToastAppearance>([
  ['friend_request', { tone: 'tone-blue', icon: iconAddFriends }],
  ['friend_accept', { tone: 'tone-green', icon: iconInFriends }],
  ['room_request', { tone: 'tone-blue', icon: iconLeave }],
  ['room_invite', { tone: 'tone-green', icon: iconLeave }],
  ['approve', { tone: 'tone-green', icon: iconLeave }],
  ['room_access_revoked', { tone: 'tone-red', icon: iconLeave }],
  ['timeout', { tone: 'tone-orange', icon: iconDanger }],
  ['suspend', { tone: 'tone-yellow', icon: iconDanger }],
  ['ban', { tone: 'tone-red', icon: iconDanger }],
  ['avatar_reset', { tone: 'tone-red', icon: iconDanger }],
  ['nickname_reset', { tone: 'tone-red', icon: iconDanger }],
  ['role_granted', { tone: 'tone-green', icon: iconCheckCircle }],
  ['role_revoked', defaultToastAppearance],
  ['coin_topup', { tone: 'tone-green', icon: iconPresent }],
  ['coin_grant', { tone: 'tone-green', icon: iconPresent }],
  ['game_reward', { tone: 'tone-green', icon: iconPresent }],
  ['subscription_activated', { tone: 'tone-green', icon: iconPresent }],
  ['subscription_purchase', { tone: 'tone-green', icon: iconPresent }],
  ['subscription_gift', { tone: 'tone-green', icon: iconPresent }],
  ['subscription_expiring', { tone: 'tone-orange', icon: iconPresent }],
  ['subscription_expired', { tone: 'tone-red', icon: iconPresent }],
  ['subscription_compensation', { tone: 'tone-green', icon: iconPresent }],
  ['contact_request', defaultToastAppearance],
  ['contact_request_reply', defaultToastAppearance],
  ['game_winked', defaultToastAppearance],
  ['game_wink_spotted', defaultToastAppearance],
  ['game_knocked', defaultToastAppearance],
])

function toastAppearance(kind: string): ToastAppearance {
  return toastAppearances.get(kind) ?? defaultToastAppearance
}

function onToast(event: Event): void {
  const toast = (event as CustomEvent<ToastPayload>).detail
  if (!toast) return
  const key = Date.now() + Math.random()
  items.value.unshift({ ...toast, key })
  if (!toast.silent) playToastSound()
  window.setTimeout(() => {
    const current = items.value.find(x => x.key === key)
    if (!current) return
    current._closing = true
    window.setTimeout(() => { void close(key) }, 500)
  }, TOAST_TTL_MS)
}

onMounted(() => {
  window.addEventListener('toast', onToast)
  window.addEventListener('auth-room_app_approved', onApproved)
})

onBeforeUnmount(() => {
  window.removeEventListener('toast', onToast)
  window.removeEventListener('auth-room_app_approved', onApproved)
})
</script>

<style scoped lang="scss">
.toasts {
  display: flex;
  position: fixed;
  flex-direction: column;
  left: 40px;
  bottom: 40px;
  gap: 10px;
  z-index: 2000;
  pointer-events: none;
  .toast {
    --toast-border-color: #{$blue-500};
    display: flex;
    box-sizing: border-box;
    padding: 16px;
    gap: 8px;
    width: 450px;
    pointer-events: auto;
    border-left: 4px solid var(--toast-border-color);
    border-radius: 24px;
    background-color: $neutral-100;
    box-shadow: 0 2px 16px 0 rgba($neutral-black, 0.20);
    opacity: 1;
    transform: translateY(0);
    transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
    will-change: opacity, transform;
    &.closing {
      opacity: 0;
      transform: translateY(30px);
      pointer-events: none;
    }
    &.tone-yellow {
      --toast-border-color: #{$yellow-500};
    }
    &.tone-orange {
      --toast-border-color: #{$orange-500};
    }
    &.tone-red {
      --toast-border-color: #{$red-500};
    }
    &.tone-green {
      --toast-border-color: #{$green-500};
    }
    &.tone-blue {
      --toast-border-color: #{$blue-500};
    }
    .toast-icon {
      --ui-icon-width: 24px;
      --ui-icon-height: 24px;
      --ui-icon-color: var(--toast-border-color);
    }
    .toast-div {
      display: flex;
      flex-direction: column;
      width: 386px;
      gap: 16px;
      header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        span {
          color: $neutral-black;
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        button {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          width: 24px;
          height: 24px;
          border: none;
          background: none;
          cursor: pointer;
          .btn-icon {
            --ui-icon-width: 24px;
            --ui-icon-height: 24px;
            --ui-icon-color: #{$neutral-black};
          }
          &:not(:disabled):hover,
          &:not(:disabled):focus-visible,
          &:not(:disabled):active {
            .btn-icon {
              --ui-icon-color: #{$green-600};
            }
          }
        }
      }
      .user {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        .meta {
          display: flex;
          align-items: center;
          gap: 8px;
          min-width: 0;
          &.meta--subscription-gift {
            flex-direction: column;
            align-items: flex-start;
          }
          &.has-theme-color .nick {
            background: var(--toast-user-nick-theme);
            background-clip: text;
            color: transparent;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
          }
          .user-profile-trigger {
            display: flex;
            align-items: center;
            min-width: 0;
            padding: 0;
            gap: 8px;
            border: 0;
            outline: 0;
            background: none;
            &:not(:disabled) {
              cursor: pointer;
            }
          }
          img {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            object-fit: cover;
          }
          .profile-theme-icons {
            display: inline-flex;
            align-items: center;
            margin-left: -8px;
            .profile-theme-icon {
              border-radius: 0;
              object-fit: contain;
            }
          }
          span {
            max-width: 170px;
            color: $neutral-900;
            font-family: Hauora-Regular;
            font-size: 16px;
            line-height: 22px;
            letter-spacing: -0.32px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          p {
            margin: 0;
            color: $neutral-500;
            font-family: Hauora-Regular;
            font-size: 16px;
            line-height: 22px;
            letter-spacing: -0.32px;
          }
          .sanction-text {
            display: flex;
            flex-direction: column;
            gap: 12px;
            min-width: 0;
            .sanction-text__lead {
              color: $neutral-900;
              font-family: Hauora-Bold;
              font-size: 16px;
              line-height: 18px;
              letter-spacing: -0.32px;
            }
            .sanction-text__details {
              color: $neutral-500;
            }
          }
        }
        .actions {
          display: flex;
          align-items: center;
          gap: 4px;
        }
      }
    }
  }
}

</style>
