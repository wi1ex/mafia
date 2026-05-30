<template>
  <div ref="rootEl" class="ui-dropdown" :class="[rootClass, modeClass, sizeClass, placementClass, labelModeClass, { open, invalid, disabled }]" :style="rootStyle">
    <button :id="resolvedId" type="button" @click="toggle" :disabled="disabled" :aria-expanded="open"
            :aria-controls="listId" :aria-label="buttonAriaLabel" aria-haspopup="listbox">
      <span :class="{ placeholder: !selectedLabel }">{{ displayLabel }}</span>
      <UiIcon class="dropdown-icon" :icon="iconArrow" />
    </button>
    <label v-if="label" :for="resolvedId">{{ label }}</label>
    <Transition name="ui-dropdown-menu">
      <ul v-show="open" :id="listId" role="listbox" :data-open="open ? 1 : 0">
        <li v-for="option in options" :key="optionKey(option)" class="option" :class="{ selected: isSelected(option.value), disabled: option.disabled }"
            role="option" :aria-selected="isSelected(option.value)" :aria-disabled="option.disabled || undefined" @click="selectOption(option)">
          <span>{{ option.label }}</span>
        </li>
        <li v-if="options.length === 0" class="empty" aria-disabled="true">{{ emptyText }}</li>
      </ul>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useAttrs, watch, type StyleValue } from 'vue'

import UiIcon from '@/components/UiIcon.vue'

import iconArrow from '@/assets/svg/iconArrow.svg'

defineOptions({ inheritAttrs: false })

type UiDropdownValue = string | number | null

type UiDropdownOption = {
  value: UiDropdownValue
  label: string
  disabled?: boolean
}

let uid = 0

const props = withDefaults(defineProps<{
  modelValue?: UiDropdownValue
  options?: readonly UiDropdownOption[]
  id?: string
  label?: string
  placeholder?: string
  emptyText?: string
  disabled?: boolean
  invalid?: boolean
  mode?: 'light' | 'dark'
  size?: 'default' | 'compact'
  menuPlacement?: 'bottom' | 'top'
  ariaLabel?: string
  labelMode?: 'floating' | 'placeholder'
}>(), {
  modelValue: null,
  options: () => [],
  id: '',
  label: '',
  placeholder: 'Выберите значение',
  emptyText: 'Нет вариантов',
  disabled: false,
  invalid: false,
  mode: 'dark',
  size: 'default',
  menuPlacement: 'bottom',
  ariaLabel: '',
  labelMode: 'floating',
})

const emit = defineEmits<{
  'update:modelValue': [UiDropdownValue]
}>()

const attrs = useAttrs()
const rootEl = ref<HTMLElement | null>(null)
const open = ref(false)
const fallbackId = `ui-dropdown-${++uid}`
const resolvedId = computed(() => props.id || fallbackId)
const listId = computed(() => `${resolvedId.value}-listbox`)
const rootClass = computed(() => attrs.class)
const rootStyle = computed<StyleValue>(() => (attrs.style ?? null) as StyleValue)
const modeClass = computed(() => `ui-dropdown--${props.mode}`)
const sizeClass = computed(() => `ui-dropdown--${props.size}`)
const placementClass = computed(() => `ui-dropdown--${props.menuPlacement}`)
const labelModeClass = computed(() => `ui-dropdown--${props.labelMode}-label`)
const selectedOption = computed(() => props.options.find((option) => isSameValue(option.value, props.modelValue)) ?? null)
const selectedLabel = computed(() => selectedOption.value?.label || '')
const displayLabel = computed(() => selectedLabel.value || props.placeholder)
const buttonAriaLabel = computed(() => props.ariaLabel || props.label || props.placeholder)

function isSameValue(left: UiDropdownValue, right: UiDropdownValue): boolean {
  return left === right
}

function isSelected(value: UiDropdownValue): boolean {
  return isSameValue(value, props.modelValue)
}

function optionKey(option: UiDropdownOption): string {
  return `${String(option.value)}:${option.label}`
}

function toggle(): void {
  if (props.disabled) return
  open.value = !open.value
}

function close(): void {
  open.value = false
}

function selectOption(option: UiDropdownOption): void {
  if (option.disabled) return
  emit('update:modelValue', option.value)
  close()
}

