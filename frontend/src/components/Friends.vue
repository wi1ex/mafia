<template>
  <Transition name="friends-panel">
    <div v-show="open" :class="['friends-panel', { 'room-mode': isRoomMode }]" :data-open="open ? 1 : 0" ref="root" @click.stop>
      <header>
        <span class="title">Список друзей — {{ friendsTotal }}</span>
        <button class="close-btn" type="button" aria-label="Закрыть" @click="$emit('update:open', false)">
          <UiIcon class="close-icon" :icon="iconClose" />
        </button>
      </header>

      <div class="list">
        <template v-for="section in sections" :key="section.kind">
          <div v-if="section.items.length > 0" class="section-title">
            <span>{{ section.title }} {{ section.items.length }}</span>
          </div>
          <article v-for="f in section.items" :key="`${f.kind}-${f.id}`" class="item" :class="{ 'has-theme-color': hasFriendThemeColor(f) }" :style="friendNickStyle(f)">
            <button v-if="canOpenMiniProfile(f)" class="left profile-trigger" type="button" @click="openMiniProfile(f)">
              <img v-minio-img="{ key: f.avatar_name ? `avatars/${f.avatar_name}` : '', placeholder: iconDefaultAvatarBlack, lazy: false, animated: true }" alt="avatar" />
              <div v-if="friendThemeIconSrcs(f).length" class="profile-theme-icons" aria-hidden="true">
                <img v-for="badgeSrc in friendThemeIconSrcs(f)" :key="`${f.id}-${badgeSrc}`" class="profile-theme-icon" :src="badgeSrc" alt="" />
              </div>
              <span class="nick">{{ f.username || ('user' + f.id) }}</span>
            </button>
            <div v-else class="left profile-trigger">
              <img v-minio-img="{ key: f.avatar_name ? `avatars/${f.avatar_name}` : '', placeholder: iconDefaultAvatarBlack, lazy: false, animated: true }" alt="avatar" />
              <div v-if="friendThemeIconSrcs(f).length" class="profile-theme-icons" aria-hidden="true">
                <img v-for="badgeSrc in friendThemeIconSrcs(f)" :key="`${f.id}-${badgeSrc}`" class="profile-theme-icon" :src="badgeSrc" alt="" />
              </div>
              <span class="nick">{{ f.username || ('user' + f.id) }}</span>
            </div>
            <div class="info">
              <template v-if="isAccepted(f)">
                <div v-if="f.room_id" class="room-info">
                  <span class="room">{{ f.room_title || ('Комната #' + f.room_id) }}</span>
                  <span class="game" :class="{ active: f.room_in_game }">{{ f.room_in_game ? 'Игра' : 'Лобби' }}</span>
                </div>
                <div v-if="shouldShowInviteButton(f)" class="invite-select">
                  <button type="button" class="icon-btn invite-btn" :disabled="isInviteDisabled(f) || Boolean(inviteBusy[f.id])" :title="inviteDisabledReason(f)" @click="invite(f)" aria-label="Пригласить в комнату">
                    <UiIcon class="invite-icon" :icon="inviteIcon(f)" />
                  </button>
                </div>
              </template>
            </div>
            <div v-if="f.kind === 'incoming'" class="actions">
              <button class="icon-btn accept" :disabled="isActionBusy(f.id)" @click="accept(f.id)" aria-label="Принять заявку">
                <UiIcon class="active-icon" :icon="iconAccept" />
              </button>
              <button class="icon-btn danger" :disabled="isActionBusy(f.id)" @click="decline(f.id)" aria-label="Отклонить заявку">
                <UiIcon class="active-icon" :icon="iconClose" />
              </button>
            </div>
            <div v-else-if="f.kind === 'outgoing'" class="actions">
              <button class="icon-btn danger" :disabled="isActionBusy(f.id)" @click="cancelOutgoing(f.id, f.username)" aria-label="Отменить заявку">
                <UiIcon class="active-icon" :icon="iconClose" />
              </button>
            </div>
            <div v-else-if="isAccepted(f)" class="actions">
              <button class="icon-btn danger" :disabled="isActionBusy(f.id)" @click="remove(f.id)" aria-label="Удалить из друзей">
                <UiIcon class="active-icon" :icon="iconRemove" />
              </button>
            </div>
          </article>
        </template>
        <div v-if="friends.list.length === 0" class="empty">
          <img :src="iconNoFriendsNotifs" alt="nofriends" />
          <span>Список друзей пока пуст...</span>
        </div>
      </div>
    </div>
  </Transition>

  <MiniProfile
    v-model:open="miniProfileOpen"
    :user-id="miniProfileUserId"
    :initial-profile="miniProfileInitial"
    :show-stats-button="true"
    :refresh-friends-list-on-action="true"
    :refresh-friends-room-id="currentListRoomId()"
  />
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { getProfileThemeOption } from '@/constants/profileThemes'
import { getProfileThemeBadgeSources } from '@/constants/profileIcons'
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId } from '@/services/miniProfile'
import {
  type FriendListItem,
  resolveFriendsApiError,
  shouldRefreshFriendsStateAfterError,
  useFriendsStore,
  useUserStore
} from '@/store'
import { alertDialog, confirmDialog, useConfirmState } from '@/services/confirm'
import MiniProfile from '@/components/MiniProfile.vue'
import UiIcon from '@/components/UiIcon.vue'

