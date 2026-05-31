<template>
  <div ref="rootEl" class="ui-dropdown" :class="[rootClass, { open, invalid, 'ui-dropdown--selected': selectedOption, 'ui-dropdown--light': mode === 'light', 'ui-dropdown--top': menuPlacement === 'top', 'ui-dropdown--placeholder-label': labelMode === 'placeholder' }]" :style="rootStyle">
    <button :id="resolvedId" type="button" @click="toggle" :aria-expanded="open"
            :aria-controls="listId" :aria-label="buttonAriaLabel" aria-haspopup="listbox">
      <span :class="{ placeholder: !selectedLabel }">{{ displayLabel }}</span>
      <UiIcon class="dropdown-icon" :icon="iconArrow" />
    </button>
    <label v-if="label" :for="resolvedId">{{ label }}</label>
    <Transition name="ui-dropdown-menu">
      <ul v-show="open" :id="listId" role="listbox" :data-open="open ? 1 : 0">
        <li v-for="option in options" :key="optionKey(option)" class="option" :class="{ selected: isSelected(option.value) }"
            role="option" :aria-selected="isSelected(option.value)" @click="selectOption(option)">
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
}

let uid = 0

const props = withDefaults(defineProps<{
  modelValue?: UiDropdownValue
  options?: readonly UiDropdownOption[]
  id?: string
  label?: string
  placeholder?: string
  emptyText?: string
  invalid?: boolean
  mode?: 'light' | 'dark'
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
  invalid: false,
  mode: 'dark',
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
  open.value = !open.value
}

function close(): void {
  open.value = false
}

function selectOption(option: UiDropdownOption): void {
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
  --ui-dropdown-selected-text: #{$neutral-100};
  --ui-dropdown-placeholder: #{$neutral-300};
  --ui-dropdown-icon: #{$neutral-300};
  --ui-dropdown-hover-border: #{$green-500};
  --ui-dropdown-hover-text: #{$neutral-100};
  --ui-dropdown-hover-icon: #{$neutral-white};
  --ui-dropdown-label-bg: var(--ui-dropdown-label-bg-override, #{$neutral-black});
  --ui-dropdown-label-text: #{$neutral-300};
  --ui-dropdown-menu-bg: #{$neutral-black};
  --ui-dropdown-menu-border: #{$neutral-700};
  --ui-dropdown-option-text: #{$neutral-300};
  --ui-dropdown-option-hover-bg: #{$soft-purple-900};
  --ui-dropdown-option-hover-text: #{$neutral-white};
  --ui-dropdown-error-border: #{$red-500};
  --ui-dropdown-error-text: #{$neutral-white};
  &.ui-dropdown--light {
    --ui-dropdown-border: #{$green-800};
    --ui-dropdown-text: #{$neutral-700};
    --ui-dropdown-selected-text: #{$neutral-900};
    --ui-dropdown-placeholder: #{$neutral-700};
    --ui-dropdown-icon: #{$neutral-700};
    --ui-dropdown-hover-border: #{$green-500};
    --ui-dropdown-hover-text: #{$neutral-900};
    --ui-dropdown-hover-icon: #{$neutral-black};
    --ui-dropdown-label-bg: var(--ui-dropdown-label-bg-override, #{$neutral-100});
    --ui-dropdown-label-text: #{$neutral-500};
    --ui-dropdown-menu-bg: #{$neutral-100};
    --ui-dropdown-menu-border: #{$neutral-200};
    --ui-dropdown-option-text: #{$neutral-600};
    --ui-dropdown-option-hover-bg: #{$neutral-50};
    --ui-dropdown-option-hover-text: #{$neutral-black};
    --ui-dropdown-error-border: #{$red-600};
    --ui-dropdown-error-text: #{$neutral-black};
  }
  &.ui-dropdown--selected {
    --ui-dropdown-text: var(--ui-dropdown-selected-text);
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
    line-height: 20px;
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
      --ui-icon-color: var(--ui-dropdown-icon);
      transition: transform 0.25s ease-in-out, background-color 0.25s ease-in-out;
    }
    &:hover,
    &:focus-visible {
      border-color: var(--ui-dropdown-hover-border);
      color: var(--ui-dropdown-hover-text);
      span.placeholder {
        color: var(--ui-dropdown-hover-text);
      }
      .dropdown-icon {
        --ui-icon-color: var(--ui-dropdown-hover-icon);
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
    right: -2px;
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
      line-height: 22px;
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
      &.selected {
        background-color: var(--ui-dropdown-option-hover-bg);
        color: var(--ui-dropdown-option-hover-text);
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
      span.placeholder {
        color: var(--ui-dropdown-hover-text);
      }
      .dropdown-icon {
        --ui-icon-color: var(--ui-dropdown-hover-icon);
        transform: rotate(180deg);
      }
    }
  }
  &.invalid {
    button {
      border-color: var(--ui-dropdown-error-border);
      color: var(--ui-dropdown-error-text);
      span.placeholder {
        color: var(--ui-dropdown-error-text);
      }
      .dropdown-icon {
        --ui-icon-color: var(--ui-dropdown-error-text);
      }
    }
  }
  &.ui-dropdown--top {
    ul {
      top: auto;
      bottom: calc(100% + 4px);
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
