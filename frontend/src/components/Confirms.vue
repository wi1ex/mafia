<template>
  <Transition name="confirm">
    <div v-if="state.open" class="overlay" @pointerdown.stop @click.stop>
      <div class="modal" :role="dialogRole" aria-modal="true" :aria-labelledby="titleId" @pointerdown.stop @click.stop>
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
        <div v-if="showRadioOptions" class="radio-options" role="radiogroup">
          <div v-for="option in state.radioOptions" :key="option.value" class="radio-option">
            <UiCheckbox
              :id="`${radioGroupId}-${option.value}`"
              :model-value="state.radioValue === option.value"
              :name="radioGroupId"
              :disabled="option.disabled"
              input-type="radio"
              radio-style
              @update:model-value="checked => onRadioChange(option.value, checked)"
            >
              {{ option.label }}
            </UiCheckbox>
            <UiTooltip
              v-if="option.tooltip"
              :text="option.tooltip"
              placement="top-right"
              bubble-width="320px"
              :icon-size="20"
            />
          </div>
        </div>
        <div class="actions">
          <UiButton
            v-if="isConfirm"
            variant="white"
            size="middle"
            :text="state.cancelText"
            @click.stop="onCancel"
          />
          <UiButton
            class="confirm"
            size="middle"
            :text="state.confirmText"
            :disabled="confirmDisabled"
            @click.stop="onConfirm"
          />
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
import UiTooltip from '@/components/UiTooltip.vue'
import UiButton from '@/components/UiButton.vue'

const state = useConfirmState()
const isConfirm = computed(() => state.mode === 'confirm')
const showText = computed(() => Boolean(state.text) && !state.hideText)
const showCheckbox = computed(() => Boolean(state.checkboxLabel) || Boolean(state.checkboxLinkText) || Boolean(state.checkboxLabelSuffix))
const showCheckboxLink = computed(() => Boolean(state.checkboxLinkText) && Boolean(state.checkboxLinkTo))
const showRadioOptions = computed(() => state.radioOptions.length > 0)
const confirmDisabled = computed(() => state.checkboxRequired && !state.checkboxChecked)
const dialogRole = computed(() => (state.mode === 'alert' ? 'alertdialog' : 'dialog'))
const titleId = 'confirm-title'
const checkboxId = 'confirm-checkbox'
const radioGroupId = 'confirm-radio'

function onRadioChange(value: string, checked: boolean) {
  if (checked) state.radioValue = value
}

function onConfirm() {
  if (confirmDisabled.value) return
  resolveConfirm(true, 'confirm')
}

function onCancel() {
  resolveConfirm(false, 'cancel')
}

function onClose() {
  resolveConfirm(false, 'close')
}

function onKeydown(e: KeyboardEvent) {
  if (!state.open) return
  if (e.key === 'Escape') resolveConfirm(false, 'close')
  if (e.key === 'Enter' && !confirmDisabled.value) resolveConfirm(true, 'confirm')
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
  background-color: rgba($neutral-black, 0.2);
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
        &:not(:disabled):hover,
        &:not(:disabled):focus-visible,
        &:not(:disabled):active {
          .close-icon {
            --ui-icon-color: #{$green-500};
          }
        }
      }
    }
    .radio-options {
      display: flex;
      flex-direction: column;
      gap: 10px;
      .radio-option {
        display: flex;
        align-items: center;
        gap: 4px;
      }
    }
    .actions {
      display: flex;
      gap: 10px;
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
