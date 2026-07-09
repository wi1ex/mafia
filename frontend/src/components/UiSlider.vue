<template>
  <div class="ui-slider ui-slider--filled" :class="[themeClass, { disabled }]">
    <div class="ui-slider__fill-wrap">
      <div v-if="hasDeadZone" class="ui-slider__dead-zone" :style="deadZoneStyle" @click.stop="onDeadZoneClick"></div>
      <div class="ui-slider__fill-track" :style="fillStyle" aria-hidden="true"></div>
      <input
        class="ui-slider__input ui-slider__input--filled"
        type="range"
        :min="minValue"
        :max="maxValue"
        :step="stepValue"
        :value="currentValue"
        :disabled="disabled"
        :aria-label="ariaLabel || undefined"
        @input="onInput"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: number
  min?: number
  max?: number
  step?: number
  disabled?: boolean
  ariaLabel?: string
  deadZoneUntil?: number | null
  deadZoneValue?: number | null
  theme?: 'dark' | 'light'
}>(), {
  min: 0,
  max: 100,
  step: 1,
  disabled: false,
  ariaLabel: '',
  deadZoneUntil: null,
  deadZoneValue: null,
  theme: 'dark',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: number): void
}>()

function toNum(v: unknown, fallback: number): number {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n))
}

const minRaw = computed(() => toNum(props.min, 0))
const maxRaw = computed(() => toNum(props.max, 100))
const minValue = computed(() => Math.min(minRaw.value, maxRaw.value))
const maxValue = computed(() => Math.max(minRaw.value, maxRaw.value))
const stepValue = computed(() => {
  const v = toNum(props.step, 1)
  return v > 0 ? v : 1
})
const themeClass = computed(() => `ui-slider--${props.theme}`)

const currentValue = computed(() => normalizeValue(toNum(props.modelValue, minValue.value)))

const fillPct = computed(() => {
  const span = maxValue.value - minValue.value
  if (span <= 0) return 0
  return ((currentValue.value - minValue.value) * 100) / span
})
const fillStyle = computed<Record<string, string>>(() => ({ '--fill': `${fillPct.value}%` }))

const deadUntil = computed(() => {
  if (props.deadZoneUntil == null) return null
  return clamp(toNum(props.deadZoneUntil, minValue.value), minValue.value, maxValue.value)
})
const deadValue = computed(() => {
  if (props.deadZoneValue == null) return null
  return clamp(toNum(props.deadZoneValue, minValue.value), minValue.value, maxValue.value)
})
const hasDeadZone = computed(() => deadUntil.value != null && deadValue.value != null)
const deadZonePct = computed(() => {
  if (!hasDeadZone.value || deadUntil.value == null) return 0
  const span = maxValue.value - minValue.value
  if (span <= 0) return 0
  return ((deadUntil.value - minValue.value) * 100) / span
})
const deadZoneStyle = computed<Record<string, string>>(() => ({ '--dead': `${deadZonePct.value}%` }))

function normalizeValue(next: number): number {
  const clamped = clamp(next, minValue.value, maxValue.value)
  if (!hasDeadZone.value || deadUntil.value == null || deadValue.value == null) return clamped
  return clamped <= deadUntil.value ? deadValue.value : clamped
}

function emitValue(next: number): number {
  const normalized = normalizeValue(next)
  emit('update:modelValue', normalized)
  return normalized
}

function onInput(e: Event): void {
  const input = e.target as HTMLInputElement
  input.value = String(emitValue(Number(input.value)))
}

function onDeadZoneClick(): void {
  if (!hasDeadZone.value || props.disabled || deadValue.value == null) return
  emitValue(deadValue.value)
}
</script>

