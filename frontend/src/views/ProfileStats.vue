<template>
  <div class="stats-tab">
    <div class="stats-head">
      <h2 class="tab-title">Статистика</h2>
      <div class="stats-filters">
        <UiDropdown
          id="profile-stats-mode"
          aria-label="Режим игр"
          size="low"
          v-model="selectedMode"
          class="stats-season-dropdown"
          :options="modeOptions"
        />
        <UiDropdown
          id="profile-stats-season"
          aria-label="Сезон"
          size="low"
          v-model="selectedSeason"
          class="stats-season-dropdown"
          :options="seasonOptions"
        />
      </div>
    </div>

    <div v-if="loading && !loaded" class="state">Загрузка...</div>
    <div v-else-if="error" class="state state-danger">
      <span>{{ error }}</span>
    </div>

    <div v-else class="stats-layout">
      <div class="overview">
        <article class="result-card">
          <h3>Результаты игр</h3>
          <div class="results-grid">
            <div class="result-ring" :style="overviewRingStyle">
              <div class="result-center">
                <span>Всего игр</span>
                <strong>{{ formatInt(totalFinishedGames) }}</strong>
                <div class="result-legend">
                  <div v-for="item in overviewSegments" :key="item.key" class="legend-row">
                    <span class="legend-dot" :class="item.key" :title="item.label"></span>
                    <span class="legend-label">{{ item.label }}</span>
                    <strong class="legend-pct">{{ formatPctWithGames(item.percent, item.count) }}</strong>
                  </div>
                </div>
              </div>
            </div>
            <div class="role-rings">
              <article v-for="item in roleRingItems" :key="item.key" class="role-ring-card">
                <span class="role-name">{{ item.label }}</span>
                <div class="role-result-ring" :style="item.style">
                  <div class="role-result-center">
                    <img class="role-title-icon" :src="item.icon" :alt="item.label" />
                    <strong>{{ formatInt(item.games) }}</strong>
                    <div class="result-legend role-legend">
                      <div v-for="segment in item.segments" :key="segment.key" class="legend-row">
                        <span class="legend-dot" :class="segment.key" :title="segment.label"></span>
                        <strong class="legend-pct">{{ formatPctWithGames(segment.percent, segment.count) }}</strong>
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            </div>
          </div>
        </article>

        <section class="block">
          <h3>Совместные игры</h3>
          <p class="section-hint">Топ-5 игроков, с которыми вы играли чаще всего</p>
          <div v-if="game.top_players.length === 0" class="state state-inline">Пока нет данных</div>
          <ol v-else class="rank-list">
            <li v-for="(player, idx) in game.top_players" :key="player.id" class="rank-row">
              <div class="rank-top">
                <span class="rank-pos">#{{ idx + 1 }}</span>
                <span class="rank-name">{{ player.username || `user${player.id}` }}</span>
                <strong class="rank-val">{{ formatInt(player.games_together) }}</strong>
              </div>
              <div class="rank-bar">
                <span :style="{ width: `${barPct(player.games_together, topTogetherMax)}%` }"></span>
              </div>
            </li>
          </ol>
        </section>
      </div>

      <section class="block">
        <h3>Лучший ход</h3>
        <div class="best-move">
          <article class="metric-card">
            <span>Количество ПУ</span>
            <strong>{{ formatInt(game.best_move.first_killed_total) }}</strong>
          </article>
          <div class="best-bars">
            <div v-for="item in bestMoveItems" :key="item.key" class="best-row">
              <span class="best-label">{{ item.label }}</span>
              <div class="best-bar">
                <span :style="{ width: `${barPct(item.value, bestMoveMax)}%` }"></span>
              </div>
              <strong>{{ formatInt(item.value) }}</strong>
            </div>
          </div>
        </div>
      </section>

      <section class="block">
        <h3>Игровые показатели</h3>
        <div class="extra-grid">
          <article class="metric-card">
            <span>Средний доп. балл</span>
            <strong>{{ game.average_additional_points.toFixed(2) }} ({{ formatGames(game.rating_games) }})</strong>
          </article>
          <article class="metric-card">
            <span>Достоверность завещаний</span>
            <strong>{{ formatFarewellSuccess(game.farewell_success_percent, game.farewell_total_count) }}</strong>
          </article>
          <article class="metric-card">
            <span>Заголосован в 1-2 день</span>
            <strong>{{ formatPct(game.vote_leave_day12_percent) }}</strong>
          </article>
          <article class="metric-card">
            <span>Проголосовал на поражение</span>
            <strong>{{ formatTimes(game.vote_for_red_on_black_win_count) }}</strong>
          </article>
          <article class="metric-card">
            <span>Снял Дона/Шерифа в 1-2 день (черный)</span>
            <strong>{{ formatDonSheriffSplit(game.vote_out_don_day12_black_count, game.vote_out_sheriff_day12_black_count) }}</strong>
          </article>
          <article class="metric-card">
            <span>Снял Дона/Шерифа в 1-2 день (мирный)</span>
            <strong>{{ formatDonSheriffSplit(game.vote_out_don_day12_citizen_count, game.vote_out_sheriff_day12_citizen_count) }}</strong>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { useSettingsStore } from '@/store'
