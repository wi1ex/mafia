<template>
  <Header />
  <section class="card card-grid">
    <div class="left">
      <h2 class="title">Комнаты</h2>
      <div v-if="sortedRooms.length === 0" class="muted">Пока пусто</div>
      <ul class="list" ref="listEl">
        <li v-for="r in sortedRooms" :key="r.id" class="item" :class="{ active: r.id === selectedId }" tabindex="0" @click="selectRoom(r.id)">
          <div class="item_main">
            <span class="item_title">#{{ r.id }} — {{ r.title }}</span>
            <span class="item_meta">({{ r.occupancy }}/{{ r.user_limit }}) • владелец: {{ r.creator_name }}</span>
          </div>
          <span class="chev">›</span>
        </li>
      </ul>

      <div v-if="auth.isAuthed" class="create">
        <h3 class="subtitle">Создать комнату</h3>
        <input v-model.trim="title" class="input" placeholder="Название" maxlength="64" />
        <input v-model.number="limit" class="input" type="number" min="2" max="12" placeholder="Лимит" />
        <button class="btn" :disabled="creating || !valid" @click="onCreate">
          {{ creating ? 'Создаю...' : 'Создать' }}
        </button>
      </div>
    </div>

    <aside class="right" aria-live="polite" ref="rightEl" @click.self="clearSelection">
      <div v-if="!selectedId" class="placeholder muted">Скоро здесь будет красиво</div>

      <div v-else class="room-info">
        <div class="ri-head">
          <h3 class="ri-title">#{{ selectedRoom?.id }} — {{ selectedRoom?.title || '...' }}</h3>
          <div class="ri-meta">
            <span>Участников: {{ selectedRoom?.occupancy ?? 0 }}/{{ selectedRoom?.user_limit ?? 0 }}</span>
            <span>Владелец: {{ selectedRoom?.creator_name || '—' }}</span>
          </div>
        </div>

        <div class="ri-members">
          <h4 class="ri-subtitle">В комнате</h4>
          <div v-if="loadingInfo" class="muted">Загрузка…</div>
          <div v-else-if="(info?.members?.length ?? 0) === 0" class="muted">Пока никого</div>
          <ul v-else class="ri-grid">
            <li v-for="m in info!.members" :key="m.id" class="ri-user">
              <img v-minio-img="{ key: m.avatar_name ? `avatars/${m.avatar_name}` : '', placeholder: defaultAvatar }" alt="" class="ri-ava" />
              <div class="ri-u-main">
                <div class="ri-u-name">{{ m.username || ('user' + m.id) }}</div>
              </div>
            </li>
          </ul>
        </div>

        <div class="ri-actions">
          <button v-if="auth.isAuthed && selectedRoom && !isFullRoom(selectedRoom)" class="btn enter" @click="goRoom(selectedRoom.id)">Войти</button>
          <div v-else-if="auth.isAuthed && selectedRoom && isFullRoom(selectedRoom)" class="muted">Комната заполнена</div>
          <div v-else class="muted">Авторизуйтесь, чтобы войти</div>
        </div>
      </div>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed, reactive, watch } from 'vue'
import Header from '@/components/Header.vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store'
import { Socket } from 'socket.io-client'
import { api } from '@/services/axios'
import { createPublicSocket } from '@/services/sio'

import defaultAvatar from "@/assets/svg/defaultAvatar.svg"

type Room = {
  id: number
  title: string
  user_limit: number
  creator: number
  creator_name: string
  created_at: string
  occupancy: number
}
type RoomInfoMember = {
  id: number
  username?: string
  avatar_name?: string | null
}
type RoomMembers = { members: RoomInfoMember[] }

const router = useRouter()
const auth = useAuthStore()

const roomsMap = reactive(new Map<number, Room>())
const sio = ref<Socket | null>(null)
const listEl = ref<HTMLElement | null>(null)
const rightEl = ref<HTMLElement | null>(null)
const suppressedAutoselect = ref(true)

const title = ref('')
const limit = ref(12)
const creating = ref(false)

const infoTimers = new Map<number, number>()
const selectedId = ref<number | null>(null)
const info = ref<RoomMembers | null>(null)
const loadingInfo = ref(false)

const selectedRoom = computed(() => selectedId.value ? (roomsMap.get(selectedId.value) || null) : null)
const valid = computed(() => title.value.length > 0 && limit.value >= 2 && limit.value <= 12)
const sortedRooms = computed(() => Array.from(roomsMap.values()).sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)))