function onDocumentPointerDown(event: PointerEvent): void {
  if (!open.value) return
  const target = event.target as Node | null
  if (target && rootEl.value?.contains(target)) return
  close()
}

function onKeydown(event: KeyboardEvent): void {
  if (!open.value) return
  if (event.key === 'Escape') close()
}

watch(open, (value) => {
  if (value) {
    document.addEventListener('pointerdown', onDocumentPointerDown, { capture: true })
    document.addEventListener('keydown', onKeydown)
  } else {
    document.removeEventListener('pointerdown', onDocumentPointerDown, { capture: true } as AddEventListenerOptions)
    document.removeEventListener('keydown', onKeydown)
  }
})

watch(() => props.disabled, (disabled) => {
  if (disabled) close()
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown, { capture: true } as AddEventListenerOptions)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped lang="scss">
.ui-dropdown {
  position: relative;
  width: 100%;
  --ui-dropdown-border: #{$green-200};
  --ui-dropdown-text: #{$neutral-300};
  --ui-dropdown-placeholder: #{$neutral-700};
  --ui-dropdown-hover-border: #{$green-500};
  --ui-dropdown-hover-text: #{$neutral-100};
  --ui-dropdown-label-bg: var(--ui-dropdown-label-bg-override, #{$neutral-black});
  --ui-dropdown-label-text: #{$neutral-300};
  --ui-dropdown-menu-bg: #{$neutral-900};
  --ui-dropdown-menu-border: #{$neutral-700};
  --ui-dropdown-option-text: #{$neutral-100};
  --ui-dropdown-option-hover-bg: #{$neutral-800};
  --ui-dropdown-option-selected-bg: #{$green-900};
  --ui-dropdown-option-selected-text: #{$neutral-white};
  --ui-dropdown-error-border: #{$red-500};
  --ui-dropdown-disabled-border: #{$neutral-700};
  --ui-dropdown-disabled-text: #{$neutral-500};
  &.ui-dropdown--light {
    --ui-dropdown-border: #{$green-800};
    --ui-dropdown-text: #{$neutral-700};
    --ui-dropdown-placeholder: #{$neutral-700};
    --ui-dropdown-hover-border: #{$green-500};
    --ui-dropdown-hover-text: #{$neutral-900};
    --ui-dropdown-label-bg: var(--ui-dropdown-label-bg-override, #{$neutral-100});
    --ui-dropdown-label-text: #{$neutral-500};
    --ui-dropdown-menu-bg: #{$neutral-600};
    --ui-dropdown-menu-border: #{$neutral-200};
    --ui-dropdown-option-text: #{$neutral-black};
    --ui-dropdown-option-hover-bg: #{$neutral-50};
    --ui-dropdown-option-selected-bg: #{$neutral-50};
    --ui-dropdown-option-selected-text: #{$neutral-900};
    --ui-dropdown-error-border: #{$red-600};
    --ui-dropdown-disabled-border: #{$neutral-300};
    --ui-dropdown-disabled-text: #{$neutral-400};
  }
  button {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    height: 56px;
    padding: 0 32px;
    border: 1px solid var(--ui-dropdown-border);
    border-radius: 999px;
    background-color: transparent;
    color: var(--ui-dropdown-text);
    font-family: Hauora-Regular;
    font-size: 16px;
    line-height: 16px;
    letter-spacing: -0.32px;
    cursor: pointer;
    outline: none;
    transition: border-color 0.25s ease-in-out, color 0.25s ease-in-out;
    span {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      &.placeholder {
        color: var(--ui-dropdown-placeholder);
      }
    }
    .dropdown-icon {
      --ui-icon-width: 24px;
      --ui-icon-height: 24px;
      --ui-icon-color: var(--ui-dropdown-text);
      transition: transform 0.25s ease-in-out, background-color 0.25s ease-in-out;
    }
    &:not(:disabled):hover,
    &:not(:disabled):focus-visible {
      border-color: var(--ui-dropdown-hover-border);
      color: var(--ui-dropdown-hover-text);
      .dropdown-icon {
        --ui-icon-color: var(--ui-dropdown-hover-text);
      }
    }
    &:disabled {
      border-color: var(--ui-dropdown-disabled-border);
      color: var(--ui-dropdown-disabled-text);
      cursor: not-allowed;
      .dropdown-icon {
        --ui-icon-color: var(--ui-dropdown-disabled-text);
      }
    }
  }
  label {
    position: absolute;
    top: -7px;
    left: 29px;
    max-width: calc(100% - 64px);
    padding: 0 4px;
    overflow: hidden;
    background-color: var(--ui-dropdown-label-bg);
    color: var(--ui-dropdown-label-text);
    pointer-events: none;
    font-family: Hauora-Regular;
    font-size: 12px;
    line-height: 12px;
    letter-spacing: -0.24px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  &.ui-dropdown--placeholder-label label {
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
  ul {
    display: flex;
    position: absolute;
    flex-direction: column;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    margin: 0;
    padding: 8px;
    gap: 4px;
    border-radius: 24px;
    border: 1px solid var(--ui-dropdown-menu-border);
    background-color: var(--ui-dropdown-menu-bg);
    box-shadow: 0 2px 16px rgba($neutral-black, 0.20);
    list-style: none;
    z-index: 30;
    &[data-open="0"] {
      pointer-events: none;
    }
    .option,
    .empty {
      display: flex;
      align-items: center;
      padding: 0 16px;
      height: 64px;
      border-radius: 16px;
      color: var(--ui-dropdown-option-text);
      font-family: Hauora-Regular;
      font-size: 18px;
      line-height: 20px;
      letter-spacing: -0.36px;
    }
    .option {
      cursor: pointer;
      transition: background-color 0.25s ease-in-out, color 0.25s ease-in-out;
      span {
        display: block;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      &:hover,
      &:focus-visible {
        background-color: var(--ui-dropdown-option-hover-bg);
      }
      &.selected {
        background-color: var(--ui-dropdown-option-selected-bg);
        color: var(--ui-dropdown-option-selected-text);
      }
      &.disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
    .empty {
      color: var(--ui-dropdown-placeholder);
    }
  }
  &.open {
    button {
      border-color: var(--ui-dropdown-hover-border);
      color: var(--ui-dropdown-hover-text);
      .dropdown-icon {
        --ui-icon-color: var(--ui-dropdown-hover-text);
        transform: rotate(180deg);
      }
    }
  }
  &.invalid {
    button {
      border-color: var(--ui-dropdown-error-border);
    }
  }
  &.ui-dropdown--top {
    ul {
      top: auto;
      bottom: calc(100% + 4px);
      transform-origin: bottom;
    }
  }
  &.ui-dropdown--compact {
    button {
      height: 35px;
      padding: 0 12px;
      border-color: $lead;
      border-radius: 5px;
      background-color: $graphite;
      font-family: Manrope-Medium;
      font-size: 14px;
      line-height: 14px;
      letter-spacing: 0;
      &:not(:disabled):hover,
      &:not(:disabled):focus-visible {
        border-color: $grey;
        background-color: $lead;
      }
    }
    label {
      left: 10px;
      max-width: calc(100% - 24px);
      font-family: Manrope-Medium;
      letter-spacing: 0;
    }
    ul {
      gap: 0;
      top: calc(100% + 4px);
      padding: 0;
      border-color: $lead;
      border-radius: 5px;
      background-color: $graphite;
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      .option,
      .empty {
        padding: 10px;
        border-radius: 0;
        font-family: Manrope-Medium;
        font-size: 14px;
        line-height: 16px;
        letter-spacing: 0;
      }
      .option:hover,
      .option:focus-visible,
      .option.selected {
        background-color: $lead;
        color: $fg;
      }
    }
    &.ui-dropdown--top {
      ul {
        top: auto;
        bottom: calc(100% + 4px);
      }
    }
  }
}

.ui-dropdown-menu-enter-active,
.ui-dropdown-menu-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}

.ui-dropdown-menu-enter-from,
.ui-dropdown-menu-leave-to {
  opacity: 0;
  transform: translateY(-5px);
}

.ui-dropdown--top {
  .ui-dropdown-menu-enter-from,
  .ui-dropdown-menu-leave-to {
    transform: translateY(5px);
  }
}

</style>
