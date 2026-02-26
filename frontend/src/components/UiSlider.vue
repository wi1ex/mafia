<template>
  <div class="ui-slider ui-slider--filled" :class="{ disabled }">
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
}>(), {
  min: 0,
  max: 100,
  step: 1,
  disabled: false,
  ariaLabel: '',
  deadZoneUntil: null,
  deadZoneValue: null,
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

const currentValue = computed(() => clamp(toNum(props.modelValue, minValue.value), minValue.value, maxValue.value))

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

function emitValue(next: number): void {
  emit('update:modelValue', clamp(next, minValue.value, maxValue.value))
}

function onInput(e: Event): void {
  emitValue(Number((e.target as HTMLInputElement).value))
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
}
.ui-slider__input {
  width: 100%;
  min-width: 0;
  margin: 0;
  padding: 0;
}
.ui-slider--filled {
  .ui-slider__fill-wrap {
    position: relative;
    width: 100%;
    height: var(--ui-slider-filled-height, 20px);
    box-shadow: 3px 3px 5px rgba($black, 0.25);
  }
  .ui-slider__dead-zone {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: var(--dead);
    border-radius: var(--ui-slider-filled-radius, 5px);
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
    inset: 0;
    border-radius: var(--ui-slider-filled-radius, 5px);
    border: 1px solid var(--ui-slider-filled-border, $lead);
    background-color: var(--ui-slider-filled-bg, $graphite);
    overflow: hidden;
  }
  .ui-slider__fill-track::after {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: var(--fill);
    background-color: var(--ui-slider-filled-color, $fg);
    border-radius: inherit;
    transition: width 0.25s ease-in-out;
    will-change: width;
  }
  .ui-slider__input--filled {
    position: absolute;
    inset: 0;
    height: 100%;
    background: none;
    cursor: pointer;
    z-index: 2;
    -webkit-appearance: none;
    appearance: none;
  }
  .ui-slider__input--filled::-webkit-slider-runnable-track {
    background: transparent;
    height: 100%;
  }
  .ui-slider__input--filled::-moz-range-track {
    background: transparent;
    height: 100%;
  }
  .ui-slider__input--filled::-ms-track {
    background: transparent;
    color: transparent;
    border: none;
    height: 100%;
  }
  .ui-slider__input--filled::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 1px;
    height: 100%;
    background: transparent;
    border: none;
  }
  .ui-slider__input--filled::-moz-range-thumb {
    width: 1px;
    height: 100%;
    background: transparent;
    border: none;
  }
  .ui-slider__input--filled:focus-visible {
    outline: 2px solid var(--ui-slider-filled-focus, $lead);
    outline-offset: 2px;
  }
  .ui-slider__input--filled:disabled {
    cursor: not-allowed;
  }
}
</style>
