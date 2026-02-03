<template>
  <Transition name="panel" @after-leave="onAfterLeave">
    <div v-show="open" class="apps-panel" @click.stop>
      <header>
        <span>Заявки</span>
        <button @click="$emit('update:open', false)" aria-label="Закрыть">
          <img :src="iconClose" alt="close" />
        </button>
      </header>
      <ul v-if="apps.length">
        <li v-for="u in apps" :key="u.id">
          <img v-minio-img="{ key: u.avatar_name ? `avatars/${u.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
          <span>{{ u.username || ('user' + u.id) }}</span>
          <button v-if="u.status === 'pending'" class="btn-approve" :disabled="actionBusy[u.id]" @click="approve(u.id)">Одобрить</button>
          <button v-else class="btn-deny" :disabled="actionBusy[u.id]" @click="deny(u.id)">Запретить</button>
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
import { alertDialog } from '@/services/confirm'

type AppItem = {id: number; username?: string; avatar_name?: string|null; status: 'pending'|'approved'}

const props = defineProps<{
  open: boolean
  roomId: number
}>()
const emit = defineEmits<{
  'update:open': [boolean]
  counts: [{ total: number; unread: number }]
}>()

const apps = ref<AppItem[]>([])
const seenKey = computed(() => `room:${props.roomId}:apps_seen`)
const isLoading = ref(false)
const showEmpty = computed(() => !isLoading.value && apps.value.length === 0)
const actionBusy = ref<Record<number, boolean>>({})
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
    const raw = Array.isArray(data) ? data : []
    apps.value = raw.map((u: any) => ({
      id: Number(u.id),
      username: u.username,
      avatar_name: u.avatar_name ?? null,
      status: u.status === 'approved' ? 'approved' : 'pending'
    }))
  }
  catch {}
  finally {
    recomputeCounts()
    inFlight = false
    isLoading.value = false
  }
}

async function approve(uid: number) {
  if (actionBusy.value[uid]) return
  actionBusy.value = { ...actionBusy.value, [uid]: true }
  await new Promise(resolve => setTimeout(resolve, 500))
  try {
    await api.post(`/rooms/${props.roomId}/requests/${uid}/approve`)
    apps.value = apps.value.map(x => x.id === uid ? { ...x, status: 'approved' } : x)
    seen.add(uid)
    saveSeen([...seen])
    recomputeCounts()

    window.dispatchEvent(new CustomEvent('auth-room_app_approved', {
      detail: { room_id: props.roomId, user_id: uid }
    }))
  } catch { void alertDialog('Возникла непредвиденная ошибка') }
  finally {
    actionBusy.value = { ...actionBusy.value, [uid]: false }
  }
}

async function deny(uid: number) {
  if (actionBusy.value[uid]) return
  actionBusy.value = { ...actionBusy.value, [uid]: true }
  await new Promise(resolve => setTimeout(resolve, 500))
  try {
    await api.post(`/rooms/${props.roomId}/requests/${uid}/deny`)
    apps.value = apps.value.filter(x => x.id !== uid)
    seen.delete(uid)
    saveSeen([...seen])
    recomputeCounts()

    window.dispatchEvent(new CustomEvent('auth-room_app_revoked', {
      detail: { room_id: props.roomId, user_id: uid }
    }))
  } catch { void alertDialog('Возникла непредвиденная ошибка') }
  finally {
    actionBusy.value = { ...actionBusy.value, [uid]: false }
  }
}

function onInvite(e: any) {
  const p = e?.detail
  if (Number(p?.room_id) !== props.roomId) return
  const uid = Number(p?.user?.id)
  if (!Number.isFinite(uid)) return
  const u = { id: uid, username: p.user?.username, avatar_name: p.user?.avatar_name ?? null, status: 'pending' as const }
  if (!apps.value.some(x => x.id === uid)) apps.value = [u, ...apps.value]
  else apps.value = apps.value.map(x => x.id === uid ? { ...x, ...u, status: 'pending' } : x)
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
    apps.value = apps.value.map(x => x.id === uid ? { ...x, status: 'approved' } : x)
    seen.add(uid)
    saveSeen([...seen])
    recomputeCounts()
  } else {
    void load()
  }
}

function onRevoked(e: any) {
  const p = e?.detail
  if (Number(p?.room_id) !== props.roomId) return
  const uid = Number(p?.user_id)
  if (!Number.isFinite(uid)) return
  if (apps.value.some(x => x.id === uid)) {
    apps.value = apps.value.filter(x => x.id !== uid)
    seen.delete(uid)
    saveSeen([...seen])
    recomputeCounts()
  } else {
    void load()
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
  }
})

watch(() => props.roomId, async () => {
  seen = loadSeen()
  await load()
}, { immediate: true })

onMounted(() => {
  window.addEventListener('auth-room_invite', onInvite)
  window.addEventListener('auth-room_app_approved', onApproved)
  window.addEventListener('auth-room_app_revoked', onRevoked)
  window.addEventListener('room-app-seen', onSeen)
})

onBeforeUnmount(() => {
  window.removeEventListener('auth-room_invite', onInvite)
  window.removeEventListener('auth-room_app_approved', onApproved)
  window.removeEventListener('auth-room_app_revoked', onRevoked)
  window.removeEventListener('room-app-seen', onSeen)
})
</script>

<style scoped lang="scss">
.apps-panel {
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  bottom: 50px;
  width: 400px;
  min-height: 200px;
  max-height: 600px;
  border-radius: 5px;
  background-color: $dark;
  box-shadow: 3px 3px 5px rgba($black, 0.25);
  z-index: 25;
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 10px;
    border-radius: 5px;
    background-color: $graphite;
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
  ul {
    display: flex;
    flex-direction: column;
    margin: 10px;
    padding: 0;
    gap: 10px;
    border-radius: 5px;
    box-shadow: 3px 3px 5px rgba($black, 0.25);
    overflow-y: auto;
    scrollbar-width: none;
    list-style: none;
    li {
      display: flex;
      align-items: center;
      padding: 5px;
      gap: 5px;
      border-radius: 5px;
      background-color: $graphite;
      img {
        width: 30px;
        height: 30px;
        border-radius: 50%;
      }
      span {
        flex: 1;
        height: 18px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 10px;
        height: 30px;
        border: none;
        border-radius: 5px;
        font-size: 14px;
        font-family: Manrope-Medium;
        line-height: 1;
        cursor: pointer;
        transition: background-color 0.25s ease-in-out;
        &.btn-approve {
          background-color: rgba($green, 0.75);
          color: $bg;
          &:hover {
            background-color: $green;
          }
        }
        &.btn-deny {
          background-color: rgba($red, 0.75);
          color: $fg;
          &:hover {
            background-color: $red;
          }
        }
      }
    }
  }
  p {
    color: $grey;
    margin: auto;
  }
}

.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}
.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(30px);
}

@media (max-width: 1280px) {
  .apps-panel {
    bottom: 30px;
    max-height: calc(100dvh - 40px);
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
    ul {
      margin: 5px;
      gap: 5px;
      li {
        img {
          width: 20px;
          height: 20px;
        }
        span {
          height: 14px;
          font-size: 12px;
        }
        button {
          padding: 5px;
          height: 20px;
          font-size: 10px;
        }
      }
    }
  }
}
</style>