function isFullRoom(r: Room) { return r.occupancy >= r.user_limit }
function upsert(r: Room) { roomsMap.set(r.id, { ...(roomsMap.get(r.id) || {} as Room), ...r }) }
function remove(id: number) {
  roomsMap.delete(id)
  if (selectedId.value === id) {
    selectedId.value = null
    info.value = null
  }
}

async function fetchRoomInfo(id: number) {
  loadingInfo.value = true
  try {
    const { data } = await api.get<RoomMembers>(`/rooms/${id}/info`, { __skipAuth: true })
    info.value = data
  } catch {
    info.value = null
  } finally {
    loadingInfo.value = false
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

function goRoom(id: number) { router.push(`/room/${id}`) }

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
    transports: ['websocket'],
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
}

function stopWS() {
  try { sio.value?.off?.() } catch {}
  try { sio.value?.close?.() } catch {}
  sio.value = null
}

async function createRoom(title: string, user_limit: number) {
  const { data } = await api.post<Room>('/rooms', { title, user_limit })
  upsert(data)
  return data
}
async function onCreate() {
  if (!valid.value || creating.value) return
  creating.value = true
  try {
    const r = await createRoom(title.value, limit.value)
    await router.push(`/room/${r.id}`)
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 409 && d === 'rooms_limit_global')      alert('Достигнут общий лимит активных комнат (100). Попробуйте позже.')
    else if (st === 409 && d === 'rooms_limit_user')   alert('У вас уже 3 активные комнаты. Закройте одну и попробуйте снова.')
    else if (st === 422 && (d === 'title_empty'))      alert('Название не должно быть пустым')
    else if (typeof d === 'string' && d)               alert(d)
    else if (d && typeof d === 'object' && d.detail)   alert(String(d.detail))
    else                                               alert('Ошибка создания комнаты')
  } finally { creating.value = false }
}

onMounted(() => {
  startWS()
  document.addEventListener('pointerdown', onGlobalPointerDown, { capture: true })
})

onBeforeUnmount(() => {
  infoTimers.forEach((t) => { try { clearTimeout(t) } catch {} })
  infoTimers.clear()
  stopWS()
  try { document.removeEventListener('pointerdown', onGlobalPointerDown, { capture: true } as any) } catch {}
})
</script>

<style lang="scss" scoped>
.card {
  &.card-grid {
    display: grid;
    grid-template-columns: 1fr 420px;
    gap: 16px;
    padding: 12px 16px;
  }
  .left {
    .title {
      color: $fg;
    }
  }
  .muted {
    color: $muted;
  }
  .list {
    margin: 8px 0 0;
    padding: 0;
    list-style: none;
  }
  .item {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    margin: 6px 0;
    border: 1px solid transparent;
    border-radius: 10px;
    cursor: pointer;
    color: $fg;
    background: transparent;
    transition: border-color 0.15s ease-in-out, background 0.15s ease-in-out;
    &:hover {
      border-color: rgba(255, 255, 255, 0.15);
      background: rgba(255, 255, 255, 0.03);
    }
    &.active {
      border-color: $color-secondary;
      background: rgba(14, 165, 233, 0.07);
    }
    .item_main {
      display: flex;
      align-items: baseline;
      gap: 6px;
      .item_title {
        font-weight: 600;
      }
      .item_meta {
        margin-left: 6px;
        color: $muted;
      }
    }
    .chev {
      opacity: 0.6;
    }
  }
  .create {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 16px;
  }
  .input {
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid $fg;
    color: $fg;
    background: $bg;
  }
  .btn {
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    background: $color-primary;
    color: $bg;
  }
  .right {
    position: sticky;
    top: 12px;
    align-self: start;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
  }
  .placeholder {
    padding: 8px 4px;
  }
  .room-info {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px;
    .ri-head {
      .ri-title {
        margin: 0;
        color: $fg;
      }
      .ri-meta {
        display: flex;
        gap: 10px;
        color: $muted;
      }
    }
    .ri-members {
      .ri-subtitle {
        margin: 6px 0;
        color: $fg;
      }
      .ri-grid {
        list-style: none;
        margin: 8px 0 0;
        padding: 0;
        display: grid;
        grid-template-columns: 1fr;
        gap: 8px;
        max-height: 420px;
        overflow: auto;
        .ri-user {
          display: flex;
          gap: 10px;
          align-items: center;
          .ri-ava {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            object-fit: cover;
            background: $black;
          }
          .ri-u-main {
            .ri-u-name {
              font-weight: 600;
            }
          }
        }
      }
    }
    .ri-actions {
      .enter {
        width: 100%;
      }
    }
  }
}
</style>