import iconClose from '@/assets/svg/iconClose.svg'
import iconAccept from '@/assets/svg/iconCheckMark.svg'
import iconRemove from '@/assets/svg/iconDelete.svg'
import iconInviteOnline from '@/assets/svg/iconNotifBell.svg'
import iconInviteOffline from '@/assets/svg/iconTelegram.svg'
import iconDefaultAvatarBlack from '@/assets/svg/iconDefaultAvatarBlack.svg'
import iconNoFriendsNotifs from '@/assets/svg/iconNoFriendsNotifs.svg'

const props = defineProps<{
  open: boolean
  anchor?: HTMLElement | null
  mode?: 'header' | 'room'
  roomId?: number | null
}>()
const emit = defineEmits<{
  'update:open': [boolean]
}>()

const friends = useFriendsStore()
const userStore = useUserStore()
const confirmState = useConfirmState()
const root = ref<HTMLElement | null>(null)
const inviteBusy = reactive<Record<number, boolean>>({})
const actionBusy = reactive<Record<number, boolean>>({})
const miniProfileOpen = ref(false)
const miniProfileUserId = ref<number | null>(null)
const miniProfileInitial = ref<FriendListItem | null>(null)
const isRoomMode = computed(() => props.mode === 'room')
const inviteRoomId = computed(() => Number(props.roomId || 0))
const viewerUserId = computed(() => normalizeMiniProfileUserId(userStore.user?.id))
const isAccepted = (f: { kind?: string }) => f.kind === 'online' || f.kind === 'offline'
const currentListRoomId = () => (isRoomMode.value && inviteRoomId.value > 0 ? inviteRoomId.value : null)
const canInvite = (f: { kind?: string; room_id?: number | null; in_current_room?: boolean | null }) => {
  if (!isRoomMode.value || inviteRoomId.value <= 0 || !isAccepted(f)) return false
  if (Boolean(f.in_current_room)) return false
  return Number(f.room_id || 0) !== inviteRoomId.value
}
const shouldShowInviteButton = (f: { kind?: string; room_id?: number | null; in_current_room?: boolean | null }) => canInvite(f)
const hasFriendThemeColor = (friend: { theme_color?: string | null }) => Boolean(getProfileThemeOption(friend.theme_color))
const friendNickStyle = (friend: { theme_color?: string | null }) => {
  const option = getProfileThemeOption(friend.theme_color)
  return option ? { '--friend-nick-theme': option.bg } : {}
}
const friendThemeIconSrcs = (friend: { theme_icon?: string | null; role?: string | null }) => getProfileThemeBadgeSources(friend.theme_icon, friend.role)
const sections = computed(() => [
  { kind: 'incoming', title: 'Входящие заявки —', items: friends.list.filter(f => f.kind === 'incoming') },
  { kind: 'online', title: 'В сети —', items: friends.list.filter(f => f.kind === 'online') },
  { kind: 'offline', title: 'Не в сети —', items: friends.list.filter(f => f.kind === 'offline') },
  { kind: 'outgoing', title: 'Исходящие заявки —', items: friends.list.filter(f => f.kind === 'outgoing') },
])
const friendsTotal = computed(() => friends.list.filter(f => f.kind === 'online' || f.kind === 'offline').length)

