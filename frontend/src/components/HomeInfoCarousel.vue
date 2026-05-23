<template>
  <section class="home-carousel" role="region" aria-roledescription="carousel" aria-label="Информационная карусель" tabindex="0" :class="{ 'is-paused': isPaused }"
           :style="carouselProgressStyle" @mouseenter="hovered = true" @mouseleave="hovered = false" @focusin="focused = true" @focusout="onFocusOut" @keydown="onKeydown" >
    <Transition :name="slideTransitionName" mode="out-in">
      <article v-if="activeIndex === 0" key="slide-1" class="slide-one">

      </article>

      <article v-else-if="activeIndex === 1" key="slide-2" class="slide-two">

      </article>

      <article v-else-if="activeIndex === 2" key="slide-3" class="slide-three">

      </article>

      <article v-else-if="activeIndex === 3" key="slide-4" class="slide-four">

      </article>

      <article v-else key="install" class="slide-five">
        <img class="image51" :src="Image51" alt="" aria-hidden="true" />
        <button type="button" class="primary-btn" :disabled="installButtonDisabled" @click="openInstall">
          {{ installButtonLabel }}
        </button>
      </article>
    </Transition>

    <div class="carousel-controls">
      <button type="button" class="nav-btn" aria-label="Предыдущий блок" @click="goPrevious(true)">
        <img class="nav-icon nav-icon--prev" :src="iconArrowDown" alt="" aria-hidden="true" />
      </button>

      <div class="carousel-dots">
        <span v-for="index in SLIDE_COUNT" :key="index" class="carousel-dot" :class="{ active: activeIndex === index - 1 }" aria-hidden="true" />
      </div>

      <button type="button" class="nav-btn" aria-label="Следующий блок" @click="goNext(true)">
        <img class="nav-icon nav-icon--next" :src="iconArrowDown" alt="" aria-hidden="true" />
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { requestPwaInstall, usePwaInstallState } from '@/services/pwa'

import iconArrowDown from '@/assets/svg/iconArrowDown.svg'

import Image51 from '@/assets/images/carousel-image51.png'

const AUTOPLAY_DELAY_MS = 10000
const SLIDE_COUNT = 5

const activeIndex = ref(0)
const slideDirection = ref<1 | -1>(1)
const hovered = ref(false)
const focused = ref(false)
const documentHidden = ref(false)
const prefersReducedMotion = ref(false)
const manualInstallHintVisible = ref(false)
const pwaInstall = usePwaInstallState()

const carouselProgressStyle = computed(() => ({
  '--carousel-dot-duration': `${AUTOPLAY_DELAY_MS}ms`,
}))

let autoplayTimer: number | null = null
let motionQuery: MediaQueryList | null = null

const canPromptInstall = computed(() => !pwaInstall.installed && pwaInstall.deferredPrompt !== null)
const installButtonDisabled = computed(() => pwaInstall.installed || (manualInstallHintVisible.value && !canPromptInstall.value))
const installButtonLabel = computed(() => {
  if (pwaInstall.installed) return 'Приложение установлено'
  if (manualInstallHintVisible.value && !canPromptInstall.value) return 'Используйте меню браузера'
  if (canPromptInstall.value) return 'Установить приложение'
  return 'Установить приложение'
})

watch(() => canPromptInstall.value, (next) => {
  if (next) manualInstallHintVisible.value = false
})

watch(() => pwaInstall.installed, (next) => {
  if (next) manualInstallHintVisible.value = false
})

const slideTransitionName = computed(() => slideDirection.value > 0 ? 'carousel-slide-forward' : 'carousel-slide-backward')
const isPaused = computed(() => hovered.value || focused.value || documentHidden.value || prefersReducedMotion.value)

function clearAutoplayTimer() {
  if (autoplayTimer == null) return
  window.clearTimeout(autoplayTimer)
  autoplayTimer = null
}

function syncAutoplay() {
  clearAutoplayTimer()
  if (isPaused.value) return
  autoplayTimer = window.setTimeout(() => {
    goNext(false)
  }, AUTOPLAY_DELAY_MS)
}

function normalizeIndex(index: number): number {
  return ((index % SLIDE_COUNT) + SLIDE_COUNT) % SLIDE_COUNT
}

function setActive(nextIndex: number, direction: 1 | -1, userInitiated: boolean) {
  const normalized = normalizeIndex(nextIndex)
  if (normalized === activeIndex.value) {
    if (userInitiated) syncAutoplay()
    return
  }
  slideDirection.value = direction
  activeIndex.value = normalized
  if (userInitiated) syncAutoplay()
}

function goPrevious(userInitiated = false) {
  setActive(activeIndex.value - 1, -1, userInitiated)
}

function goNext(userInitiated = false) {
  setActive(activeIndex.value + 1, 1, userInitiated)
}

async function openInstall() {
  if (pwaInstall.installed) return
  if (!canPromptInstall.value) {
    manualInstallHintVisible.value = true
    return
  }

  manualInstallHintVisible.value = false
  const result = await requestPwaInstall()
  if (result === 'dismissed' || result === 'unavailable') {
    manualInstallHintVisible.value = true
  }
}

