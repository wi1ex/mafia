<template>
  <div
    ref="track"
    class="scrollbar"
    :class="[themeClass, { 'scrollbar--visible': visible }]"
    :style="scrollbarStyle"
    aria-hidden="true"
    @pointerdown="onTrackPointerDown"
  >
    <div class="thumb" :style="thumbStyle" @pointerdown.stop="onThumbPointerDown"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

const DEFAULT_MIN_THUMB_HEIGHT = 60
type ScrollbarInset = number | string

const props = withDefaults(defineProps<{
  target?: HTMLElement | null
  active?: boolean
  theme?: 'light' | 'dark' | 'grey'
  minThumbHeight?: number
  overflowTolerance?: number
  insetTop?: ScrollbarInset
  insetBottom?: ScrollbarInset
  right?: ScrollbarInset | null
}>(), {
  active: true,
  theme: 'light',
  minThumbHeight: DEFAULT_MIN_THUMB_HEIGHT,
  overflowTolerance: 1,
  insetTop: 0,
  insetBottom: 0,
  right: null,
})

const visible = ref(false)
const thumbTop = ref(0)
const thumbHeight = ref(0)
const track = ref<HTMLElement | null>(null)

let targetEl: HTMLElement | null = null
let ro: ResizeObserver | null = null
let mo: MutationObserver | null = null
let rafId: number | null = null
let onTargetScroll: (() => void) | null = null
let onTargetInput: (() => void) | null = null
let onThumbDragMove: ((e: PointerEvent) => void) | null = null
let onThumbDragEnd: ((e: PointerEvent) => void) | null = null

const thumbStyle = computed(() => ({
  height: `${thumbHeight.value}px`,
  transform: `translateY(${thumbTop.value}px)`,
}))
const themeClass = computed(() => `scrollbar--${props.theme}`)
const scrollbarStyle = computed<Record<string, string>>(() => {
  const style: Record<string, string> = {
    top: toCssSize(props.insetTop),
    bottom: toCssSize(props.insetBottom),
  }
  if (props.right !== null && props.right !== '') {
    style.right = toCssSize(props.right)
  }
  return style
})

function toCssSize(value: ScrollbarInset): string {
  return typeof value === 'number' ? `${value}px` : value
}

function reset() {
  visible.value = false
  thumbTop.value = 0
  thumbHeight.value = 0
}

function update() {
  if (!props.active || !targetEl) {
    reset()
    return
  }

  const { clientHeight, scrollHeight, scrollTop } = targetEl
  const trackHeight = track.value?.clientHeight ?? 0
  if (clientHeight <= 0 || trackHeight <= 0 || scrollHeight <= clientHeight + props.overflowTolerance) {
    reset()
    return
  }

  const nextThumbHeight = Math.min(
    trackHeight,
    Math.max(props.minThumbHeight, (clientHeight / scrollHeight) * trackHeight),
  )
  const maxThumbTop = trackHeight - nextThumbHeight
  const maxScrollTop = scrollHeight - clientHeight

  visible.value = true
  thumbHeight.value = nextThumbHeight
  thumbTop.value = maxScrollTop > 0 ? (scrollTop / maxScrollTop) * maxThumbTop : 0
}

function scheduleUpdate() {
  if (rafId !== null) return
  rafId = window.requestAnimationFrame(() => {
    rafId = null
    update()
  })
}

function cleanupTarget() {
  cleanupThumbDrag()
  if (targetEl && onTargetScroll) targetEl.removeEventListener('scroll', onTargetScroll)
  if (targetEl && onTargetInput) targetEl.removeEventListener('input', onTargetInput)
  try { ro?.disconnect() } catch {}
  try { mo?.disconnect() } catch {}

  targetEl = null
  ro = null
  mo = null
  onTargetScroll = null
  onTargetInput = null
  reset()
}

