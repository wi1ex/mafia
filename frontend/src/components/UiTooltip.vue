<template>
  <component :is="triggerText ? 'button' : 'span'" class="ui-tooltip" :class="{ 'ui-tooltip--text': triggerText }"
             :style="tooltipStyle" :type="triggerText ? 'button' : undefined" :role="triggerText ? undefined : 'button'"
             :tabindex="triggerText ? undefined : 0" :aria-label="tooltipAriaLabel" :aria-describedby="tooltipId"
             @click.stop.prevent @keydown.enter.stop.prevent @keydown.space.stop.prevent>
    <span v-if="triggerText" class="ui-tooltip__trigger-text">{{ triggerText }}</span>
    <UiIcon v-else class="tooltip-img" :icon="iconInfo" />
    <span :id="tooltipId" class="ui-tooltip__bubble" :class="`ui-tooltip__bubble--${tooltipPlacement}`" role="tooltip">
      <slot>{{ text }}</slot>
    </span>
  </component>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue'

import UiIcon from '@/components/UiIcon.vue'

import iconInfo from '@/assets/svg/iconInfo.svg'

type TooltipPlacement = 'top-right' | 'top-center' | 'top-left' | 'bottom-right' | 'bottom-center' | 'bottom-left'

const props = withDefaults(defineProps<{
  text?: string
  triggerText?: string
  placement?: TooltipPlacement
  ariaLabel?: string
  iconSize?: number | string
  bubbleWidth?: number | string
}>(), {
  text: '',
  placement: 'top-right',
  iconSize: 24,
  bubbleWidth: 450,
})

const tooltipId = useId()
const tooltipStyle = computed<Record<string, string>>(() => ({
  '--ui-tooltip-icon-size': typeof props.iconSize === 'number' ? `${props.iconSize}px` : props.iconSize,
  '--ui-tooltip-bubble-width': typeof props.bubbleWidth === 'number' ? `${props.bubbleWidth}px` : props.bubbleWidth,
}))
const tooltipAriaLabel = computed(() => props.ariaLabel || props.triggerText || 'Подсказка')
const tooltipPlacement = computed<TooltipPlacement>(() => {
  switch (props.placement) {
    case 'top-left':
    case 'top-center':
    case 'bottom-right':
    case 'bottom-center':
    case 'bottom-left':
      return props.placement
    default:
      return 'top-right'
  }
})
</script>

<style scoped lang="scss">
.ui-tooltip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  flex: 0 0 auto;
  width: var(--ui-tooltip-icon-size);
  height: var(--ui-tooltip-icon-size);
  cursor: default;
  outline: none;
  &--text {
    width: auto;
    height: auto;
    padding: 0;
    border: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
    &:focus-visible {
      outline: 2px solid $green-600;
      outline-offset: 3px;
    }
  }
  .tooltip-img {
    --ui-icon-width: var(--ui-tooltip-icon-size);
    --ui-icon-height: var(--ui-tooltip-icon-size);
    --ui-icon-color: #{$neutral-300};
  }
  &:not(:disabled):hover,
  &:not(:disabled):focus-visible,
  &:not(:disabled):active {
    .tooltip-img {
      --ui-icon-color: #{$green-500};
    }
  }
  &__bubble {
    position: absolute;
    width: var(--ui-tooltip-bubble-width);
    padding: 16px;
    border-radius: 20px;
    border: 1px solid $neutral-200;
    background-color: $neutral-100;
    box-shadow: 0 2px 16px rgba($neutral-black, 0.20);
    color: $neutral-900;
    font-family: Hauora-Regular;
    font-size: 16px;
    line-height: 22px;
    letter-spacing: -0.32px;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
    z-index: 20;
    &--top-right {
      left: 0;
      bottom: calc(100% + 4px);
      transform: translateY(5px);
    }
    &--top-left {
      right: 0;
      bottom: calc(100% + 4px);
      transform: translateY(5px);
    }
    &--top-center {
      left: 50%;
      bottom: calc(100% + 4px);
      transform: translate(-50%, 5px);
    }
    &--bottom-right {
      left: 0;
      top: calc(100% + 4px);
      transform: translateY(-5px);
    }
    &--bottom-center {
      left: 50%;
      top: calc(100% + 4px);
      transform: translate(-50%, -5px);
    }
    &--bottom-left {
      right: 0;
      top: calc(100% + 4px);
      transform: translateY(-5px);
    }
  }
  &:not(:disabled):hover,
  &:not(:disabled):focus-visible,
  &:not(:disabled):active,
  &--text:focus {
    .ui-tooltip__bubble {
      opacity: 1;
      transform: translateY(0);
      pointer-events: auto;
    }
    .ui-tooltip__bubble--top-center,
    .ui-tooltip__bubble--bottom-center {
      transform: translate(-50%, 0);
    }
  }
}

</style>
