<template>
  <section class="card">
    <div class="left">
      <div v-if="auth.isAuthed" class="create">
        <button @click="openCreate = true">Создать комнату</button>
      </div>

      <RoomModal v-if="openCreate" @close="openCreate=false" @created="onCreated" />

      <div v-if="sortedRooms.length === 0" class="muted">Пока пусто</div>
      <ul v-else class="list" ref="listEl">
        <li class="item" v-for="r in sortedRooms" :key="r.id" :class="{ active: r.id === selectedId }" tabindex="0" @click="selectRoom(r.id)">
          <div class="item_main">
            <span class="item_title">Комната #{{ r.id }}: {{ r.title }}</span>
            <div class="item_meta">
              <span>({{ r.occupancy }}/{{ r.user_limit }})</span>
              <span class="badge" :data-kind="r.privacy === 'private' ? 'priv' : 'open'">
                {{ r.privacy === 'private' ? 'Приватная' : 'Открытая' }}
              </span>
              <img class="owner_ava" v-minio-img="{ key: r.creator_avatar_name ? `avatars/${r.creator_avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
              <span>Владелец: {{ r.creator_name }}</span>
            </div>
          </div>
        </li>
      </ul>
    </div>

    <aside class="right" aria-live="polite" ref="rightEl" @click.self="clearSelection">
      <div v-if="!selectedId" class="placeholder">Выберите комнату для отображения информации</div>

      <div v-else class="room-info">
        <div class="ri-title">
          <div class="ri-actions">
            <template v-if="auth.isAuthed && selectedRoom">
              <button v-if="selectedRoom.privacy === 'open' && !isFullRoom(selectedRoom)" :disabled="entering" @click="onEnter">{{ entering ? 'Вхожу...' : 'Войти в комнату' }}</button>
              <template v-else-if="selectedRoom.privacy === 'private'">
                <button v-if="access==='approved' && !isFullRoom(selectedRoom)" :disabled="entering" @click="onEnter">{{ entering ? 'Вхожу...' : 'Войти в комнату' }}</button>
                <button v-else-if="access==='none'" :disabled="false" @click="onApply">Подать заявку</button>
                <button v-else disabled>Заявка отправлена</button>
              </template>
              <div v-else class="muted">Комната заполнена</div>
            </template>
            <div v-else class="muted">Авторизуйтесь, чтобы войти</div>
          </div>
          <p class="ri-name">Комната #{{ selectedRoom?.id }}: {{ selectedRoom?.title }}</p>
        </div>

        <div class="ri-meta">
          <span class="owner">
            <img class="owner_ava" v-minio-img="{ key: selectedRoom?.creator_avatar_name ? `avatars/${selectedRoom!.creator_avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
            <span>Владелец: {{ selectedRoom?.creator_name }}</span>
          </span>
          <span>Приватность: {{ (selectedRoom?.privacy === 'private') ? 'закрытая' : 'открытая' }}</span>
        </div>

        <div class="ri-members">
          <p class="ri-subtitle">Участники: {{ selectedRoom?.occupancy ?? 0 }}/{{ selectedRoom?.user_limit ?? 0 }}</p>
          <div v-if="(info?.members?.length ?? 0) === 0" class="muted">Пока никого</div>
          <ul v-else class="ri-grid">
            <li class="ri-user" v-for="m in info!.members" :key="m.id">
              <img v-minio-img="{ key: m.avatar_name ? `avatars/${m.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
              <p class="ri-u-name">{{ m.username || ('user' + m.id) }}</p>
              <img v-if="m.screen" :src="iconScreenOn" alt="streaming" />
            </li>
          </ul>
        </div>
      </div>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed, reactive, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/store'
import { Socket } from 'socket.io-client'
import { api } from '@/services/axios'
import { createPublicSocket } from '@/services/sio'
import RoomModal from '@/components/RoomModal.vue'

import defaultAvatar from "@/assets/svg/defaultAvatar.svg"
import iconScreenOn from '@/assets/svg/screenOn.svg'

type Room = {
  id: number
  title: string
  user_limit: number
  privacy: 'open' | 'private'
  creator: number
  creator_name: string
  creator_avatar_name?: string | null
  created_at: string
  occupancy: number
}
type RoomInfoMember = {
  id: number
  username?: string
  avatar_name?: string | null
  screen?: boolean
}
type RoomMembers = { members: RoomInfoMember[] }
type Access = 'approved'|'pending'|'none'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const roomsMap = reactive(new Map<number, Room>())
const sio = ref<Socket | null>(null)
const listEl = ref<HTMLElement | null>(null)
const rightEl = ref<HTMLElement | null>(null)
const suppressedAutoselect = ref(true)

const entering = ref(false)
const infoTimers = new Map<number, number>()
const infoInFlight = new Set<number>()
const selectedId = ref<number | null>(null)
const info = ref<RoomMembers | null>(null)

const openCreate = ref(false)
const access = ref<Access>('approved')

const selectedRoom = computed(() => selectedId.value ? (roomsMap.get(selectedId.value) || null) : null)
const sortedRooms = computed(() => Array.from(roomsMap.values()).sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)))

