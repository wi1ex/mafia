<template>
  <Transition name="confirm">
    <div v-if="state.open" class="overlay">
      <div class="modal" :role="dialogRole" aria-modal="true" :aria-labelledby="titleId">
        <header :id="titleId">
          <div class="header-div">
            <span class="header-title">{{ state.title }}</span>
            <span v-if="showText" class="header-text">{{ state.text }}</span>
          </div>
          <button type="button" aria-label="Закрыть" @click.stop="onClose">
            <UiIcon class="close-icon" :icon="iconClose" />
          </button>
        </header>
        <UiCheckbox v-if="showCheckbox" :id="checkboxId" v-model="state.checkboxChecked">
          <span v-if="state.checkboxLabel">{{ state.checkboxLabel }}</span>
          <router-link v-if="showCheckboxLink" :to="state.checkboxLinkTo" target="_blank" rel="noopener noreferrer" @click.stop>
            {{ state.checkboxLinkText }}
          </router-link>
          <span v-if="state.checkboxLabelSuffix">{{ state.checkboxLabelSuffix }}</span>
        </UiCheckbox>
        <div class="actions">
          <button v-if="isConfirm" @click.stop="onClose">{{ state.cancelText }}</button>
          <button class="confirm" :disabled="confirmDisabled" @click.stop="onConfirm">{{ state.confirmText }}</button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import { resolveConfirm, useConfirmState } from '@/services/confirm'
import iconClose from '@/assets/svg/iconClose.svg'
import UiIcon from '@/components/UiIcon.vue'
import UiCheckbox from '@/components/UiCheckbox.vue'

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

function onClose() {
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
  padding: 20px;
  background-color: rgba($neutral-black, 0.20);
  backdrop-filter: blur(12px);
  z-index: 3000;
  .modal {
    display: flex;
    flex-direction: column;
    padding: 24px;
    gap: 32px;
    width: 558px;
    border-radius: 24px;
    background-color: $neutral-100;
    box-shadow: 0 2px 16px 0 rgba($neutral-black, 0.20);
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      .header-div {
        display: flex;
        flex-direction: column;
        gap: 8px;
        .header-title {
          color: $neutral-black;
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        .header-text {
          color: $neutral-500;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 22px;
          letter-spacing: -0.32px;
        }
      }
      button {
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
        &:hover,
        &:focus-visible,
        &:active {
          .close-icon {
            --ui-icon-color: #{$green-500};
          }
        }
      }
    }
    .actions {
      display: flex;
      gap: 10px;
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 16px;
        height: 40px;
        border-radius: 12px;
        border: none;
        background-color: $neutral-white;
        color: $neutral-black;
        font-family: Hauora-Regular;
        font-size: 16px;
        line-height: 16px;
        letter-spacing: -0.32px;
        cursor: pointer;
        transition: opacity 0.25s ease-in-out, background-color 0.25s ease-in-out, color 0.25s ease-in-out;
        &:not(:disabled):hover,
        &:not(:disabled):focus-visible {
          color: $green-600;
        }
        &.confirm {
          background-color: $green-500;
          color: $neutral-900;
          &:not(:disabled):hover,
          &:not(:disabled):focus-visible {
            background-color: $green-300;
            color: $neutral-black;
          }
          &:disabled {
            background-color: $neutral-200;
            color: $neutral-400;
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

@media (max-width: 1280px) {

}

</style>
