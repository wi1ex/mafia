<template>
  <span
    v-if="breakdown"
    ref="trigger"
    class="points-metric points-metric--explainable"
    :class="{ 'points-metric--open': open }"
    tabindex="0"
    :aria-describedby="panelId"
    @pointerenter="preview"
    @pointerleave="scheduleClose"
    @focus="previewFocus"
    @blur="onBlur"
  >
    <span>Баллы:</span>
    <strong :class="pointsTone(points)">{{ formatPoints(points) }}</strong>
    <UiIcon class="points-metric__icon" :icon="iconInfo" />
  </span>
  <span v-else class="points-metric">Баллы: {{ formatPoints(points) }}</span>

  <Teleport to="#desktop-teleport-root">
    <Transition name="points-panel">
      <section
        v-if="open && breakdown"
        :id="panelId"
        ref="panel"
        class="points-tooltip"
        :style="panelStyle"
        role="tooltip"
        :aria-labelledby="titleId"
        @pointerenter="enterPanel"
        @pointerleave="scheduleClose"
      >
        <header class="points-tooltip__header">
          <div>
            <span class="points-tooltip__eyebrow">{{ playerName || 'Рейтинговая игра' }}</span>
            <h3 :id="titleId">Расчёт баллов</h3>
          </div>
        </header>

        <div class="points-tooltip__base">
          <div class="points-tooltip__base-label">
            <span class="points-tooltip__step" aria-hidden="true">1</span>
            <div>
              <span class="points-tooltip__label">За результат игры</span>
              <span class="points-tooltip__reason" :class="`points-tooltip__reason--${breakdown.base_reason}`">{{ baseReason }}</span>
            </div>
          </div>
          <strong class="points-tooltip__value" :class="pointsTone(breakdown.base_points)">{{ formatPoints(breakdown.base_points) }}</strong>
        </div>

        <div class="points-tooltip__adjustments">
          <div class="points-tooltip__section-heading">
            <span class="points-tooltip__step" aria-hidden="true">2</span>
            <h4>Бонусы и штрафы</h4>
            <span v-if="breakdown.rules_available && eventCount" class="points-tooltip__count">{{ eventCount }}</span>
          </div>

          <template v-if="breakdown.rules_available">
            <ul v-if="adjustments.length" class="points-tooltip__list">
              <li v-for="adjustment in adjustments" :key="adjustment.key" class="points-tooltip__adjustment">
                <div class="points-tooltip__adjustment-label">
                  <span>{{ adjustment.label }}</span>
                </div>
                <strong class="points-tooltip__value points-tooltip__adjustment-value" :class="pointsTone(adjustment.points)">
                  {{ formatPoints(adjustment.points) }}
                  <template v-if="adjustment.count > 1">
                    <span class="points-tooltip__multiply">×</span>
                    <span class="points-tooltip__multiplicity">{{ adjustment.count }}</span>
                  </template>
                </strong>
              </li>
            </ul>
            <p v-else class="points-tooltip__empty">В этой игре нет бонусов и штрафов.</p>

            <div class="points-tooltip__subtotal">
              <span>Сумма за действия</span>
              <strong class="points-tooltip__value" :class="pointsTone(breakdown.additional_points_raw)">{{ formatPoints(breakdown.additional_points_raw) }}</strong>
            </div>

            <div v-if="breakdown.additional_points_capped" class="points-tooltip__limit">
              <div class="points-tooltip__limit-heading">
                <UiIcon :icon="iconInfo" />
                <span>Применён лимит</span>
              </div>
              <p>Лимит действует только на бонусы и штрафы<span v-if="limitsLabel">: {{ limitsLabel }}</span>.</p>
              <div class="points-tooltip__limit-result">
                <span>Учтено по лимиту</span>
                <strong class="points-tooltip__value" :class="pointsTone(breakdown.additional_points)">{{ formatPoints(breakdown.additional_points) }}</strong>
              </div>
            </div>
          </template>
          <p v-else class="points-tooltip__empty points-tooltip__empty--unavailable">
            Дополнительные баллы не рассчитаны: правила этой игры не сохранены.
          </p>
        </div>

        <footer class="points-tooltip__total" :class="pointsTone(breakdown.final_points)">
          <div>
            <span class="points-tooltip__label">Итого за игру</span>
            <span class="points-tooltip__formula">{{ formatPoints(breakdown.base_points) }} + ({{ formatPoints(breakdown.additional_points) }})</span>
          </div>
          <strong :class="pointsTone(breakdown.final_points)">{{ formatPoints(breakdown.final_points) }}</strong>
        </footer>
      </section>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import UiIcon from '@/components/UiIcon.vue'
