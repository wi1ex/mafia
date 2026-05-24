<template>
  <div class="switch" :style="switchStyle">
    <span class="switch-label">
      <slot name="label">{{ label }}</slot>
    </span>
    <label>
      <input type="checkbox" :checked="modelValue" :disabled="isDisabled" :aria-label="ariaLabel || label" @change="onChange" />
      <div class="slider">
        <span class="slider-option">
          <span class="slider-option__text">{{ offLabel }}</span>
          <span v-if="showTooltipFor('off')" class="switch-tooltip-trigger" role="button" tabindex="0" :aria-label="tooltipAriaLabel"
                :aria-describedby="tooltipId" @click.stop.prevent @keydown.enter.stop.prevent @keydown.space.stop.prevent>
            <span class="switch-tooltip-icon" aria-hidden="true">?</span>
            <span :id="tooltipId" class="switch-tooltip" :class="`switch-tooltip--${tooltipPosition}`" role="tooltip">
              {{ props.tooltip }}
            </span>
          </span>
        </span>
        <span class="slider-option">
          <span class="slider-option__text">{{ onLabel }}</span>
          <span v-if="showTooltipFor('on')" class="switch-tooltip-trigger" role="button" tabindex="0" :aria-label="tooltipAriaLabel"
                :aria-describedby="tooltipId" @click.stop.prevent @keydown.enter.stop.prevent @keydown.space.stop.prevent>
            <span class="switch-tooltip-icon" aria-hidden="true">?</span>
            <span :id="tooltipId" class="switch-tooltip" :class="`switch-tooltip--${tooltipPosition}`" role="tooltip">
              {{ props.tooltip }}
            </span>
          </span>
        </span>
      </div>
    </label>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useId } from 'vue'

const TOGGLE_GUARD_MS = 500
type TooltipTarget = 'off' | 'on'

const props = defineProps<{
  modelValue: boolean
  label?: string
  offLabel?: string
  onLabel?: string
  ariaLabel?: string
  disabled?: boolean
  width?: number
  tooltip?: string
  tooltipPosition?: 'top' | 'bottom'
  tooltipTarget?: TooltipTarget
  tooltipAriaLabel?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'change', value: boolean): void
}>()

const offLabel = computed(() => props.offLabel ?? 'Откл')
const onLabel = computed(() => props.onLabel ?? 'Вкл')
const tooltipPosition = computed(() => props.tooltipPosition === 'bottom' ? 'bottom' : 'top')
const tooltipTarget = computed<TooltipTarget>(() => props.tooltipTarget === 'off' ? 'off' : 'on')
const tooltipAriaLabel = computed(() => props.tooltipAriaLabel || 'Подсказка')
const widthPx = computed(() => `${Number.isFinite(props.width) && props.width ? props.width : 274}px`)
const switchStyle = computed<Record<string, string>>(() => ({ '--switch-width': widthPx.value }))
const tooltipId = useId()

const switchLocked = ref(false)
const isDisabled = computed(() => Boolean(props.disabled) || switchLocked.value)
let unlockTimer: number | null = null

function lockSwitch() {
  switchLocked.value = true
  if (unlockTimer !== null) window.clearTimeout(unlockTimer)
  unlockTimer = window.setTimeout(() => {
    switchLocked.value = false
    unlockTimer = null
  }, TOGGLE_GUARD_MS)
}

function onChange(e: Event) {
  if (isDisabled.value) return
  const checked = (e.target as HTMLInputElement).checked
  lockSwitch()
  emit('update:modelValue', checked)
  emit('change', checked)
}

function showTooltipFor(target: TooltipTarget): boolean {
  return Boolean(props.tooltip) && tooltipTarget.value === target
}

onBeforeUnmount(() => {
  if (unlockTimer !== null) {
    window.clearTimeout(unlockTimer)
    unlockTimer = null
  }
})
</script>

<style scoped lang="scss">
.switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  --switch-width: 274px;
  --switch-knob: calc((var(--switch-width) - 8px) / 2);
  --switch-translate: calc(var(--switch-knob) + 0px);
  .switch-label {
    display: inline-flex;
    align-items: center;
    width: calc(100% - var(--switch-width) - 10px);
    color: $neutral-black;
    font-family: Hauora-Bold;
    font-size: 16px;
    line-height: 18px;
    letter-spacing: -0.32px;
  }
  label {
    position: relative;
    width: var(--switch-width);
    height: 56px;
    input {
      position: absolute;
      opacity: 0;
      width: 0;
      height: 0;
    }
    .slider {
      display: flex;
      align-items: center;
      justify-content: space-around;
      position: absolute;
      inset: 0;
      cursor: pointer;
      border-radius: 999px;
      border: 4px solid $soft-purple-900;
      background-color: $soft-purple-900;
      .slider-option {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 5px;
        position: relative;
        width: 100%;
        min-width: 0;
        color: $neutral-500;
        font-family: Hauora-Regular;
        font-size: 18px;
        line-height: 20px;
        letter-spacing: -0.36px;
        text-align: center;
        transition: color 0.25s ease-in-out;
        z-index: 1;
      }
      .slider-option__text {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .switch-tooltip-trigger {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        position: relative;
        flex: 0 0 auto;
        width: 15px;
        height: 15px;
        border-radius: 50%;
        border: 1px solid currentColor;
        color: currentColor;
        cursor: help;
        font-family: Hauora-Bold;
        font-size: 10px;
        line-height: 1;
        outline: none;
      }
      .switch-tooltip-trigger:focus-visible {
        box-shadow: 0 0 0 2px rgba($fg, 0.45);
      }
    }
    .slider:before {
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      width: var(--switch-knob);
      height: 48px;
      border-radius: 999px;
      background: linear-gradient(261deg, $soft-purple-800 0%, $green-700 100%);
      transition: transform 0.25s ease-in-out;
    }
    input:checked + .slider:before {
      transform: translateX(var(--switch-translate));
    }
    input:not(:checked) + .slider .slider-option:first-child,
    input:checked + .slider .slider-option:last-child {
      color: $neutral-white;
    }
    input:disabled + .slider {
      cursor: not-allowed;
    }
    .switch-tooltip {
      position: absolute;
      left: 50%;
      bottom: calc(100% + 10px);
      min-width: 260px;
      max-width: 360px;
      padding: 10px;
      border: 1px solid $grey;
      border-radius: 5px;
      background-color: $lead;
      box-shadow: 0 5px 15px rgba($black, 0.25);
      color: $fg;
      font-size: 12px;
      line-height: 1.2;
      opacity: 0;
      transform: translate(-50%, 5px);
      pointer-events: none;
      transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
      z-index: 5;
      &.switch-tooltip--bottom {
        top: calc(100% + 10px);
        bottom: auto;
        transform: translate(-50%, -5px);
      }
    }
    .switch-tooltip-trigger:hover .switch-tooltip,
    .switch-tooltip-trigger:focus-visible .switch-tooltip {
      opacity: 1;
      transform: translate(-50%, 0);
      pointer-events: auto;
    }
  }
}
</style>
