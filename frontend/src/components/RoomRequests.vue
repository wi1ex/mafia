<template>
  <Transition name="panel" @after-leave="onAfterLeave">
    <div v-show="open" class="apps-panel" @click.stop>
      <header>
        <span>Заявки</span>
        <button @click="$emit('update:open', false)" aria-label="Закрыть">
          <img :src="iconClose" alt="close" />
        </button>
      </header>
      <ul v-if="apps.length" class="apps-list">
        <li v-for="u in apps" :key="u.id">
          <img v-minio-img="{ key: u.avatar_name ? `avatars/${u.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
          <span>{{ u.username || ('user' + u.id) }}</span>
          <button @click="approve(u.id)">Разрешить вход</button>
        </li>
      </ul>
      <p v-else-if="showEmpty">Нет заявок</p>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import { api } from '@/services/axios'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconClose from '@/assets/svg/close.svg'

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
const isLoading = ref(false)
const showEmpty = computed(() => !isLoading.value && apps.value.length === 0)
let inFlight = false

function loadSeen(): Set<number> {
  try { return new Set<number>(JSON.parse(localStorage.getItem(seenKey.value) || '[]')) } catch { return new Set() }
}

function saveSeen(ids: number[]) {
  try { localStorage.setItem(seenKey.value, JSON.stringify([...new Set(ids)].sort((a, b) => a - b))) } catch {}
}

let seen = loadSeen()
function recomputeCounts() {
  const ids = apps.value.map(x => x.id)
  const total = ids.length
  const unread = ids.filter(id => !seen.has(id)).length
  emit('counts', { total, unread })
}

async function load() {
  if (inFlight) return
  inFlight = true
  isLoading.value = true
  try {
    const { data } = await api.get(`/rooms/${props.roomId}/requests`)
    apps.value = data
  }
  catch {}
  finally {
    recomputeCounts()
    inFlight = false
    isLoading.value = false
  }
}

async function approve(uid: number) {
  try {
    await api.post(`/rooms/${props.roomId}/requests/${uid}/approve`)
    apps.value = apps.value.filter(x => x.id !== uid)
    seen.delete(uid)
    saveSeen([...seen])
    recomputeCounts()
  }
  catch { alert('Ошибка') }
}

function onInvite(e: any) {
  const p = e?.detail
  if (Number(p?.room_id) !== props.roomId) return
  const uid = Number(p?.user?.id)
  if (!Number.isFinite(uid)) return
  const u = { id: uid, username: p.user?.username, avatar_name: p.user?.avatar_name ?? null }
  if (!apps.value.some(x => x.id === uid)) apps.value = [u, ...apps.value]
  else apps.value = apps.value.map(x => x.id === uid ? { ...x, ...u } : x)
  if (props.open) {
    seen.add(uid)
    saveSeen([...seen])
  }
  recomputeCounts()
}

function onSeen(e: any) {
  const p = e?.detail
  if (Number(p?.room_id) !== props.roomId) return
  const uid = Number(p?.user_id)
  if (!Number.isFinite(uid)) return
  seen.add(uid)
  saveSeen([...seen])
  recomputeCounts()
}

function onApproved(e: any) {
  const p = e?.detail
  if (Number(p?.room_id) !== props.roomId) return
  const uid = Number(p?.user_id)
  if (!Number.isFinite(uid)) return
  if (apps.value.some(x => x.id === uid)) {
    apps.value = apps.value.filter(x => x.id !== uid)
    seen.delete(uid)
    saveSeen([...seen])
    recomputeCounts()
  }
}

function onAfterLeave() {
  apps.value = []
  isLoading.value = false
}

watch(() => props.open, async on => {
  if (on) {
    await load()
    seen = new Set(apps.value.map(x => x.id))
    saveSeen([...seen])
    recomputeCounts()
  } else {}
})

watch(() => props.roomId, async () => {
  seen = loadSeen()
  await load()
})

onMounted(() => {
  window.addEventListener('auth-room_invite', onInvite)
  window.addEventListener('auth-room_app_approved', onApproved)
  window.addEventListener('room-app-seen', onSeen)
})

onBeforeUnmount(() => {
  window.removeEventListener('auth-room_invite', onInvite)
  window.removeEventListener('auth-room_app_approved', onApproved)
  window.removeEventListener('room-app-seen', onSeen)
})
</script>

<style scoped lang="scss">
.apps-panel {
  position: absolute;
  right: 0;
  bottom: 60px;
  z-index: 20;
  min-width: 300px;
  min-height: 300px;
  overflow: auto;
  background-color: #1e1e1e;
  border-radius: 5px;
  padding: 10px;
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    span {
      color: $fg;
      font-weight: bold;
    }
    button {
      background: none;
      border: none;
      color: $fg;
      cursor: pointer;
      font-size: 18px;
      padding: 0;
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
  }
  .apps-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
    li {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px;
      border-radius: 5px;
      background-color: rgba(255, 255, 255, 0.05);
    }
    img {
      width: 24px;
      height: 24px;
      border-radius: 50%;
    }
    span {
      color: $fg;
      flex: 1;
    }
    button {
      margin-left: auto;
      padding: 5px 10px;
      background-color: $green;
      color: $bg;
      border: none;
      border-radius: 5px;
      cursor: pointer;
      font-size: 12px;
    }
  }
  p {
    color: $grey;
    text-align: center;
    margin: 0;
    padding: 15px 0;
  }
}

.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}
.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>
