<template>
  <Teleport to="body">
    <Transition name="overlay">
      <div v-if="open" class="overlay" :style="{ zIndex }" @pointerdown.stop.self="armed = true" @pointerup.stop.self="armed && close()"
           @pointerleave.stop.self="armed = false" @pointercancel.stop.self="armed = false" @click.stop>
        <div class="modal" role="dialog" aria-modal="true" :aria-label="title" @pointerdown.stop @pointerup.stop @click.stop>
          <header>
            <span>{{ title }}</span>
            <button class="icon" @click="close" aria-label="Закрыть">
              <img :src="iconClose" alt="close" />
            </button>
          </header>
          <div class="modal-body">
            <div v-if="showDuration" class="grid">
              <UiInput id="sanction-months" v-model.number="form.months" type="number" min="0" max="240" step="1" autocomplete="off" label="Месяцы" />
              <UiInput id="sanction-days" v-model.number="form.days" type="number" min="0" max="31" step="1" autocomplete="off" label="Дни" />
              <UiInput id="sanction-hours" v-model.number="form.hours" type="number" min="0" max="23" step="1" autocomplete="off" label="Часы" />
            </div>
            <UiDropdown
              v-if="showReason"
              id="sanction-reason"
              v-model="form.reason"
              label="Причина"
              :options="reasons"
            />
            <UiInput
              v-if="showDescription"
              id="sanction-description"
              v-model="form.description"
              as="textarea"
              rows="5"
              maxlength="2048"
              label="Описание (пользователь не увидит этот текст)"
              class="sanction-description-textarea"
            />
          </div>
          <div class="modal-actions">
            <button class="btn dark" @click="close">Отмена</button>
            <button class="btn confirm" :disabled="saving || !canSave" @click="$emit('save')">
              {{ saving ? '...' : saveLabel }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import UiDropdown from '@/components/UiDropdown.vue'
import UiInput from '@/components/UiInput.vue'

import iconClose from '@/assets/svg/iconClose.svg'

withDefaults(defineProps<{
  open: boolean
  title: string
  saving: boolean
  canSave: boolean
  showDuration?: boolean
  showReason?: boolean
  showDescription?: boolean
  saveLabel?: string
  zIndex?: number
  reasons: { value: string; label: string }[]
  form: {
    months: number
    days: number
    hours: number
    reason: string
    description: string
  }
}>(), {
  showDuration: true,
  showReason: true,
  showDescription: true,
  saveLabel: 'Применить',
  zIndex: 1000,
})

const emit = defineEmits<{
  'update:open': [boolean]
  'save': []
}>()

const armed = ref(false)

function close() {
  emit('update:open', false)
}
</script>

<style scoped lang="scss">
.overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(black, 0.25);
  backdrop-filter: blur(5px);
  z-index: 1000;
  .modal {
    width: 420px;
    max-width: calc(100% - 30px);
    border-radius: 5px;
    background-color: $neutral-800;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    .btn {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 20px;
      gap: 5px;
      height: 40px;
      border: none;
      border-radius: 5px;
      background-color: $neutral-100;
      font-size: 14px;
      color: $neutral-black;
      font-family: Hauora-Regular;
      line-height: 1;
      cursor: pointer;
      transition: opacity 0.25s ease-in-out, color 0.25s ease-in-out, border-radius 0.25s ease-in-out, background-color 0.25s ease-in-out;
      &:hover {
        background-color: $neutral-white;
      }
      &.confirm {
        background-color: rgba($green-500, 0.75);
        &:hover {
          background-color: $green-500;
        }
      }
      &.dark {
        background-color: $neutral-700;
        color: $neutral-100;
        &:hover {
          background-color: rgba($neutral-500, 0.5);
        }
      }
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      span {
        font-size: 18px;
        font-family: Hauora-Regular;
      }
      .icon {
        width: 28px;
        height: 28px;
        border: none;
        background: none;
        cursor: pointer;
        img {
          width: 20px;
          height: 20px;
        }
      }
    }
    .modal-body {
      display: flex;
      flex-direction: column;
      gap: 10px;
      .grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
      }
      :deep(.sanction-description-textarea textarea) {
        min-height: 100px;
      }
    }
    .modal-actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }
  }
}

.overlay-enter-active,
.overlay-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}

</style>
