<template>
  <div class="ui-select" :class="{ open }" ref="root" role="combobox" :aria-expanded="String(open)" :aria-controls="listId" aria-haspopup="listbox" >
    <button type="button" @click="toggle" @keydown="onTriggerKeydown" :aria-label="ariaLabel" >
      <span>{{ currentLabel || placeholder }}</span>
      <img :src="open ? iconArrowUp : iconArrowDown" alt="arrow" />
    </button>

    <ul v-show="open" :id="listId" role="listbox" :aria-activedescendant="activeId" ref="menu" @keydown="onMenuKeydown" tabindex="-1" >
      <li v-for="(it, i) in items" :key="it.deviceId" class="option" :id="optId(i)" role="option" :aria-selected="String(it.deviceId === modelValue)"
          :class="{ active: i === activeIndex, selected: it.deviceId === modelValue }" @click="select(it.deviceId)" @mouseenter="activeIndex = i">
        <span>{{ it.label || fallback }}</span>
        <img v-if="it.deviceId === modelValue" :src="iconReady" alt="ready" />
      </li>
      <li v-if="items.length === 0" class="empty" aria-disabled="true">Нет устройств</li>
    </ul>
  </div>
  </template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import iconArrowDown from '@/assets/svg/arrow_down.svg'
import iconArrowUp from '@/assets/svg/arrow_up.svg'
import iconReady from '@/assets/svg/ready.svg'

type Dev = {
  deviceId: string
  label: string
}

const props = defineProps<{
  modelValue: string
  items: Dev[]
  placeholder?: string
  fallback?: string
  ariaLabel?: string
}>()
const emit = defineEmits<{ 'update:modelValue': [string], change: [string] }>()

const open = ref(false)
const root = ref<HTMLElement|null>(null)
const menu = ref<HTMLElement|null>(null)
const listId = `ls-${Math.random().toString(36).slice(2)}`
const activeIndex = ref(0)

const placeholder = computed(() => props.placeholder ?? 'Выбрать…')
const fallback = computed(() => props.fallback ?? 'Устройство')
const currentLabel = computed(() => props.items.find(i => i.deviceId === props.modelValue)?.label || '')
const activeId = computed(() => props.items[activeIndex.value] ? optId(activeIndex.value) : undefined)

function optId(i: number) { return `${listId}-opt-${i}` }

function toggle() {
  open.value = !open.value
  if (open.value) focusMenu()
}

function focusMenu() {
  activeIndex.value = Math.max(0, props.items.findIndex(i => i.deviceId === props.modelValue))
  requestAnimationFrame(() => menu.value?.focus())
}

function close() { open.value = false }

function select(id: string) {
  emit('update:modelValue', id)
  emit('change', id)
  close()
}

function onTriggerKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    if (!open.value) toggle()
    else focusMenu()
  }
}

function onMenuKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    close()
    return
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(props.items.length - 1, activeIndex.value + 1)
    scrollActiveIntoView()
    return
  }
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(0, activeIndex.value - 1)
    scrollActiveIntoView()
    return
  }
  if (e.key === 'Enter') {
    e.preventDefault()
    const it = props.items[activeIndex.value]
    if (it) select(it.deviceId)
  }
}

function scrollActiveIntoView() {
  const el = document.getElementById(optId(activeIndex.value))
  el?.scrollIntoView({ block: 'nearest' })
}

function onDocPointerDown(ev: PointerEvent) {
  const t = ev.target as Node
  if (!root.value?.contains(t)) close()
}

onMounted(() => document.addEventListener('pointerdown', onDocPointerDown, { capture: true }))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocPointerDown, { capture: true } as any))
</script>

<style scoped lang="scss">
.ui-select {
  position: relative;
  width: 100%;
  button {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    height: 30px;
    border: 1px solid $lead;
    border-radius: 5px;
    background-color: $dark;
    padding: 0 10px;
    cursor: pointer;
    span {
      color: $fg;
      font-size: 14px;
      font-family: Manrope-Medium;
      line-height: 1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    img {
      width: 15px;
      height: 15px;
    }
  }
}
ul {
  position: absolute;
  z-index: 30;
  bottom: 0;
  margin: 0;
  padding: 0;
  width: calc(100% - 2px);
  max-height: 160px;
  border: 1px solid $lead;
  border-radius: 5px;
  background-color: $graphite;
  outline: none;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: $grey transparent;
  .option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px;
    cursor: pointer;
    transition: background-color 0.25s ease-in-out;
    span {
      font-size: 14px;
      color: $fg;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    img {
      width: 15px;
      height: 15px;
    }
  }
  .option.active {
    background-color: $graphite;
  }
  .option.selected {
    background-color: $lead;
  }
  .option.active.selected {
    background-color: $lead;
  }
  .empty {
    padding: 10px;
    color: $grey;
    font-size: 14px;
  }
}
</style>
