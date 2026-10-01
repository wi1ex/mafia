<template>
  <Teleport to="#desktop-teleport-root">
    <Transition name="overlay">
      <div v-if="open" class="overlay" :style="{ zIndex }" @pointerdown.stop.self="armed = true" @pointerup.stop.self="armed && close()"
           @pointerleave.stop.self="armed = false" @pointercancel.stop.self="armed = false" @click.stop>
        <div class="modal" role="dialog" aria-modal="true" :aria-label="title" @pointerdown.stop @pointerup.stop @click.stop>
          <header>
            <h2>{{ title }}</h2>
            <UiButton variant="white" size="low" :icon="iconClose" width="40px" aria-label="Закрыть" @click="close" />
          </header>
          <div class="modal-body">
            <div v-if="showDuration" class="duration-card">
              <h3>Срок</h3>
              <div class="grid">
                <UiInput id="sanction-months" v-model.number="form.months" type="number" min="0" max="240" step="1" autocomplete="off" label="Месяцы" size="low" />
                <UiInput id="sanction-days" v-model.number="form.days" type="number" min="0" max="31" step="1" autocomplete="off" label="Дни" size="low" />
                <UiInput id="sanction-hours" v-model.number="form.hours" type="number" min="0" max="23" step="1" autocomplete="off" label="Часы" size="low" />
              </div>
              <p v-if="durationHint" class="duration-hint">{{ durationHint }}</p>
            </div>
            <div v-if="showReason" class="reason-card">
              <label for="sanction-reason">Причина</label>
              <select id="sanction-reason" v-model="form.reason">
                <option v-for="option in reasons" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>
            <div v-if="showDescription" class="description-card">
              <h3>Служебное описание</h3>
              <p id="sanction-description-hint">Пользователь не увидит этот текст</p>
              <UiInput
                id="sanction-description"
                v-model="form.description"
                as="textarea"
                rows="5"
                maxlength="2048"
                label="Описание"
                size="low"
                aria-describedby="sanction-description-hint"
                class="sanction-description-textarea"
              />
            </div>
          </div>
          <div class="modal-actions">
            <UiButton variant="white" size="middle" text="Отмена" @click="close" />
            <UiButton size="middle" :text="saving ? 'Сохранение…' : saveLabel" :disabled="saving || !canSave" @click="$emit('save')" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import UiInput from '@/components/UiInput.vue'
import UiButton from '@/components/UiButton.vue'

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
  durationHint?: string
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
  durationHint: '',
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
  display: flex;
  position: fixed;
  inset: 0;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 40px;
  background-color: rgba($neutral-black, 0.6);
  backdrop-filter: blur(12px);
  z-index: 1000;
  .modal {
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    width: 640px;
    max-width: 100%;
    max-height: 100%;
    min-height: 0;
    padding: 24px;
    gap: 24px;
    border-radius: 24px;
    background-color: $soft-purple-900;
    color: $neutral-100;
    font-family: Hauora-Regular;
    line-height: 1.4;
    overflow: auto;
    overscroll-behavior: contain;
    scrollbar-width: thin;
    scrollbar-color: $soft-purple-700 transparent;
    > * {
      flex-shrink: 0;
    }
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
      h2 {
        min-width: 0;
        margin: 0;
        color: $neutral-white;
        font-family: Involve-Medium;
        font-weight: 500;
        font-size: 24px;
        line-height: 26px;
        letter-spacing: -0.48px;
      }
    }
    .modal-body {
      display: flex;
      flex-direction: column;
      min-width: 0;
      gap: 10px;
      --ui-input-label-bg: #{$soft-purple-800};
      .duration-card {
        display: flex;
        flex-direction: column;
        min-width: 0;
        padding: 20px;
        gap: 20px;
        border-radius: 20px;
        background-color: $soft-purple-800;
        h3 {
          margin: 0;
          color: $neutral-white;
          font-family: Involve-Medium;
          font-weight: 500;
          font-size: 20px;
          line-height: 24px;
          letter-spacing: -0.4px;
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
          :deep(input) {
            box-sizing: content-box;
          }
        }
        .duration-hint {
          margin: 0;
          color: $yellow-500;
          font-size: 14px;
          line-height: 20px;
        }
      }
      .reason-card {
        display: flex;
        flex-direction: column;
        min-width: 0;
        padding: 20px;
        gap: 20px;
        border-radius: 20px;
        background-color: $soft-purple-800;
        label {
          color: $neutral-white;
          font-family: Involve-Medium;
          font-size: 20px;
          line-height: 24px;
          letter-spacing: -0.4px;
        }
        select {
          box-sizing: border-box;
          width: 100%;
          min-width: 0;
          height: 40px;
          padding: 0 12px;
          border: 1px solid $green-200;
          border-radius: 12px;
          background-color: $soft-purple-800;
          color: $neutral-100;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 20px;
          text-overflow: ellipsis;
          color-scheme: dark;
          cursor: pointer;
          &:hover {
            border-color: $green-500;
          }
          &:focus-visible {
            outline: 2px solid $green-500;
            outline-offset: 3px;
          }
          option {
            background-color: $soft-purple-900;
            color: $neutral-100;
          }
        }
      }
      .description-card {
        display: flex;
        flex-direction: column;
        min-width: 0;
        padding: 20px;
        gap: 20px;
        border-radius: 20px;
        background-color: $soft-purple-800;
        h3 {
          margin: 0;
          color: $neutral-white;
          font-family: Involve-Medium;
          font-weight: 500;
          font-size: 20px;
          line-height: 24px;
          letter-spacing: -0.4px;
        }
        p {
          margin: -10px 0 0;
          color: $neutral-300;
          font-size: 14px;
          line-height: 20px;
        }
        .sanction-description-textarea {
          :deep(textarea) {
            box-sizing: content-box;
            min-height: 100px;
          }
        }
      }
    }
    .modal-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 12px;
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
