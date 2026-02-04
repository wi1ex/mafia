<template>
  <Teleport to="body">
    <Transition name="overlay">
      <div v-if="open" class="overlay" @pointerdown.self="armed = true" @pointerup.self="armed && close()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <div class="modal" role="dialog" aria-modal="true" :aria-label="title">
          <header>
            <span>{{ title }}</span>
            <button class="icon" @click="close" aria-label="Закрыть">
              <img :src="iconClose" alt="close" />
            </button>
          </header>
          <div class="modal-body">
            <UiInput id="update-version" v-model.trim="form.version" type="text" autocomplete="off" label="Версия" />
            <UiInput id="update-date" v-model="form.date" type="date" autocomplete="off" label="Дата" />
            <UiInput id="update-desc" v-model.trim="form.description" as="textarea" rows="5" label="Описание" class="update-textarea" />
          </div>
          <div class="modal-actions">
            <button class="btn dark" @click="close">Отмена</button>
            <button class="btn confirm" :disabled="saving || !canSave" @click="$emit('save')">
              <img v-if="saveIcon" class="btn-img" :src="saveIcon" alt="save" />
              Сохранить
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import UiInput from '@/components/UiInput.vue'

import iconClose from '@/assets/svg/close.svg'

defineProps<{
  open: boolean
  title: string
  saving: boolean
  canSave: boolean
  saveIcon?: string
  form: {
    version: string
    date: string
    description: string
  }
}>()

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
    width: 400px;
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
      .btn-img {
        width: 20px;
        height: 20px;
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

@media (max-width: 1280px) {
  .overlay {
    .modal {
      .btn {
        padding: 0 10px;
        height: 30px;
        .btn-img {
          width: 16px;
          height: 16px;
        }
      }
      :deep(.update-textarea textarea) {
        min-height: 60px;
        max-height: 60px;
      }
    }
  }
}
</style>
