<template>
  <section class="home-carousel" role="region" aria-roledescription="carousel" aria-label="Информационный блок" tabindex="0"
           @mouseenter="hovered = true" @mouseleave="hovered = false" @focusin="focused = true" @focusout="onFocusOut" @keydown="onKeydown" >
    <div class="carousel-viewport">
      <Transition :name="slideTransitionName" mode="out-in">
        <article v-if="activeIndex === 0" key="support" class="slide slide--support">
          <div class="slide-surface">
            <div class="slide-content">
              <div class="slide-head">
                <span class="slide-badge">
                  <img :src="iconCard" alt="" aria-hidden="true" />
                  Поддержать
                </span>
                <span class="slide-index">01/03</span>
              </div>

              <h3 class="slide-copy">Поддержка платформы влияет на темпы её роста</h3>

              <div class="slide-highlight">
                <span class="slide-highlight-value">Твой вклад</span>
                <span class="slide-highlight-label">Поддерживает инфраструктуру стабильной и ускоряет развитие платформы</span>
              </div>

              <div class="info-banner">
                <span class="info-banner-title">Приятные бонусы</span>
                <p>Кастомизация профиля (GIF-аватары, выбор цвета и иконки профиля), скрытые комнаты без зрителей и трансляции в качестве 1080p.</p>
              </div>

              <div class="slide-actions">
                <button type="button" class="primary-btn" @click="openSupportModal">
                  Поддержать платформу
                </button>
              </div>
            </div>
          </div>
        </article>

        <article v-else-if="activeIndex === 1" key="install" class="slide slide--install">
          <div class="slide-surface">
            <div class="slide-content">
              <div class="slide-head">
                <span class="slide-badge">
                  <img :src="iconInstall" alt="" aria-hidden="true" />
                  Установить
                </span>
                <span class="slide-index">02/03</span>
              </div>

              <h3 class="slide-copy">Откройте платформу как отдельное приложение</h3>

              <div class="slide-highlight">
                <span class="slide-highlight-value">Установка в 2 клика</span>
                <span class="slide-highlight-label">Для запуска платформы на весь экран Вашего устройства</span>
              </div>

              <div class="slide-grid">
                <div class="info-card">
                  <span class="info-card-title">Android — Chrome</span>
                  <p>Откройте меню браузера и выберите установку приложения или добавление на главный экран.</p>
                </div>
                <div class="info-card">
                  <span class="info-card-title">iPhone/iPad — Safari</span>
                  <p>Через меню «Поделиться» добавьте сайт на экран Домой и открывайте платформу как отдельное приложение.</p>
                </div>
              </div>

              <div class="slide-actions">
                <button type="button" class="primary-btn" :disabled="installButtonDisabled" @click="openInstall">
                  {{ installButtonLabel }}
                </button>
              </div>
            </div>
          </div>
        </article>

        <article v-else key="contacts" class="slide slide--contacts">
          <div class="slide-surface">
            <div class="slide-content">
              <div class="slide-head">
                <span class="slide-badge">
                  <img :src="iconMail" alt="" aria-hidden="true" />
                  Обратная связь
                </span>
                <span class="slide-index">03/03</span>
              </div>

              <h3 class="slide-copy">Свяжитесь с командой разработки</h3>

              <div class="slide-highlight">
                <span class="slide-highlight-value">Прямая коммуникация</span>
                <span class="slide-highlight-label">Для Ваших идей, замечаний и рабочих вопросов по платформе</span>
              </div>

              <div class="slide-grid">
                <div class="info-card">
                  <span class="info-card-title">Для пользователей</span>
                  <p>Вопросы по работе сайта, предложения по улучшениям, замечания по интерфейсу и функциональности платформы.</p>
                </div>
                <div class="info-card">
                  <span class="info-card-title">Для партнёров и организаторов</span>
                  <p>Обсуждение идей по развитию, интеграциям и новым сценариям использования платформы.</p>
                </div>
              </div>

              <div class="slide-actions">
                <a class="primary-btn" :href="contactsLink" target="_blank" rel="noopener noreferrer">
                  Связаться с командой
                </a>
              </div>
            </div>
          </div>
        </article>
      </Transition>

      <div class="carousel-controls">
        <button type="button" class="nav-btn" aria-label="Предыдущий блок" @click="goPrevious(true)">
          <img class="nav-icon nav-icon--prev" :src="iconArrowDown" alt="" aria-hidden="true" />
        </button>

        <button type="button" class="carousel-dot" :class="{ active: activeIndex === 0 }" aria-label="Показать блок поддержки"
                :aria-current="activeIndex === 0 ? 'true' : undefined" @click="goTo(0, true)" />
        <button type="button" class="carousel-dot" :class="{ active: activeIndex === 1 }" aria-label="Показать блок установки"
                :aria-current="activeIndex === 1 ? 'true' : undefined" @click="goTo(1, true)" />
        <button type="button" class="carousel-dot" :class="{ active: activeIndex === 2 }" aria-label="Показать блок контактов"
                :aria-current="activeIndex === 2 ? 'true' : undefined" @click="goTo(2, true)" />

        <button type="button" class="nav-btn" aria-label="Следующий блок" @click="goNext(true)">
          <img class="nav-icon nav-icon--next" :src="iconArrowDown" alt="" aria-hidden="true" />
        </button>
      </div>
    </div>
    <SupportSiteModal v-model:open="supportModalOpen" @select="onSupportSiteSelect" />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { requestPwaInstall, usePwaInstallState } from '@/services/pwa'
