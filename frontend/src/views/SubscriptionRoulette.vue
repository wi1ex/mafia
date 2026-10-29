<template>
  <Teleport to="#desktop-teleport-root">
    <Transition name="roulette-window" appear>
      <div v-if="open" class="roulette-overlay" @pointerdown.self="overlayArmed = true" @pointerup.self="onOverlayUp" @pointercancel="overlayArmed = false">
        <section ref="dialog" class="roulette-dialog" role="dialog" aria-modal="true" aria-labelledby="roulette-title" @keydown="onKeydown">
          <header class="roulette-header">
            <div>
              <span class="roulette-eyebrow">Рулетка подписки</span>
              <h2 id="roulette-title">{{ phase === 'result' ? 'Удача на вашей стороне' : 'Ваш счастливый поворот' }}</h2>
            </div>
            <UiButton class="roulette-close" variant="white" size="low" :icon="iconClose" width="40px" aria-label="Закрыть рулетку" @click="$emit('close')" />
          </header>

          <div class="roulette-content">
            <div class="roulette-info">
              <div class="roulette-prize" :class="{ 'is-won': phase === 'result' }" aria-live="polite" aria-atomic="true">
                <span>{{ phase === 'result' ? 'Ваш выигрыш' : 'Подписка в подарок' }}</span>
                <strong>{{ phase === 'result' && days ? days : '1–30' }}</strong>
                <span class="roulette-prize__caption">{{ phase === 'result' && days ? `${daysWord(days)} подписки` : 'дней бесплатного доступа' }}</span>
              </div>
              <UiButton class="roulette-action" :text="buttonText" width="100%" :disabled="buttonDisabled" @click="phase === 'result' ? $emit('share') : $emit('start')" />
              <p v-if="error" class="roulette-error" role="alert">{{ error }}</p>
            </div>

            <div class="roulette-machine" :class="{ 'is-pulled': pulled, 'is-won': phase === 'result' }">
              <div class="roulette-wheel-shell">
                <div class="roulette-pointer" aria-hidden="true"></div>
                <svg class="roulette-wheel" :style="wheelStyle" viewBox="-200 -200 400 400" role="img" aria-label="Колесо с тридцатью равными секторами от одного до тридцати дней подписки">
                  <circle r="195" class="wheel-rim" />
                  <circle r="185" class="wheel-edge" />
                  <g v-for="sector in sectors" :key="sector.days">
                    <path :d="sector.path" class="wheel-sector" :class="{ 'is-red': sector.red }" />
                    <text :x="sector.labelX" :y="sector.labelY" :transform="sector.labelTransform" :data-day="sector.days" class="wheel-number">{{ sector.days }}</text>
                    <circle :cx="sector.dotX" :cy="sector.dotY" r="1.7" class="wheel-dot" />
                  </g>
                  <circle r="124" class="wheel-inner-ring" />
                </svg>
                <span class="roulette-hub" aria-hidden="true"><img :src="logo" alt="" /></span>
              </div>
              <button class="roulette-lever" type="button" aria-label="Потянуть рычаг и получить бесплатную подписку" :disabled="!canSpin || busy || phase === 'result' || phase === 'error'" @click="$emit('start')">
                <span class="roulette-lever__base" aria-hidden="true"></span>
                <span class="roulette-lever__arm" aria-hidden="true"></span>
                <span class="roulette-lever__knob" aria-hidden="true"></span>
              </button>
            </div>
          </div>
          <div v-if="confettiVisible && !reducedMotion" class="roulette-confetti" aria-hidden="true">
            <i v-for="piece in confetti" :key="piece.id" :style="piece.style"></i>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import UiButton from '@/components/UiButton.vue'
import iconClose from '@/assets/svg/iconClose.svg'
import logo from '@/assets/svg/iconLogo.svg'
import { ROULETTE_DAYS, ROULETTE_MAX_STOP_OFFSET, ROULETTE_SPIN_MS, rouletteAngle, rouletteDaysWord as daysWord, validRouletteDays, type RoulettePhase } from '@/services/subscriptionRoulette'

