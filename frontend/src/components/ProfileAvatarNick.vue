<template>
  <div class="profile-tab-block block-profile">
    <h3>Аватар и никнейм</h3>
    <div class="avatar-row">
      <img class="avatar-img" v-minio-img="{ key: me.avatar_name ? `avatars/${me.avatar_name}` : '', placeholder: iconDefaultAvatar, lazy: false, animated: true }" alt="Текущий аватар" />
      <div class="actions">
        <input ref="fileEl" type="file" :accept="avatarAccept" @change="emit('pick', $event)" :disabled="isBanned" hidden />
        <button class="btn dark" @click="fileEl?.click()" :disabled="busyAva || isBanned">
          <img class="btn-img" :src="iconDownload" alt="edit" />
          {{ me.avatar_name ? 'Изменить' : 'Загрузить' }}
        </button>
        <span class="hint center">{{ avatarFormatHint }}</span>
        <button class="btn danger" v-if="me.avatar_name" @click="emit('deleteAvatar')" :disabled="busyAva || isBanned">
          <img class="btn-img" :src="iconDelete" alt="delete" />
          Удалить
        </button>
      </div>
    </div>

    <div class="nick-row">
      <div class="nick-input-line">
        <UiInput class="profile-input" id="profile-nick" :model-value="nick" :model-modifiers="{ trim: true }" :maxlength="nickMax" :disabled="busyNick || isBanned || isProtectedAdminSelf" autocomplete="off" inputmode="text" label="Никнейм"
          :invalid="!!nick && !validNick" :aria-invalid="!!nick && !validNick" aria-describedby="profile-nick-hint" @update:modelValue="emit('update:nick', String($event).trim())">
          <template #meta>
            <span id="profile-nick-hint">{{ nick.length }}/{{ nickMax }}</span>
          </template>
        </UiInput>
        <div v-if="me.id > 0" class="nickname-history-tooltip-wrap" tabindex="0" aria-label="История никнеймов" @mouseenter="emit('loadNicknameHistory')" @focusin="emit('loadNicknameHistory')">
          <img class="nickname-history-icon" :src="iconTimeHistory" alt="" />
          <div class="nickname-history-tooltip" role="tooltip" @click.stop>
            <button class="btn danger nickname-history-clear" type="button" :disabled="nicknameHistoryClearDisabled" @click="emit('clearNicknameHistory')">
              {{ nicknameHistoryClearBusy ? '...' : 'Очистить историю' }}
            </button>
            <span class="nickname-history-access-text" :class="{ disabled: !canEditProfileTheme }">{{ nicknameHistoryAccessText }}</span>
            <span class="nickname-history-divider" aria-hidden="true"></span>
            <span v-if="nicknameHistoryLoading" class="nickname-history-state">Загрузка...</span>
            <span v-else-if="nicknameHistoryError" class="nickname-history-state danger">{{ nicknameHistoryError }}</span>
            <span v-else class="nickname-history-list">
              <span v-for="(nicknameItem, index) in nicknameHistoryItems" :key="`${nicknameItem}-${index}`" :class="{ current: index === 0 }">
                {{ nicknameItem }}
              </span>
              <span v-if="!nicknameHistoryItems.length" class="nickname-history-state">-</span>
            </span>
          </div>
        </div>
      </div>
      <span class="hint"><code>латиница, кириллица, цифры, символы ()._-</code></span>
      <span class="hint" :class="{ red: nicknameChangesLeft <= 0 }">Осталось изменений никнейма: {{ nicknameChangesLeft }}</span>
      <button class="btn confirm" @click="emit('saveNick')" :disabled="saveNickDisabled">
        <img class="btn-img" :src="iconSave" alt="save" />
        {{ busyNick ? '...' : 'Сохранить' }}
      </button>
    </div>
    <p class="hint">Никнейм является логином для авторизации</p>

    <div v-if="crop.show" :ref="setModalRef" class="modal" @keydown.esc="emit('cancelCrop')" tabindex="0" aria-modal="true" aria-label="Кадрирование аватара" >
      <div class="modal-body">
        <canvas :ref="setCanvasRef" @mousedown="emit('dragStart', $event)" @mousemove="emit('dragMove', $event)" @mouseup="emit('dragStop')" @mouseleave="emit('dragStop')" @wheel.passive="emit('wheel', $event)" />
        <div class="range">
          <span>Масштаб</span>
          <UiSlider
            :model-value="crop.scale"
            :min="crop.min"
            :max="crop.max"
            :step="0.01"
            :disabled="isBanned"
            aria-label="Масштаб"
            @update:modelValue="emit('scaleTo', $event)" />
        </div>
        <div class="modal-actions">
          <button class="btn danger" @click="emit('cancelCrop')">Отменить</button>
          <button class="btn confirm" @click="emit('applyCrop')" :disabled="busyAva || isBanned">Загрузить</button>
        </div>
      </div>
    </div>

    <div v-if="gifPicker.show" :ref="setGifModalRef" class="modal gif-modal" @keydown.esc="emit('cancelGifPicker')" tabindex="0" aria-modal="true" aria-label="Выбор статичного кадра GIF">
      <div class="modal-body gif-modal-body">
        <div class="gif-preview-row">
          <div class="gif-preview-block">
            <span>Анимация</span>
            <img v-if="gifPicker.animatedUrl" :src="gifPicker.animatedUrl" alt="GIF-анимация" />
          </div>
          <div class="gif-preview-block">
            <span>Статичный кадр</span>
            <canvas :ref="setGifCanvasRef" />
          </div>
        </div>
        <p v-if="gifPicker.error" class="hint red">{{ gifPicker.error }}</p>
        <div class="range">
          <span>Кадр {{ gifFrameLabel }}</span>
          <UiSlider
            :model-value="gifPicker.frameIndex"
            :min="0"
            :max="Math.max(0, gifPicker.frameCount - 1)"
            :step="1"
            :disabled="busyAva || isBanned || gifPicker.frameCount <= 1 || gifPicker.decoding"
            aria-label="Кадр GIF"
            @update:modelValue="emit('gifFrameRange', $event)" />
        </div>
        <div class="modal-actions">
          <button class="btn danger" @click="emit('cancelGifPicker')">Отменить</button>
          <button class="btn confirm" @click="emit('applyGifPicker')" :disabled="busyAva || isBanned || gifPicker.loading || gifPicker.decoding || !!gifPicker.error">Загрузить</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, type ComponentPublicInstance } from 'vue'
