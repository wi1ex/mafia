<template>
  <Teleport to="body">
    <Transition name="overlay">
      <div v-if="open" class="overlay" @pointerdown.self="armed = true" @pointerup.self="armed && close()"
           @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <div class="modal" role="dialog" aria-modal="true" :aria-label="title">
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
              :disabled="saving"
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

import iconClose from '@/assets/svg/close.svg'

withDefaults(defineProps<{
  open: boolean
  title: string
  saving: boolean
  canSave: boolean
  showDuration?: boolean
  showReason?: boolean
  saveLabel?: string
  reasons: { value: string; label: string }[]
  form: {
    months: number
    days: number
    hours: number
    reason: string
  }
}>(), {
  showDuration: true,
  showReason: true,
  saveLabel: 'Применить',
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
  background-color: rgba($black, 0.25);
  backdrop-filter: blur(5px);
  z-index: 1000;
  .modal {
    width: 420px;
    max-width: calc(100% - 30px);
    border-radius: 5px;
    background-color: $graphite;
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
      background-color: $fg;
      font-size: 14px;
      color: $bg;
      font-family: Manrope-Medium;
      line-height: 1;
      cursor: pointer;
      transition: opacity 0.25s ease-in-out, color 0.25s ease-in-out, border-radius 0.25s ease-in-out, background-color 0.25s ease-in-out;
      &:hover {
        background-color: $white;
      }
      &.confirm {
        background-color: rgba($green, 0.75);
        &:hover {
          background-color: $green;
        }
      }
      &.dark {
        background-color: $lead;
        color: $fg;
        &:hover {
          background-color: rgba($grey, 0.5);
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
        font-family: Manrope-Medium;
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
