<template>
  <div v-show="open" class="settings" aria-label="Настройки устройств" @click.stop>
    <div v-if="room" class="room-brief">
      <div class="rb-title">Комната #{{ room.id }}: {{ room.title }}</div>
      <div class="rb-meta">
        <span class="rb-badge" :data-kind="room.privacy === 'private' ? 'priv' : 'open'">
          {{ room.privacy === 'private' ? 'Приватная' : 'Открытая' }}
        </span>
        <span>— {{ room.occupancy }}/{{ room.user_limit }}</span>
      </div>
      <div class="rb-owner">
        <img v-minio-img="{ key: room.creator_avatar_name ? `avatars/${room.creator_avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
        <span>{{ room.creator_name }}</span>
      </div>
    </div>

    <label>
      <span>Микрофон</span>
      <select :value="micId" @change="onChange('audioinput',$event)" :disabled="mics.length===0">
        <option v-for="d in mics" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Микрофон не обнаружен' }}</option>
      </select>
    </label>
    <label>
      <span>Камера</span>
      <select :value="camId" @change="onChange('videoinput',$event)" :disabled="cams.length===0">
        <option v-for="d in cams" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Камера не обнаружена' }}</option>
      </select>
    </label>
  </div>
</template>

<script setup lang="ts">
import { defineProps, defineEmits } from 'vue'

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

defineProps<{
  open: boolean
  room?: RoomBrief | null
  mics: Dev[]
  cams: Dev[]
  micId: string
  camId: string
}>()

const emit = defineEmits<{
  'update:micId': [string]
  'update:camId': [string]
  'device-change': ['audioinput' | 'videoinput']
}>()

function onChange(kind: 'audioinput'|'videoinput', e: Event) {
  const val = (e.target as HTMLSelectElement).value
  if (kind === 'audioinput') emit('update:micId', val)
  else emit('update:camId', val)
  emit('device-change', kind)
}
</script>

<style scoped lang="scss">
.settings {
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  bottom: 60px;
  padding: 10px;
  gap: 16px;
  min-width: 250px;
  border-radius: 5px;
  background-color: $dark;
  z-index: 20;
  .room-brief {
    display: grid;
    gap: 6px;
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
