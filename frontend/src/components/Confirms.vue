<template>
  <Transition name="confirm">
    <div v-if="state.open" class="overlay">
      <div class="modal" :role="dialogRole" aria-modal="true" :aria-labelledby="titleId">
        <header :id="titleId">
          <span class="title">{{ state.title }}</span>
        </header>
        <span v-if="showText" class="text">{{ state.text }}</span>
        <div v-if="showCheckbox" class="checkbox">
          <input :id="checkboxId" v-model="state.checkboxChecked" type="checkbox" />
          <label v-if="state.checkboxLabel" :for="checkboxId" class="checkbox-label">{{ state.checkboxLabel }}</label>
          <router-link v-if="showCheckboxLink" class="checkbox-link" :to="state.checkboxLinkTo" target="_blank" rel="noopener noreferrer" @click.stop>
            {{ state.checkboxLinkText }}
          </router-link>
          <label v-if="state.checkboxLabelSuffix" :for="checkboxId" class="checkbox-label">{{ state.checkboxLabelSuffix }}</label>
        </div>
        <div class="actions">
          <button v-if="isConfirm" @click="onCancel">{{ state.cancelText }}</button>
          <button class="confirm" :disabled="confirmDisabled" @click="onConfirm">{{ state.confirmText }}</button>
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
const showText = computed(() => Boolean(state.text) && !state.hideText)
const showCheckbox = computed(() => Boolean(state.checkboxLabel) || Boolean(state.checkboxLinkText) || Boolean(state.checkboxLabelSuffix))
const showCheckboxLink = computed(() => Boolean(state.checkboxLinkText) && Boolean(state.checkboxLinkTo))
const confirmDisabled = computed(() => state.checkboxRequired && !state.checkboxChecked)
const dialogRole = computed(() => (state.mode === 'alert' ? 'alertdialog' : 'dialog'))
const titleId = 'confirm-title'
const checkboxId = 'confirm-checkbox'

function onConfirm() {
  if (confirmDisabled.value) return
  resolveConfirm(true)
}

function onCancel() {
  resolveConfirm(false)
}

function onKeydown(e: KeyboardEvent) {
  if (!state.open) return
  if (e.key === 'Escape') resolveConfirm(false)
  if (e.key === 'Enter' && !confirmDisabled.value) resolveConfirm(true)
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
  background-color: rgba($black, 0.75);
  backdrop-filter: blur(5px);
  z-index: 3000;
  .modal {
    display: flex;
    flex-direction: column;
    gap: 15px;
    width: min(40%, 400px);
    border-radius: 5px;
    background-color: $dark;
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 15px;
      border-radius: 5px;
      background-color: $graphite;
      box-shadow: 0 3px 5px rgba($black, 0.25);
      .title {
        font-size: 18px;
        font-weight: bold;
      }
    }
    .text {
      margin: 0 15px;
      line-height: 1.25;
      white-space: pre-line;
    }
    .checkbox {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 3px;
      margin: 0 15px;
      font-size: 14px;
      line-height: 1.25;
      input {
        width: 16px;
        height: 16px;
        accent-color: $green;
        cursor: pointer;
      }
      .checkbox-label {
        cursor: pointer;
      }
      .checkbox-link {
        color: $white;
        text-decoration: underline;
      }
    }
    .actions {
      display: flex;
      justify-content: flex-end;
      margin: 0 15px 15px;
      gap: 15px;
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 15px;
        height: 30px;
        border: none;
        border-radius: 5px;
        background-color: $graphite;
        color: $fg;
        font-size: 14px;
        font-family: Manrope-Medium;
        line-height: 1;
        cursor: pointer;
        transition: opacity 0.25s ease-in-out, background-color 0.25s ease-in-out;
        &:hover {
          background-color: $lead;
        }
        &.confirm {
          background-color: rgba($green, 0.75);
          color: $bg;
          &:hover {
            background-color: $green;
          }
          &:disabled {
            opacity: 0.5;
            cursor: not-allowed;
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

</style>
