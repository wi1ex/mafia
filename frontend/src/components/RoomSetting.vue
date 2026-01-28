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
        <template v-if="!inGame">
          <div class="switch-div">
            <div class="switch">
              <span class="switch-label">Зеркальность камеры:</span>
              <label>
                <input type="checkbox" :checked="mirrorOn" :disabled="mirrorToggleLocked" @change="onToggleMirror" aria-label="Зеркальность" />
                <div class="slider">
                  <span>Откл</span>
                  <span>Вкл</span>
                </div>
              </label>
            </div>
          </div>
        </template>
        <template v-else>
          <div v-if="!isSpectator && canToggleKnownRoles" class="switch-div">
            <div class="switch switch-wide">
              <span class="switch-label">
                Видимость ролей:
                <span v-if="!isMobile && hotkeysVisible !== false" class="hot-btn">R</span>
              </span>
              <label>
                <input type="checkbox" :checked="knownRolesVisible" @change="onToggleKnownRoles" aria-label="Показ ролей" />
                <div class="slider">
                  <span>Скрыть</span>
                  <span>Показать</span>
                </div>
              </label>
            </div>
          </div>

          <div class="volume-block">
            <span class="volume-text">Громкость музыки:</span>
            <div class="volume">
              <img :src="volumeIcon" alt="vol" />
              <input type="range" min="0" max="100" step="5" :value="volume" aria-label="Громкость фоновой музыки" @input="onVolumeInput" />
              <span>{{ volume }}%</span>
            </div>
          </div>
        </template>

        <div v-if="!isSpectator" class="switch-device-div">
          <span>Выбор камеры:</span>
          <div class="ui-select" ref="camRoot" :class="{ open: camOpen }">
            <button type="button" @click="toggleCamDd" :aria-expanded="String(camOpen)" aria-label="Список камер">
              <span>{{ camLabel }}</span>
              <img :src="iconArrowDown" alt="arrow" />
            </button>
            <Transition name="menu">
              <ul v-show="camOpen" role="listbox">
                <li v-for="it in cams" :key="it.deviceId" class="option" :aria-selected="it.deviceId === camId"
                    :class="{ selected: it.deviceId === camId }" @click="selectCam(it.deviceId)">
                  <span>{{ it.label || 'Камера' }}</span>
                  <img v-if="it.deviceId === camId" :src="iconReadyGreen" alt="ready" />
                </li>
                <li v-if="cams.length === 0" class="empty" aria-disabled="true">Нет устройств</li>
              </ul>
            </Transition>
          </div>
        </div>

        <div v-if="!isSpectator" class="switch-device-div">
          <span>Выбор микрофона:</span>
          <div class="ui-select" ref="micRoot" :class="{ open: micOpen }">
            <button type="button" @click="toggleMicDd" :aria-expanded="String(micOpen)" aria-label="Список микрофонов">
              <span>{{ micLabel }}</span>
              <img :src="iconArrowDown" alt="arrow" />
            </button>
            <Transition name="menu">
              <ul v-show="micOpen" role="listbox">
                <li v-for="it in mics" :key="it.deviceId" class="option" :aria-selected="it.deviceId === micId"
                    :class="{ selected: it.deviceId === micId }" @click="selectMic(it.deviceId)">
                  <span>{{ it.label || 'Микрофон' }}</span>
                  <img v-if="it.deviceId === micId" :src="iconReadyGreen" alt="ready" />
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

import iconClose from '@/assets/svg/close.svg'
import iconReadyGreen from '@/assets/svg/readyGreen.svg'
import iconArrowDown from '@/assets/svg/arrowDown.svg'

type Dev = {
  deviceId: string
  label: string
}

const props = defineProps<{
  open: boolean
  inGame: boolean
  isSpectator?: boolean
  isMobile?: boolean
  hotkeysVisible?: boolean
  mics: Dev[]
  cams: Dev[]
  micId: string
  camId: string
  mirrorOn: boolean
  volume: number
  volumeIcon: string
  canToggleKnownRoles: boolean
  knownRolesVisible: boolean
}>()

const emit = defineEmits<{
  'update:micId': [string]
  'update:camId': [string]
  'update:mirrorOn': [boolean]
  'update:volume': [number]
  'toggle-known-roles': []
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
const mirrorToggleLocked = ref(false)
let mirrorToggleTimer: number | null = null

const micIdProxy = computed({
  get: () => props.micId,
  set: (v: string) => { pickDevice('audioinput', v) }
})
const camIdProxy = computed({
  get: () => props.camId,
  set: (v: string) => { pickDevice('videoinput', v) }
})

function onToggleMirror(e: Event) {
  if (mirrorToggleLocked.value) {
    (e.target as HTMLInputElement).checked = props.mirrorOn
    return
  }
  mirrorToggleLocked.value = true
  if (mirrorToggleTimer !== null) clearTimeout(mirrorToggleTimer)
  mirrorToggleTimer = window.setTimeout(() => {
    mirrorToggleLocked.value = false
    mirrorToggleTimer = null
  }, 500)
  emit('update:mirrorOn', (e.target as HTMLInputElement).checked)
}
function onVolumeInput(e: Event) {
  emit('update:volume', Number((e.target as HTMLInputElement).value))
}
function onToggleKnownRoles() {
  emit('toggle-known-roles')
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
  if (mirrorToggleTimer !== null) clearTimeout(mirrorToggleTimer)
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
        .switch-label {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          height: 18px;
        }
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
              width: 100%;
              color: $fg;
              font-size: 14px;
              text-align: center;
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
      .switch.switch-wide {
        label {
          width: 200px;
          .slider:before {
            width: 98px;
          }
          input:checked + .slider:before {
            transform: translateX(100px);
          }
        }
      }
      .hot-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        height: 16px;
        min-width: 16px;
        border-radius: 5px;
        background-color: $fg;
        color: $black;
        font-size: 11px;
        font-weight: bold;
      }
    }
    .volume-block {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      .volume-text {
        height: 18px;
        color: $fg;
        font-size: 16px;
      }
      .volume {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 5px;
        gap: 5px;
        width: 190px;
        height: 20px;
        border-radius: 5px;
        background-color: $graphite;
        box-shadow: 3px 3px 5px rgba($black, 0.25);
        -webkit-overflow-scrolling: touch;
        img {
          flex: 0 0 auto;
          width: 20px;
          height: 20px;
        }
        input[type="range"] {
          flex: 1 1 auto;
          min-width: 0;
          height: 8px;
          accent-color: $fg;
          cursor: pointer;
          appearance: none;
          background: transparent;
        }
        span {
          flex: 0 0 auto;
          min-width: 32px;
          text-align: center;
          font-size: 12px;
        }
        input[type="range"]:disabled {
          cursor: default;
          opacity: 0.5;
        }
        input[type="range"]:focus-visible {
          outline: 1px solid $fg;
          outline-offset: 1px;
        }
        input[type="range"]::-webkit-slider-runnable-track {
          height: 6px;
          border-radius: 3px;
          background-color: $grey;
        }
        input[type="range"]::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background-color: $fg;
          border: 3px solid $dark;
          margin-top: calc(-18px / 2 + 3px);
        }
        input[type="range"]::-moz-range-track {
          height: 6px;
          border-radius: 3px;
          background-color: $grey;
        }
        input[type="range"]::-moz-range-thumb {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background-color: $fg;
          border: 3px solid $dark;
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
          transition: background-color 0.25s ease-in-out;
          &:hover {
            background-color: $graphite;
          }
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
          &:hover {
            background-color: $lead;
          }
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

@media (max-width: 1280px) {
  .settings {
    bottom: 30px;
  }
}
</style>
