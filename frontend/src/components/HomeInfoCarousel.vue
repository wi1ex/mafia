<template>
  <section class="home-carousel" role="region" aria-roledescription="carousel" aria-label="Информационная карусель" tabindex="0"
           @mouseenter="hovered = true" @mouseleave="hovered = false" @focusin="focused = true" @focusout="onFocusOut" @keydown="onKeydown" >
    <div class="carousel-viewport">
      <Transition :name="slideTransitionName" mode="out-in">
        <article v-if="activeIndex === 0" key="slide-1" class="slide slide--one">
          <div class="slide-content">

          </div>
        </article>

        <article v-else-if="activeIndex === 1" key="slide-2" class="slide slide--two">
          <div class="slide-content">

          </div>
        </article>

        <article v-else-if="activeIndex === 2" key="slide-3" class="slide slide--three">
          <div class="slide-content">

          </div>
        </article>

        <article v-else-if="activeIndex === 3" key="slide-4" class="slide slide--four">
          <div class="slide-content">

          </div>
        </article>

        <article v-else key="install" class="slide slide--install">
          <div class="slide-content">
            <button type="button" class="primary-btn" :disabled="installButtonDisabled" @click="openInstall">
              {{ installButtonLabel }}
            </button>
          </div>
        </article>
      </Transition>

      <div class="carousel-controls">
        <button type="button" class="nav-btn" aria-label="Предыдущий блок" @click="goPrevious(true)">
          <img class="nav-icon nav-icon--prev" :src="iconArrowDown" alt="" aria-hidden="true" />
        </button>

        <button v-for="index in SLIDE_COUNT" :key="index" type="button" class="carousel-dot" :class="{ active: activeIndex === index - 1 }"
                :aria-label="`Показать блок ${index}`" :aria-current="activeIndex === index - 1 ? 'true' : undefined" @click="goTo(index - 1, true)" />

        <button type="button" class="nav-btn" aria-label="Следующий блок" @click="goNext(true)">
          <img class="nav-icon nav-icon--next" :src="iconArrowDown" alt="" aria-hidden="true" />
        </button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { requestPwaInstall, usePwaInstallState } from '@/services/pwa'

import iconArrowDown from '@/assets/svg/arrowDown.svg'

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

function goTo(index: number, userInitiated = false) {
  const normalized = normalizeIndex(index)
  const direction: 1 | -1 = normalized >= activeIndex.value ? 1 : -1
  setActive(normalized, direction, userInitiated)
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
  } else if (event.key === 'Home') {
    event.preventDefault()
    goTo(0, true)
  } else if (event.key === 'End') {
    event.preventDefault()
    goTo(SLIDE_COUNT - 1, true)
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
  width: 100%;
  height: 100%;
  .carousel-viewport {
    display: flex;
    flex-direction: column;
    padding: 24px 24px 16px;
    width: calc(100% - 48px);
    height: calc(100% - 40px);
    background-color: $neutral-800;
    .slide {
      display: flex;
      width: 100%;
      height: 100%;
      .slide-content {
        display: flex;
        z-index: 1;
        .primary-btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          height: 40px;
        }
      }
    }
    .carousel-controls {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      width: 100%;
      height: 40px;
      z-index: 5;
      .nav-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        width: 40px;
        height: 40px;
        border-radius: 12px;
        cursor: pointer;
        .nav-icon {
          width: 20px;
          height: 20px;
          &.nav-icon--prev {
            transform: rotate(90deg);
          }
          &.nav-icon--next {
            transform: rotate(-90deg);
          }
        }
      }
      .carousel-dot {
        padding: 0;
        position: relative;
        overflow: hidden;
        width: 20px;
        height: 10px;
        border-radius: 999px;
        cursor: pointer;
        transition: width 0.25s ease-in-out, background-color 0.25s ease-in-out, border-color 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
        &:hover,
        &:focus-visible {
          background:
            linear-gradient(180deg, rgba($white, 0.25), rgba($white, 0.1)),
            rgba($white, 0.25);
        }
        &.active {
          width: 50px;
          background:
            linear-gradient(180deg, rgba($white, 0.25), rgba($white, 0.1)),
            rgba($white, 0.25);
        }
      }
    }
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
