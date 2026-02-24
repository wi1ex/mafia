<template>
  <div class="stats-tab">
    <div class="stats-head">
      <h3>Статистика пользователя</h3>
      <button class="reload" type="button" :disabled="loading" @click="load(true)">
        {{ loading ? '...' : 'Обновить' }}
      </button>
    </div>

    <div v-if="loading && !loaded" class="state">Загрузка...</div>
    <div v-else-if="error" class="state state-danger">
      <span>{{ error }}</span>
      <button class="retry" type="button" :disabled="loading" @click="load(true)">Повторить</button>
    </div>
    <div v-else class="stats-layout">
      <section class="block">
        <h4>Неигровая активность</h4>
        <div class="non-game-grid">
          <article v-for="item in nonGameItems" :key="item.key" class="metric-card">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </section>

      <section class="block">
        <h4>Общий игровой результат</h4>
        <div class="overview">
          <div class="rings">
            <article class="ring-card">
              <div class="ring" :style="ringStyle(game.winrate_percent, '--ring-win')">
                <strong>{{ formatPct(game.winrate_percent) }}</strong>
              </div>
              <span>Винрейт</span>
            </article>
            <article class="ring-card">
              <div class="ring" :style="ringStyle(game.draws_percent, '--ring-draw')">
                <strong>{{ formatPct(game.draws_percent) }}</strong>
              </div>
              <span>Доля ничьих</span>
            </article>
          </div>
          <div class="overview-cards">
            <article class="metric-card">
              <span>Игр сыграно</span>
              <strong>{{ formatInt(game.games_played) }}</strong>
            </article>
            <article class="metric-card">
              <span>Игр выиграно</span>
              <strong>{{ formatInt(game.games_won) }}</strong>
            </article>
            <article class="metric-card">
              <span>Игр ведущим</span>
              <strong>{{ formatInt(game.games_hosted) }}</strong>
            </article>
            <article class="metric-card">
              <span>Ничьих</span>
              <strong>{{ formatInt(game.draws_count) }}</strong>
            </article>
          </div>
        </div>
      </section>

      <section class="block">
        <h4>Статистика по ролям</h4>
        <div class="roles-grid">
          <article v-for="item in roleItems" :key="item.key" class="role-card">
            <div class="role-head">
              <strong>{{ item.label }}</strong>
              <span>{{ formatPct(item.winrate) }}</span>
            </div>
            <div class="role-bar">
              <span :style="{ width: `${clampPct(item.winrate)}%` }"></span>
            </div>
            <div class="role-foot">
              <span>Побед {{ formatInt(item.wins) }}</span>
              <span>Игр {{ formatInt(item.games) }}</span>
            </div>
          </article>
        </div>
      </section>

      <section class="block">
        <h4>Топ-5 игроков по количеству игр вместе</h4>
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

      <section class="block">
        <h4>Последние 10 игр</h4>
        <div v-if="game.recent_games.length === 0" class="state state-inline">Пока нет данных</div>
        <div v-else class="recent-list">
          <article v-for="item in game.recent_games" :key="item.game_id" class="recent-item">
            <span class="recent-role">{{ roleLabel(item.role) }}</span>
            <span class="recent-result" :class="item.won ? 'win' : 'loss'">{{ item.won ? 'Победа' : 'Поражение' }}</span>
            <time>{{ formatRecentDate(item.finished_at) }}</time>
          </article>
        </div>
      </section>

      <section class="block">
        <h4>Лучший ход (если был первым убиенным)</h4>
        <div class="best-move">
          <article class="metric-card">
            <span>Был первым убиенным</span>
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
        <h4>Дополнительные показатели</h4>
        <div class="extra-grid">
          <article class="metric-card">
            <span>Средняя длительность игры</span>
            <strong>{{ formatMinutes(game.avg_game_minutes) }}</strong>
          </article>
          <article class="metric-card">
            <span>Среднее фолов за игру</span>
            <strong>{{ formatFloat(game.avg_fouls_per_game) }}</strong>
          </article>
          <article class="metric-card">
            <span>Дон: проверки в 1-ю ночь</span>
            <strong>{{ formatInt(game.don_first_night_checks) }}</strong>
          </article>
          <article class="metric-card">
            <span>Дон: нашёл шерифа</span>
            <strong>{{ formatInt(game.don_first_night_found_sheriff) }} / {{ formatPct(game.don_first_night_find_percent) }}</strong>
          </article>
          <article class="metric-card">
            <span>Промахи из-за меня</span>
            <strong>{{ formatInt(game.misses_due_to_me) }}</strong>
          </article>
          <article class="metric-card">
            <span>Подмигивания / постукивания</span>
            <strong>{{ formatInt(game.winks_used) }} / {{ formatInt(game.knocks_used) }}</strong>
          </article>
          <article class="metric-card">
            <span>Уход голосованием в 1-2 день</span>
            <strong>{{ formatInt(game.vote_leave_day12_count) }} / {{ formatPct(game.vote_leave_day12_percent) }}</strong>
          </article>
          <article class="metric-card">
            <span>Успешность завещаний</span>
            <strong>{{ formatPct(game.farewell_success_percent) }}</strong>
          </article>
          <article class="metric-card">
            <span>Лучшая серия побед</span>
            <strong>{{ formatInt(game.best_win_streak) }}</strong>
          </article>
          <article class="metric-card">
            <span>Лучшая серия поражений</span>
            <strong>{{ formatInt(game.best_loss_streak) }}</strong>
          </article>
        </div>

        <div class="vote-pairs">
          <article class="vote-card">
            <span>Чаще всего голосовал против меня</span>
            <strong v-if="game.top_voted_against_me">{{ game.top_voted_against_me.username || `user${game.top_voted_against_me.id}` }} ({{ formatInt(game.top_voted_against_me.count) }})</strong>
            <strong v-else>Нет данных</strong>
          </article>
          <article class="vote-card">
            <span>Против кого чаще голосовал я</span>
            <strong v-if="game.top_i_voted_against">{{ game.top_i_voted_against.username || `user${game.top_i_voted_against.id}` }} ({{ formatInt(game.top_i_voted_against.count) }})</strong>
            <strong v-else>Нет данных</strong>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '@/services/axios'

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

