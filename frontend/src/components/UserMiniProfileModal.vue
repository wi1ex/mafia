<template>
  <Teleport to="body">
    <Transition name="user-mini-profile-fade">
      <div v-if="open" class="user-mini-profile-overlay" role="presentation" @pointerdown.stop.self="close">
        <section class="user-mini-profile-panel" :class="{ 'stats-mode': view === 'stats' }" :style="profilePanelStyle"
                 role="dialog" aria-modal="true" :aria-label="`Мини-профиль ${displayName}`" @pointerdown.stop>
          <header class="profile-top">
            <div class="profile-identity">
              <button class="profile-avatar-trigger" type="button" :disabled="!hasAvatar" aria-label="Open avatar" @click="openAvatarLightbox">
                <img ref="avatarImageEl" class="profile-avatar" v-minio-img="{ key: avatarKey, placeholder: defaultAvatar, lazy: false, animated: true }" alt="avatar" />
              </button>
              <div class="profile-icon-name">
                <div v-if="profileThemeIconSrcs.length" class="profile-theme-icons" aria-hidden="true">
                  <img v-for="badgeSrc in profileThemeIconSrcs" :key="badgeSrc" class="profile-theme-icon" :src="badgeSrc" alt="" />
                </div>
                <div class="profile-title">
                  <span class="profile-name">{{ displayName }}</span>
                </div>
              </div>
            </div>
            <button class="close-button" type="button" aria-label="Закрыть" @click="close">
              <img :src="iconClose" alt="" />
            </button>
          </header>

          <template v-if="view === 'profile'">
            <p v-if="loading && !profileLoadedForTarget" class="state">Загрузка...</p>
            <p v-else-if="loadError" class="state state-danger">{{ loadError }}</p>

            <div v-else class="profile-dates" aria-label="Даты профиля">
              <div class="date-row">
                <span>Дата регистрации</span>
                <strong>{{ registeredAtLabel }}</strong>
              </div>
              <div class="date-row">
                <span>Последняя игра</span>
                <strong>{{ lastGameAtLabel }}</strong>
              </div>
              <div class="date-row">
                <span>Последний онлайн</span>
                <strong>{{ lastOnlineLabel }}</strong>
              </div>
            </div>

            <div class="profile-actions">
              <button v-if="showStatsButton" class="profile-action secondary" type="button" @click="view = 'stats'">
                Статистика пользователя
              </button>
              <button v-if="showFriendAction" class="profile-action friend-action" :class="`status-${friendStatusClass}`"
                      type="button" :disabled="friendDisabled" @click="onFriendAction(friendActionKind)">
                <img :src="friendActionIcon" alt="" />
                <span>{{ friendActionLabel }}</span>
              </button>
            </div>
          </template>

          <template v-else>
            <div class="stats-toolbar">
              <button class="profile-action secondary" type="button" @click="view = 'profile'">Назад к профилю</button>
            </div>
            <ProfileStatsTab :stats-url="resolvedStatsUrl" />
          </template>
        </section>
      </div>
    </Transition>
    <Transition name="avatar-lightbox-transition">
      <div v-if="avatarLightboxOpen && avatarLightboxSrc" class="avatar-lightbox-overlay" role="dialog"
           aria-modal="true" aria-label="Avatar preview" @pointerdown.stop @click.stop @click.self="closeAvatarLightbox">
        <img class="avatar-lightbox-image" :src="avatarLightboxSrc" alt="avatar" />
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { formatLocalDateTime } from '@/services/datetime'
import { isMiniProfilePrivilegedViewer, normalizeMiniProfileRole } from '@/services/miniProfile'
import { buildProfileThemeBgStyle } from '@/constants/profileThemes'
import { getProfileThemeBadgeSources } from '@/constants/profileThemeIcons'
import {
  useFriendsStore,
  useUserStore,
  resolveFriendsApiError,
  shouldRefreshFriendsStateAfterError,
  type FriendApiAction,
  type FriendStatus,
} from '@/store'
import ProfileStatsTab from '@/components/ProfileStatsTab.vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconClose from '@/assets/svg/close.svg'
import iconAddFriends from '@/assets/svg/addFriends.svg'
import iconInFriends from '@/assets/svg/inFriends.svg'
import iconRecieveFriends from '@/assets/svg/recieveFriends.svg'
import iconSendFriends from '@/assets/svg/sendFriends.svg'

