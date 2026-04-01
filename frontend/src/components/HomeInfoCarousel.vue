<template>
  <section
    class="home-carousel"
    role="region"
    aria-roledescription="carousel"
    aria-label="Информационные блоки лобби"
    tabindex="0"
    @mouseenter="hovered = true"
    @mouseleave="hovered = false"
    @focusin="focused = true"
    @focusout="onFocusOut"
    @keydown="onKeydown"
  >
    <div class="carousel-topbar">
      <div class="carousel-heading">
        <span class="carousel-eyebrow">Сервисные окна</span>
        <span class="carousel-title">Нужные действия без поиска в хедере</span>
      </div>
      <span class="carousel-state" :class="{ 'carousel-state--paused': isPaused }">
        {{ autoplayStateLabel }}
      </span>
    </div>

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

              <div class="slide-copy">
                <span class="slide-kicker">DECEIT.games / Быстрый запуск</span>
                <h3>Откройте платформу как отдельное приложение</h3>
                <p>Без адресной строки, лишних элементов браузера и постоянного ручного поиска сайта. Один жест и вы уже в игре.</p>
              </div>

              <div class="slide-highlight">
                <span class="slide-highlight-value">1 тап</span>
                <span class="slide-highlight-label">До запуска платформы с рабочего стола, панели задач или главного экрана</span>
              </div>

              <div class="slide-chip-row">
                <span class="slide-chip">Полный экран</span>
                <span class="slide-chip">Android</span>
                <span class="slide-chip">iPhone / iPad</span>
                <span class="slide-chip">Desktop</span>
              </div>

              <div class="slide-grid">
                <div class="info-card">
                  <span class="info-card-title">Android / Chrome</span>
                  <p>Откройте меню браузера и выберите установку приложения или добавление на главный экран.</p>
                </div>
                <div class="info-card">
                  <span class="info-card-title">iPhone / iPad</span>
                  <p>Через меню «Поделиться» добавьте сайт на экран Домой и открывайте платформу как отдельный app-entry.</p>
                </div>
              </div>

              <ul class="slide-points">
                <li>Подходит для мобильных устройств и настольных браузеров.</li>
                <li>Установка не требует App Store, Google Play или отдельной регистрации.</li>
                <li>Внутри окна уже собрана компактная пошаговая инструкция.</li>
              </ul>

              <div class="slide-actions">
                <button type="button" class="primary-btn" @click="openInstall">
                  Установить платформу
                </button>
                <span class="action-note">Откроется встроенное окно с инструкцией по установке.</span>
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

              <div class="slide-copy">
                <span class="slide-kicker">DECEIT.games / Развитие проекта</span>
                <h3>Поддержка платформы напрямую влияет на её темп роста</h3>
                <p>Через этот блок пользователь попадает в окно поддержки и дальше на официальный сервис, где можно помочь проекту без лишних шагов.</p>
              </div>

              <div class="slide-highlight">
                <span class="slide-highlight-value">Твой вклад</span>
                <span class="slide-highlight-label">Помогает удерживать инфраструктуру стабильной и быстрее выпускать новые улучшения</span>
              </div>

              <div class="slide-chip-row">
                <span class="slide-chip">Стабильность</span>
                <span class="slide-chip">Развитие</span>
                <span class="slide-chip">Новые функции</span>
                <span class="slide-chip">Инфраструктура</span>
              </div>

              <div class="info-banner info-banner--warm">
                <span class="info-banner-title">На что идёт поддержка</span>
                <p>На хостинг, поддержку сервиса, развитие продукта, улучшение UX и внедрение новых возможностей для платформы.</p>
              </div>

              <div class="slide-grid">
                <div class="info-card">
                  <span class="info-card-title">Прозрачный переход</span>
                  <p>Пользователь сначала видит понятный контекст в окне, а уже потом переходит на официальный сервис поддержки.</p>
                </div>
                <div class="info-card">
                  <span class="info-card-title">Нативный сценарий</span>
                  <p>Поддержка встроена в главный экран и ощущается как часть продукта, а не как внешний случайный элемент.</p>
                </div>
              </div>

              <ul class="slide-points">
                <li>Окно открывается без ухода с главной страницы.</li>
                <li>Внутри остаётся знакомая кнопка перехода на сервис поддержки.</li>
                <li>Позже этот блок можно расширить спецпредложениями, акциями или анонсами.</li>
              </ul>

              <div class="slide-actions">
                <button type="button" class="primary-btn" @click="openSupport">
                  Поддержать проект
                </button>
                <span class="action-note">Откроется окно поддержки с переходом на официальный сервис.</span>
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
                  Контакты
                </span>
                <span class="slide-index">03/03</span>
              </div>

              <div class="slide-copy">
                <span class="slide-kicker">DECEIT.games / Прямая связь</span>
                <h3>Свяжитесь с командой без поиска нужного контакта</h3>
                <p>Вопросы по работе платформы, предложения по улучшениям, идеи по развитию и обратная связь теперь доступны прямо из главной карусели.</p>
              </div>

              <div class="slide-highlight">
                <span class="slide-highlight-value">TG</span>
                <span class="slide-highlight-label">Прямая точка входа для обратной связи, идей, замечаний и рабочих вопросов по платформе</span>
              </div>

              <div class="slide-chip-row">
                <span class="slide-chip">Идеи</span>
                <span class="slide-chip">Ошибки</span>
                <span class="slide-chip">Предложения</span>
                <span class="slide-chip">Сотрудничество</span>
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

              <ul class="slide-points">
                <li>Не нужно искать контакт в хедере, меню или футере.</li>
                <li>Окно обратной связи открывается прямо из главной карусели.</li>
                <li>Позже сюда можно добавить регламент ответа и дополнительные каналы связи.</li>
              </ul>

              <div class="slide-actions">
                <button type="button" class="primary-btn" @click="openContacts">
                  Связаться с командой
                </button>
                <span class="action-note">Откроется окно с переходом в Telegram.</span>
              </div>
            </div>
          </div>
        </article>
      </Transition>
    </div>

    <div class="carousel-controls">
      <div class="carousel-dots" role="group" aria-label="Навигация по информационным блокам">
        <button type="button" class="carousel-dot" :class="{ active: activeIndex === 0 }" aria-label="Показать блок установки"
                :aria-current="activeIndex === 0 ? 'true' : undefined" @click="goTo(0, true)" />
        <button type="button" class="carousel-dot" :class="{ active: activeIndex === 1 }" aria-label="Показать блок поддержки"
                :aria-current="activeIndex === 1 ? 'true' : undefined" @click="goTo(1, true)" />
        <button type="button" class="carousel-dot" :class="{ active: activeIndex === 2 }" aria-label="Показать блок контактов"
                :aria-current="activeIndex === 2 ? 'true' : undefined" @click="goTo(2, true)" />
      </div>

      <div class="carousel-nav">
        <button type="button" class="nav-btn" aria-label="Предыдущий блок" @click="goPrevious(true)">
          <img class="nav-icon nav-icon--prev" :src="iconArrowDown" alt="" aria-hidden="true" />
        </button>
        <button type="button" class="nav-btn" aria-label="Следующий блок" @click="goNext(true)">
          <img class="nav-icon nav-icon--next" :src="iconArrowDown" alt="" aria-hidden="true" />
        </button>
      </div>
    </div>

    <AppModal v-model:open="installOpen" />
    <SupportModal v-model:open="supportOpen" :support-link="supportLink" />
    <ContactsModal v-model:open="contactsOpen" :contacts-link="contactsLink" />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import AppModal from '@/components/AppModal.vue'
