<template>
  <div class="ui-checkbox">
    <input
      class="ui-checkbox__input"
      type="checkbox"
      :id="checkboxId"
      :name="name || undefined"
      :checked="modelValue"
      :required="required"
      :aria-label="ariaLabel || undefined"
      @change="onChange"
    />
    <label class="ui-checkbox__label" :for="checkboxId">
      <slot>{{ label }}</slot>
    </label>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

let checkboxUid = 0

const props = withDefaults(defineProps<{
  modelValue: boolean
  id?: string
  name?: string
  label?: string
  required?: boolean
  ariaLabel?: string
}>(), {
  id: '',
  name: '',
  label: '',
  required: false,
  ariaLabel: '',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const fallbackId = `ui-checkbox-${++checkboxUid}`
const checkboxId = computed(() => props.id || fallbackId)

function onChange(e: Event): void {
  emit('update:modelValue', Boolean((e.target as HTMLInputElement).checked))
}
</script>

<style scoped lang="scss">
.ui-checkbox {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
  min-width: 0;
  color: $fg;
  font-family: Hauora-Regular;
  font-size: 16px;
  line-height: 1.25;
  transition: color 0.25s ease-in-out;
  &__input {
    flex: 0 0 auto;
    width: 20px;
    height: 20px;
    margin: 0;
    border: 2px solid $neutral-500;
    border-radius: 4px;
    background-color: transparent;
    cursor: pointer;
    appearance: none;
    -webkit-appearance: none;
    transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out;
    &:checked {
      border-color: $green-500;
      background-color: $green-500;
    }
    &:checked::after {
      content: '';
      display: block;
      width: 5px;
      height: 10px;
      margin: 1px auto 0;
      border: solid $neutral-white;
      border-width: 0 2px 2px 0;
      transform: rotate(45deg);
    }
    &:focus-visible {
      outline: 2px solid rgba($green-500, 0.45);
      outline-offset: 2px;
    }
  }
  &__label {
    display: inline-flex;
    flex: 1 1 0;
    flex-wrap: wrap;
    align-items: center;
    gap: 3px;
    min-width: 0;
    cursor: pointer;
    :deep(a) {
      color: currentColor;
      text-decoration: underline;
    }
  }
  &:hover {
    color: $green-500;
    .ui-checkbox__input {
      border-color: $green-500;
    }
  }
}
</style>
