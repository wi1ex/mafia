<template>
  <Teleport to="#desktop-teleport-root">
  <div class="toasts" :class="{ 'toasts--scrollable': items.length > 1 && items.some(t => t.kind === 'gift_received') }" @transitionend="onTransEnd">
    <div v-for="t in items" :key="t.key" class="toast" :data-key="t.key" :class="[toastAppearance(t.kind).tone, { closing: t._closing }]">
      <UiIcon class="toast-icon" :icon="toastAppearance(t.kind).icon" />
      <div class="toast-div">
        <header>
          <span>{{ t.title }}</span>
          <button type="button" aria-label="Закрыть уведомление" :disabled="t.kind === 'gift_received' && t._actionBusy" @click="dismissToast(t)">
            <UiIcon class="btn-icon" :icon="iconClose" />
          </button>
        </header>

        <div class="user">
          <div class="meta" :class="{ 'has-theme-color': hasToastUserThemeColor(t.user), 'meta--gift': isGiftReceipt(t.kind) }" :style="toastUserNickStyle(t.user)">
            <div v-if="t.user || isGiftReceipt(t.kind)" class="profile-line">
              <button v-if="t.user" class="user-profile-trigger" type="button" @click.stop="openToastUserMiniProfile(t.user)"
                      :disabled="!canOpenToastUserMiniProfile(t.user)" :aria-label="`Открыть мини-профиль пользователя ${toastUserName(t.user)}`" aria-haspopup="dialog">
                <img v-minio-img="{ key: t.user.avatar_name ? `avatars/${t.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                <div v-if="toastUserThemeIconSrcs(t.user).length" class="profile-theme-icons" aria-hidden="true">
                  <img v-for="badgeSrc in toastUserThemeIconSrcs(t.user)" :key="`${t.user.id}-${badgeSrc}`" class="profile-theme-icon" :src="badgeSrc" alt="" />
                </div>
                <span class="nick">{{ toastUserName(t.user) }}</span>
              </button>
              <div v-else-if="t.kind === 'gift_received'" class="user-profile-trigger">
                <img :src="defaultAvatar" alt="" />
                <span class="nick">{{ t.text }}</span>
              </div>
              <span v-if="t.kind === 'subscription_gift'" class="gift-action">{{ subscriptionGiftReceiptLine(t) }}</span>
            </div>
            <template v-if="!isGiftReceipt(t.kind)">
              <div v-if="t.details" class="sanction-text">
                <p class="sanction-text__lead">{{ t.text }}</p>
                <p class="sanction-text__details">{{ t.details }}</p>
              </div>
              <p v-else-if="t.text">{{ t.text }}</p>
            </template>
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
  <GiftOpeningModal v-if="openedGift" :key="openedGift.id" :gift="openedGift" :can-view-profile="giftProfileUser !== null"
                    @close="openedGift = null" @view-profile="viewGiftProfile" />
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore, useNotifStore, useUserStore, inferFriendApiAction, resolveFriendsApiError } from '@/store'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId } from '@/services/miniProfile'
import { parseSocketToast, type ToastAction, type ToastPayload, type ToastUser } from '@/services/toast'
import type { GiftCollectionItem } from '@/services/gifts'
import { getProfileThemeOption } from '@/constants/profileThemes'
import { getProfileThemeBadgeSources } from '@/constants/profileIcons'

import MiniProfile from '@/views/MiniProfile.vue'
import GiftOpeningModal from '@/views/GiftOpeningModal.vue'
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
import iconSubscribe from '@/assets/svg/iconSubscribe.svg'
import toastSoundUrl from '@/assets/audio/short.mp3'

const router = useRouter()
const auth = useAuthStore()
const notif = useNotifStore()
const userStore = useUserStore()
const TOAST_TTL_MS = 30000
const GIFT_TOAST_TTL_MS = 10 * 60 * 1000
const PENDING_GIFT_TOAST_PAGE_SIZE = 20
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
const openedGift = ref<GiftCollectionItem | null>(null)
const miniProfileOpen = ref(false)
const miniProfileUserId = ref<number | null>(null)
const miniProfileInitial = ref<ToastUser | null>(null)
const shownGiftToastIds = new Set<number>()
let giftToastRequest: AbortController | null = null

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

