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
            <span>Качество видео:</span>
            <label>
              <input type="checkbox" :checked="vq === 'hd'" :disabled="vqDisabled" @change="onToggleVQ" aria-label="Качество видео: SD/HD" />
              <div class="slider">
                <span>SD</span>
                <span>HD</span>
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
        </div>

        <div class="switch-device-div">
          <span>Выбор камеры:</span>
          <div class="ui-select" ref="camRoot" :class="{ open: camOpen }">
            <button type="button" @click="toggleCamDd" :aria-expanded="String(camOpen)" aria-label="Список камер">
              <span>{{ camLabel }}</span>
              <img :src="iconArrowDown" alt="arrow" />
<!--              <img :src="open ? iconArrowUp : iconArrowDown" alt="arrow" />-->
            </button>
            <Transition name="menu">
              <ul v-show="camOpen" role="listbox">
                <li v-for="it in cams" :key="it.deviceId" class="option" :aria-selected="it.deviceId === camId"
                    :class="{ selected: it.deviceId === camId }" @click="selectCam(it.deviceId)">
                  <span>{{ it.label || 'Камера' }}</span>
                  <img v-if="it.deviceId === camId" :src="iconReady" alt="ready" />
                </li>
                <li v-if="cams.length === 0" class="empty" aria-disabled="true">Нет устройств</li>
              </ul>
            </Transition>
          </div>
        </div>

        <div class="switch-device-div">
          <span>Выбор микрофона:</span>
          <div class="ui-select" ref="micRoot" :class="{ open: micOpen }">
            <button type="button" @click="toggleMicDd" :aria-expanded="String(micOpen)" aria-label="Список микрофонов">
              <span>{{ micLabel }}</span>
              <img :src="iconArrowDown" alt="arrow" />
<!--              <img :src="open ? iconArrowUp : iconArrowDown" alt="arrow" />-->
            </button>
            <Transition name="menu">
              <ul v-show="micOpen" role="listbox">
                <li v-for="it in mics" :key="it.deviceId" class="option" :aria-selected="it.deviceId === micId"
                    :class="{ selected: it.deviceId === micId }" @click="selectMic(it.deviceId)">
                  <span>{{ it.label || 'Микрофон' }}</span>
                  <img v-if="it.deviceId === micId" :src="iconReady" alt="ready" />
                </li>
                <li v-if="mics.length === 0" class="empty" aria-disabled="true">Нет устройств</li>
              </ul>
            </Transition>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import type { VQ } from '@/services/rtc'

import iconClose from '@/assets/svg/close.svg'
import iconReady from '@/assets/svg/ready.svg'
import iconArrowUp from '@/assets/svg/arrow_up.svg'
import iconArrowDown from '@/assets/svg/arrow_down.svg'

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
  mirrorOn: boolean
}>()

const emit = defineEmits<{
  'update:micId': [string]
  'update:camId': [string]
  'update:vq': [VQ]
  'update:mirrorOn': [boolean]
  'device-change': ['audioinput' | 'videoinput']
  'close': []
}>()

const camRoot = ref<HTMLElement|null>(null)
const micRoot = ref<HTMLElement|null>(null)
const camOpen = ref(false)
const micOpen = ref(false)
let suppressNextDocClick = false

const camLabel = computed(() => props.cams.find(i => i.deviceId === props.camId)?.label || 'Камера')
const micLabel = computed(() => props.mics.find(i => i.deviceId === props.micId)?.label || 'Микрофон')

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
function onToggleMirror(e: Event) {
  emit('update:mirrorOn', (e.target as HTMLInputElement).checked)
}
function pickDevice(kind: 'audioinput'|'videoinput', id: string) {
  if (kind === 'audioinput') {
    if (id === props.micId) return
    emit('update:micId', id)
  } else {
    if (id === props.camId) return
    emit('update:camId', id)
  }
  emit('device-change', kind)
}

