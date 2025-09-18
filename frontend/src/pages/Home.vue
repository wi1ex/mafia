<template>
  <Header />
  <section class="card">
    <h2 class="title">Комнаты</h2>
    <div v-if="rooms.length===0" class="muted">Пока пусто</div>
    <ul class="list">
      <li v-for="r in rooms" :key="r.id" class="item">
        <span class="item__title">#{{ r.id }} — {{ r.title }}</span>
        <span class="item__meta">({{ r.occupancy }}/{{ r.user_limit }})</span>
        <router-link v-if="auth.isAuthed" :to="`/room/${r.id}`" class="link">Открыть</router-link>
        <div v-else class="link disabled">Войдите, чтобы открыть</div>
      </li>
    </ul>

    <div v-if="auth.isAuthed" class="create">
      <h3 class="subtitle">Создать комнату</h3>
      <input v-model.trim="title" class="input" placeholder="Название" />
      <input v-model.number="limit" class="input" type="number" min="2" max="20" placeholder="Лимит" />
      <button class="btn btn-primary" :disabled="creating || !valid" @click="onCreate">
        {{ creating ? 'Создаю…' : 'Создать' }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from 'vue'
import Header from '@/components/Header.vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/modules/auth'
import { io, Socket } from 'socket.io-client'
import { api } from '@/services/axios'

type Room = { id:number; title:string; user_limit:number; is_private:boolean; creator:number; created_at:string; occupancy:number }

const router = useRouter()
const auth = useAuthStore()

const rooms = ref<Room[]>([])
const sio = ref<Socket|null>(null)

function upsert(r: Room) {
  const i = rooms.value.findIndex(x => x.id === r.id)
  if (i>=0) rooms.value[i] = { ...rooms.value[i], ...r }
  else rooms.value.push(r)
}

async function load() {
  const { data } = await api.get<Room[]>('/rooms')
  rooms.value = data
}

function startWS() {
  if (sio.value && (sio.value.connected || (sio.value as any).connecting)) return

  sio.value = io('/rooms', {
    path:'/ws/socket.io',
    transports:['websocket']
  })

  sio.value.on('connect', async () => {
    try {
      const { data } = await api.get<Room[]>('/rooms', { headers: { 'Cache-Control': 'no-cache' } })
      rooms.value = data
    } catch {}
  })

  sio.value.on('connect_error', err => console.warn('rooms sio error', err?.message))

  sio.value.on('rooms_upsert', (r:Room) => upsert(r))

  sio.value.on('rooms_remove', (p:{id:number}) => {
    rooms.value = rooms.value.filter(r => r.id !== p.id)
  })

  sio.value.on('rooms_occupancy', (p:{id:number; occupancy:number}) => {
    const i = rooms.value.findIndex(r => r.id === p.id)
    if (i>=0) rooms.value[i] = { ...rooms.value[i], occupancy:p.occupancy }
  })
}

function stopWS() {
  try { sio.value?.off?.() } catch {}
  try { sio.value?.close?.() } catch {}
  sio.value = null
}

async function createRoom(title:string, user_limit:number, is_private:boolean){
  const { data } = await api.post<Room>('/rooms', { title, user_limit, is_private })
  upsert(data)
  return data
}

const title = ref('')
const limit = ref(12)
const creating = ref(false)
const valid = computed(() => (title.value || '').length > 0 && limit.value >= 2 && limit.value <= 20)

async function onCreate() {
  if (!valid.value || creating.value) return
  creating.value = true
  try {
    const r = await createRoom(title.value, limit.value, false)
    await router.push(`/room/${r.id}`)
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  startWS()
  await load()
})
onBeforeUnmount(() => {
  stopWS()
})
</script>

<style lang="scss" scoped>
.card {
  .title {
    color: $fg;
    margin: 0 0 8px;
  }
  .subtitle {
    color: $fg;
    margin: 12px 0 6px;
    font-size: 16px;
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
    &__title {
      font-weight: 500;
    }
    &__meta {
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
    margin-top: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .input {
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid #334155;
    color: #e5e7eb;
    background: #0b0f14;
  }
  .btn {
    padding: 8px 12px;
    border-radius: 8px;
    border: 0;
    cursor: pointer;
  }
  .btn-primary {
    background: $color-primary;
    color: #06110b;
  }
}
</style>