let onDocDown: ((e: Event) => void) | null = null
let pollTimer: number | undefined
let autoCloseTimer: number | undefined
const POLL_MS = 3000
const AUTO_CLOSE_MS = 5 * 60 * 1000

onMounted(() => {
  friends.ensureWS()
})

function inviteBlockedReason(friend: { kind?: string; telegram_verified?: boolean; tg_invites_enabled?: boolean; tg_invite_cooldown_active?: boolean | null; ban_active?: boolean | null; timeout_active?: boolean | null; in_active_game_as_alive_player?: boolean | null; in_active_game_as_host?: boolean | null }): string {
  if (friend.ban_active) return 'Аккаунт пользователя забанен'
  if (friend.timeout_active) return 'У пользователя активный таймаут'
  if (friend.in_active_game_as_host) return 'Пользователь сейчас является ведущим в активной игре'
  if (friend.kind === 'online' && friend.in_active_game_as_alive_player) return 'Пользователь сейчас является живым игроком в активной игре'
  if (friend.kind !== 'offline') return ''
  if (friend.tg_invites_enabled === false) return 'Пользователь запретил приглашения через уведомления в Telegram'
  if (!friend.telegram_verified) return 'Пользователь не прошел верификацию через Telegram'
  if (friend.tg_invite_cooldown_active) return 'Пользователя уже приглашали через Telegram в последние 30 минут'
  return ''
}

function isAlreadyInvited(friend: { room_invited?: boolean | null }): boolean {
  return Boolean(friend.room_invited)
}

function isInviteDisabled(friend: { id: number; kind?: string; telegram_verified?: boolean; tg_invites_enabled?: boolean; tg_invite_cooldown_active?: boolean | null; ban_active?: boolean | null; timeout_active?: boolean | null; room_invited?: boolean | null; in_active_game_as_alive_player?: boolean | null; in_active_game_as_host?: boolean | null }): boolean {
  const uid = Number(friend.id || 0)
  if (uid <= 0) return true
  if (inviteBlockedReason(friend)) return true
  return isAlreadyInvited(friend)
}

function inviteDisabledReason(friend: { id: number; kind?: string; telegram_verified?: boolean; tg_invites_enabled?: boolean; tg_invite_cooldown_active?: boolean | null; ban_active?: boolean | null; timeout_active?: boolean | null; room_invited?: boolean | null; in_active_game_as_alive_player?: boolean | null; in_active_game_as_host?: boolean | null }): string {
  if (inviteBusy[Number(friend.id || 0)]) return 'Отправка приглашения'
  const blockedReason = inviteBlockedReason(friend)
  if (blockedReason) return blockedReason
  if (isAlreadyInvited(friend)) return 'Пользователь уже приглашен в эту комнату'
  return ''
}

function inviteIcon(friend: { kind?: string }): string {
  return friend.kind === 'offline' ? iconInviteOffline : iconInviteOnline
}

function isActionBusy(uid: number): boolean {
  return Boolean(actionBusy[uid])
}

function canOpenMiniProfile(friend: FriendListItem): boolean {
  return canOpenMiniProfileTarget({
    targetId: friend.id,
    viewerId: viewerUserId.value,
    viewerRole: userStore.user?.role,
    targetRole: friend.role,
  })
}

function openMiniProfile(friend: FriendListItem) {
  if (!canOpenMiniProfile(friend)) return
  miniProfileUserId.value = Number(friend.id || 0)
  miniProfileInitial.value = friend
  miniProfileOpen.value = true
}

