<template>
  <div class="stats-tab">
    <div class="stats-head">
      <h3>Статистика пользователя</h3>
      <div class="stats-season-switch">
        <button v-for="option in seasonOptions" :key="option.key" class="stats-season-btn" type="button"
                :class="{ active: selectedSeasonKey === option.key }" @click="setSeason(option.season)">
          {{ option.label }}
        </button>
      </div>
    </div>

    <div v-if="loading && !loaded" class="state">Загрузка...</div>
    <div v-else-if="error" class="state state-danger">
      <span>{{ error }}</span>
    </div>

    <div v-else class="stats-layout">
      <div class="non-game-grid">
        <article v-for="item in nonGameItems" :key="item.key" class="metric-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>

      <div class="overview">
        <article class="result-card">
          <div class="result-ring" :style="overviewRingStyle">
            <div class="result-center">
              <span>Всего игр</span>
              <strong>{{ formatInt(totalFinishedGames) }}</strong>
              <div class="result-legend">
                <div v-for="item in overviewSegments" :key="item.key" class="legend-row">
                  <span class="legend-dot" :class="item.key"></span>
                  <strong class="legend-pct">{{ formatPctWithGames(item.percent, item.count) }}</strong>
                </div>
              </div>
            </div>
          </div>
          <div class="role-rings">
            <article v-for="item in roleRingItems" :key="item.key" class="role-ring-card">
              <div class="role-result-ring" :style="item.style">
                <div class="role-result-center">
                  <img class="role-title-icon" :src="item.icon" :alt="item.label" />
                  <strong>{{ formatInt(item.games) }}</strong>
                  <div class="result-legend role-legend">
                    <div v-for="segment in item.segments" :key="segment.key" class="legend-row">
                      <span class="legend-dot" :class="segment.key"></span>
                      <strong class="legend-pct">{{ formatPctWithGames(segment.percent, segment.count) }}</strong>
                    </div>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </article>

        <section class="block">
          <h4>"Любимые" игроки</h4>
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
          <h4>Лучший ход</h4>
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
      </div>

      <section class="block">
        <h4>Дополнительные показатели</h4>
        <div class="extra-grid">
          <article class="metric-card">
            <span>Верное завещание</span>
            <strong>{{ formatPct(game.farewell_success_percent) }}</strong>
          </article>
          <article class="metric-card">
            <span>Заголосован в 1-2 день</span>
            <strong>{{ formatPct(game.vote_leave_day12_percent) }}</strong>
          </article>
          <article class="metric-card">
            <span>Удалён/Покинул игру</span>
            <strong>{{ formatPct(game.foul_removed_percent) }}</strong>
          </article>
          <article class="metric-card">
            <span>Нашел шерифа в 1 ночь</span>
            <strong>{{ formatPct(game.don_first_night_find_percent) }}</strong>
          </article>
          <article class="metric-card">
            <span>Проголосовал на поражение</span>
            <strong>{{ formatTimes(game.vote_for_red_on_black_win_count) }}</strong>
          </article>
          <article class="metric-card">
            <span>Лучший WinStreak</span>
            <strong>{{ formatInt(game.best_win_streak) }} {{ gameWord(game.best_win_streak) }}</strong>
          </article>
          <article class="metric-card">
            <span>Худший LoseStreak</span>
            <strong>{{ formatInt(game.best_loss_streak) }} {{ gameWord(game.best_loss_streak) }}</strong>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, withDefaults } from 'vue'
import { api } from '@/services/axios'
import { useSettingsStore } from '@/store'
import iconRoleCitizen from '@/assets/images/roleCitizen.png'
import iconRoleMafia from '@/assets/images/roleMafia.png'
import iconRoleDon from '@/assets/images/roleDon.png'
import iconRoleSheriff from '@/assets/images/roleSheriff.png'

type UserTopPlayer = {
  id: number
  username?: string | null
  games_together: number
}

type UserRoleStats = {
  games: number
  wins: number
  winrate_percent: number
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
  winrate_percent: number
  games_hosted: number
  don_first_night_find_count: number
  don_first_night_find_percent: number
  vote_leave_day12_count: number
  vote_leave_day12_percent: number
  foul_removed_count: number
  foul_removed_percent: number
  vote_for_red_on_black_win_count: number
  farewell_total: number
  farewell_success_percent: number
  best_win_streak: number
  best_loss_streak: number
  role_citizen: UserRoleStats
  role_sheriff: UserRoleStats
  role_don: UserRoleStats
  role_mafia: UserRoleStats
  best_move: UserBestMoveStats
  top_players: UserTopPlayer[]
}

type UserStats = {
  rooms_created: number
  room_minutes: number
  stream_minutes: number
  spectator_minutes: number
  game: UserGameStats
}

