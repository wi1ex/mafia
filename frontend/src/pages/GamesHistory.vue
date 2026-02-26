<template>
  <main class="history-page">
    <section class="history-card">
      <header class="history-header">
        <h1>История игр</h1>
        <p class="history-header-stats">Победы мирных: {{ totalRedWins }} · Победы мафии: {{ totalBlackWins }} · Ничьи: {{ totalDraws }}</p>
      </header>

      <div v-if="loading" class="history-state">Загрузка...</div>
      <div v-else-if="error" class="history-state history-state--error">{{ error }}</div>
      <div v-else-if="items.length === 0" class="history-state">История пока пуста</div>

      <ul v-else class="history-list">
        <li v-for="game in items" :key="game.id" class="history-item"
            :class="{ open: isExpanded(game.id), 'history-item--red': game.result === 'red', 'history-item--black': game.result === 'black' }">
          <button class="history-main" type="button" :aria-expanded="isExpanded(game.id)" @click="toggleExpanded(game.id)">
            <div class="history-main-left">
              <span class="game-number">Игра #{{ game.number }}</span>
              <div class="game-head">
                <span>Ведущий:</span>
                <template v-if="game.head.auto">
                  <strong>Авто</strong>
                </template>
                <template v-else>
                  <img v-minio-img="{ key: game.head.avatar_name ? `avatars/${game.head.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                  <strong>{{ headName(game) }}</strong>
                </template>
              </div>
            </div>

            <div class="history-main-mid">
              <span class="game-result">{{ resultLabel(game) }}</span>
              <span>Начало: {{ formatStart(game.started_at) }}</span>
              <span>Длительность: {{ formatDuration(game.duration_seconds) }}</span>
            </div>

            <img class="arrow" :class="{ open: isExpanded(game.id) }" :src="iconArrowDown" alt="" />
          </button>

          <Transition name="history-expand">
            <div v-if="isExpanded(game.id)" class="history-extra">
              <div v-if="isDetailsLoading(game.id)" class="history-extra-state">Загрузка деталей игры...</div>
              <div v-else-if="detailsErrorFor(game.id)" class="history-extra-state history-extra-state--error">{{ detailsErrorFor(game.id) }}</div>
              <GameHistoryDetails v-else :slots="detailsSlots(game.id)" />
            </div>
          </Transition>
        </li>
      </ul>

      <footer class="history-pager">
        <button class="btn" type="button" :disabled="loading || page <= 1" @click="prevPage">Назад</button>
        <span>Страница {{ page }} из {{ pages }} · Игр: {{ total }}</span>
        <button class="btn" type="button" :disabled="loading || page >= pages" @click="nextPage">Вперёд</button>
      </footer>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '@/services/axios'
import { formatLocalDateTime } from '@/services/datetime'
import GameHistoryDetails from '@/components/GameHistoryDetails.vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconArrowDown from '@/assets/svg/arrowDown.svg'

type GameHistoryRole = 'citizen' | 'mafia' | 'don' | 'sheriff'
type LeaveReason = 'vote' | 'foul' | 'suicide' | 'night'
type FarewellVerdict = 'citizen' | 'mafia'
type NightCheckVerdict = 'citizen' | 'mafia' | 'sheriff'

interface GameHistoryHost {
  id?: number | null
  username?: string | null
  avatar_name?: string | null
  auto: boolean
}

interface GameHistoryFarewellItem {
  slot: number
  verdict: FarewellVerdict
}

interface GameHistoryNightCheckItem {
  slot: number
  verdict: NightCheckVerdict
}

interface GameHistorySlot {
  slot: number
  user_id?: number | null
  username?: string | null
  avatar_name?: string | null
  role?: GameHistoryRole | null
  points: number
  mmr: number
  leave_day?: number | null
  leave_reason?: LeaveReason | null
  voted_by_slots?: number[] | null
  best_move_slots?: number[] | null
  farewell?: GameHistoryFarewellItem[] | null
  night_checks?: GameHistoryNightCheckItem[] | null
}

interface GameHistoryListItem {
  id: number
  number: number
  head: GameHistoryHost
  result: 'red' | 'black' | 'draw'
  black_alive_at_finish: number
  started_at: string
  finished_at: string
  duration_seconds: number
}

interface GameHistoryDetailsResponse {
  id: number
  slots: GameHistorySlot[]
}

interface GameHistoryResponse {
  total: number
  page: number
  pages: number
  per_page: number
  total_red_wins: number
  total_black_wins: number
  total_draws: number
  items: GameHistoryListItem[]
}