async function refreshListAfterStateError(e: any): Promise<void> {
  if (!shouldRefreshFriendsStateAfterError(e)) return
  await friends.fetchList(currentListRoomId())
}

function bindDoc() {
  if (onDocDown) return
  onDocDown = (e: Event) => {
    if (confirmState.open) return
    const t = e.target as Node | null
    if (!t) return
    const hasContains = (el: any, target: Node) => typeof el?.contains === 'function' && el.contains(target)
    const inRoot = hasContains(root.value, t)
    const inAnchor = hasContains(props.anchor, t)
    if (inRoot || inAnchor) return
    emit('update:open', false)
  }
  document.addEventListener('pointerdown', onDocDown)
}
function unbindDoc() {
  if (!onDocDown) return
  document.removeEventListener('pointerdown', onDocDown)
  onDocDown = null
}

function startPolling() {
  if (pollTimer) return
  void friends.fetchList(currentListRoomId())
  pollTimer = window.setInterval(() => {
    void friends.fetchList(currentListRoomId())
  }, POLL_MS)
}

function stopPolling() {
  if (!pollTimer) return
  window.clearInterval(pollTimer)
  pollTimer = undefined
}

function startAutoClose() {
  if (autoCloseTimer) return
  autoCloseTimer = window.setTimeout(() => {
    autoCloseTimer = undefined
    emit('update:open', false)
  }, AUTO_CLOSE_MS)
}

function stopAutoClose() {
  if (!autoCloseTimer) return
  window.clearTimeout(autoCloseTimer)
  autoCloseTimer = undefined
}

