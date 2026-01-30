<template>
  <div class="switch" :style="switchStyle">
    <span class="switch-label">
      <slot name="label">{{ label }}</slot>
    </span>
    <label>
      <input type="checkbox"
             :checked="modelValue"
             :disabled="disabled"
             :aria-label="ariaLabel || label"
             @change="onChange" />
      <div class="slider">
        <span>{{ offLabel }}</span>
        <span>{{ onLabel }}</span>
      </div>
    </label>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValue: boolean
  label?: string
  offLabel?: string
  onLabel?: string
  ariaLabel?: string
  disabled?: boolean
  width?: number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'change', value: boolean): void
}>()

const offLabel = computed(() => props.offLabel ?? 'Откл')
const onLabel = computed(() => props.onLabel ?? 'Вкл')
const widthPx = computed(() => `${Number.isFinite(props.width) && props.width ? props.width : 170}px`)
const switchStyle = computed<Record<string, string>>(() => ({ '--switch-width': widthPx.value }))

function onChange(e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  emit('update:modelValue', checked)
  emit('change', checked)
}
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
    width: calc(100% - var(--switch-width));
    height: 18px;
  }
  label {
    position: relative;
    width: var(--switch-width);
    height: 25px;
    box-shadow: 3px 3px 5px rgba($black, 0.25);
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
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
}
</style>
