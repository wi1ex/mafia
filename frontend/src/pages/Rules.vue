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
              <span class="pill">Редакция от 06.10.2026</span>
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
            <div class="notice-item notice-item--ban">Бан — постоянная полная блокировка доступа к платформе без возможности его восстановления.</div>
          </div>
        </section>

        <section v-if="settingsStore.sanctionRules.length" class="rules-grid">
          <article v-for="section in settingsStore.sanctionRules" :id="section.id" :key="section.id" class="rule-card">
            <h3>{{ section.title }}</h3>
            <ul>
              <li v-for="(rule, ruleIndex) in section.rules" :key="`${section.id}-${ruleIndex}`" class="rule-item">
                <span v-if="getRuleSanctionBadge(rule)" class="sanction-badge" :style="{ backgroundColor: getRuleSanctionBadge(rule)?.backgroundColor, color: getRuleSanctionBadge(rule)?.textColor }">
                  {{ getRuleSanctionBadge(rule)?.code }}
                </span>
                <span class="rule-text">{{ rule.text }}</span>
              </li>
            </ul>
          </article>
        </section>
        <p v-else class="rules-state">{{ rulesStateText }}</p>
        <section id="scoring" class="scoring-intro">
          <h2>6. Скоринг</h2>
          <div v-if="scoringLoadFailed" class="scoring-state" role="alert">
            <p>Не удалось загрузить баллы. Условия доступны ниже.</p>
            <UiButton variant="white" size="low" text="Повторить загрузку" @click="loadScoring" />
          </div>
          <p v-else-if="!scoringValues" role="status">Загрузка актуальных баллов…</p>

          <section v-for="(section, index) in SCORING_SECTIONS" :id="section.id" :key="section.id" class="scoring-section" :aria-labelledby="`${section.id}-title`">
            <header class="scoring-section-header">
              <span class="scoring-number" aria-hidden="true">{{ String(index + 1).padStart(2, '0') }}</span>
              <div>
                <h3 :id="`${section.id}-title`">{{ section.title }}</h3>
                <p>{{ section.description }}</p>
              </div>
            </header>
            <div class="scoring-grid">
              <article v-for="rule in section.rules" :key="rule.key" class="scoring-tile" :class="scoreTone(rule.key)">
                <div class="scoring-tile-top">
                  <h4>{{ rule.title }}</h4>
                  <div class="scoring-value">
                    <strong>{{ formatScore(rule.key) }}</strong>
                  </div>
                </div>
                <p>{{ rule.description }}</p>
                <p v-if="rule.key === 'farewell_red_correct' || rule.key === 'farewell_black_correct'">
                  После ночного убийства: {{ formatScore(rule.key) }}.
                  Если заголосован, в том числе в подъёме: {{ formatVotedFarewellScore(rule.key) }}.
                </p>
              </article>
            </div>
          </section>
        </section>
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
import { api } from '@/services/axios'
import UiButton from '@/components/UiButton.vue'
interface ScoringRule {
  key: string
  title: string
  description: string
}

interface ScoringSection {
  id: string
  title: string
  description: string
  rules: ScoringRule[]
}

const rule = (key: string, title: string, description: string): ScoringRule => ({ key, title, description })
const nominationConditions = 'В списке кандидатов перед голосованием только один чёрный, и он реально уходит по голосованию в этот день. За столом больше четырёх игроков, после выставляющего в порядке речей нет красных.'
const obviousColors = 'Оценки считаются отдельно за каждого указанного игрока. Очевидные для автора цвета не приносят баллов. Если указан цвет, отличный от очевидного, оценка всё равно учитывается.'

