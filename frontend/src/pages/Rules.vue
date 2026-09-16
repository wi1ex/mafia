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
              <span class="pill">Редакция от 01.09.2026</span>
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
          <p class="scoring-eyebrow">Рейтинговые игры</p>
          <h2>6. Скоринг</h2>

          <div v-if="scoringLoadFailed" class="scoring-state" role="alert">
            <p>Не удалось загрузить баллы. Условия доступны ниже.</p>
            <button type="button" class="scoring-retry" @click="loadScoring">Повторить загрузку</button>
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
    id: 'scoring-opinions', title: 'Ночные мнения', description: `Учитываются ночные мнения красных игроков — мирных и шерифа. ${obviousColors}`,
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
    -webkit-user-select: text;
    user-select: text;
  }
  .scoring-intro {
    padding: 24px;
    border: 1px solid $orange-500;
    border-radius: 14px;
    background: linear-gradient(120deg, $neutral-700, $neutral-900);
    h2 {
      margin: 4px 0 12px;
      font-size: 24px;
    }
    p {
      margin: 10px 0 0;
      color: $neutral-100;
    }
    .scoring-eyebrow {
      margin: 0;
      color: $orange-300;
      font-size: 12px;
      letter-spacing: 1.5px;
      text-transform: uppercase;
    }
  }
  .scoring-retry {
    margin-top: 10px;
    padding: 8px 14px;
    border: 1px solid $neutral-500;
    border-radius: 8px;
    background: $neutral-800;
    color: $neutral-100;
    cursor: pointer;
    &:hover {
      background: $neutral-700;
    }
  }
  .scoring-section {
    min-width: 0;
    padding-top: 12px;
  }
  .scoring-section-header {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 16px;
    h3 {
      margin: 0 0 6px;
      font-size: 21px;
      color: $neutral-100;
    }
    p {
      margin: 0;
      color: $neutral-300;
      font-size: 14px;
    }
  }
  .scoring-number {
    flex-shrink: 0;
    display: grid;
    place-items: center;
    width: 38px;
    height: 38px;
    border: 1px solid $neutral-500;
    border-radius: 10px;
    background: $neutral-800;
    color: $orange-300;
    font-variant-numeric: tabular-nums;
  }
  .scoring-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }
  .scoring-tile {
    padding: 18px;
    border: 1px solid $neutral-600;
    border-top: 3px solid $neutral-400;
    border-radius: 12px;
    background: $neutral-800;
    p {
      margin: 14px 0 0;
      color: $neutral-200;
      font-size: 14px;
      line-height: 1.65;
    }
    &.positive {
      border-top-color: $green-400;
      .scoring-value strong {
        color: $green-300;
      }
    }
    &.negative {
      border-top-color: $red-400;
      .scoring-value strong {
        color: $red-300;
      }
    }
  }
  .scoring-tile-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    h4 {
      flex: 1 1 130px;
      margin: 0;
      font-size: 16px;
      color: $neutral-100;
    }
  }
  .scoring-value {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    flex-shrink: 0;
    strong {
      font-size: 26px;
      line-height: 1.15;
      font-variant-numeric: tabular-nums;
      color: $neutral-100;
    }
    span {
      margin-top: 4px;
      font-size: 11px;
      color: $neutral-300;
    }
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
      max-height: calc(100dvh - 210px);
      overflow-y: auto;
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
        font-size: 24px;
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
        font-size: 24px;
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