type FriendActionKind = 'add' | 'remove' | 'incoming' | 'outgoing'

type MiniProfileInitial = {
  id?: number | null
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  theme_color?: string | null
  theme_icon?: string | null
  profile_theme_color?: string | null
  profile_theme_icon?: string | null
  friend_status?: FriendStatus | null
  deleted?: boolean | null
  deleted_at?: string | null
  kind?: 'incoming' | 'outgoing' | 'online' | 'offline' | string | null
}

type MiniProfileResponse = {
  id: number
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  deleted?: boolean
  registered_at?: string | null
  last_visit_at?: string | null
  last_game_at?: string | null
  online?: boolean
  subscription_active?: boolean
  profile_theme_color?: string | null
  profile_theme_icon?: string | null
  friend_status?: FriendStatus | null
}

const props = withDefaults(defineProps<{
  open: boolean
  userId?: number | null
  initialProfile?: MiniProfileInitial | null
  showStatsButton?: boolean
  adminMode?: boolean
  allowDeleted?: boolean
  statsUrl?: string | null
  refreshFriendsListOnAction?: boolean
  refreshFriendsRoomId?: number | null
}>(), {
  userId: null,
  initialProfile: null,
  showStatsButton: false,
  adminMode: false,
  allowDeleted: false,
  statsUrl: null,
  refreshFriendsListOnAction: false,
  refreshFriendsRoomId: null,
})

const emit = defineEmits<{
  'update:open': [value: boolean]
  'friend-status-change': [userId: number, status: FriendStatus]
}>()

const friends = useFriendsStore()
const userStore = useUserStore()
const loading = ref(false)
const loadError = ref('')
const profile = ref<MiniProfileResponse | null>(null)
const friendStatus = ref<FriendStatus>('none')
const friendBusy = ref(false)
const view = ref<'profile' | 'stats'>('profile')
const avatarImageEl = ref<HTMLImageElement | null>(null)
const avatarLightboxOpen = ref(false)
const avatarLightboxSrc = ref('')
let requestSeq = 0

const targetUserId = computed(() => {
  const raw = props.userId ?? props.initialProfile?.id ?? 0
  const uid = Number(raw)
  return Number.isFinite(uid) && uid > 0 ? Math.trunc(uid) : 0
})
const profileLoadedForTarget = computed(() => Boolean(profile.value && profile.value.id === targetUserId.value))
const viewerUserId = computed(() => Number(userStore.user?.id || 0))
const viewerRole = computed(() => normalizeMiniProfileRole(userStore.user?.role))
const privilegedViewer = computed(() => isMiniProfilePrivilegedViewer(viewerRole.value, props.adminMode))
const initialTargetDeleted = computed(() => {
  const initialId = Number(props.initialProfile?.id || 0)
  if (!Number.isFinite(initialId) || initialId <= 0 || Math.trunc(initialId) !== targetUserId.value) return false
  return Boolean(props.initialProfile?.deleted || props.initialProfile?.deleted_at)
})
const targetDeleted = computed(() => Boolean(
  (profileLoadedForTarget.value && profile.value?.deleted)
  || (!profileLoadedForTarget.value && initialTargetDeleted.value)
))