const SCORING_SECTIONS: ScoringSection[] = [
  {
    id: 'scoring-limits', title: 'Ограничение доп. баллов',
    description: 'Сначала все дополнительные баллы и штрафы суммируются, затем сумма ограничивается указанными границами.',
    rules: [
      rule('additional_points_min', 'Минимум суммы', 'Если итоговая сумма дополнительных баллов ниже этого значения, применяется нижняя граница.'),
      rule('additional_points_max', 'Максимум суммы', 'Если итоговая сумма дополнительных баллов выше этого значения, применяется верхняя граница.'),
    ],
  },
  {
    id: 'scoring-removals', title: 'Удаления и фолы',
    description: 'Штраф «на поражение» применяется, когда именно уход приводит к поражению команды; для удаления по фолам также учитывается отметка ППК.',
    rules: [
      rule('fourth_foul', 'Удаление по фолам', 'Игрок получает четвёртый обычный фол и удаляется.'),
      rule('fourth_foul_lost', 'Удаление по фолам на поражение', 'Четвёртый фол приводит к удалению на поражение команды или с отметкой ППК.'),
      rule('tech_foul', 'Технический фол', 'За каждый из первых двух технических фолов.'),
      rule('second_tech_foul_lost', 'Удаление по тех. фолам на поражение', 'За 2й технический фол, если удаление приводит к поражению команды или отмечено ППК.'),
      rule('suicide', 'Самоубийство', 'За уход из игры с причиной «самоубийство».'),
      rule('suicide_lost', 'Самоубийство на поражение', 'За уход с причиной «самоубийство», непосредственно приводящий к поражению команды.'),
    ],
  },
  {
    id: 'scoring-best-move', title: 'Лучший ход',
    description: 'Для красного игрока — мирного или шерифа — с записанным лучшим ходом. Учитывается число названных чёрных.',
    rules: [0, 1, 2, 3].map(count => rule(`best_move_black_${count}`, `${count} из 3`, `В записанном лучшем ходе ${count === 0 ? 'не назван ни один чёрный игрок' : `верно ${count === 1 ? 'назван 1 чёрный игрок' : `названы ${count} чёрных игрока`}`}.`)),
  },
  {
    id: 'scoring-shooting', title: 'Отстрелы',
    description: 'Учитываются результат ночной стрельбы и индивидуальные выстрелы.',
    rules: [
      rule('night_shoot_miss', 'Промахнувшийся чёрный', 'При трёх живых чёрных двое выбрали одну цель, а третий — другую или не выстрелил. Если убийство не состоялось, штраф получает третий. При двух живых чёрных или отсутствии пары одинаковых выстрелов этот штраф не применяется.'),
      rule('night_shoot_miss_terminal', 'Промах при гарантированной победе', 'Если успешный отстрел принёс бы чёрным победу, штраф получает единственный живой чёрный при промахе либо один из трёх, не совпавший с выстрелами двух остальных. Отсутствие выстрела тоже учитывается. При двух живых чёрных не применяется.'),
      rule('night_self_shot_black_win_1', 'Самострел в 1-ю ночь', 'Компенсация чёрному игроку, убитому в первую ночь, если чёрные в итоге победили.'),
      rule('night_self_shot_black_win_2', 'Самострел во 2-ю ночь', 'Компенсация чёрному игроку, убитому во вторую ночь, если чёрные в итоге победили.'),
    ],
  },
  {
    id: 'scoring-checks', title: 'Проверки',
    description: 'Фактические ночные проверки и проверки, записанные ведущим в версиях, оцениваются по разным условиям.',
    rules: [
      rule('sheriff_two_unobvious_black_checks', 'Шериф проверил двух чёрных подряд', 'Две подряд чёрные проверки шерифа, которые на момент каждой проверки не были записаны как вскрывшиеся шерифы.'),
      rule('don_missed_sheriff_two_checks', 'Дон не нашёл шерифа', 'Дон сделал проверки и в первую, и во вторую ночь, но не нашел шерифа.'),
      rule('citizen_false_check', 'Мирный вскрылся с неверной проверкой', 'Один раз за игру обычному мирному, если в его записанной версии как шерифа в любой момент игры была хотя бы одна проверка с цветом, не соответствующим реальной роли.'),
      rule('citizen_active_version_after_death', 'Мирный оставил активное вскрытие после ухода', 'Один раз обычному мирному, если чёрные победили, его версия активна на момент завершения игры, а после его ухода успело начаться и закончиться хотя бы одно голосование.'),
      rule('sheriff_false_check_black_win', 'Шериф оставил неверную проверку', 'При победе чёрных: в последней сохранённой версии шерифа осталась хотя бы одна проверка с неверным цветом. Штраф применяется один раз.'),
    ],
  },
  {
    id: 'scoring-nominations', title: 'Выставления', description: nominationConditions,
    rules: [
      rule('nomination_red_last_hope', 'Последняя надежда', 'Красный — мирный или шериф — выставил единственного чёрного кандидата при условиях выше. Цвет выставленного не должен быть очевиден для автора по версиям.'),
      rule('nomination_black_prevents_black_win', 'Чёрный выставил чёрного', 'Чёрный игрок выставил единственного чёрного кандидата при условиях выше и тем самым сорвал гарантированную победу своей команды при уходе красного.'),
    ],
  },
  {
    id: 'scoring-voting', title: 'Голосование и исход игры',
    description: 'Правила слома требуют отметки ведущего.',
    rules: [
      rule('vote_black_unchecked_nine_ten', 'Уход чёрного без проверки при 9–10х', 'Со 2го дня: штраф чёрному, покинувшему игру через голосование, если на момент ухода ни в одной активной версии ведущего нет чёрной проверки этого игрока.'),
      rule('vote_opponent_team', 'Заголосовал игрока другой команды', 'Начиная со 2го дня — каждому, кто заголосовал игрока принадлежащего другой команде. В 1й день и при подъёме это правило не применяется.'),
      rule('vote_sheriff_nine_red', 'Штраф за вывод шерифа при 9–10х', 'Со 2го дня: красному, голосовавшему в шерифа, который единолично ушёл по голосованию.'),
      rule('vote_sheriff_nine_black', 'Бонус за вывод шерифа при 9–10х', 'Со 2го дня: чёрному, голосовавшему в шерифа, который единолично ушёл по голосованию. Дополнительный бонус, который складывается с баллами за вывод игрока противоположной команды.'),
      rule('vote_red_day_one_compensation', 'Красный заголосован в 1й день', 'Компенсация красному, который ушёл в 1й день единственным заголосованным игроком.'),
      rule('vote_red_terminal', 'Голосование на поражение', 'Каждому красному, голосовавшему в красного, чей единоличный уход по голосованию привёл к победе чёрных на 2в2 или 1в1. Не применяется при подъёме.'),
      rule('vote_red_terminal_3v3', 'Голосование на 3в3', 'Каждому красному, голосовавшему в красного, чей единоличный уход по голосованию привёл к победе чёрных на 3в3. Заменяет обычный штраф за голосование на поражение.'),
      rule('vote_lift_same_team', 'Подъём игроков своей команды', 'Каждому проголосовавшему за подъём двух или более игроков, если все поднимаемые принадлежат его команде. При смешанном составе поднимаемых не применяется.'),
      rule('vote_lift_opponent_team', 'Подъём игроков другой команды', 'Каждому проголосовавшему за подъём двух или более игроков, если все поднимаемые принадлежат противоположной команде. При смешанном составе поднимаемых не применяется.'),
      rule('vote_break_red_to_red', 'Слом в красного на поражение', 'Отмеченный ведущим красный голосовал в другого красного, единолично ушедшего по голосованию в 1й день. Сам отмеченный ушёл на поражение красных через голосование или подъём во 2й день либо по фолам, техфолам или самоубийству в 1-2й день. Также применяется, если 2й день не наступил из-за победы чёрных.'),
      rule('vote_break_red_to_red_safe', 'Слом в красного без ухода на поражение', 'Отмеченный ведущим красный голосовал в другого красного, единолично ушедшего по голосованию в 1й день. Сам отмеченный по итогам следующего дня должен остаться за столом.'),
      rule('vote_break_red_to_sheriff_extra', 'Штраф за слом в шерифа', 'Если при подтверждённом сломе красного в красного выведенная в 1й день цель — шериф, этот штраф добавляется к одному из двух штрафов.'),
      rule('vote_break_red_to_black', 'Слом в чёрного будучи красным', 'Отмеченный ведущим красный голосовал в чёрного, единолично ушедшего в 1й день. Отмеченный не должен уйти по голосованию во 2й день, включая подъём, или по фолам, тех. фолам либо самоубийству в 1-2й день.'),
      rule('vote_break_black_to_sheriff', 'Слом в шерифа будучи чёрным', 'Отмеченный ведущим чёрный голосовал в шерифа, единолично ушедшего по голосованию в 1й день.'),
      rule('black_win_3v3', 'Победа чёрных 3в3', 'Каждому чёрному при итоговой победе чёрных на 3в3.'),
      rule('black_win_2v2_1v1_alive', 'Победа чёрным за столом', 'Чёрному, оставшемуся в игре при победе чёрных на 2в2 или 1в1.'),
      rule('black_win_2v2_1v1_dead', 'Победа чёрным будучи мертвым', 'Выбывшему чёрному при победе его команды.'),
      rule('black_day_under_seven', 'Проход в круг при 3–6х', 'Каждому живому чёрному в начале каждого дня, когда в игре осталось от 3 до 6 игроков включительно. Может начисляться несколько раз за игру.'),
    ],
  },
  {
    id: 'scoring-opinions', title: 'Ночные мнения', description: `Игрок красной команды может указать цвет любого живого игрока только один раз за игру. ${obviousColors}`,
    rules: [
      rule('night_opinion_correct', 'Верный цвет', 'Красному за каждого игрока, чей цвет правильно указан в ночном мнении, если этот выбор не повторяет очевидный для автора цвет.'),
      rule('night_opinion_wrong', 'Неверный цвет', 'Красному за каждого игрока, чей цвет не совпал с реальным, если выбор не повторяет очевидный для автора цвет.'),
      rule('night_opinion_black_named_red', 'Чёрного оставили красным', 'Чёрному игроку за каждый учитываемый выбор красного, назвавшего его красным в ночном мнении.'),
    ],
  },
  {
    id: 'scoring-farewells', title: 'Завещания', description: `Учитываются завещания красных игроков — мирных и шерифа.  ${obviousColors}`,
    rules: [
      rule('farewell_red_correct', 'Верно указан красный', 'Красному завещания за каждого красного, оставленного красным, с учётом общего исключения очевидных цветов.'),
      rule('farewell_red_wrong', 'Красный указан чёрным', 'Красному завещания за каждого красного, оставленного чёрным, с учётом общего исключения очевидных цветов.'),
      rule('farewell_black_correct', 'Верно указан чёрный', 'Красному завещания за каждого чёрного, оставленного чёрным, с учётом общего исключения очевидных цветов.'),
      rule('farewell_black_wrong', 'Чёрный указан красным', 'Красному завещания за каждого чёрного, оставленного красным, с учётом общего исключения очевидных цветов.'),
      rule('farewell_black_named_red', 'Чёрного оставили красным', 'Чёрному игроку за каждый учитываемый выбор красного, назвавшего его красным в завещании, если этот чёрный не записан как вскрывшийся шериф в версиях на момент завещания.'),
      rule('farewell_claimant_black_named_red', 'Чёрного оставили приоритетной версией', 'Чёрному игроку за каждый учитываемый выбор красного, назвавшего его красным в завещании, если этот чёрный записан как вскрывшийся шериф в версиях на момент завещания.'),
    ],
  },
]