const loading = ref(false)
const error = ref('')
const page = ref(1)
const pages = ref(1)
const total = ref(0)
const totalRedWins = ref(0)
const totalBlackWins = ref(0)
const totalDraws = ref(0)
const items = ref<GameHistoryListItem[]>([])
const expanded = ref<Set<number>>(new Set())
const detailsByGameId = ref<Record<number, GameHistorySlot[]>>({})
const detailsErrors = ref<Record<number, string>>({})
const detailsLoading = ref<Set<number>>(new Set())

let requestSeq = 0

const DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
}

function intOr(raw: unknown, fallback: number): number {
  const n = Number(raw)
  if (!Number.isFinite(n)) return fallback
  return Math.trunc(n)
}

function clearExpanded(): void {
  expanded.value = new Set()
}

function clearDetailsCache(): void {
  detailsByGameId.value = {}
  detailsErrors.value = {}
  detailsLoading.value = new Set()
}

function isExpanded(gameId: number): boolean {
  return expanded.value.has(gameId)
}

function toggleExpanded(gameId: number): void {
  const next = new Set(expanded.value)
  if (next.has(gameId)) {
    next.delete(gameId)
  } else {
    next.add(gameId)
    void fetchGameDetails(gameId)
  }
  expanded.value = next
}

function isDetailsLoading(gameId: number): boolean {
  return detailsLoading.value.has(gameId)
}

function detailsErrorFor(gameId: number): string {
  return detailsErrors.value[gameId] || ''
}

function detailsSlots(gameId: number): GameHistorySlot[] {
  return detailsByGameId.value[gameId] || []
}

async function fetchGameDetails(gameId: number): Promise<void> {
  if (detailsByGameId.value[gameId]) return
  if (detailsLoading.value.has(gameId)) return

  const loadingNext = new Set(detailsLoading.value)
  loadingNext.add(gameId)
  detailsLoading.value = loadingNext

  const errorsNext = { ...detailsErrors.value }
  delete errorsNext[gameId]
  detailsErrors.value = errorsNext

  try {
    const { data } = await api.get<GameHistoryDetailsResponse>(`/users/games/history/${gameId}`)
    const slots = Array.isArray(data?.slots) ? data.slots : []
    detailsByGameId.value = {
      ...detailsByGameId.value,
      [gameId]: slots,
    }
  } catch (e: any) {
    const status = Number(e?.response?.status || 0)
    const msg = status === 404 ? 'Игра не найдена' : 'Не удалось загрузить детали игры'
    detailsErrors.value = {
      ...detailsErrors.value,
      [gameId]: msg,
    }
  } finally {
    const loadingDone = new Set(detailsLoading.value)
    loadingDone.delete(gameId)
    detailsLoading.value = loadingDone
  }
}

function resultLabel(game: GameHistoryListItem): string {
  if (game.result === 'red') return 'Победа мирных'
  if (game.result === 'black') {
    const count_black = Math.max(0, intOr(game.black_alive_at_finish, 0))
    return `Победа мафии ${count_black}в${count_black}`
  }
  return 'Ничья'
}

function headName(game: GameHistoryListItem): string {
  const name = (game.head.username || '').trim()
  if (name) return name
  const id = intOr(game.head.id, 0)
  return id > 0 ? `user${id}` : 'Авто'
}

function formatStart(value: string): string {
  return formatLocalDateTime(value, DATE_OPTIONS)
}

function formatDuration(secondsRaw: number): string {
  const totalSec = Math.max(0, intOr(secondsRaw, 0))
  const hours = Math.floor(totalSec / 3600)
  const minutes = Math.floor((totalSec % 3600) / 60)
  const seconds = totalSec % 60
  if (hours > 0) {
    return `${hours}ч ${String(minutes).padStart(2, '0')}м ${String(seconds).padStart(2, '0')}с`
  }
  return `${minutes}м ${String(seconds).padStart(2, '0')}с`
}

