<template>
  <div class="switch" :style="switchStyle">
    <span class="switch-label">
      <slot name="label">{{ label }}</slot>
    </span>
    <label :class="{ 'has-tooltip': Boolean(props.tooltip) }" :tabindex="props.tooltip ? 0 : undefined" :title="props.tooltip || undefined">
      <input type="checkbox" :checked="modelValue" :disabled="isDisabled" :aria-label="ariaLabel || label" @change="onChange" />
      <div class="slider">
        <span>{{ offLabel }}</span>
        <span>{{ onLabel }}</span>
      </div>
      <span
        v-if="props.tooltip"
        class="switch-tooltip"
        :class="`switch-tooltip--${tooltipPosition}`"
        role="tooltip"
      >{{ props.tooltip }}</span>
    </label>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

const TOGGLE_GUARD_MS = 500

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
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'change', value: boolean): void
}>()

const offLabel = computed(() => props.offLabel ?? 'Откл')
const onLabel = computed(() => props.onLabel ?? 'Вкл')
const tooltipPosition = computed(() => props.tooltipPosition === 'bottom' ? 'bottom' : 'top')
const widthPx = computed(() => `${Number.isFinite(props.width) && props.width ? props.width : 170}px`)
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
  --switch-width: 170px;
  --switch-knob: calc((var(--switch-width) - 4px) / 2);
  --switch-translate: calc(var(--switch-knob) + 2px);
  .switch-label {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    width: calc(100% - var(--switch-width) - 5px);
    height: 18px;
  }
  label {
    position: relative;
    width: var(--switch-width);
    height: 25px;
    box-shadow: 3px 3px 5px rgba($black, 0.25);
    &.has-tooltip {
      cursor: help;
    }
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
      border: 1px solid $lead;
      border-radius: 5px;
      background-color: $graphite;
      span {
        position: relative;
        width: 100%;
        color: $fg;
        font-size: 14px;
        text-align: center;
        transition: color 0.25s ease-in-out;
      }
    }
    .slider:before {
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      width: var(--switch-knob);
      height: 23px;
      background-color: $fg;
      border-radius: 5px;
      transition: transform 0.25s ease-in-out;
    }
    input:checked + .slider:before {
      transform: translateX(var(--switch-translate));
    }
    input:not(:checked) + .slider span:first-child,
    input:checked + .slider span:last-child {
      color: $bg;
    }
    input:disabled + .slider {
      cursor: not-allowed;
    }
    .switch-tooltip {
      position: absolute;
      right: 0;
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
      transform: translateY(5px);
      pointer-events: none;
      transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
      z-index: 5;
      &.switch-tooltip--bottom {
        top: calc(100% + 10px);
        bottom: auto;
        transform: translateY(-5px);
      }
    }
    &.has-tooltip:hover .switch-tooltip,
    &.has-tooltip:focus-within .switch-tooltip {
      opacity: 1;
      transform: translateY(0);
      pointer-events: auto;
    }
  }
}
</style>
