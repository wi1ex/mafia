<template>
  <section class="home-carousel" role="region" aria-roledescription="carousel" aria-label="Информационная карусель" tabindex="0" :class="{ 'is-paused': isPaused }"
           :style="carouselProgressStyle" @mouseenter="hovered = true" @mouseleave="hovered = false" @focusin="focused = true" @focusout="onFocusOut" @keydown="onKeydown" >
    <Transition :name="slideTransitionName">
      <article v-if="activeIndex === 0" key="slide-1" class="slide slide-one">
        <img class="background-image" :src="imageSlide1" alt="" aria-hidden="true" />
      </article>

      <article v-else-if="activeIndex === 1" key="slide-2" class="slide slide-two">
        <img class="background-image" :src="imageSlide2" alt="" aria-hidden="true" />
        <div class="slide-div">
          <div class="slide-top">
            <span class="slide-title">Стриминг</span>
            <UiTooltip
              text="Платформа для тех, кто хочет не только играть. Общайтесь, смотрите фильмы,
              проводите стримы и собирайте своё сообщество в одном месте. Бесплатно, без ограничений
              по времени и без необходимости переключаться между разными сервисами."
              placement="bottom-left"
            />
          </div>
        </div>
      </article>

      <article v-else-if="activeIndex === 2" key="slide-3" class="slide slide-three">
        <img class="background-image" :src="imageSlide3" alt="" aria-hidden="true" />
        <div class="slide-div">
          <div class="slide-top">
            <span class="slide-title">Статистика</span>
            <UiTooltip
              text="Каждая партия влияет на ваш прогресс. Изучайте статистику,
              зарабатывайте достижения, повышайте рейтинг и наблюдайте, как растёт ваш уровень игры.
              Все результаты сохраняются автоматически и доступны в любое время."
              placement="bottom-left"
            />
          </div>
        </div>
      </article>

      <article v-else-if="activeIndex === 3" key="slide-4" class="slide slide-four">
        <img class="background-image" :src="imageSlide4" alt="" aria-hidden="true" />
        <div class="slide-div">
          <div class="slide-top">
            <span class="slide-title">Комьюнити</span>
            <UiTooltip
              text="Игра — это только начало. Общайтесь в общем чате, находите единомышленников,
              собирайте команды для новых партий и знакомьтесь с людьми, которые разделяют ваши интересы.
              Здесь формируется настоящее игровое сообщество."
              placement="bottom-left"
            />
          </div>
        </div>
      </article>

      <article v-else key="install" class="slide slide-five">
        <img class="background-image" :src="imageSlide5" alt="" aria-hidden="true" />
        <div class="slide-div">
          <div class="slide-top">
            <span class="slide-title">Web App</span>
            <UiTooltip
              text="Платформу можно установить на смартфон и запускать как обычное приложение.
              После установки она появится на главном экране устройства, будет открываться
              в отдельном окне и обеспечит быстрый доступ. Android (Chrome): откройте меню браузера
              и выберите «Установить приложение» или «Добавить на главный экран».
              iPhone/iPad (Safari): нажмите кнопку «Поделиться» и выберите «На экран Домой»."
              placement="bottom-left"
            />
          </div>
          <div class="slide-bottom">
            <UiButton
              class="slide-btn"
              size="small"
              :text="installButtonLabel"
              :disabled="installButtonDisabled"
              @click="openInstall"
            />
          </div>
        </div>
      </article>
    </Transition>

    <div class="carousel-controls">
      <button type="button" class="nav-btn" aria-label="Предыдущий блок" @click="goPrevious(true)">
        <UiIcon class="nav-icon nav-icon--prev" :icon="iconArrowDown" />
      </button>

      <div class="carousel-dots">
        <span v-for="index in SLIDE_COUNT" :key="index" class="carousel-dot" :class="{ active: activeIndex === index - 1 }" aria-hidden="true" />
      </div>

      <button type="button" class="nav-btn" aria-label="Следующий блок" @click="goNext(true)">
        <UiIcon class="nav-icon nav-icon--next" :icon="iconArrowDown" />
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { requestPwaInstall, usePwaInstallState } from '@/services/pwa'

