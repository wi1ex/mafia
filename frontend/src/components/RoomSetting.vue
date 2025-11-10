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
          <div class="switch-text">Шумо- и эхоподавление:</div>
          <label class="switch">
            <input type="checkbox" :checked="nsOn" @change="onToggleNs" aria-label="Шумоподавление" />
            <div class="slider">
              <div class="slider-text" aria-hidden="true">Откл</div>
              <div class="slider-text" aria-hidden="true">Вкл</div>
            </div>
          </label>
        </div>

        <div class="switch-div">
          <div class="switch-text">Отражение камеры:</div>
          <label class="switch">
            <input type="checkbox" :checked="mirrorOn" @change="onToggleMirror" aria-label="Зеркальность" />
            <div class="slider">
              <div class="slider-text" aria-hidden="true">Откл</div>
              <div class="slider-text" aria-hidden="true">Вкл</div>
            </div>
          </label>
        </div>

        <div class="switch-div">
          <div class="switch-text">Качество видео:</div>
          <label class="switch">
            <input type="checkbox" :checked="vq === 'hd'" :disabled="vqDisabled" @change="onToggleVQ" aria-label="Качество видео: SD/HD" />
            <div class="slider">
              <div class="slider-text" aria-hidden="true">SD</div>
              <div class="slider-text" aria-hidden="true">HD</div>
            </div>
          </label>
        </div>

        <div class="switch-title-device">
          <div class="switch-title">Выбор камеры:</div>
          <div class="switch-device" role="listbox" aria-label="Список камер">
            <div class="switch-device-item" v-for="d in cams" :key="d.deviceId" role="option" :aria-selected="d.deviceId === camId" @click="pickDevice('videoinput', d.deviceId)" >
              <div class="switch-device-item-text">{{ d.label || 'Камера' }}</div>
              <img :src="iconCheck" alt="" v-if="d.deviceId === camId" />
            </div>
          </div>
        </div>

        <div class="switch-title-device">
          <div class="switch-title">Выбор микрофона:</div>
          <div class="switch-device" role="listbox" aria-label="Список микрофонов">
            <div class="switch-device-item" v-for="d in mics" :key="d.deviceId" role="option" :aria-selected="d.deviceId === micId" @click="pickDevice('audioinput', d.deviceId)" >
              <div class="switch-device-item-text">{{ d.label || 'Микрофон' }}</div>
              <img :src="iconCheck" alt="" v-if="d.deviceId === micId" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import type { VQ } from '@/services/rtc'

import iconClose from '@/assets/svg/close.svg'
import iconCheck from '@/assets/svg/ready.svg'

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
  .change-devices {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: 17px;
    gap: 17px;
    background-color: $dark;
    .switch-div {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      .switch-text {
        font-size: 16px;
        color: $fg;
        line-height: 100%;
      }
      .switch {
        position: relative;
        display: inline-block;
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
          .slider-text {
            font-size: 14px;
            color: $grey;
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
          border-radius: 4px;
          transition: transform 0.25s ease-in-out;
        }
        input:checked + .slider:before {
          transform: translateX(70px);
        }
        input:disabled + .slider {
          opacity: 0.5;
          cursor: not-allowed;
        }
      }
    }
    .switch-title-device {
      display: flex;
      flex-direction: column;
      width: 100%;
      gap: 10px;
      .switch-title {
        font-size: 16px;
        color: $fg;
      }
      .switch-device {
        width: 100%;
        max-height: 140px;
        border: 1px solid $graphite;
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: $grey transparent;
        .switch-device-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 7px 15px;
          height: 34px;
          cursor: pointer;
          background: none;
          &:hover {
            background-color: $graphite;
          }
          .switch-device-item-text {
            font-size: 14px;
            color: $fg;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: calc(100% - 30px);
          }
          img {
            width: 20px;
            height: 20px;
            object-fit: cover;
            filter: none;
          }
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