function toggleCamDd() {
  camOpen.value = !camOpen.value
  if (camOpen.value) micOpen.value = false
}
function toggleMicDd() {
  micOpen.value = !micOpen.value
  if (micOpen.value) camOpen.value = false
}
function closeDropdowns() {
  camOpen.value = false
  micOpen.value = false
}
function selectCam(id: string) {
  if (id !== props.camId) camIdProxy.value = id
  closeDropdowns()
}
function selectMic(id: string) {
  if (id !== props.micId) micIdProxy.value = id
  closeDropdowns()
}

function onDocPointerDown(ev: PointerEvent) {
  const t = ev.target as Node
  const clickedOutsideCam = camOpen.value && camRoot.value && !camRoot.value.contains(t)
  const clickedOutsideMic = micOpen.value && micRoot.value && !micRoot.value.contains(t)
  if (clickedOutsideCam || clickedOutsideMic) {
    closeDropdowns()
    suppressNextDocClick = true
    ev.stopPropagation?.()
  }
}
function onDocClickCapture(e: MouseEvent) {
  if (suppressNextDocClick) {
    e.stopPropagation()
    suppressNextDocClick = false
  }
}

watch(() => props.open, (v) => {
  if (!v) {
    camOpen.value = false
    micOpen.value = false
  }
})

onMounted(() => {
  document.addEventListener('pointerdown', onDocPointerDown, { capture: true })
  document.addEventListener('click', onDocClickCapture, { capture: true })
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocPointerDown, { capture: true } as any)
  document.removeEventListener('click', onDocClickCapture, { capture: true } as any)
})
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
  box-shadow: 3px 3px 5px rgba($black, 0.25);
  z-index: 20;
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
  .change-devices {
    display: flex;
    flex-direction: column;
    padding: 10px;
    gap: 10px;
    border-radius: 5px;
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
          width: 120px;
          height: 25px;
          box-shadow: 3px 3px 5px rgba($black, 0.25);
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
            border: 1px solid $lead;
            border-radius: 5px;
            background-color: $graphite;
            span {
              position: relative;
              font-size: 14px;
              color: $fg;
              transition: color 0.25s ease-in-out;
            }
          }
          .slider:before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 58px;
            height: 23px;
            background-color: $fg;
            border-radius: 5px;
            transition: transform 0.25s ease-in-out;
          }
          input:checked + .slider:before {
            transform: translateX(60px);
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
      .ui-select {
        position: relative;
        width: 100%;
        box-shadow: 3px 3px 5px rgba($black, 0.25);
        button {
          display: flex;
          align-items: center;
          justify-content: space-between;
          width: 100%;
          height: 30px;
          border: 1px solid $lead;
          border-radius: 5px;
          background-color: $dark;
          padding: 0 10px;
          cursor: pointer;
          span {
            height: 16px;
            color: $fg;
            font-size: 14px;
            font-family: Manrope-Medium;
            line-height: 1;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          img {
            width: 15px;
            height: 15px;
          }
        }
      }
      ul {
        position: absolute;
        z-index: 30;
        bottom: 0;
        margin: 0;
        padding: 0;
        width: calc(100% - 2px);
        border: 1px solid $lead;
        border-radius: 5px;
        background-color: $graphite;
        transform-origin: bottom;
        .option {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          padding: 10px;
          cursor: pointer;
          transition: background-color 0.25s ease-in-out;
          span {
            height: 16px;
            font-size: 14px;
            color: $fg;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          img {
            width: 15px;
            height: 15px;
          }
        }
        .option.selected {
          background-color: $lead;
        }
        .empty {
          padding: 10px;
          color: $grey;
          font-size: 14px;
        }
      }
    }
  }
}

.menu-enter-active,
.menu-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
  will-change: opacity, transform;
}
.menu-enter-from,
.menu-leave-to {
  opacity: 0;
  transform: translateY(30px);
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