const displayName = computed(() => {
  if (profileLoadedForTarget.value && profile.value?.username) return profile.value.username
  if (props.initialProfile?.username) return props.initialProfile.username
  return targetUserId.value > 0 ? `user${targetUserId.value}` : 'Пользователь'
})
const avatarName = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.avatar_name || ''
  return props.initialProfile?.avatar_name || ''
})
const avatarKey = computed(() => {
  const name = String(avatarName.value || '').trim()
  if (!name) return ''
  return name.startsWith('avatars/') ? name : `avatars/${name}`
})
const hasAvatar = computed(() => Boolean(avatarKey.value))
const profileThemeColor = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.profile_theme_color || null
  return props.initialProfile?.profile_theme_color || props.initialProfile?.theme_color || null
})
const profileThemeIcon = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.profile_theme_icon || null
  return props.initialProfile?.profile_theme_icon || props.initialProfile?.theme_icon || null
})
const profileRole = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.role || null
  return props.initialProfile?.role || null
})
const profilePanelStyle = computed(() => buildProfileThemeBgStyle(profileThemeColor.value))
const profileThemeIconSrcs = computed(() => getProfileThemeBadgeSources(profileThemeIcon.value, profileRole.value))
const registeredAtLabel = computed(() => formatLocalDateTime(profile.value?.registered_at))
const lastGameAtLabel = computed(() => formatLocalDateTime(profile.value?.last_game_at))
const lastOnlineLabel = computed(() => (profile.value?.online ? 'Онлайн' : formatLocalDateTime(profile.value?.last_visit_at)))
const resolvedStatsUrl = computed(() => {
  const provided = String(props.statsUrl || '').trim()
  return provided || `/users/${targetUserId.value}/stats`
})

const friendStatusClass = computed(() => (friendStatus.value === 'self' ? 'none' : friendStatus.value))
const friendActionLabel = computed(() => {
  if (loading.value && !profileLoadedForTarget.value && friendStatus.value === 'none') return 'Загрузка...'
  if (friendStatus.value === 'none') return 'Добавить в друзья'
  if (friendStatus.value === 'friends') return 'В друзьях'
  if (friendStatus.value === 'outgoing') return 'Отменить заявку'
  if (friendStatus.value === 'incoming') return 'Входящий запрос'
  return ''
})
const friendActionIcon = computed(() => {
  if (friendStatus.value === 'friends') return iconInFriends
  if (friendStatus.value === 'outgoing') return iconSendFriends
  if (friendStatus.value === 'incoming') return iconRecieveFriends
  return iconAddFriends
})
const friendActionKind = computed<FriendActionKind>(() => {
  if (friendStatus.value === 'none') return 'add'
  if (friendStatus.value === 'friends') return 'remove'
  if (friendStatus.value === 'outgoing') return 'outgoing'
  return 'incoming'
})
const friendDisabled = computed(() => (
  friendBusy.value
  || friendStatus.value === 'self'
  || targetDeleted.value
  || (loading.value && !profileLoadedForTarget.value && friendStatus.value === 'none')
))
const showFriendAction = computed(() => (
  targetUserId.value > 0
  && !targetDeleted.value
  && friendStatus.value !== 'self'
  && friendActionLabel.value !== ''
))
const showStatsButton = computed(() => Boolean(
  props.showStatsButton
  && targetUserId.value > 0
  && (privilegedViewer.value || friendStatus.value === 'friends' || friendStatus.value === 'self')
))

function normalizeFriendStatus(value: unknown): FriendStatus {
  if (value === 'self' || value === 'friends' || value === 'outgoing' || value === 'incoming' || value === 'none') return value
  return 'none'
}

function inferInitialFriendStatus(): FriendStatus {
  if (targetUserId.value > 0 && viewerUserId.value === targetUserId.value) return 'self'
  const direct = normalizeFriendStatus(props.initialProfile?.friend_status)
  if (direct !== 'none') return direct
  const kind = String(props.initialProfile?.kind || '')
  if (kind === 'incoming') return 'incoming'
  if (kind === 'outgoing') return 'outgoing'
  if (kind === 'online' || kind === 'offline') return 'friends'
  return 'none'
}

function close() {
  closeAvatarLightbox()
  emit('update:open', false)
}

function closeAvatarLightbox() {
  avatarLightboxOpen.value = false
  avatarLightboxSrc.value = ''
}

function openAvatarLightbox() {
  if (!hasAvatar.value) return
  const src = avatarImageEl.value?.currentSrc || avatarImageEl.value?.src || ''
  if (!src) return
  avatarLightboxSrc.value = src
  avatarLightboxOpen.value = true
}