const giftProfileUser = computed<ToastUser | null>(() => {
  const user = userStore.user
  if (!auth.isAuthed || !user) return null
  const profile = {
    id: normalizeMiniProfileUserId(user.id),
    username: user.username,
    avatar_name: user.avatar_name,
    role: user.role,
    theme_color: userStore.activeProfileThemeColor,
    theme_icon: userStore.activeProfileThemeIcon,
  }
  return canOpenToastUserMiniProfile(profile) ? profile : null
})

function openToastUserMiniProfile(toastUser?: ToastUser): void {
  if (!toastUser || !canOpenToastUserMiniProfile(toastUser)) return
  const userId = normalizeMiniProfileUserId(toastUser.id)
  if (userId <= 0) return
  miniProfileUserId.value = userId
  miniProfileInitial.value = toastUser
  miniProfileOpen.value = true
}

function viewGiftProfile(): void {
  const profile = giftProfileUser.value
  if (!openedGift.value || !profile) return
  openedGift.value = null
  openToastUserMiniProfile(profile)
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

function giftToastAcquisitionId(toast: ToastPayload): number | undefined {
  if (toast.kind !== 'gift_received') return
  const action = toast.actions?.find(action => action.kind === 'gift_open')
  if (action && Number.isSafeInteger(action.acquisition_id) && action.acquisition_id > 0) return action.acquisition_id
}

async function dismissGiftToast(acquisitionId: number): Promise<void> {
  await api.post(`/gifts/purchases/${acquisitionId}/dismiss-toast`)
}

async function dismissToast(t: ToastItem): Promise<void> {
  const acquisitionId = giftToastAcquisitionId(t)
  if (acquisitionId === undefined) return closeManual(t)
  if (t._actionBusy || t._closing) return

  const sessionId = auth.sessionId
  t._actionBusy = true
  try {
    await dismissGiftToast(acquisitionId)
    if (sessionId === auth.sessionId) await closeManual(t)
  } catch {
    if (sessionId === auth.sessionId) void alertDialog('Не удалось закрыть уведомление о подарке. Попробуйте ещё раз.')
  } finally {
    t._actionBusy = false
  }
}

async function runAction(t: ToastItem, action: ToastAction) {
  if (t._actionBusy) return
  t._actionBusy = true
  const sessionId = auth.sessionId
  let actionOk = false
  try {
    if (!action) return
    if (action.kind === 'route') {
      await router.push(action.to)
    } else if (action.kind === 'gift_open') {
      const acquisitionId = action.acquisition_id
      if (!Number.isSafeInteger(acquisitionId) || acquisitionId <= 0) throw new Error('Invalid gift')
      const { data } = await api.get<GiftCollectionItem>(`/gifts/purchases/${acquisitionId}`)
      if (sessionId !== auth.sessionId) return
      await dismissGiftToast(acquisitionId)
      if (sessionId !== auth.sessionId) return
      openedGift.value = data
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
    } else if (action.kind === 'gift_open') {
      if (sessionId !== auth.sessionId) return
      void alertDialog(e?.response?.status === 404
        ? 'Подарок больше недоступен.'
        : 'Не удалось открыть подарок. Попробуйте ещё раз.')
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
  ['subscription_activated', { tone: 'tone-green', icon: iconSubscribe }],
  ['subscription_purchase', { tone: 'tone-green', icon: iconSubscribe }],
  ['subscription_gift', { tone: 'tone-green', icon: iconSubscribe }],
  ['gift_purchase', { tone: 'tone-green', icon: iconPresent }],
  ['gift_received', { tone: 'tone-green', icon: iconPresent }],
  ['subscription_expiring', { tone: 'tone-orange', icon: iconSubscribe }],
  ['subscription_expired', { tone: 'tone-red', icon: iconSubscribe }],
  ['subscription_compensation', { tone: 'tone-green', icon: iconSubscribe }],
  ['contact_request', defaultToastAppearance],
  ['contact_request_reply', defaultToastAppearance],
  ['game_winked', defaultToastAppearance],
  ['game_wink_spotted', defaultToastAppearance],
  ['game_knocked', defaultToastAppearance],
])

function toastAppearance(kind: string): ToastAppearance {
  return toastAppearances.get(kind) ?? defaultToastAppearance
}

function isGiftReceipt(kind: string): boolean {
  return kind === 'subscription_gift' || kind === 'gift_received'
}

function subscriptionGiftReceiptLine(toast: ToastPayload): string {
  if (!toast.user) return toast.text
  return toast.subscriptionGiftDuration
    ? `подарил вам подписку на ${toast.subscriptionGiftDuration}`
    : 'подарил вам подписку'
}

function showToast(toast: ToastPayload): void {
  const acquisitionId = giftToastAcquisitionId(toast)
  if (acquisitionId !== undefined) {
    if (!auth.isAuthed || shownGiftToastIds.has(acquisitionId)) return
    shownGiftToastIds.add(acquisitionId)
  }
  const key = Date.now() + Math.random()
  items.value.unshift({ ...toast, key })
  if (!toast.silent) playToastSound()
  window.setTimeout(() => {
    const current = items.value.find(x => x.key === key)
    if (!current) return
    current._closing = true
    window.setTimeout(() => { void close(key) }, 500)
  }, isGiftReceipt(toast.kind) ? GIFT_TOAST_TTL_MS : TOAST_TTL_MS)
}

function onToast(event: Event): void {
  const toast = (event as CustomEvent<ToastPayload>).detail
  if (toast) showToast(toast)
}

async function loadPendingGiftToasts(): Promise<void> {
  giftToastRequest?.abort()
  giftToastRequest = null
  const sessionId = auth.sessionId
  if (!sessionId) return

  const controller = new AbortController()
  giftToastRequest = controller
  let afterId = 0
  try {
    while (true) {
      const { data } = await api.get<unknown[]>('/gifts/pending-toasts', {
        params: { after_id: afterId, limit: PENDING_GIFT_TOAST_PAGE_SIZE }, signal: controller.signal,
      })
      if (controller.signal.aborted || sessionId !== auth.sessionId) return

      const previousAfterId = afterId
      for (const payload of data) {
        const toast = parseSocketToast(payload)
        if (!toast) continue
        const acquisitionId = giftToastAcquisitionId(toast)
        if (acquisitionId === undefined || acquisitionId <= afterId) continue
        afterId = acquisitionId
        showToast(toast)
      }
      if (data.length < PENDING_GIFT_TOAST_PAGE_SIZE || afterId === previousAfterId) return
    }
  } catch {
    // Pending gifts stay on the server and can be loaded on the next connection.
  } finally {
    if (giftToastRequest === controller) giftToastRequest = null
  }
}

watch(() => auth.sessionId, () => {
  shownGiftToastIds.clear()
  items.value = []
  openedGift.value = null
  void loadPendingGiftToasts()
})

onMounted(() => {
  window.addEventListener('toast', onToast)
  window.addEventListener('auth-connected', loadPendingGiftToasts)
  window.addEventListener('auth-room_app_approved', onApproved)
  void loadPendingGiftToasts()
})

onBeforeUnmount(() => {
  giftToastRequest?.abort()
  window.removeEventListener('toast', onToast)
  window.removeEventListener('auth-connected', loadPendingGiftToasts)
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
  &.toasts--scrollable {
    max-height: calc(var(--app-viewport-height, 100dvh) - 80px);
    padding: 12px;
    margin: -12px;
    overflow-y: auto;
    overscroll-behavior-y: contain;
    scrollbar-width: thin;
    pointer-events: auto;
    .toast {
      flex-shrink: 0;
    }
  }
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
          .profile-line {
            display: contents;
          }
          &.meta--gift {
            flex-direction: column;
            align-items: flex-start;
            .profile-line {
              display: flex;
              align-items: center;
              gap: 4px;
              max-width: 100%;
              .gift-action {
                max-width: 100%;
                white-space: normal;
                overflow-wrap: anywhere;
              }
            }
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
            &:enabled {
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