async function fetchHistory(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<GameHistoryResponse>('/users/games/history', {
      params: { page: page.value },
    })
    if (seq !== requestSeq) return

    const responsePage = Math.max(1, intOr(data?.page, page.value))
    const responsePages = Math.max(1, intOr(data?.pages, 1))
    page.value = Math.min(responsePage, responsePages)
    pages.value = responsePages
    total.value = Math.max(0, intOr(data?.total, 0))
    totalRedWins.value = Math.max(0, intOr(data?.total_red_wins, 0))
    totalBlackWins.value = Math.max(0, intOr(data?.total_black_wins, 0))
    totalDraws.value = Math.max(0, intOr(data?.total_draws, 0))
    items.value = Array.isArray(data?.items) ? data.items : []
    clearDetailsCache()
    clearExpanded()
  } catch (e: any) {
    if (seq !== requestSeq) return
    const status = Number(e?.response?.status || 0)
    if (status === 429) {
      error.value = 'Слишком много запросов, попробуйте позже'
    } else {
      error.value = 'Не удалось загрузить историю игр'
    }
    items.value = []
    total.value = 0
    totalRedWins.value = 0
    totalBlackWins.value = 0
    totalDraws.value = 0
    pages.value = 1
    clearDetailsCache()
    clearExpanded()
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function prevPage(): void {
  if (loading.value || page.value <= 1) return
  page.value -= 1
  void fetchHistory()
}

function nextPage(): void {
  if (loading.value || page.value >= pages.value) return
  page.value += 1
  void fetchHistory()
}

onMounted(() => {
  void fetchHistory()
})

onBeforeUnmount(() => {
  requestSeq += 1
})
</script>

<style scoped lang="scss">
.history-page {
  display: flex;
  width: 100%;
  justify-content: center;
  padding: 10px;
  box-sizing: border-box;
  overflow: auto;
  scrollbar-width: none;
  .history-card {
    display: flex;
    flex-direction: column;
    width: min(1100px, 100%);
    gap: 10px;
    margin-bottom: 10px;
    .history-header {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 5px;
      padding: 15px;
      border-radius: 5px;
      background-color: $fg;
      box-shadow: 0 5px 10px rgba($black, 0.25);
      h1 {
        margin: 0;
        color: $bg;
        font-size: 24px;
      }
      p {
        margin: 0;
        color: $dark;
        font-size: 14px;
      }
      .history-header-stats {
        width: 100%;
        text-align: end;
        color: $bg;
        font-size: 14px;
      }
    }
    .history-state {
      padding: 40px 10px;
      text-align: center;
      color: $ashy;
      &.history-state--error {
        color: $orange;
      }
    }
    .history-list {
      display: flex;
      flex-direction: column;
      margin: 0;
      padding: 0;
      gap: 10px;
      list-style: none;
      .history-item {
        border-radius: 5px;
        background-color: $graphite;
        box-shadow: 0 5px 10px rgba($black, 0.25);
        overflow: hidden;
        &.history-item--red:not(.open) {
          background-color: rgba($red, 0.2);
        }
        &.history-item--black:not(.open) {
          background-color: rgba($black, 0.5);
        }
        &.open {
          background-color: $lead;
        }
        .history-main {
          display: grid;
          grid-template-columns: minmax(220px, 1fr) minmax(320px, 1fr) 24px;
          align-items: center;
          gap: 10px;
          width: 100%;
          border: none;
          background: none;
          color: inherit;
          text-align: left;
          padding: 15px;
          cursor: pointer;
          .history-main-left,
          .history-main-mid {
            display: flex;
            flex-direction: column;
            gap: 5px;
            min-width: 0;
          }
          .history-main-left {
            .game-number {
              color: $fg;
              font-size: 16px;
            }
            .game-head {
              display: flex;
              align-items: center;
              gap: 5px;
              color: $ashy;
              min-width: 0;
              img {
                width: 20px;
                height: 20px;
                border-radius: 50%;
                object-fit: cover;
              }
              strong {
                color: $fg;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
              }
            }
          }
          .history-main-mid {
            span {
              color: $ashy;
              white-space: nowrap;
              overflow: hidden;
              text-overflow: ellipsis;
            }
            .game-result {
              color: $fg;
            }
          }
          .arrow {
            width: 20px;
            height: 20px;
            transition: transform 0.25s ease-in-out;
            &.open {
              transform: rotate(180deg);
            }
          }
        }
        .history-extra {
          overflow: hidden;
          .history-extra-state {
            padding: 15px 10px;
            text-align: center;
            color: $ashy;
            font-size: 14px;
            &.history-extra-state--error {
              color: $orange;
            }
          }
        }
      }
    }
    .history-pager {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 0;
      color: $ashy;
      font-size: 14px;
      .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 90px;
        height: 40px;
        border: none;
        border-radius: 5px;
        background-color: $graphite;
        color: $fg;
        cursor: pointer;
        transition: background-color 0.25s ease-in-out, opacity 0.25s ease-in-out;
        &:hover {
          background-color: $lead;
        }
        &:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      }
    }
  }

  .history-expand-enter-active,
  .history-expand-leave-active {
    transition: max-height 0.25s ease-in-out, opacity 0.25s ease-in-out;
  }
  .history-expand-enter-from,
  .history-expand-leave-to {
    max-height: 0;
    opacity: 0;
  }
  .history-expand-enter-to,
  .history-expand-leave-from {
    max-height: 1000px;
    opacity: 1;
  }
}

@media (max-width: 1280px) {
  .history-page {
    .history-card {
      .history-list {
        .history-item {
          .history-main {
            grid-template-columns: 1fr 20px;
            .history-main-mid {
              grid-column: 1 / -1;
            }
          }
        }
      }
      .history-pager {
        flex-direction: column;
        align-items: stretch;
      }
    }
  }
}

</style>