function isFullRoom(r: Room) { return r.occupancy >= r.user_limit }

function upsert(r: Room) { roomsMap.set(r.id, { ...(roomsMap.get(r.id) || {} as Room), ...r }) }

function remove(id: number) {
  roomsMap.delete(id)
  if (selectedId.value === id) {
    selectedId.value = null
    info.value = null
    suppressedAutoselect.value = true
    const t = infoTimers.get(id)
    if (t) {
      try { clearTimeout(t) } catch {}
      infoTimers.delete(id)
    }
  }
}

async function onCreated(room: any) {
  openCreate.value = false
  await router.push(`/room/${room.id}`)
}

async function fetchAccess(id: number) {
  if (!auth.isAuthed) {
    access.value = 'none'
    return
  }
  try {
    const { data } = await api.get(`/rooms/${id}/access`)
    access.value = data.access
  } catch { access.value = 'none' }
}

async function onApply() {
  const id = selectedRoom.value?.id
  if (!id) return
  try {
    await api.post(`/rooms/${id}/apply`)
    access.value='pending'
  }
  catch (e: any) { alert('Ошибка отправки заявки') }
}

async function fetchRoomInfo(id: number) {
  if (infoInFlight.has(id)) return
  infoInFlight.add(id)
  try {
    const { data } = await api.get<RoomMembers>(`/rooms/${id}/info`, { __skipAuth: true })
    info.value = data
  } catch {
    info.value = null
  } finally {
    infoInFlight.delete(id)
  }
}

function selectRoom(id: number) {
  if (selectedId.value === id) return
  suppressedAutoselect.value = false
  const prevId = selectedId.value
  selectedId.value = id
  if (prevId != null) {
    const t = infoTimers.get(prevId)
    if (t) {
      try { clearTimeout(t) } catch {}
      infoTimers.delete(prevId)
    }
  }
  void fetchRoomInfo(id)
}

function clearSelection() {
  if (selectedId.value == null) return
  const prevId = selectedId.value
  selectedId.value = null
  info.value = null
  suppressedAutoselect.value = true
  const t = infoTimers.get(prevId)
  if (t) {
    try { clearTimeout(t) } catch {}
    infoTimers.delete(prevId)
  }
}

function onGlobalPointerDown(e: PointerEvent) {
  const target = e.target as Node | null
  if ( (target && listEl.value && listEl.value.contains(target)) || (target && rightEl.value && rightEl.value.contains(target)) ) return
  clearSelection()
}

async function onEnter() {
  const id = selectedRoom?.value?.id
  if (!id || entering.value) return
  entering.value = true
  try { await router.push(`/room/${id}`) }
  finally { entering.value = false }
}

async function syncRoomsSnapshot() {
  if (!sio.value) return
  try {
    const resp: any = await sio.value.timeout(1500).emitWithAck('rooms_list')
    if (!resp?.ok || !Array.isArray(resp.rooms)) return
    const nextIds = new Set<number>()
    for (const r of resp.rooms as Room[]) {
      nextIds.add(r.id)
      upsert(r)
    }
    for (const id of Array.from(roomsMap.keys())) if (!nextIds.has(id)) roomsMap.delete(id)
  } catch {}
}

function startWS() {
  if (sio.value && (sio.value.connected || (sio.value as any).connecting)) return
  sio.value = createPublicSocket('/rooms', {
    path: '/ws/socket.io',
    transports: ['websocket','polling'],
    upgrade: true,
    autoConnect: true,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 500,
    reconnectionDelayMax: 5000,
  })

  sio.value.on('connect', syncRoomsSnapshot)

  sio.value.on('rooms_upsert', (r: Room) => {
    upsert(r)
    if (!selectedId.value && !suppressedAutoselect.value) selectRoom(r.id)
  })

  sio.value.on('rooms_remove', (p: { id: number }) => remove(p.id))

  sio.value.on('rooms_occupancy', async (p: { id: number; occupancy: number }) => {
    const cur = roomsMap.get(p.id)
    if (cur) roomsMap.set(p.id, { ...cur, occupancy: p.occupancy })
    if (selectedId.value === p.id) {
      const prev = infoTimers.get(p.id)
      if (prev) window.clearTimeout(prev)
      const roomId = p.id
      const t = window.setTimeout(() => {
        if (selectedId.value !== roomId) return
        void fetchRoomInfo(roomId)
        infoTimers.delete(roomId)
      }, 500)
      infoTimers.set(p.id, t)
    }
  })

  sio.value.on('rooms_stream', (p: { id: number; owner: number | null }) => {
    if (selectedId.value !== p.id) return
    const prev = infoTimers.get(p.id)
    if (prev) window.clearTimeout(prev)
    const roomId = p.id
    const t = window.setTimeout(() => {
      if (selectedId.value !== roomId) return
      void fetchRoomInfo(roomId)
      infoTimers.delete(roomId)
    }, 300)
    infoTimers.set(p.id, t)
  })
}

function stopWS() {
  try { sio.value?.off?.() } catch {}
  try { sio.value?.close?.() } catch {}
  sio.value = null
}