type UserTopVote = {
  id: number
  username?: string | null
  count: number
}

type UserRecentGame = {
  game_id: number
  role: string
  result: 'red' | 'black'
  won: boolean
  finished_at: string
}

type UserGameStats = {
  games_played: number
  games_won: number
  winrate_percent: number
  games_hosted: number
  avg_game_minutes: number
  draws_count: number
  draws_percent: number
  avg_fouls_per_game: number
  don_first_night_checks: number
  don_first_night_found_sheriff: number
  don_first_night_find_percent: number
  misses_due_to_me: number
  winks_used: number
  knocks_used: number
  vote_leave_day12_count: number
  vote_leave_day12_percent: number
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
  recent_games: UserRecentGame[]
  top_voted_against_me?: UserTopVote | null
  top_i_voted_against?: UserTopVote | null
}

type UserStats = {
  rooms_created: number
  room_minutes: number
  stream_minutes: number
  spectator_minutes: number
  game: UserGameStats
}

const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const intFmt = new Intl.NumberFormat('ru-RU')

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
    avg_game_minutes: 0,
    draws_count: 0,
    draws_percent: 0,
    avg_fouls_per_game: 0,
    don_first_night_checks: 0,
    don_first_night_found_sheriff: 0,
    don_first_night_find_percent: 0,
    misses_due_to_me: 0,
    winks_used: 0,
    knocks_used: 0,
    vote_leave_day12_count: 0,
    vote_leave_day12_percent: 0,
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
    recent_games: [],
    top_voted_against_me: null,
    top_i_voted_against: null,
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

function formatFloat(raw: unknown): string {
  return safeFloat(raw).toFixed(2)
}

function formatPct(raw: unknown): string {
  return `${clampPct(raw).toFixed(2)}%`
}

function formatMinutes(raw: unknown): string {
  return `${safeFloat(raw).toFixed(2)} мин`
}