import UiInput from '@/components/UiInput.vue'
import UiSlider from '@/components/UiSlider.vue'

type ProfileAvatarUser = {
  id: number
  username: string
  avatar_name: string | null
}

type CropState = {
  show: boolean
  scale: number
  min: number
  max: number
}

type GifPickerState = {
  show: boolean
  animatedUrl: string
  frameCount: number
  frameIndex: number
  loading: boolean
  decoding: boolean
  error: string
}

defineProps<{
  me: ProfileAvatarUser
  nick: string
  iconDefaultAvatar: string
  iconDownload: string
  iconDelete: string
  iconTimeHistory: string
  iconSave: string
  avatarAccept: string
  avatarFormatHint: string
  isBanned: boolean
  busyAva: boolean
  busyNick: boolean
  isProtectedAdminSelf: boolean
  nickMax: number
  validNick: boolean
  canEditProfileTheme: boolean
  nicknameHistoryAccessText: string
  nicknameHistoryClearDisabled: boolean
  nicknameHistoryClearBusy: boolean
  nicknameHistoryLoading: boolean
  nicknameHistoryError: string
  nicknameHistoryItems: string[]
  nicknameChangesLeft: number
  saveNickDisabled: boolean
  crop: CropState
  gifPicker: GifPickerState
  gifFrameLabel: string
}>()

const emit = defineEmits<{
  (e: 'update:nick', value: string): void
  (e: 'pick', event: Event): void
  (e: 'deleteAvatar'): void
  (e: 'loadNicknameHistory'): void
  (e: 'clearNicknameHistory'): void
  (e: 'saveNick'): void
  (e: 'modalRef', el: HTMLDivElement | null): void
  (e: 'canvasRef', el: HTMLCanvasElement | null): void
  (e: 'gifModalRef', el: HTMLDivElement | null): void
  (e: 'gifCanvasRef', el: HTMLCanvasElement | null): void
  (e: 'cancelCrop'): void
  (e: 'dragStart', event: MouseEvent): void
  (e: 'dragMove', event: MouseEvent): void
  (e: 'dragStop'): void
  (e: 'wheel', event: WheelEvent): void
  (e: 'scaleTo', value: number): void
  (e: 'cancelGifPicker'): void
  (e: 'gifFrameRange', value: number): void
  (e: 'applyGifPicker'): void
  (e: 'applyCrop'): void
}>()

const fileEl = ref<HTMLInputElement | null>(null)

