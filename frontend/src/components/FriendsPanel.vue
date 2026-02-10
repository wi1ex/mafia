<template>
  <Transition name="friends-panel">
    <div v-show="open" :class="['friends-panel', { 'room-mode': isRoomMode }]" ref="root" @click.stop>
      <header>
        <span>Список друзей — {{ friendsTotal }}</span>
        <button @click="$emit('update:open', false)" aria-label="Закрыть">
          <img :src="iconClose" alt="close" />
        </button>
      </header>

      <div class="list">
        <template v-if="friends.list.length === 0">
          <p class="empty">Список пуст</p>
        </template>
        <template v-else>
          <template v-for="(section, idx) in sections" :key="section.kind">
            <div v-if="section.items.length > 0" class="section-title">
              <span>{{ section.title }}</span>
              <span class="count">{{ section.items.length }}</span>
            </div>
            <article v-for="f in section.items" :key="`${f.kind}-${f.id}`" class="item">
              <div class="left">
                <img v-minio-img="{ key: f.avatar_name ? `avatars/${f.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                <span class="nick">{{ f.username || ('user' + f.id) }}</span>
              </div>
              <div class="info">
                <template v-if="isAccepted(f)">
                  <div v-if="f.room_id" class="room-info">
                    <span class="room">{{ f.room_title || ('Комната #' + f.room_id) }}</span>
                    <span class="game" :class="{ active: f.room_in_game }">{{ f.room_in_game ? 'Игра' : 'Лобби' }}</span>
                  </div>
                  <div v-if="canInvite(f)" class="invite-select">
                    <button type="button" class="icon-btn invite-btn" :disabled="isInviteDisabled(f.id) || Boolean(inviteBusy[f.id])"
                            :title="inviteTitle(f.id)" @click="invite(f)" aria-label="Пригласить в комнату">
                      <img :src="iconInvite" alt="" />
                    </button>
                  </div>
                </template>
              </div>
              <div v-if="f.kind === 'incoming'" class="actions">
                <button class="icon-btn accept" @click="accept(f.id)" aria-label="Принять заявку">
                  <img :src="iconAccept" alt="" />
                </button>
                <button class="icon-btn danger" @click="decline(f.id)" aria-label="Отклонить заявку">
                  <img :src="iconClose" alt="" />
                </button>
              </div>
              <div v-else-if="isAccepted(f)" class="actions">
                <button class="icon-btn danger" @click="remove(f.id)" aria-label="Удалить из друзей">
                  <img :src="iconRemove" alt="" />
                </button>
              </div>
            </article>
          </template>
        </template>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount, computed, reactive } from 'vue'
import { useFriendsStore } from '@/store'
import { confirmDialog, alertDialog, useConfirmState } from '@/services/confirm'

import iconClose from '@/assets/svg/close.svg'
import iconAccept from '@/assets/svg/readyBlack.svg'
import iconRemove from '@/assets/svg/delete.svg'
import iconInvite from '@/assets/svg/notifBell.svg'
import defaultAvatar from '@/assets/svg/defaultAvatar.svg'

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
const confirmState = useConfirmState()
const root = ref<HTMLElement | null>(null)
const inviteBusy = reactive<Record<number, boolean>>({})
const inviteCooldownByUser = ref<Record<number, number>>({})
const nowTs = ref(Date.now())
let nowTimer: number | undefined
const isRoomMode = computed(() => props.mode === 'room')
const inviteRoomId = computed(() => Number(props.roomId || 0))
const isAccepted = (f: { kind?: string }) => f.kind === 'online' || f.kind === 'offline'
const canInvite = (f: { kind?: string; room_id?: number | null }) => {
  if (!isRoomMode.value || inviteRoomId.value <= 0 || f.kind !== 'online') return false
  return Number(f.room_id || 0) !== inviteRoomId.value
}
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
const INVITE_COOLDOWN_MS = 60 * 60 * 1000

function parseCooldownMap(raw: unknown, now = Date.now()): Record<number, number> {
  if (!raw || typeof raw !== 'object') return {}
  const obj = raw as Record<string, unknown>
  const next: Record<number, number> = {}
  for (const [uidRaw, untilRaw] of Object.entries(obj)) {
    const uid = Number(uidRaw)
    const until = Number(untilRaw)
    if (!Number.isFinite(uid) || uid <= 0 || !Number.isFinite(until) || until <= now) continue
    next[uid] = until
  }
  return next
}

function persistCooldowns() {
  try {
    localStorage.setItem('friends_invite_cooldown_v1', JSON.stringify(inviteCooldownByUser.value))
  } catch {}
}

function loadCooldowns() {
  try {
    const raw = localStorage.getItem('friends_invite_cooldown_v1')
    if (!raw) {
      inviteCooldownByUser.value = {}
      return
    }
    inviteCooldownByUser.value = parseCooldownMap(JSON.parse(raw))
  } catch {
    inviteCooldownByUser.value = {}
  }
}