import ContactsModal from '@/components/ContactsModal.vue'
import SupportModal from '@/components/SupportModal.vue'

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
const installOpen = ref(false)
const supportOpen = ref(false)
const contactsOpen = ref(false)

const supportLink = 'https://t.me/tribute/app?startapp=dCvc'
const contactsLink = 'https://t.me/wi1ex'

let autoplayTimer: number | null = null
let motionQuery: MediaQueryList | null = null

const hasOpenModal = computed(() => installOpen.value || supportOpen.value || contactsOpen.value)
const slideTransitionName = computed(() => slideDirection.value > 0 ? 'carousel-slide-forward' : 'carousel-slide-backward')
const isPaused = computed(() => hovered.value || focused.value || documentHidden.value || prefersReducedMotion.value || hasOpenModal.value)
const autoplayStateLabel = computed(() => {
  if (hasOpenModal.value) return 'Окно открыто'
  if (prefersReducedMotion.value) return 'Авто выключено'
  if (documentHidden.value) return 'Вкладка неактивна'
  if (hovered.value || focused.value) return 'Пауза'
  return `Авто ${AUTOPLAY_DELAY_MS / 1000}с`
})

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

function closeAllModals() {
  installOpen.value = false
  supportOpen.value = false
  contactsOpen.value = false
}

