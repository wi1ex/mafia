<template>
  <main class="rules" ref="rulesEl">
    <div class="rules-layout">
      <div class="rules-content">
        <section id="intro" class="hero">
          <div class="hero-content">
            <p class="eyebrow">deceit.games</p>
            <h1>Правила платформы</h1>
            <div class="tags">
              <span class="pill">18+</span>
              <span class="pill">Редакция от 01.08.2026</span>
              <a class="pill docs" href="/files/user-agreement.pdf" target="_blank" rel="noopener noreferrer">Пользовательское соглашение</a>
              <a class="pill docs" href="/files/privacy-policy.pdf" target="_blank" rel="noopener noreferrer">Политика обработки ПД</a>
            </div>
          </div>
        </section>

        <section id="sanctions" class="notice">
          <div class="notice-text">
            <h2>Нотация санкций</h2>
            <p>Конкретный вид санкции, срок и дополнительные меры определяются Администрацией/Модераторами с учетом характера нарушения, повторяемости, последствий и иных обстоятельств.</p>
          </div>
          <div class="notice-list">
            <div class="notice-item notice-item--suspend">
              <span class="notice-item-title">Отстранение — временное отстранение от участия в играх.</span>
              <div class="notice-item-scales" aria-label="Шкала сроков отстранения">
                <div v-for="badge in SUSPEND_SANCTION_BADGES" :key="badge.code" class="notice-item-scale">
                  <span>{{ badge.notation }}</span>
                  <span class="notice-item-badge" :style="{ backgroundColor: badge.backgroundColor, color: badge.textColor }">
                    {{ badge.code }}
                  </span>
                </div>
              </div>
            </div>
            <div class="notice-item notice-item--timeout">
              <span class="notice-item-title">Таймаут — временное ограничение доступа к комнатам и чату.</span>
              <div class="notice-item-scales" aria-label="Шкала сроков таймаута">
                <div v-for="badge in TIMEOUT_SANCTION_BADGES" :key="badge.code" class="notice-item-scale">
                  <span>{{ badge.notation }}</span>
                  <span class="notice-item-badge" :style="{ backgroundColor: badge.backgroundColor, color: badge.textColor }">
                    {{ badge.code }}
                  </span>
                </div>
              </div>
            </div>
            <div class="notice-item notice-item--ban">Бан — вечная блокировка доступа к платформе.</div>
          </div>
        </section>

        <section v-if="settingsStore.sanctionRulesReady" class="rules-grid">
          <article v-for="section in settingsStore.sanctionRules" :id="section.id" :key="section.id" class="rule-card">
            <h3>{{ section.title }}</h3>
            <ul>
              <li v-for="rule in section.rules" :key="rule.text" class="rule-item">
                <span v-if="getRuleSanctionBadge(rule)" class="sanction-badge" :style="{ backgroundColor: getRuleSanctionBadge(rule)?.backgroundColor, color: getRuleSanctionBadge(rule)?.textColor }">
                  {{ getRuleSanctionBadge(rule)?.code }}
                </span>
                <span class="rule-text">{{ rule.text }}</span>
              </li>
            </ul>
          </article>
        </section>
        <p v-else class="rules-state">Загрузка правил…</p>
      </div>

      <aside class="rules-toc" aria-label="Содержание страницы">
        <router-link class="btn-home" :to="{ name: 'home' }" aria-label="На главную">На главную</router-link>
        <div class="toc-card">
          <span class="toc-title">Содержание</span>
          <nav class="toc-links">
            <a v-for="item in tocLinks" :key="item.id" :href="`#${item.id}`" :class="{ active: activeId === item.id }"
               :aria-current="activeId === item.id ? 'location' : undefined" @click="onTocClick($event, item.id)">
              {{ item.label }}
            </a>
          </nav>
        </div>
      </aside>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { SUSPEND_SANCTION_BADGES, TIMEOUT_SANCTION_BADGES, getSanctionBadge, type SanctionRule } from '@/constants/sanctionReasons'
import { useSettingsStore } from '@/store'

type TocItem = {
  id: string
  label: string
}

const settingsStore = useSettingsStore()
const tocLinks = computed<TocItem[]>(() => [
  { id: 'intro', label: 'Введение' },
  { id: 'sanctions', label: 'Нотация санкций' },
  ...settingsStore.sanctionRules.map(({ id, title }) => ({ id, label: title })),
])

function getRuleSanctionBadge(rule: SanctionRule) {
  return getSanctionBadge(rule.badge)
}

