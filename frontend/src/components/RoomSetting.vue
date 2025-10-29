<template>
  <div v-show="open" class="settings" aria-label="Настройки устройств" @click.stop>
    <div v-if="brief" class="room-brief">
      <div class="rb-title">Комната #{{ brief.id }}: {{ brief.title }}</div>
      <div class="rb-meta">
        <span class="rb-badge" :data-kind="brief.privacy === 'private' ? 'priv' : 'open'">
          {{ brief.privacy === 'private' ? 'Приватная' : 'Открытая' }}
        </span>
        <span>— {{ brief.occupancy }}/{{ brief.user_limit }}</span>
      </div>
      <div class="rb-owner">
        <img v-minio-img="{ key: brief.creator_avatar_name ? `avatars/${brief.creator_avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
        <span>{{ brief.creator_name }}</span>
      </div>
    </div>

    <label>
      <span>Микрофон</span>
      <select :value="micId" @change="onChange('audioinput', $event)" :disabled="mics.length===0">
        <option v-for="d in mics" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Микрофон не обнаружен' }}</option>
      </select>
    </label>
    <label>
      <span>Камера</span>
      <select :value="camId" @change="onChange('videoinput', $event)" :disabled="cams.length===0">
        <option v-for="d in cams" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Камера не обнаружена' }}</option>
      </select>
    </label>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { api } from '@/services/axios'
import defaultAvatar from '@/assets/svg/defaultAvatar.svg'

type Dev = {
  deviceId: string
  label: string
}
type RoomBrief = {
  id: number
  title: string
  user_limit: number
  privacy: 'open'|'private'
  creator: number
  creator_name: string
  creator_avatar_name?: string|null
  created_at: string
  occupancy: number
}

const props = defineProps<{
  open: boolean
  roomId: number
  mics: Dev[]
  cams: Dev[]
  micId: string
  camId: string
  roomBrief?: RoomBrief | null
}>()
const emit = defineEmits<{
  'update:micId': [string]
  'update:camId': [string]
  'device-change': ['audioinput' | 'videoinput']
}>()

const brief = ref<RoomBrief | null>(props.roomBrief ?? null)
let poll: number | undefined
let inFlight = false

async function fetchBrief(force = false) {
  if (inFlight || !props.roomId) return
  if (!force && brief.value) return
  inFlight = true
  try {
    const { data } = await api.get<RoomBrief>(`/rooms/${props.roomId}/brief`, { __skipAuth: true } as any)
    brief.value = data
  } catch {}
  finally { inFlight = false }
}

function onChange(kind: 'audioinput'|'videoinput', e: Event) {
  const val = (e.target as HTMLSelectElement).value
  if (kind === 'audioinput') emit('update:micId', val)
  else emit('update:camId', val)
  emit('device-change', kind)
}

watch(() => props.roomBrief, v => { if (v) brief.value = v }, { immediate: true })

watch(() => props.roomId, () => { if (props.open) void fetchBrief(true) })

watch(() => props.open, on => {
  if (on) {
    void fetchBrief(true)
    poll = window.setInterval(() => { void fetchBrief(true) }, 5000)
  } else {
    if (poll) {
      window.clearInterval(poll)
      poll = undefined
    }
  }
})

onBeforeUnmount(() => {
  if (poll) {
    window.clearInterval(poll)
    poll = undefined
  }
})
</script>

<style scoped lang="scss">
.settings {
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  bottom: 60px;
  padding: 10px;
  gap: 10px;
  min-width: 250px;
  border-radius: 5px;
  background-color: $dark;
  z-index: 20;
  .room-brief {
    display: flex;
    flex-direction: column;
    gap: 10px;
    .rb-title {
      color: $fg;
      font-weight: 600;
    }
    .rb-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      color: $grey;
    }
    .rb-badge {
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
    .rb-owner {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      img {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        object-fit: cover;
      }
    }
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 5px;
    span {
      color: $fg;
    }
    select {
      padding: 5px;
      border-radius: 5px;
      background-color: $bg;
      color: $fg;
      font-size: 14px;
      font-family: Manrope-Medium;
      line-height: 1;
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
  }
}
</style>