function applyFriendStatus(status: FriendStatus) {
  friendStatus.value = status
  if (targetUserId.value > 0) emit('friend-status-change', targetUserId.value, status)
}

async function refreshFriendStatus() {
  const uid = targetUserId.value
  if (uid <= 0 || uid === viewerUserId.value) {
    applyFriendStatus('self')
    return
  }

  try {
    applyFriendStatus(await friends.fetchStatus(uid))
  } catch {}
}

async function refreshFriendsListIfNeeded() {
  if (!props.refreshFriendsListOnAction) return
  await friends.fetchList(props.refreshFriendsRoomId)
  await friends.fetchIncomingCount()
}

async function loadProfile() {
  const uid = targetUserId.value
  if (uid <= 0) return

  const seq = ++requestSeq
  loading.value = true
  loadError.value = ''
  try {
    const reqConfig = props.allowDeleted ? { params: { allow_deleted: 1 } } : undefined
    const { data } = await api.get<MiniProfileResponse>(`/users/${uid}/mini_profile`, reqConfig)
    if (seq !== requestSeq) return
    profile.value = {
      id: Number(data?.id || uid),
      username: data?.username ?? null,
      avatar_name: data?.avatar_name ?? null,
      role: data?.role ?? null,
      deleted: Boolean(data?.deleted),
      registered_at: data?.registered_at ?? null,
      last_visit_at: data?.last_visit_at ?? null,
      last_game_at: data?.last_game_at ?? null,
      online: Boolean(data?.online),
      subscription_active: Boolean(data?.subscription_active),
      profile_theme_color: data?.profile_theme_color ?? null,
      profile_theme_icon: data?.profile_theme_icon ?? null,
      friend_status: normalizeFriendStatus(data?.friend_status),
    }
    applyFriendStatus(normalizeFriendStatus(data?.friend_status))
  } catch {
    if (seq !== requestSeq) return
    loadError.value = 'Не удалось загрузить профиль'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

async function onFriendAction(kind: FriendActionKind) {
  const uid = targetUserId.value
  if (uid <= 0 || friendBusy.value) return

  friendBusy.value = true
  let actionForError: FriendApiAction = 'unknown'
  try {
    if (kind === 'add') {
      actionForError = 'send'
      await friends.sendRequest(uid)
      applyFriendStatus('outgoing')
    } else if (kind === 'remove') {
      const ok = await confirmDialog({
        title: 'Удалить из друзей',
        text: 'Вы уверены, что хотите удалить пользователя из друзей?',
        confirmText: 'Удалить',
        cancelText: 'Отмена',
      })
      if (!ok) return
      actionForError = 'remove'
      await friends.removeFriend(uid)
      applyFriendStatus('none')
    } else if (kind === 'outgoing') {
      const ok = await confirmDialog({
        title: 'Отменить заявку',
        text: `Вы уверены, что хотите отменить заявку в друзья для пользователя ${displayName.value}?`,
        confirmText: 'Отменить',
        cancelText: 'Отмена',
      })
      if (!ok) return
      actionForError = 'cancel'
      await friends.cancelOutgoingRequest(uid)
      applyFriendStatus('none')
    } else if (kind === 'incoming') {
      const ok = await confirmDialog({
        title: 'Запрос в друзья',
        text: 'Принять запрос в друзья?',
        confirmText: 'Принять',
        cancelText: 'Отклонить',
      })
      if (ok) {
        actionForError = 'accept'
        await friends.acceptRequest(uid)
        applyFriendStatus('friends')
      } else {
        actionForError = 'decline'
        await friends.declineRequest(uid)
        applyFriendStatus('none')
      }
    }
    await refreshFriendsListIfNeeded()
  } catch (e: any) {
    if (shouldRefreshFriendsStateAfterError(e)) void refreshFriendStatus()
    void alertDialog(resolveFriendsApiError(e, actionForError))
  } finally {
    friendBusy.value = false
  }
}

function onKeydown(e: KeyboardEvent) {
  if (!props.open || e.key !== 'Escape') return
  if (avatarLightboxOpen.value) {
    closeAvatarLightbox()
    return
  }
  close()
}

function onFriendsUpdate(e: Event) {
  const detail = (e as CustomEvent)?.detail || {}
  const uid = Number(detail.user_id)
  if (!props.open || uid !== targetUserId.value) return
  applyFriendStatus(normalizeFriendStatus(detail.status))
}

watch([() => props.open, targetUserId], ([open, uid]) => {
  if (!open) {
    requestSeq += 1
    loading.value = false
    loadError.value = ''
    view.value = 'profile'
    closeAvatarLightbox()
    return
  }

  profile.value = null
  view.value = 'profile'
  loadError.value = ''
  closeAvatarLightbox()
  applyFriendStatus(inferInitialFriendStatus())
  if (uid > 0) void loadProfile()
}, { immediate: true })

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('auth-friends_update', onFriendsUpdate)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('auth-friends_update', onFriendsUpdate)
})
</script>

