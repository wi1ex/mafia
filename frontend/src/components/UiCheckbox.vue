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
  gap: var(--ui-checkbox-gap, 5px);
  min-width: 0;
}
.ui-checkbox__input {
  flex: 0 0 auto;
  width: var(--ui-checkbox-size, auto);
  height: var(--ui-checkbox-size, auto);
  margin: 0;
  accent-color: var(--ui-checkbox-accent, auto);
  cursor: pointer;
}
.ui-checkbox__label {
  min-width: 0;
  cursor: pointer;
}
.ui-checkbox--disabled .ui-checkbox__input,
.ui-checkbox--disabled .ui-checkbox__label {
  cursor: not-allowed;
}
</style>