import UiDropdown from '@/components/UiDropdown.vue'

import iconRoleCitizen from '@/assets/svg/iconRoleCitizen.svg'
import iconRoleMafia from '@/assets/svg/iconRoleMafia.svg'
import iconRoleDon from '@/assets/svg/iconRoleDon.svg'
import iconRoleSheriff from '@/assets/svg/iconRoleSheriff.svg'

type UserTopPlayer = {
  id: number
  username?: string | null
  games_together: number
}

type UserRoleStats = {
  games: number
  wins: number
}

type UserBestMoveStats = {
  first_killed_total: number
  marks_black_0: number
  marks_black_1: number
  marks_black_2: number
  marks_black_3: number
}

type UserGameStats = {
  games_played: number
  games_won: number
  vote_leave_day12_percent: number
  vote_out_don_day12_black_count: number
  vote_out_sheriff_day12_black_count: number
  vote_out_don_day12_citizen_count: number
  vote_out_sheriff_day12_citizen_count: number
  vote_for_red_on_black_win_count: number
  farewell_success_percent: number
  farewell_correct_count: number
  farewell_total_count: number
  average_additional_points: number
  rating_games: number
  role_citizen: UserRoleStats
  role_sheriff: UserRoleStats
  role_don: UserRoleStats
  role_mafia: UserRoleStats
  best_move: UserBestMoveStats
  top_players: UserTopPlayer[]
}

type UserStats = {
  game: UserGameStats
}

type SeasonOption = {
  value: number | null
  label: string
}

const props = withDefaults(defineProps<{
  statsUrl?: string
}>(), {
  statsUrl: '/users/stats',
})

const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const intFmt = new Intl.NumberFormat('ru-RU')
const settingsStore = useSettingsStore()
const selectedSeason = ref<number | null>(null)
const selectedMode = ref('all')
const modeOptions = [
  { value: 'all', label: 'Все игры' },
  { value: 'rating', label: 'Рейтинговые игры' },
]
let requestSeq = 0

const stats = reactive<UserStats>({
  game: {
    games_played: 0,
    games_won: 0,
    vote_leave_day12_percent: 0,
    vote_out_don_day12_black_count: 0,
    vote_out_sheriff_day12_black_count: 0,
    vote_out_don_day12_citizen_count: 0,
    vote_out_sheriff_day12_citizen_count: 0,
    vote_for_red_on_black_win_count: 0,
    farewell_success_percent: 0,
    farewell_correct_count: 0,
    farewell_total_count: 0,
    average_additional_points: 0,
    rating_games: 0,
    role_citizen: { games: 0, wins: 0 },
    role_sheriff: { games: 0, wins: 0 },
    role_don: { games: 0, wins: 0 },
    role_mafia: { games: 0, wins: 0 },
    best_move: { first_killed_total: 0, marks_black_0: 0, marks_black_1: 0, marks_black_2: 0, marks_black_3: 0 },
    top_players: [],
  },
})

function safeInt(raw: unknown): number {
  const value = Number(raw)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.trunc(value))
}

function safeFloat(raw: unknown): number {
  const value = Number(raw)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, value)
}

function clampPct(raw: unknown): number {
  const value = safeFloat(raw)
  return Math.max(0, Math.min(100, value))
}

function formatInt(raw: unknown): string {
  return intFmt.format(safeInt(raw))
}

function formatGames(raw: unknown): string {
  const count = safeInt(raw)
  const mod100 = count % 100
  const mod10 = count % 10
  const word = mod100 >= 11 && mod100 <= 14 ? 'игр'
    : mod10 === 1 ? 'игра' : mod10 >= 2 && mod10 <= 4 ? 'игры' : 'игр'
  return `${formatInt(count)} ${word}`
}

