<template>
  <div v-if="open" class="apps-overlay" @click.self="$emit('update:open', false)">
    <div class="apps-panel">
      <header><span>Заявки</span><button @click="$emit('update:open', false)">✕</button></header>
      <ul v-if="apps.length" class="apps-list">
        <li v-for="u in apps" :key="u.id">
          <img v-minio-img="{ key: u.avatar_name ? `avatars/${u.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
          <span>{{ u.username || ('user' + u.id) }}</span>
          <button @click="approve(u.id)">Разрешить вход</button>
        </li>
      </ul>
      <p v-else>Нет заявок</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import { api } from '@/services/axios'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'

const props = defineProps<{
  open: boolean
  roomId: number
}>()
const emit = defineEmits<{
  'update:open': [boolean]
  counts: [{ total: number; unread: number }]
}>()

const apps = ref<{id: number; username?: string; avatar_name?: string|null}[]>([])
const seenKey = computed(() => `room:${props.roomId}:apps_seen`)
const poll = ref<number | undefined>(undefined)
let inFlight = false

function loadSeen(): Set<number> {
  try { return new Set<number>(JSON.parse(localStorage.getItem(seenKey.value) || '[]')) } catch { return new Set() }
}

function saveSeen(ids: number[]) {
  try { localStorage.setItem(seenKey.value, JSON.stringify([...new Set(ids)].sort((a, b) => a - b))) } catch {}
}

let seen = loadSeen()
function recomputeCounts() {
  const ids = apps.value.map(x=>x.id)
  const total = ids.length
  const unread = ids.filter(id => !seen.has(id)).length
  emit('counts', { total, unread })
}

async function load() {
  if (inFlight) return
  inFlight = true
  try {
    const { data } = await api.get(`/rooms/${props.roomId}/requests`)
    apps.value = data
    recomputeCounts()
  }
  catch { recomputeCounts() }
  finally { inFlight = false }
}

async function approve(uid: number) {
  try {
    await api.post(`/rooms/${props.roomId}/requests/${uid}/approve`)
    apps.value = apps.value.filter(x => x.id !== uid)
    recomputeCounts()
  }
  catch { alert('Ошибка') }
}

function onInvite(e: any) {
  const p = e?.detail
  if (Number(p?.room_id) !== props.roomId) return
  const uid = Number(p?.user?.id)
  if (props.open && Number.isFinite(uid)) {
    seen.add(uid)
    saveSeen([...seen])
  }
  void load()
}

watch(() => props.open, async on => {
  if (on) {
    await load()
    poll.value = window.setInterval(load, 5000)
    seen = new Set(apps.value.map(x => x.id))
    saveSeen([...seen])
    recomputeCounts()
  } else {
    apps.value = []
    if (poll.value) {
      window.clearInterval(poll.value)
      poll.value = undefined
    }
  }
})

watch(() => props.roomId, async () => {
  seen = loadSeen()
  await load()
})

onMounted(() => window.addEventListener('auth-room_invite', onInvite))

onBeforeUnmount(() => {
  window.removeEventListener('auth-room_invite', onInvite)
  if (poll.value) {
    window.clearInterval(poll.value)
    poll.value = undefined
  }
})
</script>

<style lang="scss" scoped>
.apps-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3000;
  .apps-panel {
    min-width: 300px;
    max-width: 420px;
    max-height: 60vh;
    overflow: auto;
    background: #1e1e1e;
    border-radius: 8px;
    padding: 10px;
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }
    .apps-list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
      li {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      img {
        width: 24px;
        height: 24px;
        border-radius: 50%;
      }
      button {
        margin-left: auto;
      }
    }
  }
}
</style>
