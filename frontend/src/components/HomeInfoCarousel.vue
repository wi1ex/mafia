<template>
  <section class="home-carousel" role="region" aria-roledescription="carousel" aria-label="Информационная карусель" tabindex="0"
           @mouseenter="hovered = true" @mouseleave="hovered = false" @focusin="focused = true" @focusout="onFocusOut" @keydown="onKeydown" >
    <div class="carousel-viewport">
      <Transition :name="slideTransitionName" mode="out-in">
        <article v-if="activeIndex === 0" key="slide-1" class="slide slide--one">
          <div class="slide-surface">
            <div class="slide-content"></div>
          </div>
        </article>

        <article v-else-if="activeIndex === 1" key="slide-2" class="slide slide--two">
          <div class="slide-surface">
            <div class="slide-content"></div>
          </div>
        </article>

        <article v-else-if="activeIndex === 2" key="slide-3" class="slide slide--three">
          <div class="slide-surface">
            <div class="slide-content"></div>
          </div>
        </article>

        <article v-else-if="activeIndex === 3" key="slide-4" class="slide slide--four">
          <div class="slide-surface">
            <div class="slide-content"></div>
          </div>
        </article>

        <article v-else key="install" class="slide slide--install">
          <div class="slide-surface">
            <div class="slide-content slide-content--install">
              <div class="slide-actions">
                <button type="button" class="primary-btn" :disabled="installButtonDisabled" @click="openInstall">
                  {{ installButtonLabel }}
                </button>
              </div>
            </div>
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
  flex-direction: column;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  outline: none;
  .carousel-viewport {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
  }
  .slide {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
    .slide-surface {
      position: absolute;
      inset: 0;
    }
    .slide-content {
      display: flex;
      position: relative;
      flex-direction: column;
      height: 100%;
      padding: 15px 15px 82px;
      gap: 15px;
      box-sizing: border-box;
      overflow: auto;
      scrollbar-width: none;
      z-index: 1;
      &::-webkit-scrollbar {
        display: none;
      }
      &.slide-content--install {
        align-items: center;
        justify-content: center;
      }
    }
    .slide-actions {
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .primary-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 220px;
      height: 40px;
      border: none;
      border-radius: 10px;
      background-color: $fg;
      color: $bg;
      font-size: 16px;
      font-family: Manrope-SemiBold;
      text-decoration: none;
      outline: none;
      cursor: pointer;
      transition: opacity 0.25s ease-in-out, box-shadow 0.25s ease-in-out, background-color 0.25s ease-in-out;
      &:hover,
      &:focus-visible {
        box-shadow: 0 15px 30px rgba($black, 0.25);
        background-color: $white;
      }
      &:disabled {
        cursor: default;
        opacity: 0.5;
        box-shadow: none;
      }
    }
  }
  .carousel-controls {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    left: 50%;
    bottom: 15px;
    padding: 5px 10px;
    gap: 10px;
    overflow: hidden;
    isolation: isolate;
    border: 1px solid rgba($white, 0.1);
    border-radius: 999px;
    background:
      linear-gradient(180deg, rgba($white, 0.1), rgba($white, 0.05) 50%, rgba($white, 0.01)),
      radial-gradient(circle at top center, rgba($white, 0.1), transparent 75%),
      rgba($bg, 0.5);
    -webkit-backdrop-filter: blur(30px) saturate(180%) brightness(1.25);
    backdrop-filter: blur(30px) saturate(180%) brightness(1.25);
    transform: translateX(-50%);
    box-shadow:
      inset 0 1px 0 rgba($white, 0.25),
      inset 0 -1px 0 rgba($white, 0.1),
      0 15px 30px rgba($black, 0.25);
    z-index: 5;
  }
  .carousel-dot {
    padding: 0;
    position: relative;
    overflow: hidden;
    width: 20px;
    height: 10px;
    border: 1px solid rgba($white, 0.1);
    border-radius: 999px;
    background:
      linear-gradient(180deg, rgba($white, 0.1), rgba($white, 0.05)),
      rgba($white, 0.1);
    box-shadow:
      inset 0 1px 0 rgba($white, 0.25),
      0 5px 10px rgba($black, 0.1);
    outline: none;
    cursor: pointer;
    transition: width 0.25s ease-in-out, background-color 0.25s ease-in-out, border-color 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
    &:hover,
    &:focus-visible {
      border-color: rgba($white, 0.1);
      background:
        linear-gradient(180deg, rgba($white, 0.25), rgba($white, 0.1)),
        rgba($white, 0.25);
      box-shadow:
        inset 0 1px 0 rgba($white, 0.25),
        0 5px 15px rgba($black, 0.1);
    }
    &.active {
      width: 50px;
      border-color: rgba($white, 0.1);
      background:
        linear-gradient(180deg, rgba($white, 0.25), rgba($white, 0.1)),
        rgba($white, 0.25);
      box-shadow:
        inset 0 1px 0 rgba($white, 0.25),
        0 5px 15px rgba($black, 0.1);
    }
  }
  .nav-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    width: 40px;
    height: 40px;
    position: relative;
    overflow: hidden;
    isolation: isolate;
    border: 1px solid rgba($white, 0.1);
    border-radius: 50%;
    background:
      linear-gradient(180deg, rgba($white, 0.1), rgba($white, 0.05) 50%, rgba($white, 0.05)),
      radial-gradient(circle at top left, rgba($white, 0.25), transparent 50%),
      rgba($bg, 0.35);
    box-shadow:
      inset 0 1px 0 rgba($white, 0.25),
      inset 0 -1px 0 rgba($white, 0.1),
      0 10px 20px rgba($black, 0.1);
    -webkit-backdrop-filter: blur(20px) saturate(180%) brightness(1.25);
    backdrop-filter: blur(20px) saturate(180%) brightness(1.25);
    outline: none;
    cursor: pointer;
    transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
    &:hover,
    &:focus-visible {
      border-color: rgba($white, 0.25);
      box-shadow:
        inset 0 1px 0 rgba($white, 0.25),
        inset 0 -1px 0 rgba($white, 0.1),
        0 15px 30px rgba($black, 0.1);
    }
  }
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
  .home-carousel {
    .slide {
      .slide-content {
        padding: 5px 8px 34px;
        gap: 8px;
      }
      .primary-btn {
        min-width: 135px;
        height: 24px;
        border-radius: 5px;
        font-size: 10px;
      }
    }
    .carousel-controls {
      bottom: 5px;
      padding: 3px 5px;
      gap: 5px;
      box-shadow:
        inset 0 1px 0 rgba($white, 0.20),
        inset 0 -1px 0 rgba($white, 0.05),
        0 5px 15px rgba($black, 0.15);
      -webkit-backdrop-filter: blur(15px) saturate(170%) brightness(1.15);
      backdrop-filter: blur(15px) saturate(170%) brightness(1.15);
    }
    .carousel-dot {
      width: 10px;
      height: 3px;
      box-shadow:
        inset 0 1px 0 rgba($white, 0.2),
        0 3px 5px rgba($black, 0.1);
      &.active {
        width: 24px;
      }
    }
    .nav-btn {
      width: 16px;
      height: 16px;
      box-shadow:
        inset 0 1px 0 rgba($white, 0.2),
        inset 0 -1px 0 rgba($white, 0.1),
        0 5px 10px rgba($black, 0.1);
      -webkit-backdrop-filter: blur(10px) saturate(170%) brightness(1.15);
      backdrop-filter: blur(10px) saturate(170%) brightness(1.15);
    }
    .nav-icon {
      width: 8px;
      height: 8px;
    }
  }
}

</style>
