<template>
  <div class="ui-input" :class="[rootClass, modeClass, { invalid }]" :style="rootStyle">
    <component
      :is="controlTag"
      :id="id"
      :type="controlTag === 'input' ? type : undefined"
      :value="modelValue ?? ''"
      :placeholder="resolvedPlaceholder"
      v-bind="inputAttrs"
      @input="onInput"
    />
    <label :for="id">{{ label }}</label>
    <span v-if="$slots.meta || meta" class="meta">
      <slot name="meta">{{ meta }}</slot>
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed, useAttrs, type StyleValue } from 'vue'

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  modelValue: string | number
  modelModifiers?: { trim?: boolean; number?: boolean }
  id: string
  label: string
  type?: string
  as?: 'input' | 'textarea'
  invalid?: boolean
  placeholder?: string
  meta?: string
  mode?: 'light' | 'dark'
}>(), {
  modelValue: '',
  type: 'text',
  as: 'input',
  invalid: false,
  placeholder: ' ',
  mode: 'dark',
})

const emit = defineEmits<{ (e: 'update:modelValue', value: string | number): void }>()
const attrs = useAttrs()

const inputAttrs = computed(() => {
  const { class: _class, style: _style, ...rest } = attrs
  return rest
})
const rootClass = computed(() => attrs.class)
const rootStyle = computed<StyleValue>(() => (attrs.style ?? null) as StyleValue)
const controlTag = computed(() => props.as)
const modeClass = computed(() => `ui-input--${props.mode}`)
const resolvedPlaceholder = computed(() => props.placeholder ?? ' ')

function onInput(e: Event) {
  const target = e.target as HTMLInputElement | HTMLTextAreaElement
  let value: string | number = target.value
  if (props.modelModifiers?.trim) value = String(value).trim()
  if (props.modelModifiers?.number) {
    const parsed = parseFloat(String(value))
    value = Number.isNaN(parsed) ? value : parsed
  }
  emit('update:modelValue', value as string | number)
}
</script>

<style scoped lang="scss">
.ui-input {
  display: block;
  position: relative;
  width: 100%;
  --ui-input-border: #{$green-200};
  --ui-input-text: #{$neutral-300};
  --ui-input-hover-border: #{$green-500};
  --ui-input-hover-text: #{$neutral-100};
  --ui-input-meta: #{$neutral-300};
  --ui-input-error-border: #{$red-500};
  --ui-input-error-text: #{$neutral-white};
  &.ui-input--light {
    --ui-input-border: #{$green-800};
    --ui-input-text: #{$neutral-700};
    --ui-input-hover-border: #{$green-500};
    --ui-input-hover-text: #{$neutral-900};
    --ui-input-meta: #{$neutral-500};
    --ui-input-error-border: #{$red-600};
    --ui-input-error-text: #{$neutral-black};
  }
  input,
  textarea {
    width: calc(100% - 64px);
    height: 16px;
    padding: 20px 32px 19px;
    border-radius: 999px;
    border: 1px solid var(--ui-input-border);
    background-color: transparent;
    color: var(--ui-input-text);
    font-family: Hauora-Regular;
    font-size: 16px;
    line-height: 16px;
    letter-spacing: -0.32px;
    outline: none;
    transition: border-color 0.25s ease-in-out, color 0.25s ease-in-out;
  }
  &:hover:not(.invalid) input:not(:disabled),
  &:hover:not(.invalid) textarea:not(:disabled),
  &:focus-within:not(.invalid) input,
  &:focus-within:not(.invalid) textarea {
    border-color: var(--ui-input-hover-border);
    color: var(--ui-input-hover-text);
  }
  input::placeholder,
  textarea::placeholder {
    color: transparent;
  }
  textarea {
    resize: none;
    min-height: 80px;
  }
  label {
    position: absolute;
    top: -5px;
    left: 32px;
    padding: 0 4px;
    background-color: $neutral-100;
    color: var(--ui-input-meta);
    transform: none;
    pointer-events: none;
    font-family: Hauora-Regular;
    font-size: 12px;
    line-height: 12px;
    letter-spacing: -0.24px;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.25s ease-in-out, visibility 0.25s ease-in-out, color 0.25s ease-in-out;
  }
  .meta {
    position: absolute;
    top: -5px;
    right: 32px;
    padding: 0 4px;
    background-color: $neutral-100;
    pointer-events: none;
    color: var(--ui-input-meta);
    font-family: Hauora-Regular;
    font-size: 12px;
    line-height: 12px;
    letter-spacing: -0.24px;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.25s ease-in-out, visibility 0.25s ease-in-out, color 0.25s ease-in-out;
  }
  &:focus-within label,
  &:focus-within .meta,
  &.invalid label,
  &.invalid .meta {
    opacity: 1;
    visibility: visible;
  }
  &.invalid input,
  &.invalid textarea {
    border-color: var(--ui-input-error-border);
    color: var(--ui-input-error-text);
  }
}

</style>
