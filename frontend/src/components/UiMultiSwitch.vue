<template>
  <div class="switch" :class="[`switch--${size}`, { 'switch--disabled': disabled }]" :style="switchStyle" role="group">
    <div class="slider">
      <span v-if="selectedIndex >= 0" class="slider-knob" aria-hidden="true"></span>
      <button
        v-for="option in options"
        :key="option.id"
        class="slider-option"
        type="button"
        :aria-pressed="option.id === modelValue"
        :disabled="disabled"
        @click="select(option.id)"
      >
        <UiIcon
          v-if="option.icon && (!activeIconOnly || option.id === modelValue)"
          class="slider-option-icon"
          :class="{ 'slider-option-icon--brand': option.colorIcon }"
          :icon="option.icon"
        />
        <span>{{ option.label }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts" generic="OptionId extends string">
import { computed } from 'vue'
import UiIcon from '@/components/UiIcon.vue'

const props = withDefaults(defineProps<{
  modelValue: OptionId
  options: readonly { id: OptionId; label: string; icon?: string; colorIcon?: boolean }[]
  size?: 'big' | 'low'
  disabled?: boolean
  activeIconOnly?: boolean
}>(), {
  size: 'big',
})

const emit = defineEmits<{ 'update:modelValue': [OptionId] }>()
const selectedIndex = computed(() => props.options.findIndex(option => option.id === props.modelValue))
const switchStyle = computed(() => ({
  '--switch-count': Math.max(1, props.options.length),
  '--switch-index': selectedIndex.value,
}))

function select(id: OptionId): void {
  if (id !== props.modelValue) emit('update:modelValue', id)
}
</script>

<style scoped lang="scss">
.switch {
  --switch-height: 56px;
  --switch-border: 4px;
  --switch-radius: 999px;
  --switch-knob-radius: 999px;
  width: 100%;
  box-sizing: border-box;
  border: var(--switch-border) solid $neutral-white;
  border-radius: var(--switch-radius);
  background-color: $neutral-white;
  &--low {
    --switch-height: 40px;
    --switch-radius: 12px;
    --switch-knob-radius: 10px;
  }
  &--disabled {
    opacity: 0.6;
  }
  .slider {
    display: grid;
    grid-template-columns: repeat(var(--switch-count), minmax(0, 1fr));
    position: relative;
    min-height: calc(var(--switch-height) - 2 * var(--switch-border));
    .slider-knob {
      position: absolute;
      inset: 0 auto 0 0;
      width: calc(100% / var(--switch-count));
      border-radius: var(--switch-knob-radius);
      background: linear-gradient(261deg, $soft-purple-800 0%, $green-700 100%);
      transform: translateX(calc(100% * var(--switch-index)));
      transition: transform 0.25s ease-in-out;
      pointer-events: none;
    }
    .slider-option {
      display: flex;
      position: relative;
      flex-wrap: wrap;
      align-items: center;
      align-content: center;
      justify-content: center;
      gap: 5px;
      min-width: 0;
      padding: 4px 6px;
      border: 0;
      border-radius: var(--switch-knob-radius);
      background: transparent;
      color: $neutral-500;
      font-family: Hauora-Regular;
      font-size: 18px;
      line-height: 22px;
      letter-spacing: -0.36px;
      text-align: center;
      overflow-wrap: anywhere;
      cursor: pointer;
      transition: color 0.25s ease-in-out;
      &[aria-pressed="true"] {
        color: $neutral-white;
      }
      &:focus-visible {
        outline: 2px solid $green-500;
        outline-offset: -3px;
      }
      &:disabled {
        cursor: default;
      }
      .slider-option-icon {
        --ui-icon-width: 20px;
        --ui-icon-height: 20px;
        &--brand {
          background: var(--ui-icon-url) center / contain no-repeat;
          -webkit-mask: none;
          mask: none;
        }
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .slider-knob,
      .slider-option {
        transition: none;
      }
    }
  }
}
</style>
