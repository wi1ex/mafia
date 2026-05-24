<template>
  <span class="ui-tooltip" :style="tooltipStyle" role="button" tabindex="0" :aria-label="tooltipAriaLabel" :aria-describedby="tooltipId"
        @click.stop.prevent @keydown.enter.stop.prevent @keydown.space.stop.prevent>
    <UiIcon class="tooltip-img" :icon="iconInfo" />
    <span :id="tooltipId" class="ui-tooltip__bubble" :class="`ui-tooltip__bubble--${tooltipPlacement}`" role="tooltip">
      <slot>{{ text }}</slot>
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue'

import UiIcon from '@/components/UiIcon.vue'

import iconInfo from '@/assets/svg/iconInfo.svg'

type TooltipPlacement = 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left'

const props = withDefaults(defineProps<{
  text?: string
  placement?: TooltipPlacement
  ariaLabel?: string
  iconSize?: number | string
}>(), {
  text: '',
  placement: 'top-right',
  iconSize: 24,
  ariaLabel: 'Подсказка',
})

const tooltipId = useId()
const tooltipStyle = computed<Record<string, string>>(() => ({
  '--ui-tooltip-icon-size': typeof props.iconSize === 'number' ? `${props.iconSize}px` : props.iconSize,
}))
const tooltipAriaLabel = computed(() => props.ariaLabel || 'Подсказка')
const tooltipPlacement = computed<TooltipPlacement>(() => {
  switch (props.placement) {
    case 'top-left':
    case 'bottom-right':
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
  cursor: help;
  outline: none;
  .tooltip-img {
    --ui-icon-width: var(--ui-tooltip-icon-size);
    --ui-icon-height: var(--ui-tooltip-icon-size);
    --ui-icon-color: #{$neutral-300};
  }
  &:hover,
  &:focus-visible,
  &:active {
    .tooltip-img {
      --ui-icon-color: #{$green-500};
    }
  }
  &:focus-visible {
    border-radius: 50%;
    box-shadow: 0 0 0 2px rgba($fg, 0.45);
  }
  &__bubble {
    position: absolute;
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
    pointer-events: none;
    transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
    z-index: 20;
    &--top-right {
      left: 0;
      bottom: calc(100% + 10px);
      transform: translateY(5px);
    }
    &--top-left {
      right: 0;
      bottom: calc(100% + 10px);
      transform: translateY(5px);
    }
    &--bottom-right {
      left: 0;
      top: calc(100% + 10px);
      transform: translateY(-5px);
    }
    &--bottom-left {
      right: 0;
      top: calc(100% + 10px);
      transform: translateY(-5px);
    }
  }
  &:hover,
  &:focus-visible {
    .ui-tooltip__bubble {
      opacity: 1;
      transform: translateY(0);
      pointer-events: auto;
    }
  }
}

</style>
