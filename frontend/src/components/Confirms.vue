<template>
  <Transition name="confirm">
    <div v-if="state.open" class="overlay">
      <div class="modal" :role="dialogRole" aria-modal="true" :aria-labelledby="titleId">
        <header :id="titleId">{{ state.title }}</header>
        <span>{{ state.text }}</span>
        <div class="actions">
          <button v-if="isConfirm" @click="onCancel">{{ state.cancelText }}</button>
          <button class="confirm" @click="onConfirm">{{ state.confirmText }}</button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import { resolveConfirm, useConfirmState } from '@/services/confirm'

const state = useConfirmState()
const isConfirm = computed(() => state.mode === 'confirm')
const dialogRole = computed(() => (state.mode === 'alert' ? 'alertdialog' : 'dialog'))
const titleId = 'confirm-title'

function onConfirm() {
  resolveConfirm(true)
}

function onCancel() {
  resolveConfirm(false)
}

function onKeydown(e: KeyboardEvent) {
  if (!state.open) return
  if (e.key === 'Escape') resolveConfirm(false)
  if (e.key === 'Enter') resolveConfirm(true)
}

watch(() => state.open, (open) => {
  if (open) document.addEventListener('keydown', onKeydown)
  else document.removeEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped lang="scss">
.overlay {
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($black, 0.65);
  backdrop-filter: blur(2px);
  z-index: 3000;
  .modal {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: min(90vw, 420px);
    padding: 16px 18px;
    border-radius: 6px;
    background-color: $graphite;
    box-shadow: 0 10px 25px rgba($black, 0.35);
    header {
      font-size: 18px;
      font-family: Manrope-SemiBold;
    }
    span {
      margin: 0;
      color: $fg;
      line-height: 1.4;
      white-space: pre-line;
    }
    .actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 16px;
        height: 34px;
        border: none;
        border-radius: 5px;
        background-color: $lead;
        color: $fg;
        font-size: 14px;
        font-family: Manrope-Medium;
        line-height: 1;
        cursor: pointer;
        transition: background-color 0.25s ease-in-out, opacity 0.25s ease-in-out;
        &:hover {
          background-color: $dark;
        }
        &.confirm {
          background-color: rgba($green, 0.75);
          color: $bg;
          &:hover {
            background-color: $green;
          }
        }
      }
    }
  }
}

.confirm-enter-active,
.confirm-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.confirm-enter-from,
.confirm-leave-to {
  opacity: 0;
}

@media (max-width: 1280px) {
  .overlay {
    .modal {
      width: min(92vw, 360px);
      padding: 14px 16px;
      .actions {
        flex-direction: column-reverse;
        button {
          width: 100%;
        }
      }
    }
  }
}
</style>