function pruneCooldowns(now = Date.now()) {
  const next = parseCooldownMap(inviteCooldownByUser.value, now)
  const changed = JSON.stringify(next) !== JSON.stringify(inviteCooldownByUser.value)
  if (!changed) return
  inviteCooldownByUser.value = next
  persistCooldowns()
}

function setInviteCooldown(uid: number, untilTs = Date.now() + INVITE_COOLDOWN_MS) {
  inviteCooldownByUser.value = {
    ...inviteCooldownByUser.value,
    [uid]: untilTs,
  }
  pruneCooldowns()
  persistCooldowns()
}

function inviteCooldownLeftMs(uid: number): number {
  const until = Number(inviteCooldownByUser.value[uid] || 0)
  return Math.max(0, until - nowTs.value)
}

function isInviteDisabled(uid: number): boolean {
  return inviteCooldownLeftMs(uid) > 0
}

function formatCooldownLeft(ms: number): string {
  const totalMinutes = Math.max(1, Math.ceil(ms / 60000))
  if (totalMinutes >= 60) {
    const h = Math.floor(totalMinutes / 60)
    const m = totalMinutes % 60
    return m > 0 ? `${h} ч ${m} мин` : `${h} ч`
  }
  return `${totalMinutes} мин`
}

function inviteTitle(uid: number): string {
  if (inviteBusy[uid]) return 'Отправка приглашения...'
  const leftMs = inviteCooldownLeftMs(uid)
  if (leftMs <= 0) return 'Пригласить в комнату'
  return `Повторное приглашение через ${formatCooldownLeft(leftMs)}`
}

function startNowTimer() {
  if (nowTimer) return
  nowTimer = window.setInterval(() => {
    nowTs.value = Date.now()
    pruneCooldowns(nowTs.value)
  }, 30_000)
}