const props = defineProps<{
  open: boolean
  phase: RoulettePhase
  days: number | null
  subscriptionUntil: string | null
  canSpin: boolean
  error: string
  sharing: boolean
  reducedMotion: boolean
}>()
const emit = defineEmits<{ start: []; close: []; share: [] }>()
const dialog = ref<HTMLElement | null>(null)
const angle = ref(0)
const stopOffset = ref(0)
const animateWheel = ref(false)
const overlayArmed = ref(false)
const confettiVisible = ref(false)
const busy = computed(() => ['requesting', 'spinning', 'recovering'].includes(props.phase))
const pulled = computed(() => busy.value || props.phase === 'result')
let confettiTimer: number | undefined
let returnFocus: HTMLElement | null = null
let background: HTMLElement | null = null
let previousInert = false
let focusLocked = false

const buttonText = computed(() => {
  if (props.phase === 'result') return props.sharing ? 'Отправляем…' : 'Отправить результат в чат'
  if (props.phase === 'requesting') return 'Подготавливаем…'
  if (props.phase === 'spinning') return 'Колесо вращается…'
  if (props.phase === 'recovering') return 'Проверяем результат…'
  if (props.phase === 'error') return 'Проверить результат'
  return props.canSpin ? 'Потянуть рычаг' : 'Участие недоступно'
})
const buttonDisabled = computed(() => busy.value || props.sharing || (props.phase !== 'result' && props.phase !== 'error' && !props.canSpin))
const wheelStyle = computed(() => ({
  transform: `rotate(${angle.value}deg)`,
  transitionDuration: animateWheel.value && !props.reducedMotion ? `${ROULETTE_SPIN_MS}ms` : '0ms',
}))
const point = (radius: number, degrees: number) => ({ x: radius * Math.cos(degrees * Math.PI / 180), y: radius * Math.sin(degrees * Math.PI / 180) })
const sectors = ROULETTE_DAYS.map((days, index) => {
  const center = -90 + index * 12
  const from = point(179, center - 6)
  const to = point(179, center + 6)
  const label = point(151, center)
  const dot = point(190, center)
  return {
    days,
    red: index % 2 === 1,
    path: `M0 0 L${from.x} ${from.y} A179 179 0 0 1 ${to.x} ${to.y} Z`,
    labelX: label.x, labelY: label.y,
    labelTransform: `rotate(${center + 90} ${label.x} ${label.y})`,
    dotX: dot.x, dotY: dot.y,
  }
})
const confetti = Array.from({ length: 120 }, (_, id) => ({
  id,
  style: {
    '--piece-left': `${7 + (id * 31 % 87)}%`,
    '--piece-drift': `${(id * 43 % 400) - 200}px`,
    '--piece-turn': `${(id % 2 ? 1 : -1) * (180 + id * 31)}deg`,
    '--piece-delay': `${id % 12 * 40}ms`,
  },
}))

function randomStopOffset(): number {
  return (Math.random() * 2 - 1) * ROULETTE_MAX_STOP_OFFSET
}

watch(() => [props.phase, props.days] as const, async ([phase, days], previous) => {
  if (!validRouletteDays(days)) return
  if (phase === 'spinning') {
    stopOffset.value = randomStopOffset()
    animateWheel.value = false
    await nextTick()
    animateWheel.value = true
    angle.value = rouletteAngle(days, angle.value, stopOffset.value)
  } else if (phase === 'result') {
    if (previous?.[0] !== 'spinning') {
      stopOffset.value = randomStopOffset()
      animateWheel.value = false
      angle.value = rouletteAngle(days, 0, stopOffset.value) % 360
    }
    if (props.open && previous?.[0] === 'spinning' && !props.reducedMotion) {
      confettiVisible.value = true
      confettiTimer = window.setTimeout(() => { confettiVisible.value = false }, 3200)
    }
  }
}, { immediate: true })

function unlockFocus(): void {
  if (!focusLocked) return
  focusLocked = false
  if (background) background.inert = previousInert
  background = null
  const target = returnFocus
  returnFocus = null
  void nextTick(() => {
    if (target?.isConnected && target.getClientRects().length && !target.closest('[inert]')) {
      target.focus({ preventScroll: true })
    } else {
      const fallback = document.querySelector<HTMLElement>('.roulette-invitation button')
        || document.querySelector<HTMLElement>('main h1, main, .bar a')
      if (!fallback) return
      const previousTabindex = fallback.getAttribute('tabindex')
      fallback.setAttribute('tabindex', '-1')
      fallback.focus({ preventScroll: true })
      if (previousTabindex === null) fallback.removeAttribute('tabindex')
      else fallback.setAttribute('tabindex', previousTabindex)
    }
  })
}

