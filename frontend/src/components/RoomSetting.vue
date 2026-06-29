<template>
  <Transition name="panel">
    <div v-show="open" class="settings" :data-open="open ? 1 : 0" aria-label="Настройки устройств" @click.stop>
      <header>
        <span class="title">Настройки</span>
        <button class="close-btn" type="button" aria-label="Закрыть" @click="$emit('close')">
          <UiIcon class="close-icon" :icon="iconClose" />
        </button>
      </header>

      <div class="change-devices">
        <UiSwitch
          v-if="showHotkeysToggle"
          :model-value="hotkeysVisible !== false"
          label="Подсказки для клавиш:"
          off-label="Скрыть"
          on-label="Показать"
          aria-label="Подсказки для клавиш"
          theme="light"
          size="low"
          :disabled="hotkeysTogglePending"
          @update:modelValue="onToggleHotkeys"
        />

        <UiSwitch
          :model-value="buttonsHigh"
          label="Расположение кнопок:"
          off-label="Стандарт"
          on-label="Кастом"
          aria-label="Расположение кнопок"
          theme="light"
          size="low"
          @update:modelValue="onToggleButtonsHigh"
        />

        <UiSwitch
          v-if="showVideoFillToggle"
          :model-value="videoFillOn"
          label="Заполнение видео:"
          off-label="Откл"
          on-label="Вкл"
          aria-label="Заполнение видео"
          theme="light"
          size="low"
          @update:modelValue="onToggleVideoFill"
        />

        <UiSwitch
          v-if="showMirrorToggle"
          :model-value="mirrorOn"
          label="Зеркальность камеры:"
          aria-label="Зеркальность камеры"
          theme="light"
          size="low"
          @update:modelValue="onToggleMirror"
        />

<!--          v-if="inGame && !isSpectator && canToggleKnownRoles"-->
        <UiSwitch
          :model-value="knownRolesVisible"
          off-label="Скрыть"
          on-label="Показать"
          aria-label="Отображение ролей"
          theme="light"
          size="low"
          @update:modelValue="onToggleKnownRoles"
        >
          <template #label>
            Отображение ролей:
            <span v-if="!isMobile && hotkeysVisible" class="hot-btn">R</span>
          </template>
        </UiSwitch>

<!--        <div v-if="inGame && musicEnabled" class="volume-block">-->
        <div class="volume-block">
          <span class="block-title">Громкость музыки:</span>
          <div class="volume">
            <UiIcon class="volume-img" :icon="volumeIcon" />
            <UiSlider
              :model-value="volume"
              :min="0"
              :max="100"
              :step="10"
              aria-label="Громкость фоновой музыки"
              @update:modelValue="emit('update:volume', $event)"
            />
            <span>{{ volume }}%</span>
          </div>
        </div>

        <div v-if="!isSpectator" class="switch-device-div">
          <span class="block-title">Выбор камеры:</span>
          <UiDropdown
            :model-value="camId"
            :options="camOptions"
            placeholder="Камера"
            empty-text="Нет устройств"
            aria-label="Список камер"
            mode="light"
            size="low"
            menu-placement="top"
            @update:modelValue="onCamDropdownUpdate"
          />
        </div>

        <div v-if="!isSpectator" class="switch-device-div">
          <span class="block-title">Выбор микрофона:</span>
          <UiDropdown
            :model-value="micId"
            :options="micOptions"
            placeholder="Микрофон"
            empty-text="Нет устройств"
            aria-label="Список микрофонов"
            mode="light"
            size="low"
            menu-placement="top"
            @update:modelValue="onMicDropdownUpdate"
          />
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import UiDropdown from '@/components/UiDropdown.vue'
import UiSwitch from '@/components/UiSwitch.vue'
import UiSlider from '@/components/UiSlider.vue'
import UiIcon from '@/components/UiIcon.vue'

import iconClose from '@/assets/svg/iconClose.svg'

type Dev = {
  deviceId: string
  label: string
}

type DropdownValue = string | number | null

const props = defineProps<{
  open: boolean
  inGame: boolean
  isSpectator?: boolean
  showHotkeysToggle: boolean
  showMirrorToggle: boolean
  isMobile?: boolean
  hotkeysVisible?: boolean
  hotkeysTogglePending?: boolean
  mics: Dev[]
  cams: Dev[]
  micId: string
  camId: string
  mirrorOn: boolean
  buttonsHigh: boolean
  videoFillOn: boolean
  showVideoFillToggle: boolean
  volume: number
  volumeIcon: string
  musicEnabled: boolean
  canToggleKnownRoles: boolean
  knownRolesVisible: boolean
}>()

const emit = defineEmits<{
  'update:micId': [string]
  'update:camId': [string]
  'update:mirrorOn': [boolean]
  'update:buttonsHigh': [boolean]
  'update:videoFillOn': [boolean]
  'update:volume': [number]
  'toggle-hotkeys': [boolean]
  'toggle-known-roles': []
  'device-change': ['audioinput' | 'videoinput']
  'close': []
}>()

const camOptions = computed(() => props.cams.map((item) => ({
  value: item.deviceId,
  label: item.label || 'Камера',
})))
const micOptions = computed(() => props.mics.map((item) => ({
  value: item.deviceId,
  label: item.label || 'Микрофон',
})))

function onToggleMirror(next: boolean) {
  emit('update:mirrorOn', next)
}
function onToggleButtonsHigh(next: boolean) {
  emit('update:buttonsHigh', next)
}
function onToggleVideoFill(next: boolean) {
  emit('update:videoFillOn', next)
}
function onToggleHotkeys(next: boolean) {
  emit('toggle-hotkeys', next)
}
function onToggleKnownRoles(_next: boolean) {
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

function onCamDropdownUpdate(value: DropdownValue): void {
  if (typeof value !== 'string') return
  pickDevice('videoinput', value)
}

function onMicDropdownUpdate(value: DropdownValue): void {
  if (typeof value !== 'string') return
  pickDevice('audioinput', value)
}
</script>

<style scoped lang="scss">
.settings {
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  bottom: 48px;
  padding: 16px 24px 24px;
  width: 462px;
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
  .change-devices {
    display: flex;
    flex-direction: column;
    gap: 8px;
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
    .block-title {
      color: $neutral-900;
      font-family: Hauora-Regular;
      font-size: 16px;
      line-height: 18px;
      letter-spacing: -0.32px;
    }
    .volume-block {
      display: flex;
      align-items: center;
      justify-content: space-between;
      .volume {
        display: flex;
        align-items: center;
        padding: 0 16px;
        gap: 8px;
        width: 224px;
        height: 40px;
        border-radius: 12px;
        background-color: $neutral-white;
        -webkit-overflow-scrolling: touch;
        .volume-img {
          --ui-icon-width: 24px;
          --ui-icon-height: 24px;
          --ui-icon-color: #{$soft-purple-900};
        }
        span {
          min-width: 42px;
          color: $soft-purple-900;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 16px;
          letter-spacing: -0.32px;
          text-align: right;
        }
      }
    }
    .switch-device-div {
      display: flex;
      flex-direction: column;
      margin-top: 8px;
      gap: 10px;
    }
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
