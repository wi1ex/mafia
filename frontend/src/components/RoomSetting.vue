<template>
  <Transition name="panel">
    <div v-show="open" class="settings" aria-label="Настройки устройств" @click.stop>
      <header>
        <span>Настройки</span>
        <button @click="$emit('close')" aria-label="Закрыть">
          <img :src="iconClose" alt="close" />
        </button>
      </header>

      <div class="change-devices">
        <div class="switch-div">
          <div class="switch">
            <span>Шумо- и эхоподавление:</span>
            <label>
              <input type="checkbox" :checked="nsOn" @change="onToggleNs" aria-label="Шумоподавление" />
              <div class="slider">
                <span>Откл</span>
                <span>Вкл</span>
              </div>
            </label>
          </div>

          <div class="switch">
            <span>Зеркальность камеры:</span>
            <label>
              <input type="checkbox" :checked="mirrorOn" @change="onToggleMirror" aria-label="Зеркальность" />
              <div class="slider">
                <span>Откл</span>
                <span>Вкл</span>
              </div>
            </label>
          </div>

          <div class="switch">
            <span>Качество видео:</span>
            <label>
              <input type="checkbox" :checked="vq === 'hd'" :disabled="vqDisabled" @change="onToggleVQ" aria-label="Качество видео: SD/HD" />
              <div class="slider">
                <span>SD</span>
                <span>HD</span>
              </div>
            </label>
          </div>
        </div>

        <div class="switch-device-div">
          <span>Выбор камеры:</span>
          <UiSelect
            v-model="camIdProxy"
            :items="cams"
            placeholder="Камера"
            fallback="Камера"
            aria-label="Список камер"
          />
        </div>

        <div class="switch-device-div">
          <span>Выбор микрофона:</span>
          <UiSelect
            v-model="micIdProxy"
            :items="mics"
            placeholder="Микрофон"
            fallback="Микрофон"
            aria-label="Список микрофонов"
          />
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import type { VQ } from '@/services/rtc'
import UiSelect from '@/components/UiSelect.vue'

import iconClose from '@/assets/svg/close.svg'

type Dev = {
  deviceId: string
  label: string
}

const props = defineProps<{
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

const micIdProxy = computed({
  get: () => props.micId,
  set: (v: string) => { pickDevice('audioinput', v) }
})

const camIdProxy = computed({
  get: () => props.camId,
  set: (v: string) => { pickDevice('videoinput', v) }
})

function onToggleVQ(e: Event) {
  const on = (e.target as HTMLInputElement).checked
  emit('update:vq', on ? 'hd' : 'sd')
}

function onToggleNs(e: Event) {
  emit('update:nsOn', (e.target as HTMLInputElement).checked)
}

function onToggleMirror(e: Event) {
  emit('update:mirrorOn', (e.target as HTMLInputElement).checked)
}

function pickDevice(kind: 'audioinput'|'videoinput', id: string) {
  if (kind === 'audioinput') emit('update:micId', id)
  else emit('update:camId', id)
  emit('device-change', kind)
}
</script>

<style scoped lang="scss">
.settings {
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  bottom: 50px;
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
  .change-devices {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: 10px;
    gap: 20px;
    background-color: $dark;
    .switch-div {
      display: flex;
      flex-direction: column;
      gap: 10px;
      width: 100%;
      .switch {
        display: flex;
        align-items: center;
        justify-content: space-between;
        label {
          position: relative;
          width: 140px;
          height: 30px;
          input {
            position: absolute;
            opacity: 0;
            width: 0;
            height: 0;
          }
          .slider {
            display: flex;
            align-items: center;
            justify-content: space-around;
            position: absolute;
            inset: 0;
            cursor: pointer;
            background-color: $graphite;
            border-radius: 5px;
            span {
              position: relative;
              font-size: 14px;
              color: $fg;
              transition: color 0.5s ease-in-out;
            }
          }
          .slider:before {
            content: "";
            position: absolute;
            top: 3px;
            left: 3px;
            width: 64px;
            height: 24px;
            background-color: $fg;
            border-radius: 5px;
            transition: transform 0.25s ease-in-out;
          }
          input:checked + .slider:before {
            transform: translateX(70px);
          }
          input:not(:checked) + .slider span:first-child,
          input:checked + .slider span:last-child {
            color: $bg;
          }
        }
      }
    }
    .switch-device-div {
      display: flex;
      flex-direction: column;
      width: 100%;
      gap: 5px;
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
