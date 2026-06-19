<template>
  <div class="ui-checkbox" :class="`ui-checkbox--${checkboxTheme}`">
    <input
      class="ui-checkbox__input"
      :class="{ 'ui-checkbox__input--radio': radioStyle }"
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
type CheckboxTheme = 'dark' | 'light'

const props = withDefaults(defineProps<{
  modelValue: boolean
  id?: string
  name?: string
  label?: string
  required?: boolean
  ariaLabel?: string
  inputType?: 'checkbox' | 'radio'
  radioStyle?: boolean
  disabled?: boolean
  theme?: CheckboxTheme
}>(), {
  id: '',
  name: '',
  label: '',
  required: false,
  ariaLabel: '',
  inputType: 'checkbox',
  radioStyle: false,
  disabled: false,
  theme: 'dark',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const fallbackId = `ui-checkbox-${++checkboxUid}`
const checkboxId = computed(() => props.id || fallbackId)
const checkboxTheme = computed<CheckboxTheme>(() => props.theme === 'light' ? 'light' : 'dark')

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
  font-family: Hauora-Regular;
  font-size: 14px;
  line-height: 16px;
  letter-spacing: -0.28px;
  transition: color 0.25s ease-in-out;
  --ui-checkbox-color: #{$neutral-500};
  --ui-checkbox-hover-color: #{$neutral-black};
  --ui-checkbox-checked-color: #{$neutral-black};
  --ui-checkbox-border-color: #{$neutral-700};
  --ui-checkbox-hover-border-color: #{$neutral-black};
  &--light {
    --ui-checkbox-color: #{$neutral-300};
    --ui-checkbox-hover-color: #{$neutral-white};
    --ui-checkbox-checked-color: #{$neutral-white};
    --ui-checkbox-border-color: #{$neutral-300};
    --ui-checkbox-hover-border-color: #{$neutral-white};
  }
  color: var(--ui-checkbox-color);
  &__input {
    flex: 0 0 auto;
    width: 20px;
    height: 20px;
    margin: 0;
    border: 1px solid var(--ui-checkbox-border-color);
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
    &--radio {
      position: relative;
      border-radius: 50%;
      &:checked {
        background-color: transparent;
      }
      &:checked::after {
        position: absolute;
        inset: 2px;
        width: auto;
        height: auto;
        margin: 0;
        border: none;
        border-radius: 50%;
        background-color: $green-600;
        transform: none;
      }
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
    color: var(--ui-checkbox-checked-color);
  }
  &:has(.ui-checkbox__input:not(:checked):not(:disabled)):hover {
    color: var(--ui-checkbox-hover-color);
    .ui-checkbox__input {
      border-color: var(--ui-checkbox-hover-border-color);
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
