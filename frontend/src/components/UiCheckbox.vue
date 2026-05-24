<template>
  <div class="ui-checkbox" :class="{ 'ui-checkbox--disabled': disabled }">
    <input
      class="ui-checkbox__input"
      type="checkbox"
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
  disabled?: boolean
  required?: boolean
  ariaLabel?: string
}>(), {
  id: '',
  name: '',
  label: '',
  disabled: false,
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
  &__input {
    flex: 0 0 auto;
    width: 20px;
    height: 20px;
    margin: 0;
    accent-color: $green;
    cursor: pointer;
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
  &--disabled {
    .ui-checkbox__input,
    .ui-checkbox__label {
      cursor: not-allowed;
    }
  }
}
</style>
