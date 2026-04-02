<template>
  <section class="home-carousel" role="region" aria-roledescription="carousel" aria-label="Информационный блок" tabindex="0"
           @mouseenter="hovered = true" @mouseleave="hovered = false" @focusin="focused = true" @focusout="onFocusOut" @keydown="onKeydown" >
    <div class="carousel-viewport">
      <Transition :name="slideTransitionName" mode="out-in">
        <article v-if="activeIndex === 0" key="install" class="slide slide--install">
          <div class="slide-surface">
            <div class="slide-content">
              <div class="slide-head">
                <span class="slide-badge">
                  <img :src="iconInstall" alt="" aria-hidden="true" />
                  Установить
                </span>
                <span class="slide-index">01/03</span>
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
                <span class="action-note">{{ installActionNote }}</span>
              </div>
            </div>
          </div>
        </article>

        <article v-else-if="activeIndex === 1" key="support" class="slide slide--support">
          <div class="slide-surface">
            <div class="slide-content">
              <div class="slide-head">
                <span class="slide-badge">
                  <img :src="iconCard" alt="" aria-hidden="true" />
                  Поддержать
                </span>
                <span class="slide-index">02/03</span>
              </div>

              <h3 class="slide-copy">Поддержка платформы влияет на темпы её роста</h3>

              <div class="slide-highlight">
                <span class="slide-highlight-value">Твой вклад</span>
                <span class="slide-highlight-label">Помогает удерживать инфраструктуру стабильной и быстрее выпускать новые улучшения</span>
              </div>

              <div class="info-banner info-banner--warm">
                <span class="info-banner-title">На что идёт поддержка</span>
                <p>На хостинг, поддержку сервиса, развитие продукта, улучшение UX и внедрение новых возможностей для платформы.</p>
              </div>

              <div class="slide-actions">
                <a class="primary-btn" :href="supportLink" target="_blank" rel="noopener noreferrer">
                  Поддержать проект
                </a>
                <span class="action-note">Откроется официальный сервис поддержки в Telegram.</span>
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
                  <p>Обсуждение идей по развитию, форматам взаимодействия, интеграциям и новым сценариям использования платформы.</p>
                </div>
              </div>

              <div class="slide-actions">
                <a class="primary-btn" :href="contactsLink" target="_blank" rel="noopener noreferrer">
                  Связаться с командой
                </a>
                <span class="action-note">Откроется аккаунт пользователя в Telegram.</span>
              </div>
            </div>
          </div>
        </article>
      </Transition>

      <div class="carousel-controls">
        <button type="button" class="nav-btn" aria-label="Предыдущий блок" @click="goPrevious(true)">
          <img class="nav-icon nav-icon--prev" :src="iconArrowDown" alt="" aria-hidden="true" />
        </button>

        <button type="button" class="carousel-dot" :class="{ active: activeIndex === 0 }" aria-label="Показать блок установки"
                :aria-current="activeIndex === 0 ? 'true' : undefined" @click="goTo(0, true)" />
        <button type="button" class="carousel-dot" :class="{ active: activeIndex === 1 }" aria-label="Показать блок поддержки"
                :aria-current="activeIndex === 1 ? 'true' : undefined" @click="goTo(1, true)" />
        <button type="button" class="carousel-dot" :class="{ active: activeIndex === 2 }" aria-label="Показать блок контактов"
                :aria-current="activeIndex === 2 ? 'true' : undefined" @click="goTo(2, true)" />

        <button type="button" class="nav-btn" aria-label="Следующий блок" @click="goNext(true)">
          <img class="nav-icon nav-icon--next" :src="iconArrowDown" alt="" aria-hidden="true" />
        </button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { isPwaMode } from '@/services/pwa'

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
const appInstalled = ref(isPwaMode())
const deferredInstallPrompt = ref<BeforeInstallPromptEvent | null>(null)

const supportLink = 'https://t.me/tribute/app?startapp=dCvc'
const contactsLink = 'https://t.me/wi1ex'

let autoplayTimer: number | null = null
let motionQuery: MediaQueryList | null = null

type InstallPromptChoice = {
  outcome: 'accepted' | 'dismissed'
  platform: string
}

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<InstallPromptChoice>
}