const activeId = ref(tocLinks.value[0]?.id ?? '')
const lastId = computed(() => tocLinks.value[tocLinks.value.length - 1]?.id ?? '')
const rulesEl = ref<HTMLElement | null>(null)
let rafId = 0
let sectionEls: HTMLElement[] = []
let scrollTarget: HTMLElement | Window | null = null

function setActive(id: string) {
  if (id && activeId.value !== id) activeId.value = id
}

function onTocClick(event: MouseEvent, id: string) {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  const el = document.getElementById(id)
  if (!el) return
  event.preventDefault()
  setActive(id)
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  el.scrollIntoView({ behavior: prefersReduced ? 'auto' : 'smooth', block: 'start' })
  history.replaceState(null, '', `#${id}`)
}

function collectSections() {
  sectionEls = tocLinks.value
    .map(item => document.getElementById(item.id))
    .filter((el): el is HTMLElement => Boolean(el))
}

function updateActiveFromScroll() {
  if (!sectionEls.length) return
  if (!lastId.value) return
  const cutoff = 120
  let current = sectionEls[0].id
  const container = rulesEl.value
  if (container) {
    const containerRect = container.getBoundingClientRect()
    for (const el of sectionEls) {
      const top = el.getBoundingClientRect().top - containerRect.top
      if (top - cutoff <= 0) {
        current = el.id
      } else {
        break
      }
    }
    const scrollBottom = container.scrollTop + container.clientHeight
    const scrollHeight = container.scrollHeight
    if (scrollBottom >= scrollHeight - 4) current = lastId.value
  } else {
    for (const el of sectionEls) {
      if (el.getBoundingClientRect().top - cutoff <= 0) {
        current = el.id
      } else {
        break
      }
    }
    const scrollBottom = window.scrollY + window.innerHeight
    const docHeight = document.documentElement.scrollHeight
    if (scrollBottom >= docHeight - 4) current = lastId.value
  }
  setActive(current)
}

function onScroll() {
  if (rafId) return
  rafId = window.requestAnimationFrame(() => {
    rafId = 0
    updateActiveFromScroll()
  })
}

onMounted(() => {
  collectSections()
  if (window.location.hash) {
    history.replaceState(null, '', `${window.location.pathname}${window.location.search}`)
  }
  if (rulesEl.value) {
    rulesEl.value.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  } else {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }
  setActive(tocLinks.value[0]?.id ?? '')
  updateActiveFromScroll()
  scrollTarget = rulesEl.value ?? window
  scrollTarget.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', onScroll)
})

watch(tocLinks, async (links) => {
  await nextTick()
  collectSections()
  if (!links.some(link => link.id === activeId.value)) setActive(links[0]?.id ?? '')
  updateActiveFromScroll()
})

onBeforeUnmount(() => {
  if (rafId) window.cancelAnimationFrame(rafId)
  rafId = 0
  sectionEls = []
  if (scrollTarget) scrollTarget.removeEventListener('scroll', onScroll)
  scrollTarget = null
  window.removeEventListener('resize', onScroll)
})
</script>