import { useAuthStore } from '@/store'
import SupportSiteModal from '@/components/SupportSiteModal.vue'

import iconArrowDown from '@/assets/svg/arrowDown.svg'
import iconCard from '@/assets/svg/card.svg'
import iconInstall from '@/assets/svg/install.svg'
import iconMail from '@/assets/svg/mail.svg'

const AUTOPLAY_DELAY_MS = 10000
const SLIDE_COUNT = 3

const activeIndex = ref(0)
const slideDirection = ref<1 | -1>(1)
const hovered = ref(false)
const focused = ref(false)
const documentHidden = ref(false)
const prefersReducedMotion = ref(false)
const manualInstallHintVisible = ref(false)
const supportModalOpen = ref(false)
const pwaInstall = usePwaInstallState()
const auth = useAuthStore()

const contactsLink = 'https://t.me/wi1ex'

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
const isPaused = computed(() => hovered.value || focused.value || documentHidden.value || prefersReducedMotion.value || supportModalOpen.value)

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

function openSupportModal() {
  supportModalOpen.value = true
}

function onSupportSiteSelect(site: { id: string; name: string; url: string }) {
  if (!auth.isAuthed) return
  void api.post('/users/support_link_click', {
    source: 'home_info_carousel',
    site_id: site.id,
    site_name: site.name,
    url: site.url,
  }).catch(() => {})
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
    &::before {
      content: '';
      position: absolute;
      inset: 0;
    }
    &.slide--install::before {
      background:
        radial-gradient(circle at top left, rgba($orange, 0.25), transparent 35%),
        radial-gradient(circle at bottom right, rgba($red, 0.25), transparent 35%),
        linear-gradient(145deg, rgba(75, 50, 25, 1), rgba(15, 15, 15, 1));
    }
    &.slide--support::before {
      background:
        radial-gradient(circle at top center, rgba(10, 250, 150, 0.25), transparent 35%),
        radial-gradient(circle at right bottom, rgba($white, 0.1), transparent 35%),
        linear-gradient(145deg, rgb(50, 100, 100), rgba(15, 15, 15, 1));
    }
    &.slide--contacts::before {
      background:
        radial-gradient(circle at top right, rgba($white, 0.1), transparent 35%),
        radial-gradient(circle at left bottom, rgba($orange, 0.25), transparent 35%),
        linear-gradient(145deg, rgba(100, 60, 80, 1), rgba(60, 60, 80, 1));
    }
    .slide-surface {
      position: absolute;
      inset: 0;
      background:
        linear-gradient(180deg, rgba($white, 0.1), rgba($bg, 0.25)),
        linear-gradient(180deg, rgba($dark, 0.5), rgba($bg, 0.25));
      backdrop-filter: blur(10px);
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
    }
    .slide-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .slide-badge,
    .slide-index {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      padding: 5px 10px;
      position: relative;
      overflow: hidden;
      isolation: isolate;
      border-radius: 999px;
      border: 1px solid rgba($white, 0.1);
      font-size: 14px;
      line-height: 1.2;
      background:
        linear-gradient(180deg, rgba($white, 0.05), rgba($white, 0.03) 50%, rgba($white, 0.03)),
        radial-gradient(circle at top left, rgba($white, 1), transparent 5%),
        radial-gradient(circle at bottom right, rgba($white, 0.05), transparent 50%),
        rgba($bg, 0.15);
      box-shadow:
        inset 0 1px 0 rgba($white, 0.25),
        inset 0 -1px 0 rgba($white, 0.1),
        0 10px 30px rgba($black, 0.2);
      -webkit-backdrop-filter: blur(15px) saturate(180%) brightness(1.1);
      backdrop-filter: blur(15px) saturate(180%) brightness(1.1);
      color: $fg;
      text-shadow: 0 1px 2px rgba($black, 0.25);
      img {
        width: 20px;
        height: 20px;
      }
    }
    .slide-copy {
      margin: 0;
      color: $fg;
      font-size: 20px;
      font-family: Manrope-SemiBold;
    }
    .slide-highlight {
      display: flex;
      flex-direction: column;
      gap: 5px;
      padding: 15px;
      border: 1px solid $lead;
      border-radius: 15px;
      background: linear-gradient(180deg, rgba($white, 0.1), rgba($black, 0.1));
    }
    .slide-highlight-value {
      color: $fg;
      font-size: 24px;
      font-family: Manrope-SemiBold;
      line-height: 1;
    }
    .slide-highlight-label {
      color: $ashy;
      font-size: 14px;
      line-height: 1.2;
    }
    .slide-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 15px;
    }
    .info-card,
    .info-banner {
      display: flex;
      flex-direction: column;
      gap: 5px;
      padding: 15px;
      border: 1px solid $lead;
      border-radius: 15px;
      background: linear-gradient(180deg, rgba($white, 0.1), rgba($black, 0.1));
      p {
        margin: 0;
        color: $ashy;
        font-size: 14px;
        line-height: 1.2;
      }
    }
    .info-card-title,
    .info-banner-title {
      color: $fg;
      font-size: 16px;
      font-family: Manrope-SemiBold;
      line-height: 1.2;
    }
    .slide-actions {
      display: flex;
      align-items: center;
      justify-content: center;
      margin-top: auto;
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
      .slide-badge,
      .slide-index {
        padding: 3px 5px;
        gap: 3px;
        font-size: 8px;
        box-shadow:
          inset 0 1px 0 rgba($white, 0.2),
          inset 0 -1px 0 rgba($white, 0.05),
          0 5px 15px rgba($black, 0.15);
        -webkit-backdrop-filter: blur(10px) saturate(170%) brightness(1.1);
        backdrop-filter: blur(10px) saturate(170%) brightness(1.1);
        img {
          width: 12px;
          height: 12px;
        }
      }
      .slide-copy {
        font-size: 10px;
      }
      .slide-highlight {
        padding: 8px;
        gap: 3px;
        border-radius: 10px;
      }
      .slide-highlight-value {
        font-size: 14px;
      }
      .slide-highlight-label {
        font-size: 7px;
      }
      .slide-grid {
        gap: 10px;
      }
      .info-card,
      .info-banner {
        padding: 8px;
        gap: 3px;
        border-radius: 10px;
        p {
          font-size: 7px;
        }
      }
      .info-card-title,
      .info-banner-title {
        font-size: 10px;
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