import iconInfo from '@/assets/svg/iconInfo.svg'

interface PointsAdjustment {
  rule_key: string
  label: string
  points: number
}

interface Breakdown {
  base_points: number
  base_reason: 'win' | 'loss' | 'draw'
  adjustments: PointsAdjustment[]
  additional_points_raw: number
  additional_points: number
  additional_points_min?: number | null
  additional_points_max?: number | null
  additional_points_capped: boolean
  rules_available: boolean
  final_points: number
}

const props = defineProps<{
  points?: number | null
  breakdown?: Breakdown | null
  playerName?: string | null
}>()
const open = defineModel<boolean>('open', { default: false })
const id = useId()
const panelId = `points-breakdown-${id}`
const titleId = `${panelId}-title`
const trigger = ref<HTMLElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const panelStyle = ref<Record<string, string>>({ visibility: 'hidden' })
let pointerInside = false
let keyboardFocus = false
let closeTimer: ReturnType<typeof setTimeout> | undefined
let positionFrame = 0
let resizeObserver: ResizeObserver | undefined

const baseReason = computed(() => ({ win: 'Победа команды', loss: 'Поражение команды', draw: 'Ничья' }[props.breakdown?.base_reason || 'draw']))
const eventCount = computed(() => props.breakdown?.adjustments.length || 0)
const adjustments = computed(() => {
  const grouped = new Map<string, PointsAdjustment & { key: string; count: number }>()
  for (const adjustment of props.breakdown?.adjustments || []) {
    const points = Number.isFinite(adjustment.points) ? adjustment.points : 0
    const key = `${adjustment.label}\u0000${points}`
    const existing = grouped.get(key)
    if (existing) {
      existing.count += 1
    } else {
      grouped.set(key, { ...adjustment, points, key, count: 1 })
    }
  }
  return [...grouped.values()]
})
const limitsLabel = computed(() => {
  const min = props.breakdown?.additional_points_min
  const max = props.breakdown?.additional_points_max
  if (min != null && max != null) return `от ${formatPoints(min)} до ${formatPoints(max)}`
  if (min != null) return `от ${formatPoints(min)}`
  if (max != null) return `до ${formatPoints(max)}`
  return ''
})

function formatPoints(value: number | null | undefined): string {
  const points = Number(value)
  if (!Number.isFinite(points) || points === 0) return '0.00'
  return `${points > 0 ? '+' : '−'}${Math.abs(points).toFixed(2)}`
}

function pointsTone(value: number | null | undefined): string {
  const points = Number(value)
  return points > 0 ? 'points-positive' : points < 0 ? 'points-negative' : 'points-neutral'
}

function isInside(target: EventTarget | null): boolean {
  return target instanceof Node && Boolean(trigger.value?.contains(target) || panel.value?.contains(target))
}

function cancelClose(): void {
  clearTimeout(closeTimer)
  closeTimer = undefined
}

function preview(event: PointerEvent): void {
  if (event.pointerType !== 'mouse' || !props.breakdown) return
  cancelClose()
  pointerInside = true
  open.value = true
}

function previewFocus(): void {
  keyboardFocus = Boolean(trigger.value?.matches(':focus-visible'))
  if (keyboardFocus) open.value = true
}

function enterPanel(): void {
  pointerInside = true
  cancelClose()
}

function scheduleClose(): void {
  pointerInside = false
  cancelClose()
  if (keyboardFocus) return
  closeTimer = setTimeout(() => {
    if (!pointerInside && !keyboardFocus) close()
  }, 180)
}

function onBlur(): void {
  keyboardFocus = false
  if (!pointerInside) scheduleClose()
}

function close(): void {
  cancelClose()
  pointerInside = false
  keyboardFocus = false
  open.value = false
}

function onOutsidePointer(event: PointerEvent): void {
  if (!isInside(event.target)) close()
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopImmediatePropagation()
    close()
  }
}

function onScroll(event: Event): void {
  if (!(event.target instanceof Node) || !panel.value?.contains(event.target)) close()
}