const onRoomApproved = (e: any) => {
  const rid = Number(e?.detail?.roomId)
  if (selectedId.value && rid === selectedId.value) access.value = 'approved'
}

watch(selectedId, (id) => {
  if (id) { void fetchAccess(id) }
})

watch(() => route.query.focus, (v) => {
  const id = Number(v)
  if (Number.isFinite(id)) selectRoom(id)
})

onMounted(() => {
  startWS()

  document.addEventListener('pointerdown', onGlobalPointerDown, { capture: true })

  const f = Number(route.query.focus)
  if (Number.isFinite(f)) selectRoom(f)

  window.addEventListener('room-approved', onRoomApproved)
})

onBeforeUnmount(() => {
  infoTimers.forEach((t) => { try { clearTimeout(t) } catch {} })
  infoTimers.clear()
  stopWS()
  try { document.removeEventListener('pointerdown', onGlobalPointerDown, { capture: true } as any) } catch {}
  try { window.removeEventListener('room-approved', onRoomApproved) } catch {}
})
</script>

<style lang="scss" scoped>
.card {
  display: grid;
  grid-template-columns: 1fr 400px;
  padding: 0 10px;
  gap: 10px;
  .left {
    display: flex;
    flex-direction: column;
    padding: 10px;
    gap: 10px;
    border-radius: 5px;
    background-color: $dark;
    .create {
      display: flex;
      margin: 10px 0 20px;
      gap: 10px;
      p {
        margin: 0;
        color: $fg;
        font-size: 24px;
      }
      input {
        padding: 8px 10px;
        border-radius: 5px;
        border: 1px solid $fg;
        color: $fg;
        background-color: $bg;
      }
      button {
        padding: 0 10px;
        height: 33px;
        border-radius: 5px;
        border: none;
        background-color: $green;
        color: $bg;
        cursor: pointer;
        &:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
      }
    }
    .muted {
      color: $grey;
    }
    .list {
      margin: 0;
      padding: 0;
      gap: 5px;
      list-style: none;
      .item {
        display: flex;
        grid-template-columns: 1fr auto;
        align-items: center;
        gap: 10px;
        padding: 10px 0;
        margin: 0;
        border: 1px solid transparent;
        border-radius: 5px;
        cursor: pointer;
        color: $fg;
        background: transparent;
        transition: border-color 0.25s ease-in-out, background 0.25s ease-in-out;
        &.active {
          border-color: $blue;
          background-color: rgba(14, 165, 233, 0.07);
        }
        .item_main {
          display: flex;
          align-items: baseline;
          gap: 10px;
          .item_title {
            font-weight: 600;
          }
          .item_meta {
            display: flex;
            align-items: center;
            gap: 6px;
            .owner_ava {
              width: 18px;
              height: 18px;
              border-radius: 50%;
              object-fit: cover;
            }
            .badge {
              padding: 0 6px;
              border-radius: 4px;
              font-size: 12px;
              background: $graphite;
              &[data-kind="priv"] {
                background: rgba(239, 68, 68, 0.25);
              }
              &[data-kind="open"] {
                background: rgba(34, 197, 94, 0.25);
              }
            }
          }
        }
      }
    }
  }
  .right {
    display: flex;
    position: sticky;
    flex-direction: column;
    padding: 10px;
    border-radius: 5px;
    background-color: $dark;
    .placeholder {
      margin: auto;
      text-align: center;
    }
    .room-info {
      display: flex;
      flex-direction: column;
      gap: 20px;
      .ri-title {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
        .ri-actions {
          display: flex;
          button {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0 20px;
            height: 40px;
            border: none;
            border-radius: 5px;
            background-color: $green;
            color: $bg;
            font-size: 16px;
            font-family: Manrope-Medium;
            line-height: 1;
            cursor: pointer;
            &:disabled {
              opacity: 0.6;
              cursor: not-allowed;
            }
          }
          .muted {
            color: $grey;
          }
        }
        .ri-name {
          margin: 0;
          color: $fg;
          font-size: 24px;
        }
      }
      .ri-meta {
        display: flex;
        flex-direction: column;
        gap: 5px;
        color: $grey;
        .owner {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          .owner_ava {
            width: 18px;
            height: 18px;
            border-radius: 50%;
            object-fit: cover;
          }
        }
      }
      .ri-members {
        display: flex;
        flex-direction: column;
        gap: 10px;
        .ri-subtitle {
          margin: 0;
          color: $fg;
          font-size: 20px;
        }
        .muted {
          width: 50%;
          height: 35px;
          border-radius: 5px;
          background-color: $graphite;
        }
        .ri-grid {
          display: grid;
          grid-template-columns: 1fr;
          margin: 0;
          padding: 0;
          gap: 5px;
          max-height: 420px;
          list-style: none;
          overflow: auto;
          .ri-user {
            display: flex;
            align-items: center;
            gap: 5px;
            width: 100%;
            height: 30px;
            img {
              width: 24px;
              height: 24px;
              border-radius: 50%;
              object-fit: cover;
            }
            .ri-u-name {
              margin: 0;
            }
          }
        }
      }
    }
  }
}
</style>