function roleLabel(role: string): string {
  if (role === 'citizen') return 'Мирный'
  if (role === 'sheriff') return 'Шериф'
  if (role === 'don') return 'Дон'
  if (role === 'mafia') return 'Мафия'
  return role || '-'
}

function formatRecentDate(raw: string): string {
  const dt = new Date(raw)
  if (Number.isNaN(dt.getTime())) return '-'
  return dt.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function ringStyle(percentRaw: unknown, colorVar: string): Record<string, string> {
  const percent = clampPct(percentRaw)
  return {
    background: `conic-gradient(var(${colorVar}) ${percent}%, rgba(255,255,255,0.12) ${percent}% 100%)`,
  }
}

function barPct(valueRaw: unknown, maxRaw: unknown): number {
  const value = safeFloat(valueRaw)
  const max = safeFloat(maxRaw)
  if (value <= 0 || max <= 0) return 0
  const pct = (value / max) * 100
  return Math.max(8, Math.min(100, pct))
}

const game = computed(() => stats.game)

const nonGameItems = computed(() => [
  { key: 'rooms-created', label: 'Создал комнат', value: formatInt(stats.rooms_created) },
  { key: 'room-minutes', label: 'Минут в комнатах', value: formatInt(stats.room_minutes) },
  { key: 'stream-minutes', label: 'Минут стримил', value: formatInt(stats.stream_minutes) },
  { key: 'spectator-minutes', label: 'Минут как зритель', value: formatInt(stats.spectator_minutes) },
])

const roleItems = computed(() => [
  { key: 'citizen', label: 'Мирный житель', games: game.value.role_citizen.games, wins: game.value.role_citizen.wins, winrate: game.value.role_citizen.winrate_percent },
  { key: 'sheriff', label: 'Шериф', games: game.value.role_sheriff.games, wins: game.value.role_sheriff.wins, winrate: game.value.role_sheriff.winrate_percent },
  { key: 'don', label: 'Дон', games: game.value.role_don.games, wins: game.value.role_don.wins, winrate: game.value.role_don.winrate_percent },
  { key: 'mafia', label: 'Мафия', games: game.value.role_mafia.games, wins: game.value.role_mafia.wins, winrate: game.value.role_mafia.winrate_percent },
])

const topTogetherMax = computed(() => {
  let max = 0
  for (const item of game.value.top_players) {
    max = Math.max(max, safeInt(item.games_together))
  }
  return max
})

const bestMoveItems = computed(() => [
  { key: 'b0', label: '0/3 чёрных', value: game.value.best_move.marks_black_0 },
  { key: 'b1', label: '1/3 чёрных', value: game.value.best_move.marks_black_1 },
  { key: 'b2', label: '2/3 чёрных', value: game.value.best_move.marks_black_2 },
  { key: 'b3', label: '3/3 чёрных', value: game.value.best_move.marks_black_3 },
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

function normalizeTopVote(raw: any): UserTopVote | null {
  const id = safeInt(raw?.id)
  if (id <= 0) return null
  return {
    id,
    username: typeof raw?.username === 'string' ? raw.username : null,
    count: safeInt(raw?.count),
  }
}

function normalizeRecent(raw: any): UserRecentGame[] {
  if (!Array.isArray(raw)) return []
  return raw
    .map((item: any) => ({
      game_id: safeInt(item?.game_id),
      role: typeof item?.role === 'string' ? item.role : '',
      result: item?.result === 'black' ? 'black' : 'red',
      won: Boolean(item?.won),
      finished_at: typeof item?.finished_at === 'string' ? item.finished_at : '',
    }))
    .filter((item) => item.game_id > 0 && item.role)
    .slice(0, 10)
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
    avg_game_minutes: safeFloat(raw?.avg_game_minutes),
    draws_count: safeInt(raw?.draws_count),
    draws_percent: clampPct(raw?.draws_percent),
    avg_fouls_per_game: safeFloat(raw?.avg_fouls_per_game),
    don_first_night_checks: safeInt(raw?.don_first_night_checks),
    don_first_night_found_sheriff: safeInt(raw?.don_first_night_found_sheriff),
    don_first_night_find_percent: clampPct(raw?.don_first_night_find_percent),
    misses_due_to_me: safeInt(raw?.misses_due_to_me),
    winks_used: safeInt(raw?.winks_used),
    knocks_used: safeInt(raw?.knocks_used),
    vote_leave_day12_count: safeInt(raw?.vote_leave_day12_count),
    vote_leave_day12_percent: clampPct(raw?.vote_leave_day12_percent),
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
    recent_games: normalizeRecent(raw?.recent_games),
    top_voted_against_me: normalizeTopVote(raw?.top_voted_against_me),
    top_i_voted_against: normalizeTopVote(raw?.top_i_voted_against),
  }
}

async function load(force = false) {
  if (loading.value) return
  if (loaded.value && !force) return
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<UserStats>('/users/stats')
    stats.rooms_created = safeInt(data?.rooms_created)
    stats.room_minutes = safeInt(data?.room_minutes)
    stats.stream_minutes = safeInt(data?.stream_minutes)
    stats.spectator_minutes = safeInt(data?.spectator_minutes)
    stats.game = normalizeGame(data?.game)
    loaded.value = true
  } catch {
    error.value = 'Не удалось загрузить статистику'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<style scoped lang="scss">
.stats-tab {
  --ring-win: #30b86e;
  --ring-draw: #d7aa38;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  .stats-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    h3 {
      margin: 0;
    }
    .reload {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 120px;
      height: 32px;
      border: none;
      border-radius: 5px;
      background-color: $lead;
      color: $fg;
      font-family: Manrope-Medium;
      cursor: pointer;
      transition: opacity 0.25s ease-in-out, background-color 0.25s ease-in-out;
      &:hover {
        background-color: rgba($grey, 0.5);
      }
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
  }
  .state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    min-height: 140px;
    padding: 10px;
    border: 1px solid rgba($grey, 0.4);
    border-radius: 5px;
    background-color: rgba($graphite, 0.4);
    color: $ashy;
    &.state-inline {
      min-height: auto;
    }
    &.state-danger {
      color: $red;
    }
    .retry {
      min-width: 110px;
      height: 30px;
      border: none;
      border-radius: 5px;
      background-color: rgba($red, 0.75);
      color: $fg;
      cursor: pointer;
      transition: opacity 0.25s ease-in-out, background-color 0.25s ease-in-out;
      &:hover {
        background-color: $red;
      }
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
  }
  .stats-layout {
    display: grid;
    grid-template-columns: 1fr;
    gap: 10px;
    .block {
      display: flex;
      flex-direction: column;
      gap: 10px;
      border: 1px solid rgba($grey, 0.35);
      border-radius: 5px;
      padding: 10px;
      background: linear-gradient(155deg, rgba($graphite, 0.92), rgba($dark, 0.95));
      h4 {
        margin: 0;
      }
    }
    .metric-card {
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 5px;
      min-height: 74px;
      padding: 8px;
      border-radius: 5px;
      border: 1px solid rgba($grey, 0.4);
      background-color: rgba($black, 0.15);
      span {
        color: $ashy;
        font-size: 13px;
      }
      strong {
        color: $fg;
        font-family: Manrope-SemiBold;
        font-size: 20px;
        line-height: 1.1;
      }
    }
    .non-game-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .overview {
      display: grid;
      grid-template-columns: 260px 1fr;
      gap: 10px;
      .rings {
        display: grid;
        grid-template-columns: 1fr;
        gap: 10px;
        .ring-card {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px;
          border-radius: 5px;
          border: 1px solid rgba($grey, 0.4);
          background-color: rgba($black, 0.12);
          .ring {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 84px;
            height: 84px;
            border-radius: 50%;
            position: relative;
            &::before {
              content: "";
              position: absolute;
              inset: 10px;
              border-radius: inherit;
              background-color: rgba($dark, 0.95);
              border: 1px solid rgba($grey, 0.35);
            }
            strong {
              position: relative;
              z-index: 1;
              font-size: 13px;
            }
          }
          span {
            color: $fg;
            font-size: 14px;
          }
        }
      }
      .overview-cards {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }
    }
    .roles-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      .role-card {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 8px;
        border-radius: 5px;
        border: 1px solid rgba($grey, 0.4);
        background-color: rgba($black, 0.14);
        .role-head {
          display: flex;
          justify-content: space-between;
          gap: 8px;
          strong {
            font-size: 14px;
          }
          span {
            font-size: 13px;
            color: $green;
          }
        }
        .role-bar {
          height: 8px;
          border-radius: 999px;
          background-color: rgba($black, 0.35);
          overflow: hidden;
          span {
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, rgba($orange, 0.9), rgba($yellow, 0.95));
          }
        }
        .role-foot {
          display: flex;
          justify-content: space-between;
          gap: 8px;
          color: $ashy;
          font-size: 12px;
        }
      }
    }
    .rank-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin: 0;
      padding: 0;
      list-style: none;
      .rank-row {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 8px;
        border-radius: 5px;
        background-color: rgba($black, 0.15);
        border: 1px solid rgba($grey, 0.35);
        .rank-top {
          display: grid;
          grid-template-columns: auto 1fr auto;
          align-items: center;
          gap: 8px;
          .rank-pos {
            color: $ashy;
          }
          .rank-name {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          .rank-val {
            color: $fg;
          }
        }
        .rank-bar {
          height: 8px;
          border-radius: 999px;
          background-color: rgba($black, 0.35);
          overflow: hidden;
          span {
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, rgba($green, 0.75), rgba($yellow, 0.9));
          }
        }
      }
    }
    .recent-list {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      .recent-item {
        display: grid;
        grid-template-columns: 1fr auto auto;
        align-items: center;
        gap: 8px;
        padding: 8px;
        border-radius: 5px;
        border: 1px solid rgba($grey, 0.35);
        background-color: rgba($black, 0.15);
        .recent-role {
          color: $fg;
          font-size: 13px;
        }
        .recent-result {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 88px;
          height: 24px;
          border-radius: 999px;
          font-size: 12px;
          &.win {
            color: $fg;
            background-color: rgba($green, 0.8);
          }
          &.loss {
            color: $fg;
            background-color: rgba($red, 0.8);
          }
        }
        time {
          color: $ashy;
          font-size: 12px;
          white-space: nowrap;
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
        gap: 8px;
        .best-row {
          display: grid;
          grid-template-columns: 90px 1fr auto;
          align-items: center;
          gap: 8px;
          .best-label {
            color: $ashy;
            font-size: 12px;
          }
          .best-bar {
            height: 8px;
            border-radius: 999px;
            background-color: rgba($black, 0.35);
            overflow: hidden;
            span {
              display: block;
              height: 100%;
              border-radius: inherit;
              background: linear-gradient(90deg, rgba($orange, 0.9), rgba($red, 0.9));
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
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
    }
    .vote-pairs {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      .vote-card {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 8px;
        border-radius: 5px;
        border: 1px solid rgba($grey, 0.35);
        background-color: rgba($black, 0.15);
        span {
          color: $ashy;
          font-size: 13px;
        }
        strong {
          font-size: 15px;
        }
      }
    }
  }
}

@media (max-width: 1240px) {
  .stats-tab {
    .stats-layout {
      .non-game-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .overview {
        grid-template-columns: 1fr;
        .rings {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }
      .roles-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .extra-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .best-move {
        grid-template-columns: 1fr;
      }
    }
  }
}

@media (max-width: 760px) {
  .stats-tab {
    .stats-head {
      .reload {
        min-width: 100px;
      }
    }
    .stats-layout {
      .non-game-grid,
      .roles-grid,
      .recent-list,
      .extra-grid,
      .vote-pairs,
      .overview .overview-cards,
      .overview .rings {
        grid-template-columns: 1fr;
      }
      .overview {
        .rings {
          .ring-card {
            .ring {
              width: 72px;
              height: 72px;
            }
          }
        }
      }
      .metric-card {
        min-height: 64px;
        strong {
          font-size: 18px;
        }
      }
    }
  }
}
</style>
