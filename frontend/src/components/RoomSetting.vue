<template>
  <Transition name="panel">
    <div v-show="open" class="settings" aria-label="Настройки устройств" @click.stop>
      <header>
        <span>Настройки</span>
        <button @click="$emit('close')" aria-label="Закрыть">
          <img :src="iconClose" alt="close" />
        </button>
      </header>

      <div class="rows">
        <div class="row">
          <span>Шумо- и эхоподавление</span>
          <div class="toggle">
            <span :data-active="!nsOn ? 1 : 0">Откл</span>
            <input type="range" min="0" max="1" step="1" :value="nsOn ? 1 : 0" @input="onNsInput" aria-label="Шум/эхо" />
            <span :data-active="nsOn ? 1 : 0">Вкл</span>
          </div>
        </div>

        <div class="row">
          <span>Зеркальность камеры</span>
          <div class="toggle">
            <span :data-active="!mirrorOn ? 1 : 0">Откл</span>
            <input type="range" min="0" max="1" step="1" :value="mirrorOn ? 1 : 0" @input="onMirrorInput" aria-label="Зеркальность" />
            <span :data-active="mirrorOn ? 1 : 0">Вкл</span>
          </div>
        </div>

        <div class="row">
          <span>Качество видео</span>
          <div class="toggle">
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
    </div>
  </Transition>
</template>

<script setup lang="ts">
import type { VQ } from '@/services/rtc'

import iconClose from '@/assets/svg/close.svg'

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
  nsOn: boolean
  mirrorOn: boolean
}>()
const emit = defineEmits<{
  'update:micId': [string]
  'update:camId': [string]
  'update:vq': [VQ]
  'update:nsOn': [boolean]
  'update:mirrorOn': [boolean]
  'device-change': ['audioinput' | 'videoinput']
  'close': []
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

function onNsInput(e: Event) {
  const n = Number((e.target as HTMLInputElement).value)
  emit('update:nsOn', n >= 1)
}

function onMirrorInput(e: Event) {
  const n = Number((e.target as HTMLInputElement).value)
  emit('update:mirrorOn', n >= 1)
}
</script>

<style scoped lang="scss">
.settings {
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  bottom: 50px;
  gap: 10px;
  width: 400px;
  border-radius: 5px;
  background-color: $dark;
  z-index: 20;
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px;
    border-radius: 5px;
    background-color: $graphite;
    span {
      font-size: 18px;
      font-weight: bold;
    }
    button {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 30px;
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
  .row {
    display: flex;
    flex-direction: column;
    .row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px;
      .toggle {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        input[type="range"] {
          width: 40px;
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
      padding: 0 10px 10px;
      gap: 5px;
      select {
        padding: 5px;
        border-radius: 5px;
        background-color: $bg;
        color: $fg;
        font-size: 12px;
        font-family: Manrope-Medium;
        line-height: 1;
        &:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      }
    }
  }
}

.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out; }
.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>
