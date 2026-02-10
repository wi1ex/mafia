<template>
  <Transition name="panel" @after-leave="onAfterLeave">
    <div v-show="open" class="panel" ref="root" @click.stop>
      <header>
        <span>Друзья</span>
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
                    <span class="room">Комната: {{ f.room_title || ('Комната #' + f.room_id) }}</span>
                    <span class="game" :class="{ active: f.room_in_game }">{{ f.room_in_game ? 'Идёт игра' : 'Ожидание' }}</span>
                  </template>
                  <template v-else>
                    <div class="invite">
                      <button class="btn" @click="toggleInvite(f.id)">Пригласить</button>
                      <div v-if="inviteOpenFor === f.id" class="invite-dropdown">
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
import { confirmDialog, alertDialog } from '@/services/confirm'

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
const root = ref<HTMLElement | null>(null)
const inviteOpenFor = ref<number | null>(null)

const rooms = computed(() => friends.rooms)
const isAccepted = (f: { kind?: string }) => f.kind === 'online' || f.kind === 'offline'
const sections = computed(() => [
  { kind: 'incoming', title: 'Входящие заявки', items: friends.list.filter(f => f.kind === 'incoming') },
  { kind: 'online', title: 'В сети', items: friends.list.filter(f => f.kind === 'online') },
  { kind: 'offline', title: 'Не в сети', items: friends.list.filter(f => f.kind === 'offline') },
  { kind: 'outgoing', title: 'Исходящие заявки', items: friends.list.filter(f => f.kind === 'outgoing') },
])
const hasNextSection = (idx: number) => sections.value.slice(idx + 1).some(s => s.items.length > 0)

let onDocDown: ((e: Event) => void) | null = null
let pollTimer: number | undefined
const POLL_MS = 3000

function bindDoc() {
  if (onDocDown) return
  onDocDown = (e: Event) => {
    const t = e.target as Node | null
    if (!t) return
    if (root.value?.contains(t)) return
    if (props.anchor && props.anchor.contains(t)) return
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

function onAfterLeave() {
  inviteOpenFor.value = null
}

function toggleInvite(uid: number) {
  inviteOpenFor.value = inviteOpenFor.value === uid ? null : uid
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
  try {
    await friends.acceptRequest(uid)
    await friends.fetchList()
  } catch {
    void alertDialog('Не удалось принять запрос')
  }
}

async function decline(uid: number) {
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
  } else {
    unbindDoc()
    stopPolling()
  }
})

onBeforeUnmount(() => {
  unbindDoc()
  stopPolling()
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
      justify-content: space-between;
      font-size: 14px;
      font-family: Manrope-Medium;
      color: $grey;
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
      grid-template-columns: 1fr 1fr auto;
      align-items: center;
      padding: 5px;
      gap: 10px;
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
          max-width: 150px;
          height: 18px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }
      .info {
        display: flex;
        flex-direction: column;
        gap: 4px;
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
            height: 28px;
            border: none;
            border-radius: 5px;
            background-color: $dark;
            color: $fg;
            font-size: 12px;
            font-family: Manrope-Medium;
            cursor: pointer;
          }
          .invite-dropdown {
            position: absolute;
            top: 32px;
            left: 0;
            display: flex;
            flex-direction: column;
            min-width: 220px;
            max-height: 240px;
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
              &:hover { background-color: $dark; }
            }
            .empty {
              margin: 5px;
              color: $grey;
            }
          }
        }
      }
      .actions {
        display: flex;
        gap: 6px;
        button {
          height: 28px;
          border: none;
          border-radius: 5px;
          padding: 0 10px;
          font-size: 12px;
          font-family: Manrope-Medium;
          cursor: pointer;
        }
        .accept {
          background-color: rgba($green, 0.75);
          color: $bg;
        }
        .danger {
          background-color: rgba($red, 0.75);
          color: $bg;
        }
      }
    }
    .empty {
      color: $grey;
      text-align: center;
      margin: 20px 0;
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
    width: 95vw;
    max-height: calc(100dvh - 70px);
  }
  .item {
    grid-template-columns: 1fr;
    .info {
      order: 3;
    }
    .actions {
      order: 2;
      justify-content: flex-end;
    }
  }
}
</style>
