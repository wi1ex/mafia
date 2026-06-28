<template>
  <Transition name="panel">
    <div v-show="open" class="apps-panel" :data-open="open ? 1 : 0" @click.stop>
      <header>
        <span class="title">Заявки</span>
        <button class="close-btn" type="button" aria-label="Закрыть" @click="$emit('update:open', false)">
          <UiIcon class="close-icon" :icon="iconClose" />
        </button>
      </header>

      <ul v-if="apps.length">
        <li v-for="u in apps" :key="u.id">
          <div class="user">
            <img class="avatar" v-minio-img="{ key: u.avatar_name ? `avatars/${u.avatar_name}` : '', placeholder: iconDefaultAvatar, lazy: false }" alt="avatar" />
            <span class="username">{{ u.username || ('user' + u.id) }}</span>
          </div>
          <div class="action">
            <time class="req-time">{{ formatLocalDateTime(u.requested_at, TIME_ONLY) }}</time>
            <button v-if="u.status === 'pending'" class="btn-approve" :disabled="actionBusy[u.id]" @click="approve(u.id)">Одобрить</button>
            <button v-else class="btn-deny" :disabled="actionBusy[u.id]" @click="deny(u.id)">Запретить</button>
          </div>
        </li>
      </ul>
      <p v-else-if="showEmpty">Нет заявок</p>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { formatLocalDateTime } from '@/services/datetime'

import UiIcon from '@/components/UiIcon.vue'

import iconDefaultAvatar from '@/assets/svg/iconDefaultAvatarBlack.svg'
import iconClose from '@/assets/svg/iconClose.svg'

type AppItem = {id: number; username?: string; avatar_name?: string|null; status: 'pending'|'approved'; requested_at?: string|null}

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
const TIME_ONLY: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit', second: '2-digit' }
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
      status: u.status === 'approved' ? 'approved' : 'pending',
      requested_at: u.requested_at ?? null,
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
  const u = { id: uid, username: p.user?.username, avatar_name: p.user?.avatar_name ?? null, status: 'pending' as const, requested_at: new Date().toISOString() }
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
  const silentUnread = Boolean(p?.silent_unread || p?.source === 'owner_invite_auto_approved')
  seen.add(uid)
  saveSeen([...seen])
  if (silentUnread) {
    recomputeCounts()
  }
  if (apps.value.some(x => x.id === uid)) {
    apps.value = apps.value.map(x => x.id === uid ? { ...x, status: 'approved' } : x)
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
  bottom: 48px;
  padding: 16px 24px;
  width: 404px;
  max-height: 400px;
  border-radius: 24px;
  background-color: $neutral-100;
  box-shadow: 0 0 16px 0 rgba($neutral-black, 0.16);
  z-index: 25;
  &[data-open="0"] {
    pointer-events: none;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 4px 16px;
    .title {
      color: $neutral-black;
      font-family: Hauora-Bold;
      font-size: 18px;
      line-height: 20px;
      letter-spacing: -0.36px;
    }
    .close-btn {
      padding: 0;
      width: 24px;
      height: 24px;
      border: none;
      background: none;
      cursor: pointer;
      .close-icon {
        --ui-icon-width: 24px;
        --ui-icon-height: 24px;
        --ui-icon-color: #{$neutral-black};
      }
      &:not(:disabled):hover,
      &:not(:disabled):focus-visible,
      &:not(:disabled):active {
        .close-icon {
          --ui-icon-color: #{$green-500};
        }
      }
    }
  }
  ul {
    display: flex;
    flex-direction: column;
    margin: 0;
    padding: 0;
    gap: 8px;
    overflow-y: auto;
    scrollbar-width: none;
    list-style: none;
    li {
      display: flex;
      align-items: center;
      padding: 0 16px;
      gap: 8px;
      border-radius: 12px;
      background-color: $neutral-white;
      .user {
        display: flex;
        align-items: center;
        .avatar {
          width: 24px;
          height: 24px;
          border-radius: 50%;
        }
        .username {
          color: black;
          flex: 1;
          height: 18px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }
      .action {
        display: flex;
        .req-time {
          color: black;
          font-size: 14px;
        }
        button {
          display: flex;
          align-items: center;
          justify-content: center;
          min-width: 90px;
          height: 30px;
          border: none;
          border-radius: 5px;
          font-size: 14px;
          font-family: Manrope-Medium;
          line-height: 1;
          cursor: pointer;
          transition: background-color 0.25s ease-in-out;
          &:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
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

</style>