function bindTarget(el?: HTMLElement | null) {
  cleanupTarget()
  if (!el) return

  targetEl = el
  onTargetScroll = scheduleUpdate
  onTargetInput = scheduleUpdate
  targetEl.addEventListener('scroll', onTargetScroll, { passive: true })
  targetEl.addEventListener('input', onTargetInput)

  ro = new ResizeObserver(scheduleUpdate)
  ro.observe(targetEl)

  mo = new MutationObserver(scheduleUpdate)
  mo.observe(targetEl, { childList: true, subtree: true, characterData: true })

  void nextTick(scheduleUpdate)
}

function scrollToThumbCenter(clientY: number, track: HTMLElement) {
  if (!targetEl) return

  const trackRect = track.getBoundingClientRect()
  const maxThumbTop = trackRect.height - thumbHeight.value
  const maxScrollTop = targetEl.scrollHeight - targetEl.clientHeight
  if (maxThumbTop <= 0 || maxScrollTop <= 0) return

  const nextThumbTop = Math.min(
    maxThumbTop,
    Math.max(0, clientY - trackRect.top - thumbHeight.value / 2),
  )
  targetEl.scrollTop = (nextThumbTop / maxThumbTop) * maxScrollTop
  update()
}

function onTrackPointerDown(e: PointerEvent) {
  if (!(e.currentTarget instanceof HTMLElement)) return
  e.preventDefault()
  scrollToThumbCenter(e.clientY, e.currentTarget)
}

function onThumbPointerDown(e: PointerEvent) {
  if (!targetEl || !(e.currentTarget instanceof HTMLElement)) return

  e.preventDefault()
  cleanupThumbDrag()

  const track = e.currentTarget.parentElement
  if (!track) return

  const startY = e.clientY
  const startScrollTop = targetEl.scrollTop
  const maxThumbTop = track.clientHeight - thumbHeight.value
  const maxScrollTop = targetEl.scrollHeight - targetEl.clientHeight

  onThumbDragMove = (moveEvent: PointerEvent) => {
    if (!targetEl || maxThumbTop <= 0 || maxScrollTop <= 0) return
    const deltaY = moveEvent.clientY - startY
    targetEl.scrollTop = startScrollTop + (deltaY / maxThumbTop) * maxScrollTop
    update()
  }
  onThumbDragEnd = () => cleanupThumbDrag()

  document.addEventListener('pointermove', onThumbDragMove)
  document.addEventListener('pointerup', onThumbDragEnd)
  document.addEventListener('pointercancel', onThumbDragEnd)
}

function cleanupThumbDrag() {
  if (onThumbDragMove) document.removeEventListener('pointermove', onThumbDragMove)
  if (onThumbDragEnd) {
    document.removeEventListener('pointerup', onThumbDragEnd)
    document.removeEventListener('pointercancel', onThumbDragEnd)
  }
  onThumbDragMove = null
  onThumbDragEnd = null
}

watch(() => props.target, bindTarget, { immediate: true, flush: 'post' })
watch(() => props.active, (active) => {
  if (!active) cleanupThumbDrag()
  scheduleUpdate()
}, { flush: 'post' })
watch(() => [props.insetTop, props.insetBottom, props.overflowTolerance], scheduleUpdate, { flush: 'post' })

onBeforeUnmount(() => {
  cleanupTarget()
  if (rafId !== null) window.cancelAnimationFrame(rafId)
})
</script>

<style scoped lang="scss">
.scrollbar {
  position: absolute;
  top: 0;
  right: -8px;
  bottom: 0;
  z-index: 1;
  width: 6px;
  border-radius: 999px;
  background-color: $neutral-white;
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  touch-action: none;
  &--visible {
    opacity: 1;
    pointer-events: auto;
  }
  &--dark {
    right: 0;
    background-color: $neutral-500;
    .thumb {
      background-color: $neutral-white;
    }
  }
  &--grey {
    background-color: $neutral-100;
  }
}
.thumb {
  position: absolute;
  top: 0;
  left: 0;
  box-sizing: border-box;
  width: 100%;
  border-radius: 999px;
  background-color: $neutral-500;
  background-clip: content-box;
  cursor: grab;
  will-change: transform;
  &:active {
    cursor: grabbing;
  }
}
</style>
