<template>
  <div v-show="open" class="settings" aria-label="Настройки устройств" @click.stop>
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
  gap: 20px;
  min-width: 250px;
  border-radius: 5px;
  background-color: $dark;
  z-index: 20;
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
