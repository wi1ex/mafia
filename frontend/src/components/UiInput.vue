<template>
  <div class="ui-input" :class="[rootClass, { filled: isFilled, invalid }]" :style="rootStyle">
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
    <div v-if="showUnderline" class="underline">
      <span :style="underlineStyle"></span>
    </div>
    <div v-if="$slots.meta || meta" class="meta">
      <slot name="meta">
        <span>{{ meta }}</span>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, useAttrs } from 'vue'

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  modelValue: string | number
  modelModifiers?: { trim?: boolean; number?: boolean }
  id: string
  label: string
  type?: string
  as?: 'input' | 'textarea'
  invalid?: boolean
  filled?: boolean
  placeholder?: string
  underlineStyle?: Record<string, string>
  meta?: string
  showUnderline?: boolean
}>(), {
  modelValue: '',
  type: 'text',
  as: 'input',
  invalid: false,
  placeholder: ' ',
  showUnderline: true,
})

const emit = defineEmits<{ (e: 'update:modelValue', value: string | number): void }>()
const attrs = useAttrs()

const inputAttrs = computed(() => {
  const { class: _class, style: _style, ...rest } = attrs
  return rest
})
const rootClass = computed(() => attrs.class)
const rootStyle = computed(() => attrs.style)
const controlTag = computed(() => props.as)

const isFilled = computed(() => {
  if (props.filled !== undefined) return props.filled
  if (typeof props.modelValue === 'number') return Number.isFinite(props.modelValue)
  return String(props.modelValue ?? '').length > 0
})

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
  box-shadow: 3px 3px 5px rgba($black, 0.25);
  input,
  textarea {
    width: calc(100% - 22px);
    padding: 20px 10px 5px;
    border: 1px solid $lead;
    border-radius: 5px 5px 0 0;
    background-color: $graphite;
    color: $fg;
    font-size: 16px;
    font-family: Manrope-Medium;
    line-height: 1;
    outline: none;
    transition: border-color 0.25s ease-in-out, background-color 0.25s ease-in-out;
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
    left: 12px;
    color: $fg;
    transform: translateY(-50%);
    pointer-events: none;
    transition: all 0.25s ease-in-out;
  }
  .underline {
    position: absolute;
    left: 0;
    right: 0;
    bottom: -3px;
    height: 3px;
    border-radius: 0 0 3px 3px;
    overflow: hidden;
    span {
      position: absolute;
      left: 0;
      bottom: 0;
      height: 3px;
      width: 0;
      background-color: $fg;
      transition: width 0.25s ease-in-out;
    }
  }
  .underline::before {
    content: "";
    position: absolute;
    inset: 0;
    background-color: $lead;
    transition: background-color 0.25s ease-in-out;
  }
  .meta {
    position: absolute;
    top: 5px;
    right: 10px;
    pointer-events: none;
    span {
      font-size: 12px;
      color: $grey;
    }
  }
  &.invalid input {
    border-color: rgba($red, 0.75);
  }
  &.invalid label {
    color: $red;
  }
  &.invalid .underline::before {
    background-color: rgba($red, 0.75);
  }
}
.ui-input:focus-within label,
.ui-input input:not(:placeholder-shown) + label,
.ui-input textarea:not(:placeholder-shown) + label,
.ui-input.filled label {
  top: 5px;
  left: 10px;
  transform: none;
  font-size: 12px;
  color: $grey;
}
</style>