function formatPct(raw: unknown): string {
  return `${clampPct(raw).toFixed(2)}%`
}

function formatFarewellSuccess(percentRaw: unknown, totalRaw: unknown): string {
  return `${formatPct(percentRaw)} (${formatInt(totalRaw)} шт)`
}

function timesWord(raw: unknown): string {
  const value = safeInt(raw)
  const mod100 = value % 100
  const mod10 = value % 10
  if (mod100 >= 11 && mod100 <= 14) return 'раз'
  if (mod10 === 1) return 'раз'
  if (mod10 >= 2 && mod10 <= 4) return 'раза'
  return 'раз'
}

function formatTimes(raw: unknown): string {
  const value = safeInt(raw)
  return `${formatInt(value)} ${timesWord(value)}`
}

function formatDonSheriffSplit(donRaw: unknown, sheriffRaw: unknown): string {
  return `${formatInt(donRaw)}/${formatInt(sheriffRaw)}`
}

function formatPctWithGames(percentRaw: unknown, countRaw: unknown): string {
  const count = safeInt(countRaw)
  return `${formatInt(count)} - ${formatPct(percentRaw)}`
}

function barPct(valueRaw: unknown, maxRaw: unknown): number {
  const value = safeFloat(valueRaw)
  const max = safeFloat(maxRaw)
  if (value <= 0 || max <= 0) return 0
  const pct = (value / max) * 100
  return Math.max(8, Math.min(100, pct))
}

const game = computed(() => stats.game)

const seasonOptions = computed<SeasonOption[]>(() => {
  const options: SeasonOption[] = [{ value: null, label: 'Все сезоны' }]
  const starts = settingsStore.seasonStartGameNumbers
  for (let i = starts.length - 1; i >= 0; i -= 1) {
    const seasonNo = i + 1
    options.push({
      value: seasonNo,
      label: `${seasonNo} сезон`,
    })
  }
  return options
})

const lossesCount = computed(() => Math.max(0, safeInt(game.value.games_played) - safeInt(game.value.games_won)))

const totalFinishedGames = computed(() => safeInt(game.value.games_played))

const overviewSegments = computed(() => {
  const wins = safeInt(game.value.games_won)
  const losses = lossesCount.value
  const total = wins + losses
  const toPct = (count: number): number => {
    if (total <= 0) return 0
    return (count * 100) / total
  }
  return [
    { key: 'wins', label: 'Победы', count: wins, percent: toPct(wins) },
    { key: 'losses', label: 'Поражения', count: losses, percent: toPct(losses) },
  ]
})

function createRingStyle(winsPctRaw: number, lossesPctRaw: number): Record<string, string> {
  const stop1 = clampPct(winsPctRaw)
  const stop2 = clampPct(winsPctRaw + lossesPctRaw)
  if (stop2 <= 0) {
    return {
      background: 'conic-gradient(rgba(255,255,255,0.14) 0% 100%)',
    }
  }
  return {
    background: `conic-gradient(var(--ring-win) 0% ${stop1}%, var(--ring-loss) ${stop1}% 100%)`,
  }
}

const overviewRingStyle = computed<Record<string, string>>(() => {
  const [wins, losses] = overviewSegments.value
  return createRingStyle(wins.percent, losses.percent)
})

const roleRingItems = computed(() => {
  const roles = [
    { key: 'citizen', label: 'Мирный житель', icon: iconRoleCitizen, stats: game.value.role_citizen },
    { key: 'sheriff', label: 'Шериф', icon: iconRoleSheriff, stats: game.value.role_sheriff },
    { key: 'mafia', label: 'Мафия', icon: iconRoleMafia, stats: game.value.role_mafia },
    { key: 'don', label: 'Дон', icon: iconRoleDon, stats: game.value.role_don },
  ]
  return roles.map((item) => {
    const games = safeInt(item.stats.games)
    const wins = safeInt(item.stats.wins)
    const losses = Math.max(0, games - wins)
    const total = wins + losses
    const toPct = (count: number): number => {
      if (total <= 0) return 0
      return (count * 100) / total
    }
    const winPct = toPct(wins)
    const lossPct = toPct(losses)
    return {
      key: item.key,
      label: item.label,
      icon: item.icon,
      games,
      segments: [
        { key: 'wins', label: 'Поб', count: wins, percent: winPct },
        { key: 'losses', label: 'Пор', count: losses, percent: lossPct },
      ],
      style: createRingStyle(winPct, lossPct),
    }
  })
})