function setModalRef(el: Element | ComponentPublicInstance | null) {
  emit('modalRef', el instanceof HTMLDivElement ? el : null)
}

function setCanvasRef(el: Element | ComponentPublicInstance | null) {
  emit('canvasRef', el instanceof HTMLCanvasElement ? el : null)
}

function setGifModalRef(el: Element | ComponentPublicInstance | null) {
  emit('gifModalRef', el instanceof HTMLDivElement ? el : null)
}

function setGifCanvasRef(el: Element | ComponentPublicInstance | null) {
  emit('gifCanvasRef', el instanceof HTMLCanvasElement ? el : null)
}
</script>

<style scoped lang="scss">
.block-profile {
  .avatar-row {
    display: flex;
    gap: 20px;
    align-items: center;
    .avatar-img {
      width: 150px;
      height: 150px;
      object-fit: cover;
      border-radius: 50%;
    }
    .actions {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
  }
  .nick-row {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    margin-bottom: 5px;
    gap: 10px;
    .nick-input-line {
      display: flex;
      align-items: center;
      gap: 10px;
      width: 100%;
      :deep(.profile-input) {
        flex: 1 1 auto;
        max-width: 300px;
        width: 100%;
      }
      .nickname-history-tooltip-wrap {
        display: inline-flex;
        position: relative;
        flex: 0 0 auto;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        outline: none;
        &:hover,
        &:focus-within {
          &::after {
            display: block;
          }
          .nickname-history-tooltip {
            display: flex;
          }
        }
        &::after {
          content: '';
          display: none;
          position: absolute;
          top: 100%;
          right: 0;
          width: 300px;
          height: 10px;
          z-index: 4;
        }
        .nickname-history-icon {
          width: 24px;
          height: 24px;
          object-fit: contain;
        }
        .nickname-history-tooltip {
          display: none;
          position: absolute;
          top: calc(100% + 10px);
          right: 0;
          flex-direction: column;
          gap: 10px;
          width: 300px;
          max-height: 250px;
          padding: 10px;
          border-radius: 5px;
          background-color: $neutral-800;
          box-shadow: 3px 3px 5px rgba(black, 0.25);
          color: $neutral-100;
          font-size: 14px;
          line-height: 1.2;
          z-index: 5;
          .nickname-history-clear {
            width: 100%;
            max-width: none;
            min-height: 30px;
            font-size: 14px;
          }
          .nickname-history-access-text {
            color: $neutral-300;
            overflow-wrap: anywhere;
            &.disabled {
              color: $neutral-500;
            }
          }
          .nickname-history-divider {
            width: 100%;
            height: 1px;
            background-color: rgba($neutral-white, 0.1);
          }
          .nickname-history-list {
            display: flex;
            flex-direction: column;
            gap: 5px;
            overflow-y: auto;
            scrollbar-width: thin;
            span {
              color: $neutral-300;
              overflow-wrap: anywhere;
              &.current {
                color: $neutral-100;
                font-family: Hauora-SemiBold;
              }
            }
          }
          .nickname-history-state {
            color: $neutral-300;
            &.danger {
              color: $red-500;
            }
          }
        }
      }
    }
  }
  .modal {
    display: flex;
    position: fixed;
    align-items: center;
    justify-content: center;
    inset: 0;
    background-color: rgba($neutral-800, 0.2);
    backdrop-filter: blur(12px);
    overscroll-behavior: contain;
    z-index: 50;
    .modal-body {
      display: flex;
      flex-direction: column;
      padding: 10px;
      gap: 10px;
      border: 1px solid $neutral-800;
      border-radius: 5px;
      background-color: $neutral-900;
      > canvas {
        align-self: center;
        width: 300px;
        height: 300px;
        border-radius: 5px;
        background-color: black;
      }
      .range {
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      .modal-actions {
        display: flex;
        justify-content: space-between;
        gap: 10px;
      }
      .gif-preview-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: stretch;
        justify-content: center;
        .gif-preview-block {
          display: flex;
          flex-direction: column;
          gap: 5px;
          align-items: center;
          span {
            color: $neutral-500;
            font-size: 18px;
          }
          img {
            width: 300px;
            height: 300px;
            border-radius: 5px;
            background-color: black;
            object-fit: contain;
          }
          canvas {
            align-self: center;
            width: 300px;
            height: 300px;
            border-radius: 5px;
            background-color: black;
          }
        }
      }
      .hint {
        margin: 0;
        color: $neutral-500;
        font-size: 14px;
        &.red {
          color: $red-500;
        }
      }
    }
  }
}
</style>
