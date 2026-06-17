<template>
  <div class="switch" :class="`switch--${switchTheme}`" :style="switchStyle">
    <span class="switch-label">
      <slot name="label">{{ label }}</slot>
    </span>
    <label>
      <input type="checkbox" :checked="modelValue" :disabled="isDisabled" :aria-label="ariaLabel || label" @change="onChange" />
      <div class="slider">
        <span class="slider-option" :class="{ 'slider-option--with-tooltip': showTooltipFor('off') }">
          <span class="slider-option__text">{{ offLabel }}</span>
          <UiTooltip
            v-if="showTooltipFor('off')"
            :text="props.tooltip"
            :placement="tooltipPlacement"
            :aria-label="tooltipAriaLabel"
            :icon-size="20"
            :bubble-width="props.tooltipBubbleWidth"
          />
        </span>
        <span class="slider-option" :class="{ 'slider-option--with-tooltip': showTooltipFor('on') }">
          <span class="slider-option__text">{{ onLabel }}</span>
          <UiTooltip
            v-if="showTooltipFor('on')"
            :text="props.tooltip"
            :placement="tooltipPlacement"
            :aria-label="tooltipAriaLabel"
            :icon-size="20"
            :bubble-width="props.tooltipBubbleWidth"
          />
        </span>
      </div>
    </label>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import UiTooltip from '@/components/UiTooltip.vue'

const TOGGLE_GUARD_MS = 500
type TooltipTarget = 'off' | 'on'
type TooltipPlacement = 'top-right' | 'top-center' | 'top-left' | 'bottom-right' | 'bottom-center' | 'bottom-left'
type SwitchTheme = 'light' | 'dark'

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
  tooltipPlacement?: TooltipPlacement
  tooltipTarget?: TooltipTarget
  tooltipAriaLabel?: string
  tooltipBubbleWidth?: number | string
  theme?: SwitchTheme
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'change', value: boolean): void
}>()

const offLabel = computed(() => props.offLabel ?? 'Откл')
const onLabel = computed(() => props.onLabel ?? 'Вкл')
const tooltipTarget = computed<TooltipTarget>(() => props.tooltipTarget === 'off' ? 'off' : 'on')
const tooltipPlacement = computed<TooltipPlacement>(() => {
  if (props.tooltipPlacement) return props.tooltipPlacement
  return props.tooltipPosition === 'bottom' ? 'bottom-right' : 'top-right'
})
const tooltipAriaLabel = computed(() => props.tooltipAriaLabel || 'Подсказка')
const widthPx = computed(() => `${Number.isFinite(props.width) && props.width ? props.width : 274}px`)
const switchTheme = computed<SwitchTheme>(() => props.theme === 'dark' ? 'dark' : 'light')
const switchStyle = computed<Record<string, string>>(() => ({ '--switch-width': widthPx.value }))

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
  --switch-slider-color: #{$neutral-white};
  &.switch--dark {
    --switch-slider-color: #{$soft-purple-900};
  }
  &.switch--light {
    --switch-slider-color: #{$neutral-white};
  }
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
      border: 4px solid var(--switch-slider-color);
      background-color: var(--switch-slider-color);
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
        line-height: 22px;
        letter-spacing: -0.36px;
        transition: color 0.25s ease-in-out;
        z-index: 1;
      }
      .slider-option--with-tooltip {
        z-index: 2;
      }
      .slider-option__text {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
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
  }
}

</style>