const topTogetherMax = computed(() => {
  let max = 0
  for (const item of game.value.top_players) {
    max = Math.max(max, safeInt(item.games_together))
  }
  return max
})

const bestMoveItems = computed(() => [
  { key: 'b0', label: '0/3', value: game.value.best_move.marks_black_0 },
  { key: 'b1', label: '1/3', value: game.value.best_move.marks_black_1 },
  { key: 'b2', label: '2/3', value: game.value.best_move.marks_black_2 },
  { key: 'b3', label: '3/3', value: game.value.best_move.marks_black_3 },
])

const bestMoveMax = computed(() => {
  let max = 0
  for (const item of bestMoveItems.value) {
    max = Math.max(max, safeInt(item.value))
  }
  return max
})

function normalizeRoleStats(raw: any): UserRoleStats {
  return {
    games: safeInt(raw?.games),
    wins: safeInt(raw?.wins),
  }
}

function normalizeTopPlayers(raw: any): UserTopPlayer[] {
  if (!Array.isArray(raw)) return []
  return raw
    .map((item: any) => ({
      id: safeInt(item?.id),
      username: typeof item?.username === 'string' ? item.username : null,
      games_together: safeInt(item?.games_together),
    }))
    .filter((item) => item.id > 0)
    .slice(0, 5)
}

function normalizeGame(raw: any): UserGameStats {
  return {
    games_played: safeInt(raw?.games_played),
    games_won: safeInt(raw?.games_won),
    vote_leave_day12_percent: clampPct(raw?.vote_leave_day12_percent),
    vote_out_don_day12_black_count: safeInt(raw?.vote_out_don_day12_black_count),
    vote_out_sheriff_day12_black_count: safeInt(raw?.vote_out_sheriff_day12_black_count),
    vote_out_don_day12_citizen_count: safeInt(raw?.vote_out_don_day12_citizen_count),
    vote_out_sheriff_day12_citizen_count: safeInt(raw?.vote_out_sheriff_day12_citizen_count),
    vote_for_red_on_black_win_count: safeInt(raw?.vote_for_red_on_black_win_count),
    farewell_success_percent: clampPct(raw?.farewell_success_percent),
    farewell_correct_count: safeInt(raw?.farewell_correct_count),
    farewell_total_count: safeInt(raw?.farewell_total_count),
    average_additional_points: Number.isFinite(Number(raw?.average_additional_points))
      ? Number(raw.average_additional_points) : 0,
    rating_games: safeInt(raw?.rating_games),
    role_citizen: normalizeRoleStats(raw?.role_citizen),
    role_sheriff: normalizeRoleStats(raw?.role_sheriff),
    role_don: normalizeRoleStats(raw?.role_don),
    role_mafia: normalizeRoleStats(raw?.role_mafia),
    best_move: {
      first_killed_total: safeInt(raw?.best_move?.first_killed_total),
      marks_black_0: safeInt(raw?.best_move?.marks_black_0),
      marks_black_1: safeInt(raw?.best_move?.marks_black_1),
      marks_black_2: safeInt(raw?.best_move?.marks_black_2),
      marks_black_3: safeInt(raw?.best_move?.marks_black_3),
    },
    top_players: normalizeTopPlayers(raw?.top_players),
  }
}

