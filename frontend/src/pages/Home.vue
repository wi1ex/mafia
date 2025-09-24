<template>
  <Header />
  <section class="card">
    <h2 class="title">Комнаты</h2>

    <div v-if="sortedRooms.length === 0" class="muted">Пока пусто</div>
    <ul class="list">
      <li v-for="r in sortedRooms" :key="r.id" class="item">
        <span class="item_title">#{{ r.id }} — {{ r.title }}</span>
        <span class="item_meta">({{ r.occupancy }}/{{ r.user_limit }})</span>
        <router-link v-if="auth.isAuthed && !isFull(r)" :to="`/room/${r.id}`" class="link">
          Открыть
        </router-link>
        <div v-else-if="auth.isAuthed && isFull(r)" class="link disabled" aria-disabled="true" title="Комната заполнена">
          Заполнена
        </div>
        <div v-else class="link disabled" aria-disabled="true">Войдите, чтобы открыть</div>
      </li>
    </ul>

    <div v-if="auth.isAuthed" class="create">
      <h3 class="subtitle">Создать комнату</h3>
      <input v-model.trim="title" class="input" placeholder="Название" maxlength="64" />
      <input v-model.number="limit" class="input" type="number" min="2" max="20" placeholder="Лимит" />
      <button class="btn" :disabled="creating || !valid" @click="onCreate">
        {{ creating ? 'Создаю…' : 'Создать' }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed, reactive } from 'vue'
import Header from '@/components/Header.vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store'
import { Socket } from 'socket.io-client'
import { api } from '@/services/axios'
import { createPublicSocket } from '@/services/sio'

type Room = {
  id: number
  title: string
  user_limit: number
  creator: number
  created_at: string
  occupancy: number
}

const router = useRouter()
const auth = useAuthStore()

const roomsMap = reactive(new Map<number, Room>())
const sio = ref<Socket | null>(null)

const title = ref('')
const limit = ref(12)
const creating = ref(false)
const valid = computed(() => (title.value || '').length > 0 && limit.value >= 2 && limit.value <= 20)

const sortedRooms = computed(() => {
  return Array.from(roomsMap.values()).sort((a, b) => {
    const ta = Date.parse(a.created_at)
    const tb = Date.parse(b.created_at)
    return ta - tb
  })
})

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
    for (const id of Array.from(roomsMap.keys())) {
      if (!nextIds.has(id)) roomsMap.delete(id)
    }
  } catch (e) {
    console.warn('rooms list ack failed', e)
  }
}

function upsert(r: Room) {
  const prev = roomsMap.get(r.id)
  roomsMap.set(r.id, { ...(prev || {} as Room), ...r })
}

function remove(id: number) {
  roomsMap.delete(id)
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

  sio.value.on('rooms_upsert', (r: Room) => upsert(r))

  sio.value.on('rooms_remove', (p: { id: number }) => remove(p.id))

  sio.value.on('rooms_occupancy', (p: { id: number; occupancy: number }) => {
    const cur = roomsMap.get(p.id)
    if (cur) roomsMap.set(p.id, { ...cur, occupancy: p.occupancy })
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
  } finally {
    creating.value = false
  }
}

function isFull(r: Room) {
  return r.occupancy >= r.user_limit
}

onMounted(async () => {
  startWS()
})

onBeforeUnmount(() => {
  stopWS()
})
</script>

<style lang="scss" scoped>
.card {
  padding: 12px 16px;
  .title {
    color: $fg;
  }
  .subtitle {
    color: $fg;
  }
  .muted {
    color: $muted;
  }
  .list {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .item {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 8px 0;
    color: $fg;
    &_title {
      font-weight: 500;
    }
    &_meta {
      color: $muted;
    }
  }
  .link {
    margin-left: auto;
    text-decoration: underline;
    color: $fg;
    &.disabled {
      opacity: 0.5;
      cursor: not-allowed;
      pointer-events: none;
    }
  }
  .create {
    display: flex;
    align-items: center;
    gap: 8px;
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
}
</style>