<style scoped lang="scss">
.rules {
  --sanction-ban-background: #{$red-600};
  --sanction-timeout-background: #{$orange-600};
  --sanction-suspend-background: #{$yellow-600};
  width: 66%;
  margin: 20px auto;
  line-height: 1.5;
  overflow: auto;
  scrollbar-width: none;
  [id] {
    scroll-margin-top: 90px;
  }
  .rules-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 300px;
    gap: 20px;
    align-items: start;
  }
  .rules-state {
    margin: 20px 0;
    color: $neutral-300;
    text-align: center;
  }
  .rules-content {
    display: flex;
    flex-direction: column;
    gap: 20px;
    min-width: 0;
  }
  .rules-toc {
    display: flex;
    position: sticky;
    flex-direction: column;
    align-self: start;
    top: 0;
    gap: 10px;
    .btn-home {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 40px;
      border-radius: 10px;
      background-color: $neutral-100;
      color: $neutral-black;
      text-decoration: none;
      cursor: pointer;
      transition: background-color 0.25s ease-in-out;
      &:hover {
        background-color: $neutral-white;
      }
    }
    .toc-card {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 20px;
      border-radius: 10px;
      background-color: $neutral-800;
      border: 1px solid $neutral-500;
    }
    .toc-title {
      font-size: 12px;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: $neutral-300;
    }
    .toc-links {
      display: flex;
      flex-direction: column;
      gap: 5px;
      a {
        padding: 5px 20px;
        border-radius: 5px;
        border: 1px solid transparent;
        background-color: $neutral-900;
        color: $neutral-100;
        font-size: 14px;
        text-decoration: none;
        transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out, color 0.25s ease-in-out;
        &:hover {
          background-color: $neutral-700;
          border-color: $neutral-500;
          color: $neutral-white;
        }
        &.active {
          background-color: $neutral-700;
          border-color: $orange-500;
          color: $neutral-white;
          box-shadow: inset 10px 0 0 $orange-500;
        }
      }
    }
  }
  .hero {
    position: relative;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
    padding: 20px;
    border-radius: 10px;
    background: linear-gradient(to right, $neutral-700, $neutral-900);
    border: 1px solid $neutral-500;
    overflow: hidden;
    animation: liftIn 0.25s ease-out both;
    &::before,
    &::after {
      content: '';
      position: absolute;
      border-radius: 50%;
      filter: blur(0);
      opacity: 0.5;
    }
    &::before {
      width: 320px;
      height: 320px;
      top: -160px;
      left: -120px;
      background: radial-gradient(circle, $orange-500, transparent 50%);
    }
    &::after {
      width: 400px;
      height: 400px;
      bottom: -200px;
      right: -130px;
      background: radial-gradient(circle, $green-500, transparent 50%);
    }
    .hero-content {
      position: relative;
      z-index: 1;
      display: flex;
      flex-direction: column;
      gap: 10px;
      .eyebrow {
        margin: 0;
        font-size: 18px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: $neutral-300;
      }
      h1 {
        margin: 0;
        font-size: 35px;
        letter-spacing: 1px;
      }
      .tags {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        .pill {
          padding: 5px 15px;
          border-radius: 50px;
          border: 1px solid $neutral-500;
          background-color: $neutral-900;
          color: $neutral-100;
          font-size: 12px;
          letter-spacing: 1px;
          text-transform: uppercase;
          text-decoration: none;
          transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out, color 0.25s ease-in-out;
          &.docs {
            &:hover {
              border-color: $orange-500;
              background-color: $neutral-700;
              color: $neutral-white;
            }
          }
        }
      }
    }
  }
  .rules-grid {
    display: grid;
    grid-template-columns: repeat(1, minmax(0, 1fr));
    gap: 15px;
    .rule-card {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 20px;
      border-radius: 10px;
      background-color: $neutral-800;
      border: 1px solid $neutral-500;
      animation: liftIn 0.25s ease-out both;
      h3 {
        margin: 0;
        font-size: 18px;
        color: $neutral-100;
      }
      p {
        margin: 0;
        color: $neutral-300;
      }
      ul {
        margin: 0;
        padding-left: 0;
        display: grid;
        gap: 5px;
        .rule-item {
          display: flex;
          align-items: flex-start;
          gap: 5px;
          list-style: none;
          color: $neutral-100;
        }
        .sanction-badge {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 3px 5px;
          min-width: 35px;
          border-radius: 10px;
          font-size: 13px;
          font-family: Hauora-Bold;
        }
        .rule-text {
          min-width: 0;
        }
      }
      &:nth-child(2) { animation-delay: 0.15s; }
      &:nth-child(3) { animation-delay: 0.25s; }
      &:nth-child(4) { animation-delay: 0.15s; }
      &:nth-child(5) { animation-delay: 0.25s; }
      &:nth-child(6) { animation-delay: 0.15s; }
    }
  }
  .notice {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
    gap: 20px;
    padding: 20px;
    border-radius: 10px;
    background: linear-gradient(to right, $neutral-800, $neutral-700);
    border: 1px solid $neutral-500;
    animation: liftIn 0.25s ease-out both;
    .notice-text {
      h2 {
        margin: 0 0 10px;
        font-size: 20px;
      }
      p {
        margin: 0;
        color: $neutral-300;
        font-size: 14px;
      }
    }
    .notice-list {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      .notice-item {
        padding: 5px 10px;
        border-radius: 10px;
        background-color: $neutral-900;
        border: 1px solid $neutral-500;
        font-size: 14px;
        color: $neutral-100;
        .notice-item-title {
          display: block;
        }
        .notice-item-scales {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 6px;
          margin-top: 8px;
        }
        .notice-item-scale {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 6px;
          min-width: 0;
          font-size: 12px;
        }
        .notice-item-badge {
          flex: 0 0 38px;
          min-width: 38px;
          padding: 2px 3px;
          border-radius: 3px;
          font-size: 11px;
          font-weight: 700;
          line-height: 16px;
          letter-spacing: 0.02em;
          text-align: center;
        }
      }
      .notice-item--suspend {
        border-color: $yellow-500;
      }
      .notice-item--timeout {
        border-color: $orange-500;
      }
      .notice-item--ban {
        grid-column-start: 1;
        grid-column-end: 3;
        border-color: $red-500;
      }
    }
  }
}

@keyframes liftIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

</style>