type SeasonOption = {
  key: string
  label: string
  season: number | null
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
const selectedSeasonKey = computed(() => (selectedSeason.value === null ? 'all' : `s${selectedSeason.value}`))
let requestSeq = 0

const stats = reactive<UserStats>({
  rooms_created: 0,
  room_minutes: 0,
  stream_minutes: 0,
  spectator_minutes: 0,
  game: {
    games_played: 0,
    games_won: 0,
    winrate_percent: 0,
    games_hosted: 0,
    don_first_night_find_count: 0,
    don_first_night_find_percent: 0,
    vote_leave_day12_count: 0,
    vote_leave_day12_percent: 0,
    foul_removed_count: 0,
    foul_removed_percent: 0,
    vote_for_red_on_black_win_count: 0,
    farewell_total: 0,
    farewell_success_percent: 0,
    best_win_streak: 0,
    best_loss_streak: 0,
    role_citizen: { games: 0, wins: 0, winrate_percent: 0 },
    role_sheriff: { games: 0, wins: 0, winrate_percent: 0 },
    role_don: { games: 0, wins: 0, winrate_percent: 0 },
    role_mafia: { games: 0, wins: 0, winrate_percent: 0 },
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

function formatPct(raw: unknown): string {
  return `${clampPct(raw).toFixed(2)}%`
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

function gameWord(raw: unknown): string {
  const value = safeInt(raw)
  const mod100 = value % 100
  const mod10 = value % 10
  if (mod100 >= 11 && mod100 <= 14) return 'игр'
  if (mod10 === 1) return 'игра'
  if (mod10 >= 2 && mod10 <= 4) return 'игры'
  return 'игр'
}

function formatPctWithGames(percentRaw: unknown, countRaw: unknown): string {
  const count = safeInt(countRaw)
  return `${formatInt(count)} - ${formatPct(percentRaw)}`
}

function formatDurationDhm(raw: unknown): string {
  const totalMinutes = safeInt(raw)
  const minutesInDay = 24 * 60
  const days = Math.floor(totalMinutes / minutesInDay)
  const hours = Math.floor((totalMinutes % minutesInDay) / 60)
  const minutes = totalMinutes % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days}д`)
  if (hours > 0) parts.push(`${hours}ч`)
  parts.push(`${minutes}м`)
  return parts.join(' ')
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
  const options: SeasonOption[] = [{ key: 'all', label: 'Все игры', season: null }]
  const starts = settingsStore.seasonStartGameNumbers
  for (let i = 0; i < starts.length; i += 1) {
    const seasonNo = i + 1
    options.push({
      key: `s${seasonNo}`,
      label: `${seasonNo} сезон`,
      season: seasonNo,
    })
  }
  return options
})

function setSeason(season: number | null): void {
  if (selectedSeason.value === season) return
  selectedSeason.value = season
}

const nonGameItems = computed(() => [
  { key: 'room-minutes', label: 'В комнатах', value: formatDurationDhm(stats.room_minutes) },
  { key: 'rooms-created', label: 'Мои комнаты', value: formatInt(stats.rooms_created) },
  { key: 'stream-minutes', label: 'Мои стримы', value: formatDurationDhm(stats.stream_minutes) },
  { key: 'spectator-minutes', label: 'Зритель', value: formatDurationDhm(stats.spectator_minutes) },
  { key: 'games-hosted', label: 'Игр проведено', value: formatInt(game.value.games_hosted) },
])

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
    winrate_percent: clampPct(raw?.winrate_percent),
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
    winrate_percent: clampPct(raw?.winrate_percent),
    games_hosted: safeInt(raw?.games_hosted),
    don_first_night_find_count: safeInt(raw?.don_first_night_find_count),
    don_first_night_find_percent: clampPct(raw?.don_first_night_find_percent),
    vote_leave_day12_count: safeInt(raw?.vote_leave_day12_count),
    vote_leave_day12_percent: clampPct(raw?.vote_leave_day12_percent),
    foul_removed_count: safeInt(raw?.foul_removed_count),
    foul_removed_percent: clampPct(raw?.foul_removed_percent),
    vote_for_red_on_black_win_count: safeInt(raw?.vote_for_red_on_black_win_count),
    farewell_total: safeInt(raw?.farewell_total),
    farewell_success_percent: clampPct(raw?.farewell_success_percent),
    best_win_streak: safeInt(raw?.best_win_streak),
    best_loss_streak: safeInt(raw?.best_loss_streak),
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
    const params: { season?: number } = {}
    if (selectedSeason.value !== null) params.season = selectedSeason.value
    const { data } = await api.get<UserStats>(props.statsUrl, { params })
    if (seq !== requestSeq) return
    stats.rooms_created = safeInt(data?.rooms_created)
    stats.room_minutes = safeInt(data?.room_minutes)
    stats.stream_minutes = safeInt(data?.stream_minutes)
    stats.spectator_minutes = safeInt(data?.spectator_minutes)
    stats.game = normalizeGame(data?.game)
    loaded.value = true
  } catch {
    if (seq !== requestSeq) return
    error.value = 'Не удалось загрузить статистику'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

watch(selectedSeason, () => {
  void load(true)
})

watch(seasonOptions, (options) => {
  if (selectedSeason.value === null) return
  const exists = options.some((option) => option.season === selectedSeason.value)
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
  --ring-win: #{rgba($green, 0.75)};
  --ring-loss: #{rgba($red, 0.75)};
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  .stats-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
    h3 {
      margin: 0;
    }
    .stats-season-switch {
      display: inline-flex;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 5px;
    }
    .stats-season-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 95px;
      height: 45px;
      padding: 0 20px;
      border: none;
      border-radius: 5px;
      background-color: $graphite;
      color: $fg;
      font-size: 16px;
      cursor: pointer;
      transition: background-color 0.25s ease-in-out, color 0.25s ease-in-out;
      &:hover {
        background-color: $lead;
      }
      &.active {
        background-color: $fg;
        color: $bg;
      }
    }
  }
  .state {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 10px;
    gap: 10px;
    min-height: 140px;
    border: 1px solid rgba($grey, 0.5);
    border-radius: 5px;
    background-color: rgba($graphite, 0.5);
    color: $ashy;
    &.state-inline {
      min-height: auto;
    }
    &.state-danger {
      color: $red;
    }
  }
  .stats-layout {
    display: grid;
    grid-template-columns: 1fr;
    gap: 10px;
    .block {
      display: flex;
      flex-direction: column;
      padding: 10px;
      gap: 10px;
      border-radius: 5px;
      border: 1px solid rgba($grey, 0.5);
      background: linear-gradient(150deg, rgba($graphite, 0.75), rgba($dark, 0.75));
      h4 {
        margin: 0;
      }
    }
    .metric-card {
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 10px;
      gap: 5px;
      min-height: 75px;
      border-radius: 5px;
      border: 1px solid rgba($grey, 0.5);
      background: linear-gradient(150deg, rgba($graphite, 0.75), rgba($lead, 0.75));
      span {
        color: $ashy;
        font-size: 14px;
      }
      strong {
        text-align: end;
        color: $fg;
        font-family: Manrope-SemiBold;
        font-size: 24px;
        line-height: 1.1;
      }
    }
    .non-game-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
    }
    .overview {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      .result-card {
        display: grid;
        grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
        align-items: center;
        padding: 10px;
        gap: 10px;
        min-width: 894px;
        border-radius: 5px;
        border: 1px solid rgba($grey, 0.5);
        background: linear-gradient(150deg, rgba($graphite, 0.75), rgba($dark, 0.75));
      }
      .result-ring {
        display: flex;
        position: relative;
        align-items: center;
        justify-content: center;
        margin: 0 auto;
        width: 300px;
        height: 300px;
        border-radius: 50%;
        border: 1px solid $grey;
        &::before {
          content: "";
          position: absolute;
          inset: 30px;
          border-radius: inherit;
          background-color: $dark;
          border: 1px solid rgba($grey, 0.5);
        }
        .result-center {
          display: flex;
          position: relative;
          flex-direction: column;
          align-items: stretch;
          gap: 5px;
          width: 170px;
          z-index: 1;
          span {
            color: $ashy;
            font-size: 24px;
            text-transform: uppercase;
            text-align: center;
          }
          strong {
            color: $fg;
            font-family: Manrope-SemiBold;
            font-size: 40px;
            line-height: 1;
            text-align: center;
          }
        }
        .result-legend {
          display: flex;
          flex-direction: column;
          gap: 5px;
          .legend-row {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
            .legend-dot {
              display: block;
              width: 10px;
              height: 10px;
              border-radius: 50%;
              &.wins {
                background-color: $green;
              }
              &.losses {
                background-color: $red;
              }
            }
            .legend-pct {
              font-size: 16px;
              color: $fg;
              font-family: Manrope-SemiBold;
              text-align: right;
              white-space: nowrap;
            }
          }
        }
      }
      .role-rings {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 20px;
        .role-ring-card {
          display: flex;
          justify-content: center;
        }
        .role-result-ring {
          display: flex;
          position: relative;
          align-items: center;
          justify-content: center;
          width: 200px;
          height: 200px;
          border-radius: 50%;
          border: 1px solid $grey;
          &::before {
            content: "";
            position: absolute;
            inset: 20px;
            border-radius: inherit;
            background-color: $dark;
            border: 1px solid rgba($grey, 0.5);
          }
          .role-result-center {
            display: flex;
            position: relative;
            flex-direction: column;
            align-items: stretch;
            gap: 5px;
            width: 120px;
            z-index: 1;
            .role-title-icon {
              display: block;
              max-width: 100%;
              height: 40px;
              margin: 0 auto;
              object-fit: contain;
            }
            strong {
              color: $fg;
              font-family: Manrope-SemiBold;
              font-size: 30px;
              line-height: 1;
              text-align: center;
            }
          }
          .role-legend {
            display: flex;
            flex-direction: column;
            gap: 5px;
            .legend-row {
              display: flex;
              align-items: center;
              justify-content: center;
              gap: 5px;
              .legend-dot {
                display: block;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                &.wins {
                  background-color: $green;
                }
                &.losses {
                  background-color: $red;
                }
              }
              .legend-pct {
                font-size: 14px;
                color: $fg;
                font-family: Manrope-SemiBold;
                text-align: right;
                white-space: nowrap;
              }
            }
          }
        }
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
        padding: 10px;
        gap: 5px;
        border-radius: 5px;
        background-color: $dark;
        border: 1px solid rgba($grey, 0.5);
        .rank-top {
          display: grid;
          grid-template-columns: auto 1fr auto;
          align-items: center;
          gap: 5px;
          .rank-pos {
            color: $ashy;
          }
          .rank-name {
            text-overflow: ellipsis;
            white-space: nowrap;
            overflow: hidden;
          }
          .rank-val {
            color: $fg;
          }
        }
        .rank-bar {
          height: 10px;
          border-radius: 999px;
          background-color: rgba($black, 0.5);
          overflow: hidden;
          span {
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, $lead, $fg);
          }
        }
      }
    }
    .best-move {
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 10px;
      .best-bars {
        display: flex;
        flex-direction: column;
        gap: 10px;
        .best-row {
          display: grid;
          grid-template-columns: auto 1fr auto;
          align-items: center;
          gap: 10px;
          .best-label {
            color: $ashy;
            font-size: 14px;
          }
          .best-bar {
            height: 10px;
            border-radius: 999px;
            background-color: rgba($black, 0.5);
            overflow: hidden;
            span {
              display: block;
              height: 100%;
              border-radius: inherit;
              background: linear-gradient(90deg, rgba($yellow, 0.75), rgba($green, 0.75));
            }
          }
          strong {
            min-width: 20px;
            text-align: right;
          }
        }
      }
    }
    .extra-grid {
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      gap: 10px;
    }
  }
}

@media (max-width: 1280px) {
  .stats-tab {
    .stats-head {
      justify-content: flex-start;
      h3 {
        font-size: 20px;
      }
      .stats-season-switch {
        width: 100%;
        justify-content: flex-start;
      }
      .stats-season-btn {
        min-width: 80px;
        height: 30px;
        padding: 0 10px;
        font-size: 14px;
      }
    }
    .state {
      min-height: 90px;
      padding: 5px 10px;
      font-size: 12px;
    }
    .stats-layout {
      .block {
        padding: 10px;
        gap: 5px;
        h4 {
          font-size: 16px;
        }
      }
      .metric-card {
        min-height: 64px;
        padding: 10px;
        span {
          font-size: 12px;
          line-height: 1.2;
        }
        strong {
          font-size: 18px;
        }
      }
      .overview {
        grid-template-columns: 1fr;
        .result-card {
          justify-items: center;
          gap: 10px;
          min-width: auto;
        }
        .result-ring {
          width: 200px;
          height: 200px;
          &::before {
            inset: 25px;
          }
          .result-center {
            width: 128px;
            span {
              font-size: 16px;
            }
            strong {
              font-size: 30px;
            }
          }
          .result-legend {
            .legend-row {
              .legend-pct {
                font-size: 12px;
              }
            }
          }
        }
        .role-rings {
          width: 100%;
          gap: 10px;
          justify-items: center;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          .role-result-ring {
            width: 140px;
            height: 140px;
            &::before {
              inset: 15px;
            }
            .role-result-center {
              width: 90px;
              .role-title-icon {
                height: 20px;
              }
              strong {
                font-size: 24px;
              }
            }
            .role-legend {
              .legend-row {
                .legend-pct {
                  font-size: 10px;
                }
              }
            }
          }
        }
      }
      .rank-list {
        gap: 5px;
        .rank-row {
          padding: 5px 10px;
          .rank-top {
            grid-template-columns: auto minmax(0, 1fr) auto;
            .rank-pos,
            .rank-name,
            .rank-val {
              font-size: 14px;
            }
          }
        }
      }
      .best-move {
        .best-bars {
          gap: 5px;
          .best-row {
            grid-template-columns: 32px minmax(0, 1fr) auto;
            gap: 5px;
            .best-label {
              font-size: 12px;
            }
            strong {
              min-width: 30px;
              font-size: 14px;
            }
          }
        }
      }
      .extra-grid {
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      }
    }
  }
}
</style>
