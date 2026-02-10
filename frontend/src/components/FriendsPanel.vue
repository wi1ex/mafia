<template>
  <Transition name="panel" @after-leave="onAfterLeave">
    <div v-show="open" class="panel" ref="root" @click.stop>
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
                  <template v-if="f.room_id">
                    <span class="room">{{ f.room_title || ('Комната #' + f.room_id) }}</span>
                    <span class="game" :class="{ active: f.room_in_game }">{{ f.room_in_game ? 'Игра' : 'Лобби' }}</span>
                  </template>
                  <template v-else>
                    <div class="invite">
                      <button class="btn" @click="toggleInvite(f.id)">Пригласить</button>
                      <div v-if="inviteOpenFor === f.id" ref="inviteDropdownEl" class="invite-dropdown">
                        <button v-for="r in rooms" :key="r.id" @click="invite(f.id, r.id)">{{ r.title }}</button>
                        <p v-if="rooms.length === 0" class="empty">Нет активных комнат</p>
                      </div>
                    </div>
                  </template>
                </template>
              </div>
              <div v-if="f.kind === 'incoming'" class="actions">
                <button class="accept" @click="accept(f.id)">Принять</button>
                <button class="danger" @click="decline(f.id)">Отклонить</button>
              </div>
              <div v-else-if="isAccepted(f)" class="actions">
                <button class="danger" @click="remove(f.id)">Удалить</button>
              </div>
            </article>
          </template>
        </template>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount, computed } from 'vue'
import { useFriendsStore } from '@/store'
import { confirmDialog, alertDialog, useConfirmState } from '@/services/confirm'

import iconClose from '@/assets/svg/close.svg'
import defaultAvatar from '@/assets/svg/defaultAvatar.svg'

const props = defineProps<{
  open: boolean
  anchor?: HTMLElement | null
}>()
const emit = defineEmits<{
  'update:open': [boolean]
}>()

const friends = useFriendsStore()
const confirmState = useConfirmState()
const root = ref<HTMLElement | null>(null)
const inviteOpenFor = ref<number | null>(null)
const inviteDropdownEl = ref<HTMLElement | null>(null)
let inviteReqSeq = 0

const rooms = computed(() => friends.rooms)
const isAccepted = (f: { kind?: string }) => f.kind === 'online' || f.kind === 'offline'
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

function bindDoc() {
  if (onDocDown) return
  onDocDown = (e: Event) => {
    if (confirmState.open) return
    const t = e.target as Node | null
    if (!t) return
    const hasContains = (el: any, target: Node) => typeof el?.contains === 'function' && el.contains(target)
    const inRoot = hasContains(root.value, t)
    const inAnchor = hasContains(props.anchor, t)
    if (inviteOpenFor.value) {
      const dropdown = inviteDropdownEl.value as any
      const inDropdown = Array.isArray(dropdown)
        ? dropdown.some((el) => hasContains(el, t))
        : hasContains(dropdown, t)
      if (inDropdown) return
      inviteOpenFor.value = null
      if (inRoot || inAnchor) return
    }
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

async function refreshRooms() {
  await friends.fetchRooms()
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

function onAfterLeave() {
  inviteOpenFor.value = null
}

async function toggleInvite(uid: number) {
  if (inviteOpenFor.value === uid) {
    inviteOpenFor.value = null
    return
  }
  const reqId = ++inviteReqSeq
  inviteOpenFor.value = null
  try {
    await refreshRooms()
  } catch {
    if (reqId === inviteReqSeq) void alertDialog('Не удалось загрузить список комнат')
    return
  }
  if (reqId !== inviteReqSeq) return
  inviteOpenFor.value = uid
}

async function invite(uid: number, roomId: number) {
  inviteOpenFor.value = null
  try {
    await friends.inviteToRoom(uid, roomId)
  } catch {
    void alertDialog('Не удалось отправить приглашение')
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
    bindDoc()
    await refreshRooms()
    startPolling()
    startAutoClose()
  } else {
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
.panel {
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
          width: 24px;
          height: 24px;
          border-radius: 50%;
        }
        .nick {
          max-width: 165px;
          height: 18px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }
      .info {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 3px;
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
        .invite {
          position: relative;
          .btn {
            display: flex;
            align-items: center;
            padding: 5px 10px;
            height: 25px;
            border: none;
            border-radius: 5px;
            background-color: $dark;
            color: $fg;
            font-size: 12px;
            font-family: Manrope-Medium;
            cursor: pointer;
            transition: background-color 0.25s ease-in-out;
            &:hover {
              background-color: $graphite;
            }
          }
          .invite-dropdown {
            position: absolute;
            top: 30px;
            right: 0;
            display: flex;
            flex-direction: column;
            min-width: 200px;
            max-height: 200px;
            overflow-y: auto;
            padding: 5px;
            gap: 5px;
            border-radius: 5px;
            background-color: $graphite;
            box-shadow: 3px 3px 5px rgba($black, 0.25);
            z-index: 5;
            button {
              height: 28px;
              border: none;
              border-radius: 5px;
              background-color: $lead;
              color: $fg;
              font-size: 12px;
              font-family: Manrope-Medium;
              cursor: pointer;
              transition: background-color 0.25s ease-in-out;
              &:hover {
                background-color: $dark;
              }
            }
            .empty {
              margin: 5px;
              font-size: 12px;
              color: $grey;
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
          padding: 5px 10px;
          height: 25px;
          border: none;
          border-radius: 5px;
          font-size: 12px;
          font-family: Manrope-Medium;
          cursor: pointer;
          transition: background-color 0.25s ease-in-out;
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

.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}
.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(-30px);
}

@media (max-width: 1280px) {
  .panel {
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
    }
  }
}
</style>
