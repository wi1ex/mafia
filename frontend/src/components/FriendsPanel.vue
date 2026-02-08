<template>
  <Transition name="panel" @after-leave="onAfterLeave">
    <div v-show="open" class="panel" ref="root" @click.stop>
      <header>
        <span>Друзья</span>
        <button @click="$emit('update:open', false)" aria-label="Закрыть">
          <img :src="iconClose" alt="close" />
        </button>
      </header>

      <div class="tabs">
        <button :class="{ active: tab === 'online' }" @click="tab = 'online'">Онлайн</button>
        <button :class="{ active: tab === 'offline' }" @click="tab = 'offline'">Оффлайн</button>
        <button :class="{ active: tab === 'incoming' }" @click="tab = 'incoming'">Входящие</button>
        <button :class="{ active: tab === 'outgoing' }" @click="tab = 'outgoing'">Исходящие</button>
      </div>

      <div class="list" ref="list">
        <template v-if="tab === 'online' || tab === 'offline'">
          <article class="item" v-for="f in friendList" :key="f.id">
            <div class="left">
              <img v-minio-img="{ key: f.avatar_name ? `avatars/${f.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
              <div class="name">
                <span class="nick">{{ f.username || ('user' + f.id) }}</span>
                <span class="dot" :class="{ on: f.online, off: !f.online }"></span>
              </div>
            </div>
            <div class="info">
              <template v-if="f.room_id">
                <span class="room">Комната: {{ f.room_title || ('Комната #' + f.room_id) }}</span>
                <span class="game" :class="{ active: f.room_in_game }">{{ f.room_in_game ? 'Идёт игра' : 'Ожидание' }}</span>
              </template>
              <template v-else>
                <div class="invite">
                  <button class="btn" @click="toggleInvite(f.id)">Пригласить в комнату</button>
                  <div v-if="inviteOpenFor === f.id" class="invite-dropdown">
                    <button v-for="r in rooms" :key="r.id" @click="invite(f.id, r.id)">{{ r.title }}</button>
                    <p v-if="rooms.length === 0" class="empty">Нет активных комнат</p>
                  </div>
                </div>
              </template>
            </div>
            <div class="actions">
              <button class="danger" @click="remove(f.id)">Удалить</button>
            </div>
          </article>
          <p v-if="friendList.length === 0" class="empty">Список пуст</p>
        </template>

        <template v-else-if="tab === 'incoming'">
          <article class="item" v-for="f in friends.list.incoming" :key="f.id">
            <div class="left">
              <img v-minio-img="{ key: f.avatar_name ? `avatars/${f.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
              <div class="name">
                <span class="nick">{{ f.username || ('user' + f.id) }}</span>
              </div>
            </div>
            <div class="actions">
              <button class="accept" @click="accept(f.id)">Принять</button>
              <button class="danger" @click="decline(f.id)">Отклонить</button>
            </div>
          </article>
          <p v-if="friends.list.incoming.length === 0" class="empty">Запросов нет</p>
        </template>

        <template v-else>
          <article class="item" v-for="f in friends.list.outgoing" :key="f.id">
            <div class="left">
              <img v-minio-img="{ key: f.avatar_name ? `avatars/${f.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
              <div class="name">
                <span class="nick">{{ f.username || ('user' + f.id) }}</span>
              </div>
            </div>
          </article>
          <p v-if="friends.list.outgoing.length === 0" class="empty">Запросов нет</p>
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
const list = ref<HTMLElement | null>(null)
const tab = ref<'online' | 'offline' | 'incoming' | 'outgoing'>('online')
const inviteOpenFor = ref<number | null>(null)

const friendList = computed(() => (tab.value === 'online' ? friends.list.online : friends.list.offline))
const rooms = computed(() => friends.rooms)

let onDocDown: ((e: Event) => void) | null = null

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

async function refresh() {
  await friends.fetchAll()
  await friends.fetchRooms()
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
    await friends.fetchAll()
  } catch {
    void alertDialog('Не удалось удалить из друзей')
  }
}

async function accept(uid: number) {
  try {
    await friends.acceptRequest(uid)
    await friends.fetchAll()
  } catch {
    void alertDialog('Не удалось принять запрос')
  }
}

async function decline(uid: number) {
  try {
    await friends.declineRequest(uid)
    await friends.fetchAll()
  } catch {
    void alertDialog('Не удалось отклонить запрос')
  }
}

watch(() => props.open, async v => {
  if (v) {
    await nextTick()
    bindDoc()
    await refresh()
  } else {
    unbindDoc()
  }
})

onBeforeUnmount(() => {
  unbindDoc()
})
</script>

<style scoped lang="scss">
.panel {
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  top: 50px;
  width: 500px;
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
  .tabs {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 5px;
    padding: 10px;
    button {
      height: 28px;
      border: none;
      border-radius: 5px;
      background-color: $dark;
      color: $fg;
      font-size: 12px;
      font-family: Manrope-Medium;
      cursor: pointer;
      &.active {
        background-color: $lead;
      }
    }
  }
  .list {
    display: flex;
    flex-direction: column;
    margin: 0 10px 10px;
    gap: 10px;
    overflow-y: auto;
    scrollbar-width: none;
  }
  .item {
    display: grid;
    grid-template-columns: 1fr 1.2fr auto;
    align-items: center;
    gap: 10px;
    padding: 10px;
    border-radius: 5px;
    background-color: $lead;
    box-shadow: 0 3px 5px rgba($black, 0.25);
    .left {
      display: flex;
      align-items: center;
      gap: 8px;
      img {
        width: 30px;
        height: 30px;
        border-radius: 50%;
      }
      .name {
        display: flex;
        align-items: center;
        gap: 6px;
        .nick {
          max-width: 160px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          &.on { background-color: $green; }
          &.off { background-color: $grey; }
        }
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
        &.active { color: $green; }
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