async function load(force = false) {
  if (loaded.value && !force && !loading.value) return
  const seq = ++requestSeq
  loading.value = true
  error.value = ''
  try {
    const params: { season?: number; mode: string } = { mode: selectedMode.value }
    if (selectedSeason.value !== null) params.season = selectedSeason.value
    const { data } = await api.get<UserStats>(props.statsUrl, { params })
    if (seq !== requestSeq) return
    stats.game = normalizeGame(data?.game)
    loaded.value = true
  } catch (e: any) {
    if (seq !== requestSeq) return
    const detail = String(e?.response?.data?.detail || '')
    error.value = detail === 'subscription_required' ? 'Для просмотра чужой статистики требуется активная подписка' : 'Не удалось загрузить статистику'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

watch([selectedSeason, selectedMode], () => {
  void load(true)
})

watch(seasonOptions, (options) => {
  if (selectedSeason.value === null) return
  const exists = options.some((option) => option.value === selectedSeason.value)
  if (!exists) selectedSeason.value = null
}, { immediate: true })

watch(() => props.statsUrl, () => {
  loaded.value = false
  void load(true)
})

onMounted(() => {
  void load()
})
</script>

<style scoped lang="scss">
.stats-tab {
  --ring-win: #{$green-500};
  --ring-loss: #{$red-500};
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  min-width: 0;
  container-type: inline-size;
  color: $neutral-100;
  font-family: Hauora-Regular;
  line-height: 1.4;
  .stats-head {
    box-sizing: border-box;
    padding: 24px;
    border-radius: 24px;
    background: $soft-purple-900;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 24px;
    .tab-title {
      margin: 0;
      color: $neutral-white;
      font-family: Involve-Medium;
      font-weight: 500;
      font-size: 24px;
      line-height: 26px;
      letter-spacing: -0.48px;
    }
    .stats-filters {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      .stats-season-dropdown {
        width: 220px;
      }
    }
  }
  .state {
    box-sizing: border-box;
    padding: 24px;
    border-radius: 24px;
    background: $soft-purple-900;
    display: grid;
    place-content: center;
    min-height: 180px;
    color: $neutral-300;
    &.state-inline {
      min-height: 140px;
      background: $soft-purple-800;
      border-radius: 20px;
    }
    &.state-danger {
      color: $red-400;
    }
  }
  .stats-layout {
    display: grid;
    gap: 10px;
    .overview {
      display: grid;
      grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
      gap: 10px;
      .result-card {
        box-sizing: border-box;
        padding: 24px;
        border-radius: 24px;
        background: $soft-purple-900;
        display: flex;
        flex-direction: column;
        gap: 24px;
        min-width: 0;
        h3 {
          margin: 0;
          color: $neutral-white;
          font-family: Involve-Medium;
          font-weight: 500;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        .results-grid {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
          align-items: center;
          gap: 24px;
          .result-ring {
            display: flex;
            position: relative;
            align-items: center;
            justify-content: center;
            margin: auto;
            width: 100%;
            max-width: 280px;
            aspect-ratio: 1;
            border-radius: 50%;
            &::before {
              content: '';
              position: absolute;
              inset: 14px;
              border-radius: inherit;
              background: $soft-purple-900;
            }
            .result-center {
              position: relative;
              display: flex;
              flex-direction: column;
              align-items: center;
              gap: 8px;
              color: $neutral-300;
              strong {
                color: $neutral-white;
                font-family: Involve-Medium;
                font-weight: 500;
                font-size: 40px;
                line-height: 1.1;
              }
              .result-legend {
                display: flex;
                flex-direction: column;
                gap: 4px;
                .legend-row {
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  gap: 6px;
                  .legend-dot {
                    flex: 0 0 6px;
                    height: 6px;
                    border-radius: 50%;
                    &.wins {
                      background: $green-500;
                    }
                    &.losses {
                      background: $red-500;
                    }
                  }
                  .legend-label {
                    font-size: 12px;
                  }
                  .legend-pct {
                    font-family: Hauora-Regular;
                    font-size: 12px;
                    color: $neutral-100;
                    white-space: nowrap;
                  }
                }
              }
            }
          }
          .role-rings {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
            .role-ring-card {
              display: flex;
              flex-direction: column;
              align-items: center;
              gap: 8px;
              min-width: 0;
              .role-name {
                font-size: 14px;
                text-align: center;
              }
              .role-result-ring {
                display: flex;
                position: relative;
                align-items: center;
                justify-content: center;
                margin: auto;
                width: 100%;
                max-width: 150px;
                aspect-ratio: 1;
                border-radius: 50%;
                &::before {
                  content: '';
                  position: absolute;
                  inset: 14px;
                  border-radius: inherit;
                  background: $soft-purple-900;
                }
                &::before {
                  inset: 8px;
                }
                .role-result-center {
                  position: relative;
                  display: flex;
                  flex-direction: column;
                  align-items: center;
                  gap: 4px;
                  color: $neutral-300;
                  strong {
                    color: $neutral-white;
                    font-family: Involve-Medium;
                    font-weight: 500;
                    font-size: 40px;
                    line-height: 1.1;
                  }
                  strong {
                    font-size: 24px;
                  }
                  .role-title-icon {
                    width: 28px;
                    height: 28px;
                    object-fit: contain;
                  }
                  .result-legend {
                    display: flex;
                    flex-direction: column;
                    gap: 4px;
                    .legend-row {
                      display: flex;
                      align-items: center;
                      justify-content: center;
                      gap: 6px;
                      .legend-dot {
                        flex: 0 0 6px;
                        height: 6px;
                        border-radius: 50%;
                        &.wins {
                          background: $green-500;
                        }
                        &.losses {
                          background: $red-500;
                        }
                      }
                      .legend-pct {
                        font-family: Hauora-Regular;
                        font-size: 12px;
                        color: $neutral-100;
                        white-space: nowrap;
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
      .block {
        box-sizing: border-box;
        padding: 24px;
        border-radius: 24px;
        background: $soft-purple-900;
        display: flex;
        flex-direction: column;
        gap: 24px;
        min-width: 0;
        h3 {
          margin: 0;
          color: $neutral-white;
          font-family: Involve-Medium;
          font-weight: 500;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        .section-hint {
          margin: -8px 0 0;
          color: $neutral-300;
          font-size: 14px;
        }
        .state {
          box-sizing: border-box;
          padding: 24px;
          border-radius: 24px;
          background: $soft-purple-900;
          display: grid;
          place-content: center;
          min-height: 180px;
          color: $neutral-300;
          &.state-inline {
            min-height: 140px;
            background: $soft-purple-800;
            border-radius: 20px;
          }
          &.state-danger {
            color: $red-400;
          }
        }
        .rank-list {
          display: flex;
          flex-direction: column;
          margin: 0;
          padding: 0;
          gap: 10px;
          list-style: none;
          .rank-row {
            display: flex;
            flex-direction: column;
            padding: 12px 16px;
            gap: 10px;
            border-radius: 16px;
            background: $soft-purple-800;
            .rank-top {
              display: grid;
              grid-template-columns: 24px minmax(0, 1fr) auto;
              align-items: center;
              gap: 8px;
              .rank-pos {
                color: $neutral-300;
                font-size: 14px;
              }
              .rank-name {
                overflow: hidden;
                white-space: nowrap;
                text-overflow: ellipsis;
              }
              .rank-val {
                color: $green-500;
                font-family: Hauora-Medium;
                font-weight: 500;
              }
            }
            .rank-bar {
              height: 6px;
              border-radius: 999px;
              background: $soft-purple-900;
              overflow: hidden;
              span {
                display: block;
                height: 100%;
                border-radius: inherit;
                background: $green-500;
              }
            }
          }
        }
      }
    }
    > .block {
      box-sizing: border-box;
      padding: 24px;
      border-radius: 24px;
      background: $soft-purple-900;
      display: flex;
      flex-direction: column;
      gap: 24px;
      min-width: 0;
      h3 {
        margin: 0;
        color: $neutral-white;
        font-family: Involve-Medium;
        font-weight: 500;
        font-size: 24px;
        line-height: 26px;
        letter-spacing: -0.48px;
      }
      .best-move {
        display: grid;
        grid-template-columns: minmax(180px, 1fr) minmax(0, 3fr);
        gap: 24px;
        align-items: center;
        .metric-card {
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          box-sizing: border-box;
          padding: 16px;
          gap: 16px;
          min-width: 0;
          min-height: 112px;
          border-radius: 20px;
          background: $soft-purple-800;
          span {
            color: $neutral-300;
            font-size: 14px;
          }
          strong {
            font-family: Involve-Medium;
            font-weight: 500;
            font-size: 24px;
            line-height: 1.2;
            overflow-wrap: anywhere;
          }
        }
        .best-bars {
          display: flex;
          flex-direction: column;
          gap: 12px;
          .best-row {
            display: grid;
            grid-template-columns: 32px minmax(0, 1fr) 40px;
            align-items: center;
            gap: 16px;
            strong {
              text-align: right;
              font-weight: 500;
            }
            .best-label {
              color: $neutral-300;
              font-size: 14px;
            }
            .best-bar {
              height: 6px;
              border-radius: 999px;
              background: $soft-purple-800;
              overflow: hidden;
              span {
                display: block;
                height: 100%;
                border-radius: inherit;
                background: $green-500;
              }
            }
          }
        }
      }
      .extra-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
        .metric-card {
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          box-sizing: border-box;
          padding: 16px;
          gap: 16px;
          min-width: 0;
          min-height: 112px;
          border-radius: 20px;
          background: $soft-purple-800;
          span {
            color: $neutral-300;
            font-size: 14px;
          }
          strong {
            font-family: Involve-Medium;
            font-weight: 500;
            font-size: 24px;
            line-height: 1.2;
            overflow-wrap: anywhere;
          }
        }
      }
    }
  }
}
</style>