const canPromptInstall = computed(() => !appInstalled.value && deferredInstallPrompt.value !== null)
const installButtonDisabled = computed(() => appInstalled.value || !canPromptInstall.value)
const installButtonLabel = computed(() => {
  if (appInstalled.value) return 'Приложение установлено'
  if (canPromptInstall.value) return 'Установить платформу'
  return 'Используйте меню браузера'
})
const installActionNote = computed(() => {
  if (appInstalled.value) return 'Платформа уже установлена на этом устройстве.'
  if (canPromptInstall.value) return 'Откроется системное окно установки браузера.'
  return 'Если ничего не появилось попробуйте добавить вручную.'
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
  const promptEvent = deferredInstallPrompt.value
  if (!promptEvent || appInstalled.value) return
  deferredInstallPrompt.value = null
  try {
    await promptEvent.prompt()
    await promptEvent.userChoice
  } catch {}
}

function onBeforeInstallPrompt(event: Event) {
  event.preventDefault()
  deferredInstallPrompt.value = event as BeforeInstallPromptEvent
  appInstalled.value = false
}

function onAppInstalled() {
  appInstalled.value = true
  deferredInstallPrompt.value = null
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
  window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  window.addEventListener('appinstalled', onAppInstalled)
})

onBeforeUnmount(() => {
  clearAutoplayTimer()
  document.removeEventListener('visibilitychange', onVisibilityChange)
  window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  window.removeEventListener('appinstalled', onAppInstalled)
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
        radial-gradient(circle at top right, rgba($white, 0.1), transparent 34%),
        radial-gradient(circle at left bottom, rgba($grey, 0.25), transparent 36%),
        linear-gradient(145deg, rgba(70, 70, 70, 1), rgba(24, 24, 24, 1));
    }
    &.slide--support::before {
      background:
        radial-gradient(circle at top left, rgba($orange, 0.25), transparent 34%),
        radial-gradient(circle at bottom right, rgba($red, 0.25), transparent 38%),
        linear-gradient(145deg, rgba(76, 52, 34, 1), rgba(28, 18, 14, 1));
    }
    &.slide--contacts::before {
      background:
        radial-gradient(circle at top center, rgba($green, 0.25), transparent 34%),
        radial-gradient(circle at right bottom, rgba($white, 0.1), transparent 38%),
        linear-gradient(145deg, rgba(34, 56, 52, 1), rgba(18, 26, 24, 1));
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
      padding: 15px 15px 90px;
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
      border-radius: 999px;
      font-size: 14px;
      line-height: 1.2;
      background-color: $graphite;
      color: $fg;
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
      color: $white;
      font-size: 24px;
      font-family: Manrope-SemiBold;
      line-height: 1;
    }
    .slide-highlight-label {
      color: $ashy;
      font-size: 12px;
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
        color: $fg;
        font-size: 12px;
        line-height: 1.2;
      }
    }
    .info-banner {
      padding: 15px;
      &.info-banner--warm {
        border-color: rgba($orange, 0.1);
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
      justify-content: space-between;
      margin-top: auto;
    }
    .action-note {
      max-width: 250px;
      text-align: end;
      color: $ashy;
      font-size: 12px;
    }
    .primary-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0 15px;
      min-width: 200px;
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
    padding: 10px 15px;
    gap: 10px;
    border: 1px solid $graphite;
    border-radius: 999px;
    background-color: rgba($graphite, 0.5);
    backdrop-filter: blur(10px);
    transform: translateX(-50%);
    box-shadow: 0 15px 30px rgba($black, 0.25);
    z-index: 5;
  }
  .carousel-dot {
    padding: 0;
    width: 20px;
    height: 10px;
    border: none;
    border-radius: 999px;
    background-color: $lead;
    outline: none;
    cursor: pointer;
    transition: width 0.25s ease-in-out, background-color 0.25s ease-in-out;
    &:hover,
    &:focus-visible {
      background-color: $grey;
    }
    &.active {
      width: 50px;
      background-color: $fg;
    }
  }
  .nav-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    width: 40px;
    height: 40px;
    border: 1px solid $lead;
    border-radius: 50%;
    background: linear-gradient(180deg, rgba($lead, 0.9), rgba($graphite, 0.9));
    outline: none;
    cursor: pointer;
    transition: background-color 0.25s ease-in-out;
    &:hover,
    &:focus-visible {
      background-color: $grey;
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
</style>