function stopNowTimer() {
  if (!nowTimer) return
  window.clearInterval(nowTimer)
  nowTimer = undefined
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
  void friends.fetchList()
  pollTimer = window.setInterval(() => {
    void friends.fetchList()
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

async function invite(friend: { id: number; username?: string | null }) {
  const uid = Number(friend.id || 0)
  if (!inviteRoomId.value || uid <= 0) return
  if (inviteBusy[uid]) return
  if (isInviteDisabled(uid)) {
    void alertDialog(`Повторное приглашение можно отправить через ${formatCooldownLeft(inviteCooldownLeftMs(uid))}`)
    return
  }
  const ok = await confirmDialog({
    title: 'Приглашение в комнату',
    text: `Отправить приглашение пользователю ${friend.username || ('user' + uid)} в текущую комнату?`,
    confirmText: 'Пригласить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  inviteBusy[uid] = true
  try {
    await friends.inviteToRoom(uid, inviteRoomId.value)
    setInviteCooldown(uid)
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 409 && d === 'target_offline') {
      void alertDialog('Пользователь не в сети')
      return
    }
    if (st === 404 && d === 'user_not_found') {
      void alertDialog('Пользователь не найден')
      return
    }
    if (st === 403 && d === 'not_friends') {
      void alertDialog('Пользователь больше не в друзьях')
      return
    }
    if (st === 429 && d === 'invite_cooldown') {
      const retryAfterRaw = Number(e?.response?.headers?.['retry-after'])
      if (Number.isFinite(retryAfterRaw) && retryAfterRaw > 0) {
        setInviteCooldown(uid, Date.now() + retryAfterRaw * 1000)
        void alertDialog(`Повторное приглашение можно отправить через ${formatCooldownLeft(retryAfterRaw * 1000)}`)
      } else {
        setInviteCooldown(uid)
        void alertDialog('Повторное приглашение можно отправить через 1 час')
      }
      return
    }
    void alertDialog('Не удалось отправить приглашение')
  } finally {
    inviteBusy[uid] = false
  }
}

async function remove(uid: number) {
  const ok = await confirmDialog({
    title: 'Удалить из друзей',
    text: 'Вы уверены, что хотите удалить пользователя из друзей?',
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  try {
    await friends.removeFriend(uid)
    await friends.fetchList()
  } catch {
    void alertDialog('Не удалось удалить из друзей')
  }
}

async function accept(uid: number) {
  const ok = await confirmDialog({
    title: 'Принять заявку',
    text: 'Принять пользователя в друзья?',
    confirmText: 'Принять',
    cancelText: 'Отмена',
  })
  if (!ok) return
  try {
    await friends.acceptRequest(uid)
    await friends.fetchList()
  } catch {
    void alertDialog('Не удалось принять запрос')
  }
}

async function decline(uid: number) {
  const ok = await confirmDialog({
    title: 'Отклонить заявку',
    text: 'Отклонить запрос в друзья?',
    confirmText: 'Отклонить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  try {
    await friends.declineRequest(uid)
    await friends.fetchList()
  } catch {
    void alertDialog('Не удалось отклонить запрос')
  }
}

watch(() => props.open, async v => {
  if (v) {
    await nextTick()
    loadCooldowns()
    bindDoc()
    startPolling()
    startAutoClose()
    startNowTimer()
  } else {
    unbindDoc()
    stopPolling()
    stopAutoClose()
    stopNowTimer()
  }
})

onBeforeUnmount(() => {
  unbindDoc()
  stopPolling()
  stopAutoClose()
  stopNowTimer()
})
</script>

<style scoped lang="scss">
.friends-panel {
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  top: 50px;
  width: 400px;
  min-height: 200px;
  max-height: 600px;
  border-radius: 5px;
  background-color: $graphite;
  box-shadow: 3px 3px 5px rgba($black, 0.25);
  z-index: 100;
  &.room-mode {
    top: auto;
    bottom: 50px;
    z-index: 25;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 10px;
    border-radius: 5px;
    background-color: $lead;
    box-shadow: 0 3px 5px rgba($black, 0.25);
    span {
      font-size: 18px;
      font-weight: bold;
    }
    button {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 25px;
      height: 30px;
      border: none;
      background: none;
      cursor: pointer;
      img {
        width: 25px;
        height: 25px;
      }
    }
  }
  .list {
    display: flex;
    flex-direction: column;
    margin: 10px;
    gap: 10px;
    overflow-y: auto;
    scrollbar-width: none;
    .section-title {
      display: flex;
      align-items: center;
      gap: 5px;
      font-size: 14px;
      font-family: Manrope-Medium;
      color: $ashy;
      text-transform: uppercase;
      letter-spacing: 1px;
      .count {
        padding: 0 10px;
        height: 16px;
        border-radius: 999px;
        background-color: $lead;
        text-align: center;
        color: $fg;
        font-size: 12px;
        line-height: 16px;
      }
    }
    .item {
      display: grid;
      grid-template-columns: 1fr auto auto;
      align-items: center;
      padding: 5px;
      gap: 5px;
      border-radius: 5px;
      background-color: $lead;
      box-shadow: 0 3px 5px rgba($black, 0.25);
      .left {
        display: flex;
        align-items: center;
        gap: 5px;
        img {
          width: 20px;
          height: 20px;
          border-radius: 50%;
        }
        .nick {
          height: 16px;
          font-size: 14px;
        }
      }
      .info {
        display: flex;
        gap: 5px;
        .room-info {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          .room {
            font-size: 12px;
          }
          .game {
            font-size: 12px;
            color: $grey;
            &.active {
              color: $green;
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
            width: 25px;
            height: 25px;
            border: none;
            border-radius: 5px;
            background-color: $dark;
            cursor: pointer;
            transition: background-color 0.25s ease-in-out;
            &:hover:enabled {
              background-color: $graphite;
            }
            &:disabled {
              opacity: 0.5;
              cursor: not-allowed;
            }
            img {
              width: 16px;
              height: 16px;
            }
          }
        }
      }
      .actions {
        display: flex;
        gap: 5px;
        button {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          width: 25px;
          height: 25px;
          border: none;
          border-radius: 5px;
          cursor: pointer;
          transition: background-color 0.25s ease-in-out;
          img {
            width: 16px;
            height: 16px;
          }
        }
        .accept {
          background-color: rgba($green, 0.75);
          color: $bg;
          &:hover {
            background-color: $green;
          }
        }
        .danger {
          background-color: rgba($red, 0.75);
          color: $fg;
          &:hover {
            background-color: $red;
          }
        }
      }
    }
    .empty {
      color: $grey;
      text-align: center;
      margin: 55px;
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

@media (max-width: 1280px) {
  .friends-panel {
    max-height: calc(100dvh - 70px);
    header {
      padding: 5px;
      span {
        font-size: 14px;
      }
      button {
        width: 20px;
        height: 20px;
        img {
          width: 15px;
          height: 15px;
        }
      }
    }
    .list {
      margin: 5px;
      gap: 5px;
      .section-title {
        gap: 3px;
        font-size: 10px;
        .count {
          padding: 0 5px;
          height: 14px;
          font-size: 8px;
          line-height: 14px;
        }
      }
      .item {
        padding: 3px;
        gap: 10px;
        .left {
          gap: 3px;
          img {
            width: 16px;
            height: 16px;
          }
          .nick {
            height: 14px;
            font-size: 12px;
          }
        }
        .info {
          gap: 10px;
          .room-info {
            .room {
              font-size: 10px;
            }
            .game {
              font-size: 10px;
            }
          }
          .invite-select {
            .invite-btn {
              width: 20px;
              height: 20px;
              img {
                width: 14px;
                height: 14px;
              }
            }
          }
        }
        .actions {
          gap: 10px;
          button {
            width: 20px;
            height: 20px;
            img {
              width: 14px;
              height: 14px;
            }
          }
        }
      }
    }
  }
}
</style>