function updatePosition(): void {
  positionFrame = 0
  const anchor = trigger.value
  const bubble = panel.value
  const root = document.getElementById('desktop-teleport-root')
  if (!open.value || !anchor || !bubble || !root) return
  const rootRect = root.getBoundingClientRect()
  const anchorRect = anchor.getBoundingClientRect()
  const scaleX = rootRect.width / root.clientWidth || 1
  const scaleY = rootRect.height / root.clientHeight || 1
  const width = root.clientWidth
  const height = root.clientHeight
  const left = (anchorRect.left - rootRect.left) / scaleX
  const right = (anchorRect.right - rootRect.left) / scaleX
  const top = (anchorRect.top - rootRect.top) / scaleY
  const bottom = (anchorRect.bottom - rootRect.top) / scaleY
  if (bottom <= 0 || top >= height || right <= 0 || left >= width) {
    close()
    return
  }
  const margin = 12
  const gap = 10
  const above = Math.max(0, top - margin - gap)
  const below = Math.max(0, height - bottom - margin - gap)
  const bubbleHeight = bubble.offsetHeight
  const bubbleWidth = bubble.offsetWidth
  const placeAbove = above >= bubbleHeight || above > below
  let preferredLeft = right - bubbleWidth
  let preferredTop = placeAbove ? top - gap - bubbleHeight : bottom + gap
  if (above < bubbleHeight && below < bubbleHeight) {
    if (width - right - margin - gap >= bubbleWidth) {
      preferredLeft = right + gap
      preferredTop = (top + bottom - bubbleHeight) / 2
    } else if (left - margin - gap >= bubbleWidth) {
      preferredLeft = left - gap - bubbleWidth
      preferredTop = (top + bottom - bubbleHeight) / 2
    }
  }
  panelStyle.value = {
    left: `${Math.max(margin, Math.min(preferredLeft, width - bubbleWidth - margin))}px`,
    top: `${Math.max(margin, Math.min(preferredTop, height - bubbleHeight - margin))}px`,
    visibility: 'visible',
  }
}

function schedulePosition(): void {
  if (!positionFrame) positionFrame = requestAnimationFrame(updatePosition)
}

function removeListeners(): void {
  window.removeEventListener('pointerdown', onOutsidePointer, true)
  window.removeEventListener('keydown', onKeydown, true)
  window.removeEventListener('scroll', onScroll, true)
  window.removeEventListener('resize', schedulePosition)
  resizeObserver?.disconnect()
  resizeObserver = undefined
  cancelAnimationFrame(positionFrame)
  positionFrame = 0
}

watch(open, async (visible) => {
  removeListeners()
  if (!visible) {
    pointerInside = false
    keyboardFocus = false
    cancelClose()
    panelStyle.value = { visibility: 'hidden' }
    return
  }
  await nextTick()
  if (!open.value) return
  updatePosition()
  window.addEventListener('pointerdown', onOutsidePointer, true)
  window.addEventListener('keydown', onKeydown, true)
  window.addEventListener('scroll', onScroll, true)
  window.addEventListener('resize', schedulePosition)
  resizeObserver = new ResizeObserver(() => schedulePosition())
  if (panel.value) resizeObserver.observe(panel.value)
  if (trigger.value) resizeObserver.observe(trigger.value)
})

watch(() => props.breakdown, () => {
  if (!props.breakdown) close()
  else if (open.value) nextTick(schedulePosition)
})

onBeforeUnmount(() => {
  cancelClose()
  removeListeners()
})
</script>

