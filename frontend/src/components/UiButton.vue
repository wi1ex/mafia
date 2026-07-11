<template>
  <a v-if="href" v-bind="$attrs" class="ui-button" :class="buttonClasses" :style="buttonStyle" :href="disabled ? undefined : href" :target="target"
     :rel="rel" :aria-disabled="disabled ? 'true' : undefined" :tabindex="disabled ? -1 : undefined" @click.capture="onAnchorClick">
    <UiIcon v-if="showLeftIcon" class="ui-button__icon" :icon="icon" :label="iconLabel" />
    <span v-if="hasText" class="ui-button__text"><slot>{{ text }}</slot></span>
    <UiIcon v-if="showRightIcon" class="ui-button__icon" :icon="icon" :label="iconLabel" />
  </a>
  <button v-else v-bind="$attrs" class="ui-button" :class="buttonClasses" :style="buttonStyle" :type="type" :disabled="disabled">
    <UiIcon v-if="showLeftIcon" class="ui-button__icon" :icon="icon" :label="iconLabel" />
    <span v-if="hasText" class="ui-button__text"><slot>{{ text }}</slot></span>
    <UiIcon v-if="showRightIcon" class="ui-button__icon" :icon="icon" :label="iconLabel" />
  </button>
</template>

<script setup lang="ts">
import { computed, useSlots } from 'vue'
import UiIcon from '@/components/UiIcon.vue'

defineOptions({
  inheritAttrs: false,
})

type ButtonVariant = 'green' | 'white' | 'red'
type ButtonSize = 'big' | 'middle' | 'low'
type IconPosition = 'left' | 'right'
type ButtonType = 'button' | 'submit' | 'reset'

const props = withDefaults(defineProps<{
  variant?: ButtonVariant
  size?: ButtonSize
  text?: string
  icon?: string
  iconPosition?: IconPosition
  iconLabel?: string
  width?: number | string
  disabled?: boolean
  type?: ButtonType
  href?: string
  target?: string
  rel?: string
}>(), {
  variant: 'green',
  size: 'big',
  text: '',
  icon: '',
  iconPosition: 'left',
  iconLabel: '',
  width: undefined,
  disabled: false,
  type: 'button',
  target: undefined,
  rel: undefined,
})

const slots = useSlots()

const hasText = computed(() => Boolean(props.text) || Boolean(slots.default))
const showLeftIcon = computed(() => Boolean(props.icon) && props.iconPosition === 'left')
const showRightIcon = computed(() => Boolean(props.icon) && props.iconPosition === 'right')

const buttonClasses = computed(() => [
  `ui-button--${props.variant}`,
  `ui-button--${props.size}`,
  {
    'ui-button--disabled': props.disabled,
    'ui-button--icon-only': Boolean(props.icon) && !hasText.value,
  },
])

const buttonStyle = computed<Record<string, string>>(() => {
  if (props.width === undefined) return {} as Record<string, string>
  return {
    width: normalizeSize(props.width),
  }
})

function normalizeSize(value: number | string): string {
  if (typeof value === 'number') return `${value}px`
  const trimmed = value.trim()
  return /^\d+(\.\d+)?$/.test(trimmed) ? `${trimmed}px` : trimmed
}

function onAnchorClick(event: MouseEvent) {
  if (!props.disabled) return
  event.preventDefault()
  event.stopImmediatePropagation()
}
</script>

<style scoped lang="scss">
.ui-button {
  display: inline-flex;
  box-sizing: border-box;
  align-items: center;
  justify-content: center;
  gap: var(--ui-button-gap, 8px);
  min-width: 0;
  width: min-content;
  height: var(--ui-button-height);
  padding: 0 var(--ui-button-padding-x, 16px);
  border: none;
  border-radius: var(--ui-button-radius, 999px);
  background-color: var(--ui-button-bg);
  color: var(--ui-button-color);
  font-family: var(--ui-button-font-family, Hauora-Regular);
  font-size: var(--ui-button-font-size, 18px);
  line-height: var(--ui-button-line-height, 22px);
  letter-spacing: var(--ui-button-letter-spacing, -0.36px);
  text-decoration: none;
  white-space: nowrap;
  outline: none;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.25s ease-in-out, color 0.25s ease-in-out, opacity 0.25s ease-in-out;
  &__text {
    display: block;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  &__icon {
    --ui-icon-width: var(--ui-button-icon-size, 24px);
    --ui-icon-height: var(--ui-button-icon-size, 24px);
    --ui-icon-color: currentColor;
  }
  &:not(.ui-button--disabled):hover,
  &:not(.ui-button--disabled):focus-visible,
  &:not(.ui-button--disabled):active {
    background-color: var(--ui-button-hover-bg);
    color: var(--ui-button-hover-color);
  }
  &--disabled {
    background-color: var(--ui-button-disabled-bg);
    color: var(--ui-button-disabled-color);
    cursor: not-allowed;
  }
  &--green {
    --ui-button-bg: #{$green-500};
    --ui-button-color: #{$neutral-900};
    --ui-button-hover-bg: #{$green-300};
    --ui-button-hover-color: #{$neutral-black};
    --ui-button-disabled-bg: #{$neutral-700};
    --ui-button-disabled-color: #{$neutral-300};
  }
  &--white {
    --ui-button-bg: #{$neutral-white};
    --ui-button-color: #{$neutral-black};
    --ui-button-hover-bg: #{$neutral-white};
    --ui-button-hover-color: #{$green-600};
    --ui-button-disabled-bg: #{$neutral-200};
    --ui-button-disabled-color: #{$neutral-600};
  }
  &--red {
    --ui-button-bg: #{$red-400};
    --ui-button-color: #{$neutral-900};
    --ui-button-hover-bg: #{$red-200};
    --ui-button-hover-color: #{$neutral-black};
    --ui-button-disabled-bg: #{$neutral-700};
    --ui-button-disabled-color: #{$neutral-500};
  }
  &--big {
    --ui-button-height: 64px;
    --ui-button-gap: 8px;
    --ui-button-radius: 999px;
    --ui-button-icon-size: 24px;
    --ui-button-font-family: Hauora-Regular;
    --ui-button-font-size: 18px;
    --ui-button-line-height: 22px;
    --ui-button-letter-spacing: -0.36px;
    --ui-button-padding-x: 16px;
  }
  &--middle {
    --ui-button-height: 40px;
    --ui-button-gap: 4px;
    --ui-button-radius: 12px;
    --ui-button-icon-size: 24px;
    --ui-button-font-family: Hauora-Regular;
    --ui-button-font-size: 16px;
    --ui-button-line-height: 20px;
    --ui-button-letter-spacing: -0.32px;
    --ui-button-padding-x: 16px;
  }
  &--low {
    --ui-button-height: 36px;
    --ui-button-gap: 4px;
    --ui-button-radius: 12px;
    --ui-button-icon-size: 20px;
    --ui-button-font-family: Hauora-Regular;
    --ui-button-font-size: 14px;
    --ui-button-line-height: 18px;
    --ui-button-letter-spacing: -0.28px;
    --ui-button-padding-x: 16px;
  }
  &--icon-only {
    width: var(--ui-button-height);
    padding: 0;
  }
}
</style>