<style scoped lang="scss">
.ui-slider {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  &--dark {
    --ui-slider-track-background: #{$neutral-700};
    --ui-slider-thumb-border-color: #{$green-500};
    --ui-slider-thumb-background: #{$soft-purple-900};
  }
  &--light {
    --ui-slider-track-background: #{$neutral-200};
    --ui-slider-thumb-border-color: #{$green-600};
    --ui-slider-thumb-background: #{$neutral-white};
  }
}
.ui-slider__input {
  width: 100%;
  min-width: 0;
  margin: 0;
  padding: 0;
}
.ui-slider--filled {
  --ui-slider-track-height: var(--ui-slider-filled-track-height, 10px);
  --ui-slider-thumb-size: var(--ui-slider-filled-thumb-size, 26px);
  --ui-slider-thumb-border: var(--ui-slider-filled-thumb-border, 4px);
  --ui-slider-track-radius: var(--ui-slider-filled-radius, 999px);
  .ui-slider__fill-wrap {
    position: relative;
    width: 100%;
    height: var(--ui-slider-filled-height, var(--ui-slider-thumb-size));
    box-shadow: none;
  }
  .ui-slider__dead-zone {
    position: absolute;
    left: 0;
    top: 50%;
    width: var(--dead);
    height: var(--ui-slider-track-height);
    transform: translateY(-50%);
    border-radius: var(--ui-slider-track-radius);
    z-index: 3;
    pointer-events: auto;
    cursor: pointer;
  }
  &.disabled .ui-slider__dead-zone {
    cursor: default;
    pointer-events: none;
  }
  .ui-slider__fill-track {
    position: absolute;
    left: 0;
    right: 0;
    top: 50%;
    height: var(--ui-slider-track-height);
    transform: translateY(-50%);
    border-radius: var(--ui-slider-track-radius);
    border: none;
    background-color: var(--ui-slider-track-background);
    overflow: hidden;
    pointer-events: none;
  }
  .ui-slider__fill-track::after {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: var(--fill);
    background: linear-gradient(261deg, $soft-purple-800 0%, $green-700 100%);
    border-radius: inherit;
    will-change: width;
  }
  .ui-slider__input--filled {
    position: absolute;
    inset: 0;
    height: 100%;
    background: transparent;
    cursor: pointer;
    z-index: 2;
    -webkit-appearance: none;
    appearance: none;
  }
  .ui-slider__input--filled::-webkit-slider-runnable-track {
    width: 100%;
    height: 100%;
    background: transparent;
    border: none;
  }
  .ui-slider__input--filled::-moz-range-track {
    width: 100%;
    height: 100%;
    background: transparent;
    border: none;
  }
  .ui-slider__input--filled::-moz-range-progress {
    background: transparent;
  }
  .ui-slider__input--filled::-ms-track {
    width: 100%;
    height: 100%;
    background: transparent;
    color: transparent;
    border: none;
  }
  .ui-slider__input--filled::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: var(--ui-slider-thumb-size);
    height: var(--ui-slider-thumb-size);
    border-radius: 50%;
    border: var(--ui-slider-thumb-border) solid var(--ui-slider-thumb-border-color);
    background-color: var(--ui-slider-thumb-background);
    box-sizing: border-box;
    cursor: grab;
  }
  .ui-slider__input--filled::-moz-range-thumb {
    width: var(--ui-slider-thumb-size);
    height: var(--ui-slider-thumb-size);
    border-radius: 50%;
    border: var(--ui-slider-thumb-border) solid var(--ui-slider-thumb-border-color);
    background-color: var(--ui-slider-thumb-background);
    box-sizing: border-box;
    cursor: grab;
  }
  .ui-slider__input--filled:active::-webkit-slider-thumb {
    cursor: grabbing;
  }
  .ui-slider__input--filled:active::-moz-range-thumb {
    cursor: grabbing;
  }
  .ui-slider__input--filled:focus-visible {
    outline: 1px solid inherit;
    outline-offset: 4px;
    border-radius: 999px;
  }
  .ui-slider__input--filled:disabled {
    cursor: not-allowed;
  }
  .ui-slider__input--filled:disabled::-webkit-slider-thumb {
    cursor: not-allowed;
  }
  .ui-slider__input--filled:disabled::-moz-range-thumb {
    cursor: not-allowed;
  }
  &.disabled {
    opacity: 0.65;
  }
}
</style>
