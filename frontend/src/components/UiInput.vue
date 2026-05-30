<template>
  <div class="ui-input" :class="[rootClass, modeClass, labelModeClass, { invalid }]" :style="rootStyle">
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
  labelMode?: 'floating' | 'placeholder'
}>(), {
  modelValue: '',
  type: 'text',
  as: 'input',
  invalid: false,
  mode: 'dark',
  labelMode: 'floating',
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
const labelModeClass = computed(() => `ui-input--${props.labelMode}-label`)
const resolvedPlaceholder = computed(() => props.placeholder ?? (props.labelMode === 'placeholder' ? props.label : ' '))

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
  --ui-input-default-label-bg: #{$neutral-black};
  --ui-input-resolved-label-bg: var(--ui-input-label-bg, var(--ui-input-default-label-bg));
  &.ui-input--light {
    --ui-input-border: #{$green-800};
    --ui-input-text: #{$neutral-700};
    --ui-input-hover-border: #{$green-500};
    --ui-input-hover-text: #{$neutral-900};
    --ui-input-meta: #{$neutral-500};
    --ui-input-error-border: #{$red-600};
    --ui-input-error-text: #{$neutral-black};
    --ui-input-default-label-bg: #{$neutral-100};
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
    top: 50%;
    left: 29px;
    max-width: calc(100% - 64px);
    padding: 0;
    overflow: hidden;
    background-color: transparent;
    color: var(--ui-input-text);
    transform: translateY(-50%);
    pointer-events: none;
    font-family: Hauora-Regular;
    font-size: 16px;
    line-height: 16px;
    letter-spacing: -0.32px;
    text-overflow: ellipsis;
    white-space: nowrap;
    transition: top 0.25s ease-in-out, padding 0.25s ease-in-out, background-color 0.25s ease-in-out,
      color 0.25s ease-in-out, transform 0.25s ease-in-out, font-size 0.25s ease-in-out,
      line-height 0.25s ease-in-out, letter-spacing 0.25s ease-in-out;
  }
  .meta {
    position: absolute;
    top: -7px;
    right: 29px;
    padding: 0 4px;
    background-color: var(--ui-input-resolved-label-bg);
    pointer-events: none;
    color: var(--ui-input-meta);
    font-family: Hauora-Regular;
    font-size: 12px;
    line-height: 14px;
    letter-spacing: -0.24px;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.25s ease-in-out, visibility 0.25s ease-in-out, color 0.25s ease-in-out;
  }
  &:hover:not(.invalid) input:placeholder-shown + label,
  &:hover:not(.invalid) textarea:placeholder-shown + label {
    color: var(--ui-input-hover-text);
  }
  &:focus-within label,
  input:not(:placeholder-shown) + label,
  textarea:not(:placeholder-shown) + label,
  &.invalid label {
    top: -7px;
    padding: 0 4px;
    background-color: var(--ui-input-resolved-label-bg);
    color: var(--ui-input-meta);
    transform: none;
    font-size: 12px;
    line-height: 14px;
    letter-spacing: -0.24px;
  }
  &:focus-within .meta,
  &.invalid .meta {
    opacity: 1;
    visibility: visible;
  }
  &.invalid input,
  &.invalid textarea {
    border-color: var(--ui-input-error-border);
    color: var(--ui-input-error-text);
  }
  &.ui-input--placeholder-label {
    input::placeholder,
    textarea::placeholder {
      color: var(--ui-input-text);
      opacity: 1;
      transition: color 0.25s ease-in-out, opacity 0.25s ease-in-out;
    }
    &:hover:not(.invalid) textarea:not(:disabled)::placeholder {
      color: var(--ui-input-hover-text);
    }
    input:focus::placeholder,
    textarea:focus::placeholder {
      opacity: 0;
    }
    label {
      top: auto;
      left: auto;
      width: 1px;
      height: 1px;
      padding: 0;
      overflow: hidden;
      clip: rect(0 0 0 0);
      clip-path: inset(50%);
      background-color: transparent;
      white-space: nowrap;
    }
  }
}

</style>