function openInstall() {
  closeAllModals()
  installOpen.value = true
}

function openSupport() {
  closeAllModals()
  supportOpen.value = true
}

function openContacts() {
  closeAllModals()
  contactsOpen.value = true
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
  padding: 10px;
  gap: 10px;
  box-sizing: border-box;
  outline: none;
  .carousel-topbar {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
  }
  .carousel-heading {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .carousel-eyebrow {
    color: $grey;
    font-size: 112px;
    text-transform: uppercase;
  }
  .carousel-title {
    color: $fg;
    font-size: 18px;
    font-family: Manrope-SemiBold;
    line-height: 1.2;
  }
  .carousel-state {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 5px 10px;
    min-width: 100px;
    border: 1px solid $grey;
    border-radius: 999px;
    background: linear-gradient(135deg, rgba($lead, 0.95), rgba($graphite, 0.85));
    color: $grey;
    font-size: 12px;
    line-height: 1.2;
    white-space: nowrap;
    &.carousel-state--paused {
      border-color: rgba($orange, 0.25);
      color: $fg;
    }
  }
  .carousel-viewport {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
  }
  .slide {
    position: relative;
    width: 100%;
    height: 100%;
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 15px 30px rgba($black, 0.25);
    &::before {
      content: '';
      position: absolute;
      inset: 0;
      border-radius: inherit;
    }
    &.slide--install::before {
      background:
        radial-gradient(circle at top right, rgba($white, 0.12), transparent 34%),
        radial-gradient(circle at left bottom, rgba($grey, 0.18), transparent 36%),
        linear-gradient(145deg, rgba(70, 70, 70, 0.98), rgba(24, 24, 24, 0.98));
    }
    &.slide--support::before {
      background:
        radial-gradient(circle at top left, rgba($orange, 0.26), transparent 34%),
        radial-gradient(circle at bottom right, rgba($red, 0.18), transparent 38%),
        linear-gradient(145deg, rgba(76, 52, 34, 0.98), rgba(28, 18, 14, 0.98));
    }
    &.slide--contacts::before {
      background:
        radial-gradient(circle at top center, rgba($green, 0.2), transparent 34%),
        radial-gradient(circle at right bottom, rgba($white, 0.08), transparent 38%),
        linear-gradient(145deg, rgba(34, 56, 52, 0.98), rgba(18, 26, 24, 0.98));
    }
    .slide-surface {
      position: absolute;
      inset: 1px;
      border: 1px solid $grey;
      border-radius: 20px;
      background:
        linear-gradient(180deg, rgba($white, 0.04), rgba($bg, 0.2)),
        linear-gradient(180deg, rgba($dark, 0.46), rgba($bg, 0.18));
      backdrop-filter: blur(10px);
    }
    .slide-content {
      display: flex;
      position: relative;
      flex-direction: column;
      height: 100%;
      padding: 20px;
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
      gap: 10px;
    }
    .slide-badge,
    .slide-index {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      padding: 5px 10px;
      border-radius: 999px;
      font-size: 12px;
      line-height: 1.2;
    }
    .slide-badge {
      background-color: $dark;
      color: $fg;
      border: 1px solid $grey;
      img {
        width: 16px;
        height: 16px;
      }
    }
    .slide-index {
      background-color: $lead;
      color: $fg;
    }
    .slide-copy {
      display: flex;
      flex-direction: column;
      gap: 10px;
      .slide-kicker {
        color: $ashy;
        font-size: 12px;
        text-transform: uppercase;
      }
      h3 {
        margin: 0;
        color: $fg;
        font-size: 28px;
        font-family: Manrope-SemiBold;
        line-height: 1.2;
      }
      p {
        margin: 0;
        color: $fg;
        font-size: 14px;
        line-height: 1.2;
      }
    }
    .slide-highlight {
      display: flex;
      flex-direction: column;
      gap: 5px;
      padding: 15px;
      border: 1px solid $lead;
      border-radius: 20px;
      background: linear-gradient(180deg, rgba($white, 0.06), rgba($black, 0.12));
    }
    .slide-highlight-value {
      color: $white;
      font-size: 46px;
      font-family: Manrope-SemiBold;
      line-height: 1;
    }
    .slide-highlight-label {
      color: $ashy;
      font-size: 12px;
      line-height: 1.2;
    }
    .slide-chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .slide-chip {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 5px 10px;
      border: 1px solid $lead;
      border-radius: 999px;
      background: $lead;
      color: $fg;
      font-size: 12px;
      line-height: 1;
      white-space: nowrap;
    }
    .slide-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .info-card,
    .info-banner {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 15px;
      border: 1px solid $grey;
      border-radius: 15px;
      background: linear-gradient(180deg, rgba($white, 0.05), rgba($black, 0.12));
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
        border-color: rgba($orange, 0.25);
        box-shadow: inset 0 0 0 1px rgba($orange, 0.05);
      }
    }
    .info-card-title,
    .info-banner-title {
      color: $fg;
      font-size: 14px;
      font-family: Manrope-SemiBold;
      line-height: 1.2;
    }
    .slide-points {
      display: grid;
      margin: 0;
      padding: 0;
      gap: 10px;
      list-style: none;
      li {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        color: $fg;
        font-size: 12px;
        line-height: 1.2;
        &::before {
          content: '';
          margin-top: 5px;
          width: 5px;
          min-width: 5px;
          height: 5px;
          border-radius: 50%;
          background-color: $fg;
          box-shadow: 0 0 15px $grey;
        }
      }
    }
    .slide-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 15px;
      margin-top: auto;
    }
    .action-note {
      max-width: 220px;
      color: $ashy;
      font-size: 12px;
      line-height: 1.2;
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
      background: linear-gradient(135deg, rgba($fg, 1), rgba($white, 0.92));
      color: $bg;
      font-size: 16px;
      font-family: Manrope-SemiBold;
      line-height: 1;
      cursor: pointer;
      transition: transform 0.25s ease-in-out, opacity 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
      &:hover,
      &:focus-visible {
        transform: translateY(-1px);
        box-shadow: 0 15px 30px rgba($black, 0.25);
        outline: none;
      }
    }
  }
  .carousel-controls {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .carousel-dots {
    display: flex;
    align-items: center;
    gap: 10px;
    .carousel-dot {
      padding: 0;
      width: 30px;
      height: 10px;
      border: none;
      border-radius: 999px;
      background-color: $lead;
      cursor: pointer;
      transition: width 0.25s ease-in-out, background-color 0.25s ease-in-out;
      &:hover,
      &:focus-visible {
        background-color: $ashy;
        outline: none;
      }
      &.active {
        width: 60px;
        background-color: $fg;
      }
    }
  }
  .carousel-nav {
    display: flex;
    align-items: center;
    gap: 10px;
    .nav-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 40px;
      height: 40px;
      border: 1px solid $lead;
      border-radius: 50%;
      background: linear-gradient(180deg, rgba($lead, 0.96), rgba($graphite, 0.92));
      cursor: pointer;
      transition: transform 0.25s ease-in-out, border-color 0.25s ease-in-out;
      &:hover,
      &:focus-visible {
        transform: translateY(-1px);
        border-color: $lead;
        outline: none;
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
  transform: translateX(25px);
}

.carousel-slide-forward-leave-to,
.carousel-slide-backward-enter-from {
  opacity: 0;
  transform: translateX(-25px);
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