watch(() => props.open, async open => {
  if (!open) {
    confettiVisible.value = false
    unlockFocus()
    return
  }
  returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  background = document.getElementById('desktop-scale-root')
  previousInert = background?.inert ?? false
  if (background) background.inert = true
  focusLocked = true
  await nextTick()
  dialog.value?.querySelector<HTMLElement>('button')?.focus({ preventScroll: true })
}, { immediate: true })

function onOverlayUp(): void {
  if (overlayArmed.value) emit('close')
  overlayArmed.value = false
}
function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('close')
  }
  if (event.key !== 'Tab' || !dialog.value) return
  const focusable = [...dialog.value.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),[tabindex="0"]')].filter(element => element.getClientRects().length)
  const first = focusable[0]
  const last = focusable.at(-1)
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
onBeforeUnmount(() => {
  if (confettiTimer !== undefined) window.clearTimeout(confettiTimer)
  unlockFocus()
})
</script>

<style scoped lang="scss">
.roulette-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba($neutral-black, 0.65);
  backdrop-filter: blur(8px);
  .roulette-dialog {
    position: relative;
    width: min(800px, calc(100vw - 40px));
    max-height: calc(100dvh - 40px);
    padding: 24px;
    box-sizing: border-box;
    overflow: auto;
    overscroll-behavior: contain;
    border-radius: 24px;
    background-color: $neutral-50;
    color: $soft-purple-900;
    font-family: Hauora-Regular;
    font-weight: 400;
    font-size: 16px;
    line-height: 1.4;
    transform: translateY(0) scale(calc(1 / var(--desktop-scale, 1)));
    transform-origin: center;
    transition: transform 0.25s ease-in-out;
    box-shadow: 0 24px 80px rgba($neutral-black, 0.3);
    scrollbar-width: thin;
    :deep(button:focus-visible) {
      outline: 3px solid $soft-purple-500;
      outline-offset: 4px;
    }
    .roulette-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 20px;
      > div {
        .roulette-eyebrow {
          color: $green-700;
          font-family: Hauora-Medium;
          font-weight: 500;
          font-size: 12px;
          line-height: 16px;
          letter-spacing: 1px;
          text-transform: uppercase;
        }
        h2 {
          margin: 8px 0 0;
          font-family: Involve-Medium;
          font-weight: 500;
          font-size: 24px;
          line-height: 1.12;
          letter-spacing: -0.64px;
        }
      }
      .roulette-close {
        flex: 0 0 40px;
        --ui-button-radius: 50%;
        --ui-button-height: 40px;
      }
    }
    .roulette-content {
      display: grid;
      grid-template-columns: 1fr 1.5fr;
      gap: 42px;
      align-items: center;
      .roulette-info {
        display: flex;
        flex-direction: column;
        gap: 16px;
        min-width: 0;
        .roulette-prize {
          display: flex;
          flex-direction: column;
          gap: 6px;
          padding: 22px;
          border-radius: 20px;
          background-color: $neutral-white;
          color: $soft-purple-700;
          font-size: 14px;
          strong {
            color: $soft-purple-900;
            font-family: Involve-Medium;
            font-weight: 500;
            font-size: 52px;
            line-height: 1.1;
            letter-spacing: -1px;
          }
          .roulette-prize__caption {
            color: $soft-purple-700;
          }
          .roulette-prize__until {
            margin-top: 5px;
            font-size: 12px;
          }
          &.is-won {
            strong {
              font-size: 70px;
              color: $green-700;
            }
          }
        }
        .roulette-action {
          --ui-button-height: 50px;
          --ui-button-font-size: 16px;
        }
        .roulette-error {
          margin: 0;
          color: $red-700;
          font-size: 13px;
          line-height: 1.5;
        }
      }
      .roulette-machine {
        position: relative;
        width: min(100%, 325px);
        justify-self: end;
        padding-right: 60px;
        box-sizing: border-box;
        .roulette-wheel-shell {
          position: relative;
          width: 100%;
          aspect-ratio: 1;
          overflow: clip;
          .roulette-pointer {
            position: absolute;
            left: 50%;
            top: 3px;
            z-index: 2;
            width: 0;
            height: 0;
            transform: translateX(-50%);
            border-left: 10px solid transparent;
            border-right: 10px solid transparent;
            border-top: 27px solid $soft-purple-500;
            filter: drop-shadow(0 2px 1px rgba($neutral-black, 0.4));
          }
          .roulette-wheel {
            display: block;
            width: 100%;
            height: 100%;
            transition-property: transform;
            transition-timing-function: cubic-bezier(0.12, 0.75, 0.25, 1);
            .wheel-rim {
              fill: $soft-purple-800;
            }
            .wheel-edge {
              fill: $soft-purple-900;
              stroke: $soft-purple-500;
              stroke-width: 1;
            }
            g {
              .wheel-sector {
                fill: $neutral-900;
                stroke: $soft-purple-800;
                stroke-width: 0.8;
                &.is-red {
                  fill: $red-600;
                }
              }
              .wheel-number {
                fill: $neutral-white;
                font-family: Hauora-Regular;
                font-size: 17px;
                text-anchor: middle;
                dominant-baseline: central;
              }
              .wheel-dot {
                fill: $soft-purple-400;
              }
            }
            .wheel-inner-ring {
              fill: none;
              stroke: rgba($soft-purple-200, 0.3);
              stroke-width: 0.7;
            }
          }
          .roulette-hub {
            position: absolute;
            left: 37%;
            top: 37%;
            width: 26%;
            height: 26%;
            display: grid;
            place-items: center;
            border: 2px solid $soft-purple-500;
            border-radius: 50%;
            box-sizing: border-box;
            background: linear-gradient(135deg, $soft-purple-700, $soft-purple-900);
            box-shadow: 0 4px 16px rgba($neutral-black, 0.3);
            img {
              width: 70%;
            }
          }
        }
        .roulette-lever {
          position: absolute;
          right: 36px;
          top: 37%;
          width: 50px;
          height: 128px;
          padding: 0;
          border: none;
          background: none;
          cursor: pointer;
          -webkit-tap-highlight-color: transparent;
          &:disabled {
            cursor: default;
          }
          .roulette-lever__base {
            position: absolute;
            top: 61px;
            left: 13px;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background-color: $soft-purple-900;
          }
          .roulette-lever__arm {
            position: absolute;
            top: 0;
            left: 20px;
            width: 12px;
            height: 80px;
            border-radius: 8px;
            background: linear-gradient(90deg, $soft-purple-900, $soft-purple-500, $soft-purple-800);
            transform: rotate(-10deg);
            transform-origin: 50% 90%;
            transition: transform 0.25s;
          }
          .roulette-lever__knob {
            position: absolute;
            left: 2px;
            top: -7px;
            width: 38px;
            height: 38px;
            border-radius: 50%;
            background: radial-gradient(circle at 32% 24%, $soft-purple-500, $soft-purple-800 65%, $soft-purple-900);
            box-shadow: 0 3px 8px rgba($neutral-black, 0.24);
            transition: transform 0.25s;
          }
        }
        &.is-pulled {
          .roulette-lever {
            .roulette-lever__arm {
              transform: rotate(28deg);
            }
            .roulette-lever__knob {
              transform: translate(46px, 23px);
            }
          }
        }
      }
    }
    .roulette-confetti {
      position: absolute;
      inset: 0;
      pointer-events: none;
      overflow: hidden;
      border-radius: inherit;
      i {
        position: absolute;
        top: 8%;
        left: var(--piece-left);
        width: 7px;
        height: 13px;
        background-color: $green-500;
        animation: roulette-confetti-fall 2.5s var(--piece-delay) cubic-bezier(0.12, 0.5, 0.4, 1) both;
        &:nth-child(3n) {
          width: 9px;
          height: 9px;
        }
        &:nth-child(4n + 2) {
          background-color: $red-600;
        }
        &:nth-child(4n + 3) {
          background-color: $soft-purple-800;
        }
        &:nth-child(4n) {
          background-color: $soft-purple-400;
        }
      }
    }
  }
}

.roulette-window-enter-active,
.roulette-window-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.roulette-window-enter-from,
.roulette-window-leave-to {
  opacity: 0;
  .roulette-dialog {
    transform: translateY(-30px) scale(calc(1 / var(--desktop-scale, 1)));
  }
}

@keyframes roulette-confetti-fall {
  from {
    opacity: 0;
    transform: translate3d(0, -30px, 0) rotate(0);
  }
  12% {
    opacity: 1;
  }
  to {
    opacity: 0;
    transform: translate3d(var(--piece-drift), 400px, 0) rotate(var(--piece-turn));
  }
}
</style>