function onFocusOut(event: FocusEvent) {
  const next = event.relatedTarget as Node | null
  const current = event.currentTarget as HTMLElement | null
  if (current && next && current.contains(next)) return
  focused.value = false
}

function onKeydown(event: KeyboardEvent) {
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    goPrevious(true)
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    goNext(true)
  }
}

function onVisibilityChange() {
  documentHidden.value = document.hidden
}

function onMotionChange(event: MediaQueryListEvent) {
  prefersReducedMotion.value = event.matches
}

watch([activeIndex, isPaused], () => {
  syncAutoplay()
}, { immediate: true })

onMounted(() => {
  documentHidden.value = document.hidden
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  prefersReducedMotion.value = motionQuery.matches
  document.addEventListener('visibilitychange', onVisibilityChange, { passive: true })
  motionQuery.addEventListener('change', onMotionChange)
})

onBeforeUnmount(() => {
  clearAutoplayTimer()
  document.removeEventListener('visibilitychange', onVisibilityChange)
  if (!motionQuery) return
  motionQuery.removeEventListener('change', onMotionChange)
  motionQuery = null
})
</script>

<style scoped lang="scss">
.home-carousel {
  display: flex;
  position: relative;
  width: 100%;
  height: 100%;
  .slide-one {
    display: flex;
    padding: 24px 24px 72px;
    width: calc(100% - 48px);
    height: calc(100% - 96px);
    background-color: $neutral-800;
    z-index: 1;
  }
  .slide-two {
    display: flex;
    padding: 24px 24px 72px;
    width: calc(100% - 48px);
    height: calc(100% - 96px);
    background-color: $neutral-800;
    z-index: 1;
  }
  .slide-three {
    display: flex;
    padding: 24px 24px 72px;
    width: calc(100% - 48px);
    height: calc(100% - 96px);
    background-color: $neutral-800;
    z-index: 1;
  }
  .slide-four {
    display: flex;
    padding: 24px 24px 72px;
    width: calc(100% - 48px);
    height: calc(100% - 96px);
    background-color: $neutral-800;
    z-index: 1;
  }
  .slide-five {
    display: flex;
    padding: 24px 24px 72px;
    width: calc(100% - 48px);
    height: calc(100% - 96px);
    background: linear-gradient(180deg, rgba(17, 18, 27, 0.00) 52.18%, rgba(17, 18, 27, 0.30) 100%), #151621;
    z-index: 1;
    .image51 {

    }
    .primary-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      height: 40px;
    }
  }
  .carousel-controls {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: space-between;
    left: 24px;
    bottom: 16px;
    width: calc(100% - 48px);
    height: 40px;
    z-index: 5;
    .nav-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 40px;
      height: 40px;
      border: none;
      border-radius: 12px;
      background: linear-gradient(261deg, $green-700 0%, $soft-purple-800 100%);
      cursor: pointer;
      position: relative;
      overflow: hidden;
      isolation: isolate;
      &::after {
        content: '';
        position: absolute;
        inset: 0;
        border-radius: inherit;
        background: linear-gradient(261deg, $soft-purple-800 0%, $green-700 100%);
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.25s ease-in-out;
        z-index: 0;
      }
      &:hover,
      &:focus-visible,
      &:active {
        &::after {
          opacity: 1;
        }
      }
      .nav-icon {
        position: relative;
        z-index: 2;
        width: 24px;
        height: 24px;
        &.nav-icon--prev {
          transform: rotate(90deg);
        }
        &.nav-icon--next {
          transform: rotate(-90deg);
        }
      }
    }
    .carousel-dots {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      .carousel-dot {
        display: block;
        position: relative;
        overflow: hidden;
        width: 4px;
        height: 4px;
        border-radius: 999px;
        background-color: $neutral-300;
        transition: width 0.25s ease-in-out, background-color 0.25s ease-in-out;
        &::after {
          content: '';
          position: absolute;
          inset: 0;
          border-radius: inherit;
          background-color: $neutral-100;
          pointer-events: none;
          transform: scaleX(0);
          transform-origin: left center;
        }
        &.active {
          width: 64px;
          background-color: $neutral-300;
          &::after {
            animation: carousel-dot-progress var(--carousel-dot-duration, 10000ms) linear forwards;
          }
        }
      }
    }
  }
  &.is-paused {
    .carousel-controls {
      .carousel-dot.active {
        background-color: $neutral-100;
        &::after {
          animation: none;
          transform: scaleX(0);
        }
      }
    }
  }
}

@keyframes carousel-dot-progress {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}

.carousel-slide-forward-enter-active,
.carousel-slide-forward-leave-active,
.carousel-slide-backward-enter-active,
.carousel-slide-backward-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}

.carousel-slide-forward-enter-from,
.carousel-slide-backward-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.carousel-slide-forward-leave-to,
.carousel-slide-backward-enter-from {
  opacity: 0;
  transform: translateX(-30px);
}

.carousel-slide-forward-enter-to,
.carousel-slide-forward-leave-from,
.carousel-slide-backward-enter-to,
.carousel-slide-backward-leave-from {
  opacity: 1;
  transform: translateX(0);
}

@media (max-width: 1280px) {

}

</style>