import UiTooltip from '@/components/UiTooltip.vue'
import UiButton from '@/components/UiButton.vue'
import UiIcon from '@/components/UiIcon.vue'

import iconArrowDown from '@/assets/svg/iconArrowDown.svg'

import imageSlide1 from '@/assets/images/carousel-image1.png'
import imageSlide2 from '@/assets/images/carousel-image2.png'
import imageSlide3 from '@/assets/images/carousel-image3.png'
import imageSlide4 from '@/assets/images/carousel-image4.png'
import imageSlide5 from '@/assets/images/carousel-image5.png'

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
  if (pwaInstall.installed) return 'Установлено'
  if (manualInstallHintVisible.value && !canPromptInstall.value) return 'Используйте меню браузера'
  if (canPromptInstall.value) return 'Установить'
  return 'Установить'
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
  overflow: hidden;
  isolation: isolate;
  .slide {
    display: flex;
    position: absolute;
    left: 0;
    top: 0;
    padding: 24px 24px 88px;
    width: calc(100% - 48px);
    height: calc(100% - 112px);
    border-radius: 24px;
    z-index: 1;
    will-change: transform;
    .background-image {
      position: absolute;
      left: 0;
      top: 0;
      width: 607px;
      height: 510px;
      border-radius: 24px;
    }
    .slide-div {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      justify-content: space-between;
      width: 100%;
      height: 100%;
      z-index: 5;
      .slide-top {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        width: 100%;
        .slide-title {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 8px 12px;
          border-radius: 12px;
          background:
            linear-gradient(-45deg, #ffffff1c 0%, #ffffff03 50%, #0000003d 100%),
            linear-gradient(135deg, #ffffff21 0%, #ffffff00 100%), #ffffff00;
          backdrop-filter: blur(4px) saturate(135%) contrast(105%);
          box-shadow:
            inset -1px -1px 1px -1px $neutral-white,
            inset 1px 1px 1px -1px $neutral-white;
          color: $neutral-300;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 16px;
          letter-spacing: -0.32px;
        }
      }
      .slide-bottom {
        display: flex;
      }
    }
    &.slide-three {
      background-color: rgba(20, 29, 33, 1);
      .background-image {
        height: 421px;
      }
    }
    &.slide-five {
      background: linear-gradient(180deg, rgba(17, 18, 27, 0.00) 52.18%, rgba(17, 18, 27, 0.30) 100%), #151621;
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
      background: linear-gradient(261deg, $soft-purple-800 0%, $green-700 100%);
      cursor: pointer;
      position: relative;
      overflow: hidden;
      isolation: isolate;
      &::after {
        content: '';
        position: absolute;
        inset: 0;
        border-radius: inherit;
        background: linear-gradient(261deg, $green-700 0%, $soft-purple-800 100%);
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.25s ease-in-out;
        z-index: 0;
      }
      &:not(:disabled):hover,
      &:not(:disabled):focus-visible,
      &:not(:disabled):active {
        &::after {
          opacity: 1;
        }
      }
      .nav-icon {
        position: relative;
        z-index: 2;
        --ui-icon-width: 24px;
        --ui-icon-height: 24px;
        --ui-icon-color: #{$neutral-white};
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
  transition: transform 1s cubic-bezier(0.25, 1, 0.50, 1);
}

.carousel-slide-forward-enter-active,
.carousel-slide-backward-enter-active {
  z-index: 3;
}

.carousel-slide-forward-leave-active,
.carousel-slide-backward-leave-active {
  z-index: 2;
}

.carousel-slide-forward-enter-from {
  transform: translateX(100%);
}

.carousel-slide-forward-leave-to {
  transform: translateX(-50%);
}

.carousel-slide-backward-enter-from {
  transform: translateX(-100%);
}

.carousel-slide-backward-leave-to {
  transform: translateX(50%);
}

.carousel-slide-forward-enter-to,
.carousel-slide-forward-leave-from,
.carousel-slide-backward-enter-to,
.carousel-slide-backward-leave-from {
  transform: translateX(0);
}

</style>
