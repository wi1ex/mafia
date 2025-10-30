<template>
  <div v-show="open" class="settings" aria-label="Настройки устройств" @click.stop>
    <div class="quality">
      <span>Качество видео</span>
      <div class="quality-toggle">
        <span :data-active="vq==='sd' ? 1 : 0">SD</span>
        <input type="range" min="0" max="1" step="1" :value="vq==='hd' ? 1 : 0" :disabled="vqDisabled" @input="onVQInput" aria-label="Качество видео" />
        <span :data-active="vq==='hd' ? 1 : 0">HD</span>
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
import type { VQ } from '@/services/rtc'

type Dev = {
  deviceId: string
  label: string
}

defineProps<{
  open: boolean
  mics: Dev[]
  cams: Dev[]
  micId: string
  camId: string
  vq?: VQ
  vqDisabled?: boolean
}>()
const emit = defineEmits<{
  'update:micId': [string]
  'update:camId': [string]
  'update:vq': [VQ]
  'device-change': ['audioinput' | 'videoinput']
}>()

function onVQInput(e: Event) {
  const n = Number((e.target as HTMLInputElement).value)
  emit('update:vq', n >= 1 ? 'hd' : 'sd')
}

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
  gap: 10px;
  min-width: 250px;
  border-radius: 5px;
  background-color: $dark;
  z-index: 20;
  .quality {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    span {
      color: $fg;
    }
    .quality-toggle {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      input[type="range"] {
        width: 72px;
        height: 10px;
        accent-color: $fg;
        cursor: pointer;
      }
      span[data-active="1"] {
        color: $fg;
      }
      span[data-active="0"] {
        color: $grey;
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