type TocItem = {
  id: string
  label: string
}

const settingsStore = useSettingsStore()
const scoringValues = ref<Record<string, number> | null>(null)
const scoringLoadFailed = ref(false)

async function loadScoring() {
  scoringLoadFailed.value = false
  try {
    const { data } = await api.get('/admin/scoring/public', { __skipAuth: true })
    const values: Record<string, number> = {}
    for (const { rules } of SCORING_SECTIONS) {
      for (const { key } of rules) {
        const value = data?.[key]
        if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error('invalid_scoring_response')
        values[key] = value
      }
    }
    const deduction = data?.farewell_voted_correct_deduction
    if (typeof deduction !== 'number' || !Number.isFinite(deduction)) throw new Error('invalid_scoring_response')
    values.farewell_voted_correct_deduction = deduction
    scoringValues.value = values
  } catch {
    scoringLoadFailed.value = true
  }
}

function scoreValue(key: string): number | null {
  return scoringValues.value?.[key] ?? null
}

function scoreTone(key: string): string {
  const value = scoreValue(key)
  if (key.startsWith('additional_points_') || value === null || value === 0) return 'neutral'
  return value > 0 ? 'positive' : 'negative'
}

function formatScoreValue(value: number | null): string {
  if (value === null) return '—'
  return `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatScore(key: string): string {
  return formatScoreValue(scoreValue(key))
}

function formatVotedFarewellScore(key: string): string {
  const value = scoreValue(key)
  const deduction = scoreValue('farewell_voted_correct_deduction')
  return formatScoreValue(value === null || deduction === null
    ? null
    : (Math.round(value * 100) - Math.round(deduction * 100)) / 100)
}

const tocLinks = computed<TocItem[]>(() => [
  { id: 'intro', label: 'Введение' },
  { id: 'sanctions', label: 'Нотация санкций' },
  ...settingsStore.sanctionRules.map(({ id, title }) => ({ id, label: title })),
  { id: 'scoring', label: '6. Скоринг' },
])
const rulesStateText = computed(() => (
  settingsStore.sanctionRulesLoadFailed ? 'Не удалось загрузить правила.' : 'Загрузка правил…'
))

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
  void loadScoring()
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
  flex: 1;
  min-height: 0;
  box-sizing: border-box;
  width: 100%;
  padding: 30px 40px;
  color: $neutral-100;
  font-family: Hauora-Regular;
  line-height: 1.5;
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: $soft-purple-700 transparent;
  .rules-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 260px;
    align-items: start;
    width: 70%;
    margin: 0 auto;
    gap: 10px;
    .rules-content {
      display: flex;
      flex-direction: column;
      min-width: 0;
      gap: 10px;
      user-select: text;
      .hero {
        padding: 24px;
        border-radius: 24px;
        background-color: $soft-purple-900;
        scroll-margin-top: 24px;
        .hero-content {
          display: flex;
          flex-direction: column;
          gap: 16px;
          .eyebrow {
            margin: 0;
            color: $neutral-300;
            font-size: 14px;
            line-height: 20px;
          }
          h1 {
            margin: 0;
            color: $neutral-white;
            font-family: Involve-Medium;
            font-weight: 500;
            font-size: 24px;
            line-height: 26px;
            letter-spacing: -0.48px;
          }
          .tags {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            .pill {
              padding: 8px 12px;
              border-radius: 12px;
              background-color: $soft-purple-800;
              color: $neutral-100;
              font-size: 14px;
              line-height: 20px;
              text-decoration: none;
              &.docs {
                color: $green-200;
                transition: color 0.25s ease-in-out, background-color 0.25s ease-in-out;
                &:hover {
                  background-color: $soft-purple-700;
                  color: $neutral-white;
                }
                &:focus-visible {
                  outline: 2px solid $green-500;
                  outline-offset: 3px;
                }
              }
            }
          }
        }
      }
      .notice {
        display: flex;
        flex-direction: column;
        padding: 24px;
        gap: 20px;
        border-radius: 24px;
        background-color: $soft-purple-900;
        scroll-margin-top: 24px;
        .notice-text {
          h2 {
            margin: 0 0 12px;
            color: $neutral-white;
            font-family: Involve-Medium;
            font-weight: 500;
            font-size: 24px;
            line-height: 26px;
            letter-spacing: -0.48px;
          }
          p {
            max-width: 960px;
            margin: 0;
            color: $neutral-300;
            font-size: 14px;
            line-height: 22px;
          }
        }
        .notice-list {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px;
          .notice-item {
            min-width: 0;
            padding: 16px;
            border-radius: 20px;
            background-color: $soft-purple-800;
            font-size: 14px;
            line-height: 20px;
            &--ban {
              grid-column: 1 / -1;
            }
            .notice-item-title {
              display: block;
              color: $neutral-100;
            }
            .notice-item-scales {
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              margin-top: 16px;
              gap: 10px 100px;
              .notice-item-scale {
                display: flex;
                align-items: center;
                justify-content: space-between;
                min-width: 0;
                gap: 10px;
                > span {
                  color: $neutral-300;
                }
                .notice-item-badge {
                  flex: 0 0 40px;
                  padding: 4px 6px;
                  border-radius: 8px;
                  font-family: Hauora-Bold;
                  font-size: 12px;
                  line-height: 16px;
                  text-align: center;
                }
              }
            }
          }
        }
      }
      .rules-grid {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 10px;
        .rule-card {
          display: flex;
          flex-direction: column;
          min-width: 0;
          padding: 24px;
          gap: 20px;
          border-radius: 24px;
          background-color: $soft-purple-900;
          scroll-margin-top: 24px;
          h3 {
            margin: 0;
            color: $neutral-white;
            font-family: Involve-Medium;
            font-weight: 500;
            font-size: 24px;
            line-height: 26px;
            letter-spacing: -0.48px;
          }
          ul {
            display: grid;
            margin: 0;
            padding: 0;
            gap: 10px;
            .rule-item {
              display: flex;
              align-items: center;
              padding: 8px 16px;
              gap: 12px;
              border-radius: 20px;
              background-color: $soft-purple-800;
              list-style: none;
              .sanction-badge {
                display: flex;
                align-items: center;
                justify-content: center;
                flex: 0 0 40px;
                padding: 4px 6px;
                border-radius: 8px;
                font-family: Hauora-Bold;
                font-size: 12px;
                line-height: 16px;
              }
              .rule-text {
                min-width: 0;
                font-size: 14px;
              }
            }
          }
        }
      }
      .rules-state {
        margin: 0;
        padding: 24px;
        border-radius: 24px;
        background-color: $soft-purple-900;
        color: $neutral-300;
        text-align: center;
      }
      .scoring-intro {
        display: flex;
        flex-direction: column;
        min-width: 0;
        padding: 24px;
        gap: 24px;
        border-radius: 24px;
        background-color: $soft-purple-900;
        scroll-margin-top: 24px;
        > h2 {
          margin: 0;
          color: $neutral-white;
          font-family: Involve-Medium;
          font-weight: 500;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        > p {
          margin: 0;
          color: $neutral-300;
        }
        .scoring-state {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px;
          gap: 16px;
          border-radius: 20px;
          background-color: $soft-purple-800;
          p {
            margin: 0;
            color: $neutral-300;
            font-size: 14px;
            line-height: 20px;
          }
        }
        .scoring-section {
          min-width: 0;
          scroll-margin-top: 24px;
          .scoring-section-header {
            display: flex;
            align-items: flex-start;
            margin-bottom: 16px;
            gap: 14px;
            .scoring-number {
              display: grid;
              place-items: center;
              flex: 0 0 40px;
              height: 40px;
              border-radius: 12px;
              background-color: $soft-purple-800;
              color: $green-200;
              font-family: Involve-Medium;
              font-size: 16px;
              font-variant-numeric: tabular-nums;
            }
            > div {
              min-width: 0;
              h3 {
                margin: 0 0 6px;
                color: $neutral-white;
                font-family: Involve-Medium;
                font-weight: 500;
                font-size: 20px;
                line-height: 24px;
                letter-spacing: -0.4px;
              }
              p {
                margin: 0;
                color: $neutral-300;
                font-size: 14px;
                line-height: 22px;
              }
            }
          }
          .scoring-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
            .scoring-tile {
              min-width: 0;
              padding: 20px;
              border-radius: 20px;
              background-color: $soft-purple-800;
              --score-color: #{$neutral-100};
              &.positive {
                --score-color: #{$green-500};
              }
              &.negative {
                --score-color: #{$red-300};
              }
              .scoring-tile-top {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 16px;
                h4 {
                  flex: 1;
                  min-width: 0;
                  margin: 0;
                  color: $neutral-white;
                  font-family: Hauora-Medium;
                  font-weight: 500;
                  font-size: 16px;
                  line-height: 22px;
                }
                .scoring-value {
                  flex-shrink: 0;
                  strong {
                    color: var(--score-color);
                    font-family: Involve-Medium;
                    font-weight: 500;
                    font-size: 24px;
                    line-height: 26px;
                    font-variant-numeric: tabular-nums;
                  }
                }
              }
              > p {
                margin: 12px 0 0;
                color: $neutral-300;
                font-size: 14px;
                line-height: 22px;
              }
            }
          }
        }
      }
    }
    .rules-toc {
      display: flex;
      position: sticky;
      flex-direction: column;
      align-self: start;
      top: 0;
      min-width: 0;
      gap: 10px;
      .btn-home {
        display: flex;
        align-items: center;
        justify-content: center;
        box-sizing: border-box;
        height: 40px;
        border-radius: 12px;
        background-color: $neutral-100;
        color: $neutral-black;
        font-family: Hauora-Medium;
        font-size: 16px;
        line-height: 20px;
        text-decoration: none;
        transition: background-color 0.25s ease-in-out;
        &:hover {
          background-color: $neutral-white;
        }
        &:focus-visible {
          outline: 2px solid $green-500;
          outline-offset: 3px;
        }
      }
      .toc-card {
        display: flex;
        flex-direction: column;
        padding: 24px;
        gap: 20px;
        border-radius: 24px;
        background-color: $soft-purple-900;
        .toc-title {
          color: $neutral-white;
          font-family: Involve-Medium;
          font-size: 20px;
          line-height: 24px;
          letter-spacing: -0.4px;
        }
        .toc-links {
          display: flex;
          flex-direction: column;
          max-height: calc(var(--app-viewport-height, 100dvh) - 280px);
          gap: 6px;
          overflow-y: auto;
          scrollbar-width: thin;
          scrollbar-color: $soft-purple-700 transparent;
          a {
            padding: 12px;
            border-radius: 12px;
            background-color: $soft-purple-800;
            color: $neutral-300;
            font-size: 14px;
            line-height: 20px;
            text-decoration: none;
            transition: background-color 0.25s ease-in-out, color 0.25s ease-in-out;
            &:hover {
              background-color: $soft-purple-700;
              color: $neutral-white;
            }
            &.active {
              background-color: rgba($green-500, 0.12);
              color: $green-500;
            }
            &:focus-visible {
              outline: 2px solid $green-500;
              outline-offset: -2px;
            }
          }
        }
      }
    }
  }
}
</style>
