<template>
  <div
    class="triple-switch"
    :class="[
      `triple-switch--${switchTheme}`,
      `triple-switch--${switchSize}`,
      { 'triple-switch--without-text': withoutText, 'triple-switch--disabled': isDisabled },
    ]"
    :style="switchStyle"
  >
    <span v-if="!withoutText" class="triple-switch-label">
      <slot name="label">{{ label }}</slot>
    </span>

    <div
      ref="control"
      class="triple-switch-control"
      role="radiogroup"
      :aria-label="ariaLabel || label || 'Переключатель из трёх состояний'"
      @keydown="onKeydown"
    >
      <span class="triple-switch-indicator" aria-hidden="true" />
      <button
        v-for="(option, index) in options"
        :key="String(option.value)"
        class="triple-switch-option"
        :class="{ 'triple-switch-option--active': index === selectedIndex }"
        type="button"
        role="radio"
        :aria-checked="index === selectedIndex"
        :aria-label="option.ariaLabel || option.label"
        :disabled="isDisabled || option.disabled"
        :data-index="index"
        @click="selectOption(index)"
      >
        {{ option.label }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts" generic="T extends string | number">
import { computed, ref } from 'vue'

type TripleSwitchOption<T> = {
  value: T
  label: string
  ariaLabel?: string
  disabled?: boolean
}
type TripleSwitchOptions<T> = readonly [TripleSwitchOption<T>, TripleSwitchOption<T>, TripleSwitchOption<T>]
type SwitchTheme = 'light' | 'dark'
type SwitchSize = 'high' | 'low'

const SWITCH_WIDTH_BY_SIZE: Record<SwitchSize, number> = {
  high: 480,
  low: 480,
}

const props = defineProps<{
  modelValue: T
  options: TripleSwitchOptions<T>
  label?: string
  ariaLabel?: string
  disabled?: boolean
  width?: number
  theme?: SwitchTheme
  size?: SwitchSize
  withoutText?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: T): void
  (e: 'change', value: T): void
}>()

defineSlots<{
  label?: () => unknown
}>()

const control = ref<HTMLElement | null>(null)
const switchTheme = computed<SwitchTheme>(() => props.theme === 'light' ? 'light' : 'dark')
const switchSize = computed<SwitchSize>(() => props.size === 'low' ? 'low' : 'high')
const widthPx = computed(
  () => `${Number.isFinite(props.width) && props.width ? props.width : SWITCH_WIDTH_BY_SIZE[switchSize.value]}px`,
)
const selectedIndex = computed(() => Math.max(0, props.options.findIndex(option => option.value === props.modelValue)))
const switchStyle = computed<Record<string, string>>(() => ({
  '--triple-switch-width': widthPx.value,
  '--triple-switch-active-index': String(selectedIndex.value),
}))
const withoutText = computed(() => Boolean(props.withoutText))
const isDisabled = computed(() => Boolean(props.disabled))

function selectOption(index: number): void {
  const option = props.options[index]
  if (!option || isDisabled.value || option.disabled || index === selectedIndex.value) return
  emit('update:modelValue', option.value)
  emit('change', option.value)
}

function focusOption(index: number): void {
  const buttons = control.value?.querySelectorAll<HTMLButtonElement>('.triple-switch-option')
  buttons?.[index]?.focus()
}

function findEnabledOption(startIndex: number, direction: 1 | -1): number {
  for (let offset = 1; offset <= props.options.length; offset += 1) {
    const index = (startIndex + direction * offset + props.options.length) % props.options.length
    if (!props.options[index]?.disabled) return index
  }
  return startIndex
}

function onKeydown(event: KeyboardEvent): void {
  if (isDisabled.value) return

  let nextIndex: number | null = null
  if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    nextIndex = findEnabledOption(selectedIndex.value, -1)
  } else if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    nextIndex = findEnabledOption(selectedIndex.value, 1)
  } else if (event.key === 'Home') {
    nextIndex = props.options.findIndex(option => !option.disabled)
  } else if (event.key === 'End') {
    for (let index = props.options.length - 1; index >= 0; index -= 1) {
      if (!props.options[index]?.disabled) {
        nextIndex = index
        break
      }
    }
  } else {
    return
  }

  if (nextIndex === null || nextIndex < 0) return
  event.preventDefault()
  selectOption(nextIndex)
  focusOption(nextIndex)
}
</script>

<style scoped lang="scss">
.triple-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  --triple-switch-width: 480px;
  --triple-switch-height: 56px;
  --triple-switch-border: 4px;
  --triple-switch-radius: 999px;
  --triple-switch-knob-radius: 999px;
  --triple-switch-slider-color: #{$neutral-white};

  &.triple-switch--dark {
    --triple-switch-slider-color: #{$soft-purple-900};
  }

  &.triple-switch--light {
    --triple-switch-slider-color: #{$neutral-white};
  }

  &.triple-switch--low {
    --triple-switch-height: 40px;
    --triple-switch-radius: 12px;
    --triple-switch-knob-radius: 10px;
  }

  &.triple-switch--without-text {
    justify-self: center;
    width: fit-content;
  }

  &.triple-switch--disabled {
    opacity: 0.6;
  }

  .triple-switch-label {
    display: inline-flex;
    align-items: center;
    width: calc(100% - var(--triple-switch-width) - 10px);
    color: $neutral-black;
    font-family: Hauora-Bold;
    font-size: 16px;
    line-height: 18px;
    letter-spacing: -0.32px;
  }

  &.triple-switch--low .triple-switch-label {
    color: $neutral-900;
    font-family: Hauora-Regular;
  }

  &.triple-switch--dark .triple-switch-label {
    color: $neutral-white;
  }

  .triple-switch-control {
    display: flex;
    position: relative;
    box-sizing: border-box;
    width: var(--triple-switch-width);
    height: var(--triple-switch-height);
    overflow: hidden;
    border: var(--triple-switch-border) solid var(--triple-switch-slider-color);
    border-radius: var(--triple-switch-radius);
    background-color: var(--triple-switch-slider-color);
    isolation: isolate;
  }

  .triple-switch-indicator {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    width: calc(100% / 3);
    border-radius: var(--triple-switch-knob-radius);
    background: linear-gradient(261deg, $soft-purple-800 0%, $green-700 100%);
    transform: translateX(calc(var(--triple-switch-active-index) * 100%));
    transition: transform 0.25s ease-in-out;
    pointer-events: none;
    z-index: 0;
  }

  .triple-switch-option {
    flex: 1 1 0;
    min-width: 0;
    border: 0;
    background: transparent;
    color: $neutral-500;
    font-family: Hauora-Regular;
    font-size: 18px;
    line-height: 22px;
    letter-spacing: -0.36px;
    text-overflow: ellipsis;
    white-space: nowrap;
    overflow: hidden;
    cursor: pointer;
    transition: color 0.25s ease-in-out;
    z-index: 1;

    &.triple-switch-option--active {
      color: $neutral-white;
    }

    &:disabled {
      cursor: not-allowed;
    }

    &:focus-visible {
      outline: 2px solid $neutral-black;
      outline-offset: -4px;
    }
  }
}
</style>
