<template>
  <div class="ui-checkbox">
    <input
      class="ui-checkbox__input"
      :type="inputType"
      :id="checkboxId"
      :name="name || undefined"
      :checked="modelValue"
      :disabled="disabled"
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
  inputType?: 'checkbox' | 'radio'
  disabled?: boolean
}>(), {
  id: '',
  name: '',
  label: '',
  required: false,
  ariaLabel: '',
  inputType: 'checkbox',
  disabled: false,
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
  gap: 8px;
  min-width: 0;
  color: $neutral-500;
  font-family: Hauora-Regular;
  font-size: 14px;
  line-height: 14px;
  letter-spacing: -0.28px;
  transition: color 0.25s ease-in-out;
  &__input {
    flex: 0 0 auto;
    width: 20px;
    height: 20px;
    margin: 0;
    border: 1px solid $neutral-700;
    border-radius: 4px;
    background-color: transparent;
    cursor: pointer;
    appearance: none;
    -webkit-appearance: none;
    transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out;
    &:checked {
      border-color: $green-600;
      background-color: $green-100;
    }
    &:checked::after {
      content: "";
      display: block;
      margin: auto;
      width: 7px;
      height: 11px;
      border-radius: 0 0 3px;
      border: solid $green-600;
      border-width: 0 1.75px 1.75px 0;
      transform: rotate(40deg);
    }
    &:focus-visible {
      outline: 1px solid $neutral-black;
      outline-offset: 1px;
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
  &:has(.ui-checkbox__input:checked) {
    color: $neutral-black;
  }
  &:has(.ui-checkbox__input:not(:checked):not(:disabled)):hover {
    color: $neutral-black;
    .ui-checkbox__input {
      border-color: $neutral-black;
    }
  }
  &:has(.ui-checkbox__input:disabled) {
    .ui-checkbox__input,
    .ui-checkbox__label {
      cursor: not-allowed;
    }
  }
}

</style>
