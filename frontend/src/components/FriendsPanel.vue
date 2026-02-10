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
                  <div v-if="f.room_id" class="room-info">
                    <span class="room">{{ f.room_title || ('Комната #' + f.room_id) }}</span>
                    <span class="game" :class="{ active: f.room_in_game }">{{ f.room_in_game ? 'Игра' : 'Лобби' }}</span>
                  </div>
                  <div class="invite-select" :class="{ open: inviteOpenFor === f.id }">
                    <button type="button" class="icon-btn invite-btn" @click="toggleInvite(f.id)" :aria-expanded="String(inviteOpenFor === f.id)" :aria-label="inviteLabel(f.kind)">
                      <img :src="inviteIcon(f.kind)" alt="" />
                    </button>
                    <Transition name="menu">
                      <ul v-show="inviteOpenFor === f.id" role="listbox">
                        <li v-for="r in rooms" :key="r.id" class="option" @click="invite(f.id, r.id)">
                          <span>{{ r.title }}</span>
                        </li>
                        <li v-if="rooms.length === 0" class="empty" aria-disabled="true">Нет активных комнат</li>
                      </ul>
                    </Transition>
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
import { ref, watch, nextTick, onBeforeUnmount, computed } from 'vue'
import { useFriendsStore } from '@/store'
import { confirmDialog, alertDialog, useConfirmState } from '@/services/confirm'

import iconClose from '@/assets/svg/close.svg'
import iconAccept from '@/assets/svg/readyBlack.svg'
import iconRemove from '@/assets/svg/delete.svg'
import iconInviteOnline from '@/assets/svg/notifBell.svg'
import iconInviteOffline from '@/assets/svg/telegram.svg'
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
let inviteReqSeq = 0

const rooms = computed(() => friends.rooms)
const isAccepted = (f: { kind?: string }) => f.kind === 'online' || f.kind === 'offline'
const inviteIcon = (kind?: string) => kind === 'online' ? iconInviteOnline : iconInviteOffline
const inviteLabel = (kind?: string) => kind === 'online' ? 'Пригласить онлайн-друга в комнату' : 'Пригласить офлайн-друга в комнату'
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
      if (t instanceof Element && t.closest('.invite-select')) return
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
            &:hover {
              background-color: $graphite;
            }
            img {
              width: 16px;
              height: 16px;
            }
          }
          &.open .invite-btn {
            background-color: $graphite;
          }
        }
        ul {
          position: absolute;
          top: 30px;
          right: 0;
          margin: 0;
          padding: 0;
          width: 200px;
          max-height: 200px;
          border: 1px solid $grey;
          border-radius: 5px;
          background-color: $graphite;
          z-index: 30;
          overflow-y: auto;
          .option {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            padding: 10px;
            cursor: pointer;
            transition: background-color 0.25s ease-in-out;
            &:hover {
              background-color: $lead;
            }
            span {
              font-size: 12px;
              color: $fg;
            }
          }
          .empty {
            margin: 10px;
            color: $ashy;
            font-size: 12px;
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

.menu-enter-active,
.menu-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
  will-change: opacity, transform;
}
.menu-enter-from,
.menu-leave-to {
  opacity: 0;
  transform: translateY(30px);
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
          ul {
            .option {
              padding: 5px;
              span {
                font-size: 10px;
              }
            }
            .empty {
              margin: 5px;
              font-size: 10px;
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