async function invite(friend: { id: number; username?: string | null; kind?: string; telegram_verified?: boolean; tg_invites_enabled?: boolean; tg_invite_cooldown_active?: boolean | null; ban_active?: boolean | null; timeout_active?: boolean | null; room_invited?: boolean | null; in_active_game_as_alive_player?: boolean | null; in_active_game_as_host?: boolean | null }) {
  const uid = Number(friend.id || 0)
  if (!inviteRoomId.value || uid <= 0) return
  if (inviteBusy[uid]) return
  const blockedReason = inviteBlockedReason(friend)
  if (blockedReason) {
    void alertDialog(blockedReason)
    return
  }
  if (isAlreadyInvited(friend)) {
    void alertDialog('Пользователь уже приглашен в эту комнату')
    return
  }
  const ok = await confirmDialog({
    title: 'Приглашение в комнату',
    text: `Вы хотите пригласить пользователя ${friend.username || ('user' + uid)} в комнату?`,
    confirmText: 'Пригласить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  inviteBusy[uid] = true
  try {
    await friends.inviteToRoom(uid, inviteRoomId.value)
    await friends.fetchList(currentListRoomId())
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (
      (st === 409 && d === 'target_offline')
      || (st === 409 && d === 'target_telegram_not_verified')
      || (st === 409 && d === 'target_telegram_invites_disabled')
      || (st === 409 && d === 'target_telegram_invite_cooldown_active')
      || (st === 409 && d === 'target_in_active_game_as_alive_player')
      || (st === 409 && d === 'target_in_active_game_as_host')
      || (st === 409 && d === 'target_banned')
      || (st === 409 && d === 'target_timeout')
      || (st === 409 && d === 'target_invite_unavailable')
      || (st === 404 && d === 'user_not_found')
      || (st === 403 && d === 'not_friends')
      || (st === 409 && d === 'target_already_in_room')
      || (st === 409 && d === 'room_invite_already_sent')
    ) {
      await friends.fetchList(currentListRoomId())
      return
    }
    if (st === 409 && d === 'target_telegram_unreachable') {
      void alertDialog('Пользователю нельзя отправить сообщение в Telegram')
      return
    }
    if (st === 503 && d === 'telegram_unavailable') {
      void alertDialog('Telegram временно недоступен. Попробуйте позже')
      return
    }
    void alertDialog('Не удалось отправить приглашение')
  } finally {
    inviteBusy[uid] = false
  }
}

async function remove(uid: number) {
  if (isActionBusy(uid)) return
  const ok = await confirmDialog({
    title: 'Удалить из друзей',
    text: 'Вы уверены, что хотите удалить пользователя из друзей?',
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  actionBusy[uid] = true
  try {
    await friends.removeFriend(uid)
    await friends.fetchList(currentListRoomId())
  } catch (e: any) {
    await refreshListAfterStateError(e)
    void alertDialog(resolveFriendsApiError(e, 'remove'))
  } finally {
    actionBusy[uid] = false
  }
}

async function accept(uid: number) {
  if (isActionBusy(uid)) return
  const ok = await confirmDialog({
    title: 'Принять заявку',
    text: 'Принять пользователя в друзья?',
    confirmText: 'Принять',
    cancelText: 'Отмена',
  })
  if (!ok) return
  actionBusy[uid] = true
  try {
    await friends.acceptRequest(uid)
    await friends.fetchList(currentListRoomId())
  } catch (e: any) {
    await refreshListAfterStateError(e)
    void alertDialog(resolveFriendsApiError(e, 'accept'))
  } finally {
    actionBusy[uid] = false
  }
}

async function decline(uid: number) {
  if (isActionBusy(uid)) return
  const ok = await confirmDialog({
    title: 'Отклонить заявку',
    text: 'Отклонить запрос в друзья?',
    confirmText: 'Отклонить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  actionBusy[uid] = true
  try {
    await friends.declineRequest(uid)
    await friends.fetchList(currentListRoomId())
  } catch (e: any) {
    await refreshListAfterStateError(e)
    void alertDialog(resolveFriendsApiError(e, 'decline'))
  } finally {
    actionBusy[uid] = false
  }
}

async function cancelOutgoing(uid: number, username?: string | null) {
  if (isActionBusy(uid)) return
  const ok = await confirmDialog({
    title: 'Отменить заявку',
    text: `Вы уверены, что хотите отменить заявку в друзья для пользователя ${username || ('user' + uid)}?`,
    confirmText: 'Отменить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  actionBusy[uid] = true
  try {
    await friends.cancelOutgoingRequest(uid)
    await friends.fetchList(currentListRoomId())
  } catch (e: any) {
    await refreshListAfterStateError(e)
    void alertDialog(resolveFriendsApiError(e, 'cancel'))
  } finally {
    actionBusy[uid] = false
  }
}

watch(() => props.open, async v => {
  if (v) {
    await nextTick()
    bindDoc()
    startPolling()
    startAutoClose()
  } else {
    miniProfileOpen.value = false
    unbindDoc()
    stopPolling()
    stopAutoClose()
  }
})

onBeforeUnmount(() => {
  unbindDoc()
  stopPolling()
  stopAutoClose()
})
</script>

<style scoped lang="scss">
.friends-panel {
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  top: 72px;
  padding: 16px;
  width: 448px;
  min-height: 408px;
  max-height: 608px;
  border-radius: 24px;
  background-color: $neutral-100;
  box-shadow: 0 0 16px 0 rgba($neutral-black, 0.16);
  z-index: 100;
  &[data-open="0"] {
    pointer-events: none;
  }
  &.room-mode {
    top: auto;
    bottom: 58px;
    z-index: 25;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 8px 16px;
    .title {
      color: $neutral-black;
      font-family: Hauora-Bold;
      font-size: 18px;
      line-height: 20px;
      letter-spacing: -0.36px;
    }
    .close-btn {
      padding: 0;
      width: 24px;
      height: 24px;
      border: none;
      background: none;
      cursor: pointer;
      .close-icon {
        --ui-icon-width: 24px;
        --ui-icon-height: 24px;
        --ui-icon-color: #{$neutral-black};
      }
      &:hover,
      &:focus-visible,
      &:active {
        .close-icon {
          --ui-icon-color: #{$green-500};
        }
      }
    }
  }
  .list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow-y: auto;
    scrollbar-width: none;
    .section-title {
      margin-bottom: 4px;
      padding: 0 8px;
      color: $neutral-500;
      font-family: Hauora-Regular;
      font-size: 16px;
      line-height: 16px;
      letter-spacing: -0.32px;
      text-transform: uppercase;
    }
    .item {
      display: grid;
      grid-template-columns: 1fr auto auto;
      align-items: center;
      margin-bottom: 8px;
      padding: 16px;
      gap: 16px;
      border-radius: 20px;
      background-color: $neutral-white;
      &:has(+ .item) {
        margin-bottom: 0;
      }
      &.has-theme-color .nick {
        background: var(--friend-nick-theme);
        background-clip: text;
        color: transparent;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
      .left {
        display: flex;
        align-items: center;
        padding: 0;
        gap: 8px;
        min-width: 0;
        width: fit-content;
        border: none;
        background: none;
        cursor: default;
        &.profile-trigger:is(button) {
          cursor: pointer;
        }
        img {
          width: 28px;
          height: 28px;
          border-radius: 50%;
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
        .nick {
          max-width: 182px;
          color: $neutral-black;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 20px;
          letter-spacing: -0.32px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }
      .info {
        display: flex;
        align-items: center;
        gap: 16px;
        .room-info {
          display: flex;
          flex-direction: column;
          width: 112px;
          .room {
            max-width: 112px;
            color: $neutral-500;
            font-family: Hauora-Regular;
            font-size: 12px;
            line-height: 14px;
            letter-spacing: -0.24px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          .game {
            color: $neutral-black;
            font-family: Hauora-Regular;
            font-size: 12px;
            line-height: 14px;
            letter-spacing: -0.24px;
            &.active {
              color: $green-700;
            }
          }
        }
        .invite-select {
          position: relative;
          .invite-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0;
            width: 28px;
            height: 28px;
            border-radius: 8px;
            border: 1px solid transparent;
            background-color: $soft-purple-100;
            cursor: pointer;
            transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out;
            .invite-icon {
              --ui-icon-width: 20px;
              --ui-icon-height: 20px;
              --ui-icon-color: #{$neutral-black};
            }
            &:disabled {
              background-color: $neutral-200;
              border-color: $neutral-200;
              .action-icon {
                --ui-icon-color: #{$neutral-400};
              }
            }
            &:not(:disabled):hover,
            &:not(:disabled):focus-visible,
            &:not(:disabled):active {
              border-color: $neutral-black;
            }
          }
        }
      }
      .actions {
        display: flex;
        align-items: center;
        margin-left: -12px;
        gap: 4px;
        button {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          width: 28px;
          height: 28px;
          border-radius: 8px;
          border: 1px solid transparent;
          cursor: pointer;
          transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out;
          .action-icon {
            --ui-icon-width: 24px;
            --ui-icon-height: 24px;
            --ui-icon-color: #{$neutral-black};
          }
          &:disabled {
            background-color: $neutral-200;
            border-color: $neutral-200;
            .action-icon {
              --ui-icon-color: #{$neutral-400};
            }
          }
          &.accept {
            background-color: $green-100;
            border-color: $green-100;
            .action-icon {
              --ui-icon-color: #{$green-600};
            }
            &:not(:disabled):hover,
            &:not(:disabled):focus-visible,
            &:not(:disabled):active {
              border-color: $green-600;
            }
          }
          &.danger {
            background-color: $red-100;
            border-color: $red-100;
            .action-icon {
              --ui-icon-color: #{$red-600};
            }
            &:not(:disabled):hover,
            &:not(:disabled):focus-visible,
            &:not(:disabled):active {
              border-color: $red-600;
            }
          }
        }
      }
    }
    .empty {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 10px;
      height: 368px;
      img {
        width: 95px;
        height: 100px;
      }
      span {
        color: $neutral-500;
        font-family: Hauora-Regular;
        font-size: 14px;
        line-height: 14px;
        letter-spacing: -0.28px;
      }
    }
  }
}

.friends-panel-enter-active,
.friends-panel-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}
.friends-panel-enter-from,
.friends-panel-leave-to {
  opacity: 0;
  transform: translateY(-30px);
}

</style>