<style scoped lang="scss">
.points-positive {
  color: $green-400;
}
.points-negative {
  color: $red-300;
}
.points-neutral {
  color: $neutral-200;
}
.points-metric {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: $neutral-200;
  font-size: 14px;
  line-height: 20px;
  font-variant-numeric: tabular-nums;
  strong {
    font-family: Hauora-SemiBold;
    font-weight: normal;
  }
  &.points-metric--explainable {
    box-sizing: border-box;
    max-width: 100%;
    padding: 6px 8px;
    border: 1px solid transparent;
    border-radius: 10px;
    background: rgba($soft-purple-900, 0.65);
    font-family: Hauora-Regular;
    cursor: help;
    transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out;
    &:hover,
    &.points-metric--open {
      border-color: rgba($green-500, 0.45);
      background: $soft-purple-900;
      .points-metric__icon {
        color: $green-400;
      }
    }
    &:focus-visible {
      outline: 2px solid $green-500;
      outline-offset: 3px;
    }
  }
  .points-metric__icon {
    --ui-icon-width: 16px;
    --ui-icon-height: 16px;
    color: $soft-purple-300;
  }
}
.points-tooltip {
  position: fixed;
  z-index: 1600;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  width: min(390px, calc(var(--app-viewport-width, 100vw) - 24px));
  padding: 20px;
  border: 1px solid $soft-purple-600;
  border-radius: 20px;
  background: linear-gradient(155deg, $soft-purple-800, $soft-purple-900 60%);
  box-shadow: 0 16px 48px rgba($neutral-black, 0.55), 0 0 0 1px rgba($neutral-white, 0.03) inset;
  color: $neutral-100;
  font-family: Hauora-Regular;
  font-size: 14px;
  line-height: 20px;
  font-variant-numeric: tabular-nums;
  user-select: text;
  h3,
  h4,
  p {
    margin: 0;
  }
  strong {
    font-family: Hauora-SemiBold;
    font-weight: normal;
  }
  .points-tooltip__header {
    display: flex;
    flex: 0 0 auto;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 18px;
    .points-tooltip__eyebrow {
      display: block;
      color: $soft-purple-200;
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    h3 {
      margin-top: 4px;
      font: 20px/26px Hauora-SemiBold;
      color: $neutral-white;
    }
  }
  .points-tooltip__base {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px;
    border: 1px solid $soft-purple-700;
    border-radius: 12px;
    background: rgba($soft-purple-900, 0.5);
    .points-tooltip__base-label {
      display: flex;
      align-items: center;
      gap: 10px;
      .points-tooltip__reason {
        display: block;
        margin-top: 2px;
        color: $neutral-300;
        font-size: 12px;
        &.points-tooltip__reason--win {
          color: $green-400;
        }
        &.points-tooltip__reason--loss {
          color: $red-300;
        }
      }
    }
  }
  .points-tooltip__label {
    display: block;
    color: $neutral-100;
    font-family: Hauora-Medium;
  }
  .points-tooltip__step {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
    width: 24px;
    height: 24px;
    border: 1px solid $soft-purple-600;
    border-radius: 8px;
    color: $soft-purple-200;
    font-size: 12px;
  }
  .points-tooltip__value {
    flex: 0 0 auto;
    white-space: nowrap;
  }
  .points-tooltip__adjustments {
    margin-top: 18px;
    .points-tooltip__section-heading {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
      h4 {
        flex: 1;
        font: 14px/20px Hauora-Medium;
      }
      .points-tooltip__count {
        padding: 1px 7px;
        border-radius: 6px;
        background: $soft-purple-700;
        color: $soft-purple-100;
        font-size: 12px;
      }
    }
    .points-tooltip__list {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin: 0;
      padding: 0;
      list-style: none;
      .points-tooltip__adjustment {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 14px;
        padding: 9px 12px;
        border-radius: 10px;
        background: rgba($soft-purple-800, 0.75);
        transition: background-color 0.25s ease-in-out;
        &:hover {
          background: $soft-purple-700;
        }
        .points-tooltip__adjustment-label {
          min-width: 0;
          overflow-wrap: anywhere;
        }
        .points-tooltip__adjustment-value {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          .points-tooltip__multiply {
            color: $neutral-300;
            font-family: Hauora-Regular;
            font-size: 12px;
          }
          .points-tooltip__multiplicity {
            padding: 1px 6px;
            border-radius: 6px;
            background: rgba($neutral-white, 0.06);
            font-size: 12px;
            line-height: 18px;
          }
        }
      }
    }
    .points-tooltip__subtotal {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 0 0;
      color: $neutral-300;
    }
    .points-tooltip__empty {
      padding: 12px;
      border-radius: 10px;
      background: rgba($soft-purple-800, 0.5);
      color: $neutral-300;
      &.points-tooltip__empty--unavailable {
        color: $yellow-200;
      }
    }
    .points-tooltip__limit {
      margin-top: 12px;
      padding: 12px;
      border: 1px solid rgba($yellow-500, 0.25);
      border-radius: 12px;
      background: rgba($yellow-500, 0.06);
      .points-tooltip__limit-heading {
        display: flex;
        align-items: center;
        gap: 6px;
        color: $yellow-300;
        font-family: Hauora-Medium;
        .ui-icon {
          --ui-icon-width: 16px;
          --ui-icon-height: 16px;
        }
      }
      p {
        margin: 6px 0 10px;
        color: $neutral-200;
        font-size: 12px;
        line-height: 18px;
      }
      .points-tooltip__limit-result {
        display: flex;
        justify-content: space-between;
        gap: 12px;
      }
    }
  }
  .points-tooltip__total {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-top: 18px;
    padding: 14px;
    border: 1px solid rgba($green-500, 0.3);
    border-radius: 14px;
    background: rgba($green-500, 0.06);
    > strong {
      font-size: 28px;
      line-height: 34px;
    }
    &.points-negative {
      border-color: rgba($red-500, 0.3);
      background: rgba($red-500, 0.06);
    }
    &.points-neutral {
      border-color: $soft-purple-600;
      background: rgba($soft-purple-800, 0.6);
    }
    .points-tooltip__formula {
      display: block;
      margin-top: 3px;
      color: $neutral-300;
      font-size: 12px;
    }
  }
}

.points-panel-enter-active,
.points-panel-leave-active {
  transition: opacity 0.15s ease-in-out, transform 0.15s ease-in-out;
}
.points-panel-enter-from,
.points-panel-leave-to {
  opacity: 0;
  transform: translateY(5px);
}
</style>
