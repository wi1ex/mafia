<template>
  <div
    ref="track"
    class="scrollbar"
    :class="[themeClass, { 'scrollbar--visible': visible, 'scrollbar--horizontal': horizontal }]"
    :style="scrollbarStyle"
    aria-hidden="true"
    @pointerdown="onTrackPointerDown"
  >
    <div ref="thumb" class="thumb" :style="thumbStyle" @pointerdown.stop="onThumbPointerDown"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

const DEFAULT_MIN_THUMB_HEIGHT = 60
const DEFAULT_MIN_THUMB_WIDTH = 24
type ScrollbarInset = number | string

const props = withDefaults(defineProps<{
  target?: HTMLElement | null
  active?: boolean
  theme?: 'light' | 'dark' | 'grey'
  orientation?: 'vertical' | 'horizontal'
  minThumbHeight?: number
  minThumbWidth?: number
  overflowTolerance?: number
  insetTop?: ScrollbarInset
  insetBottom?: ScrollbarInset
  right?: ScrollbarInset | null
}>(), {
  active: true,
  theme: 'light',
  orientation: 'vertical',
  minThumbHeight: DEFAULT_MIN_THUMB_HEIGHT,
  minThumbWidth: DEFAULT_MIN_THUMB_WIDTH,
  overflowTolerance: 1,
  insetTop: 0,
  insetBottom: 0,
  right: null,
})

const visible = ref(false)
const thumbOffset = ref(0)
const thumbSize = ref(0)
const track = ref<HTMLElement | null>(null)
const thumb = ref<HTMLElement | null>(null)

let targetEl: HTMLElement | null = null
let ro: ResizeObserver | null = null
let mo: MutationObserver | null = null
let rafId: number | null = null
let onTargetScroll: (() => void) | null = null
let onTargetInput: (() => void) | null = null
let onThumbDragMove: ((e: PointerEvent) => void) | null = null
let onThumbDragEnd: ((e: PointerEvent) => void) | null = null

const horizontal = computed(() => props.orientation === 'horizontal')
const axis = computed(() => horizontal.value ? {
  clientSize: 'clientWidth',
  scrollSize: 'scrollWidth',
  scrollOffset: 'scrollLeft',
  rectSize: 'width',
  rectStart: 'left',
  pointerPosition: 'clientX',
  translate: 'translateX',
} as const : {
  clientSize: 'clientHeight',
  scrollSize: 'scrollHeight',
  scrollOffset: 'scrollTop',
  rectSize: 'height',
  rectStart: 'top',
  pointerPosition: 'clientY',
  translate: 'translateY',
} as const)
const thumbStyle = computed(() => ({
  [axis.value.rectSize]: `${thumbSize.value}px`,
  transform: `${axis.value.translate}(${thumbOffset.value}px)`,
}))
const themeClass = computed(() => `scrollbar--${props.theme}`)
const scrollbarStyle = computed<Record<string, string>>(() => {
  if (horizontal.value) return {}

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
  thumbOffset.value = 0
  thumbSize.value = 0
}

function update() {
  if (!props.active || !targetEl) {
    reset()
    return
  }

  const { clientSize, scrollSize, scrollOffset } = axis.value
  const viewportSize = targetEl[clientSize]
  const contentSize = targetEl[scrollSize]
  const trackSize = track.value?.[clientSize] ?? 0
  if (viewportSize <= 0 || trackSize <= 0 || contentSize <= viewportSize + props.overflowTolerance) {
    reset()
    return
  }

  const minThumbSize = horizontal.value ? props.minThumbWidth : props.minThumbHeight
  const nextThumbSize = Math.min(
    trackSize,
    Math.max(minThumbSize, (viewportSize / contentSize) * trackSize),
  )
  const maxThumbOffset = trackSize - nextThumbSize
  const maxScrollOffset = contentSize - viewportSize

  visible.value = true
  thumbSize.value = nextThumbSize
  thumbOffset.value = maxScrollOffset > 0 ? (targetEl[scrollOffset] / maxScrollOffset) * maxThumbOffset : 0
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
  if (horizontal.value && track.value) ro.observe(track.value)

  mo = new MutationObserver(scheduleUpdate)
  mo.observe(targetEl, { childList: true, subtree: true, characterData: true })

  void nextTick(scheduleUpdate)
}

function scrollToThumbCenter(clientPosition: number, track: HTMLElement) {
  if (!targetEl || !thumb.value) return

  const { clientSize, scrollSize, scrollOffset, rectSize, rectStart } = axis.value
  const trackRect = track.getBoundingClientRect()
  const renderedThumbSize = thumb.value.getBoundingClientRect()[rectSize]
  const maxThumbOffset = trackRect[rectSize] - renderedThumbSize
  const maxScrollOffset = targetEl[scrollSize] - targetEl[clientSize]
  if (maxThumbOffset <= 0 || maxScrollOffset <= 0) return

  const nextThumbOffset = Math.min(
    maxThumbOffset,
    Math.max(0, clientPosition - trackRect[rectStart] - renderedThumbSize / 2),
  )
  targetEl[scrollOffset] = (nextThumbOffset / maxThumbOffset) * maxScrollOffset
  update()
}

function onTrackPointerDown(e: PointerEvent) {
  if (!(e.currentTarget instanceof HTMLElement)) return
  e.preventDefault()
  scrollToThumbCenter(e[axis.value.pointerPosition], e.currentTarget)
}

function onThumbPointerDown(e: PointerEvent) {
  if (!targetEl || !(e.currentTarget instanceof HTMLElement)) return

  e.preventDefault()
  cleanupThumbDrag()

  const track = e.currentTarget.parentElement
  if (!track) return

  const { clientSize, scrollSize, scrollOffset, rectSize, pointerPosition } = axis.value
  const startPosition = e[pointerPosition]
  const startScrollOffset = targetEl[scrollOffset]
  const maxThumbOffset = track.getBoundingClientRect()[rectSize] - e.currentTarget.getBoundingClientRect()[rectSize]
  const maxScrollOffset = targetEl[scrollSize] - targetEl[clientSize]

  onThumbDragMove = (moveEvent: PointerEvent) => {
    if (!targetEl || maxThumbOffset <= 0 || maxScrollOffset <= 0) return
    const delta = moveEvent[pointerPosition] - startPosition
    targetEl[scrollOffset] = startScrollOffset + (delta / maxThumbOffset) * maxScrollOffset
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

watch([() => props.target, () => horizontal.value ? track.value : null], ([el]) => bindTarget(el), {
  immediate: true,
  flush: 'post',
})
watch(() => props.active, (active) => {
  if (!active) cleanupThumbDrag()
  scheduleUpdate()
}, { flush: 'post' })
watch(() => [props.insetTop, props.insetBottom, props.overflowTolerance, horizontal.value ? props.minThumbWidth : null],
  scheduleUpdate, { flush: 'post' })

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
  &--horizontal {
    position: relative;
    top: auto;
    right: auto;
    bottom: auto;
    flex: 0 0 auto;
    width: min(100%, 146px);
    height: 0;
    margin-inline: auto;
    &.scrollbar--visible {
      height: 6px;
    }
    .thumb {
      height: 100%;
    }
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