<style scoped lang="scss">
.user-mini-profile-overlay {
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($black, 0.5);
  backdrop-filter: blur(5px);
  z-index: 1500;
  .user-mini-profile-panel {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 20px;
    gap: 20px;
    width: 500px;
    height: min-content;
    border-radius: 10px;
    background-color: var(--user-theme-bg, $dark);
    overflow-y: auto;
    scrollbar-width: none;
    transition: width 0.25s ease-in-out, height 0.25s ease-in-out;
    &.stats-mode {
      gap: 20px;
      width: min(1250px, calc(100vw - 80px));
      height: calc(100dvh - 80px);
    }
    .profile-top {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
    }
    .profile-identity {
      display: flex;
      align-items: flex-start;
      min-width: 0;
      gap: 5px;
    }
    .profile-avatar-trigger {
      display: flex;
      position: relative;
      flex: 0 0 auto;
      align-items: center;
      justify-content: center;
      padding: 0;
      border: none;
      border-radius: 50%;
      background: transparent;
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      cursor: zoom-in;
      &:disabled {
        cursor: default;
      }
    }
    .profile-icon-name {
      display: flex;
      align-items: center;
      padding: 0 5px;
      gap: 5px;
    }
    .profile-avatar {
      width: 120px;
      height: 120px;
      border-radius: 50%;
      object-fit: cover;
    }
    .profile-theme-icon {
      flex: 0 0 auto;
      width: 26px;
      height: 38px;
      object-fit: contain;
    }
    .profile-theme-icons {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      flex: 0 0 auto;
    }
    .profile-title {
      display: flex;
      flex-direction: column;
      min-width: 0;
      .profile-name {
        max-width: 260px;
        font-size: 24px;
        line-height: 1.2;
        font-family: Manrope-SemiBold;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }
    .close-button {
      display: flex;
      flex: 0 0 auto;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 30px;
      height: 30px;
      border: none;
      border-radius: 5px;
      background-color: $graphite;
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      cursor: pointer;
      transition: background-color 0.25s ease-in-out;
      &:hover {
        background-color: $lead;
      }
      img {
        width: 20px;
        height: 20px;
      }
    }
    .state {
      margin: 0;
      color: $ashy;
      text-align: center;
      font-size: 16px;
      &.state-danger {
        color: $red;
      }
    }
    .profile-dates {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .date-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px;
      border-radius: 5px;
      background-color: rgba($graphite, 0.5);
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      span {
        color: $fg;
        font-size: 14px;
      }
      strong {
        color: $fg;
        text-align: right;
        font-size: 14px;
        font-family: Manrope-SemiBold;
        font-weight: normal;
      }
    }
    .profile-actions,
    .stats-toolbar {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .profile-action {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      min-height: 40px;
      border: none;
      border-radius: 5px;
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      color: $bg;
      font-size: 16px;
      font-family: Manrope-SemiBold;
      cursor: pointer;
      transition: background-color 0.25s ease-in-out, opacity 0.25s ease-in-out;
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      img {
        width: 24px;
        height: 24px;
      }
      &.secondary {
        background-color: $fg;
        &:not(:disabled):hover {
          background-color: $white;
        }
      }
      &.status-none {
        background-color: $fg;
        &:not(:disabled):hover {
          background-color: $white;
        }
      }
      &.status-friends {
        background-color: rgba($green, 0.75);
        &:not(:disabled):hover {
          background-color: $green;
        }
      }
      &.status-outgoing {
        background-color: rgba($yellow, 0.75);
        &:not(:disabled):hover {
          background-color: $yellow;
        }
      }
      &.status-incoming {
        background-color: rgba($orange, 0.75);
        &:not(:disabled):hover {
          background-color: $orange;
        }
      }
    }
  }
}

.avatar-lightbox-overlay {
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  overflow: hidden;
  background:
    radial-gradient(circle at top, rgba($white, 0.1) 0%, rgba($white, 0) 100%),
    rgba($black, 0.25);
  backdrop-filter: blur(15px);
  z-index: 1600;
  &::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: min(75vw, 75vh, 750px);
    height: min(75vw, 75vh, 750px);
    border-radius: 50%;
    background: radial-gradient(circle, rgba($white, 0.25) 0%, rgba($white, 0.1) 25%, rgba($white, 0) 75%);
    transform: translate(-50%, -50%);
    z-index: 0;
  }
  .avatar-lightbox-image {
    position: relative;
    z-index: 1;
    width: min(75vw, 75vh, 750px);
    height: min(75vw, 75vh, 750px);
    border-radius: 50%;
    object-fit: cover;
    box-shadow: 0 15px 30px rgba($black, 0.5);
  }
}

.user-mini-profile-fade-enter-active,
.user-mini-profile-fade-leave-active {
  transition: opacity 0.25s ease-in-out;
  .user-mini-profile-panel {
    transition: transform 0.25s ease-in-out;
  }
}
.user-mini-profile-fade-enter-from,
.user-mini-profile-fade-leave-to {
  opacity: 0;
  .user-mini-profile-panel {
    transform: translateY(10px) scale(0.9);
  }
}

.avatar-lightbox-transition-enter-active,
.avatar-lightbox-transition-leave-active {
  transition: opacity 0.25s ease-in-out;
  .avatar-lightbox-image {
    transition: transform 0.25s ease-in-out, opacity 0.25s ease-in-out;
  }
}
.avatar-lightbox-transition-enter-from,
.avatar-lightbox-transition-leave-to {
  opacity: 0;
  .avatar-lightbox-image {
    opacity: 0;
    transform: translateY(10px) scale(0.9);
  }
}

@media (max-width: 1280px) {
  .user-mini-profile-overlay {
    .user-mini-profile-panel {
      padding: 10px;
      gap: 10px;
      width: 350px;
      &.stats-mode {
        gap: 10px;
        width: min(700px, 100vw - 40px);
        height: calc(100dvh - 40px);
      }
      .profile-icon-name {
        padding: 0 3px;
        gap: 3px;
      }
      .profile-avatar {
        width: 80px;
        height: 80px;
      }
      .profile-theme-icon {
        width: 20px;
        height: 30px;
      }
      .profile-theme-icons {
        gap: 3px;
      }
      .profile-title {
        .profile-name {
          max-width: 180px;
          font-size: 18px;
        }
      }
      .close-button {
        width: 24px;
        height: 24px;
        img {
          width: 16px;
          height: 16px;
        }
      }
      .state {
        font-size: 14px;
        &.state-danger {
        }
      }
      .profile-dates {
        gap: 5px;
      }
      .date-row {
        padding: 5px 10px;
        span {
          font-size: 12px;
        }
        strong {
          font-size: 12px;
        }
      }
      .profile-actions,
      .stats-toolbar {
        gap: 5px;
      }
      .profile-action {
        min-height: 30px;
        font-size: 14px;
        line-height: 2;
        img {
          width: 20px;
          height: 20px;
        }
      }
    }
  }
  .avatar-lightbox-overlay {
    .avatar-lightbox-image {
      width: min(75vw, 75vh, 500px);
      height: min(75vw, 75vh, 500px);
    }
  }
}
</style>
