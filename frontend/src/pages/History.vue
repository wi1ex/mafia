<template>
  <main class="history-page">
    <section class="history-card">
      <header class="history-header">
        <h1>История игр</h1>
        <div class="history-header-stats">
          <div class="history-header-stat">
            <span class="history-header-stat-label">Победы мирных</span>
            <span class="history-header-stat-value history-header-stat-value--red">{{ totalRedWins }}</span>
          </div>
          <div class="history-header-stat">
            <span class="history-header-stat-label">Победы мафии</span>
            <span class="history-header-stat-value history-header-stat-value--black">{{ totalBlackWins }}</span>
          </div>
        </div>
      </header>

      <form v-if="isAdmin" class="history-admin-filters" @submit.prevent="applyAdminFilters">
        <div class="history-admin-filters-grid">
          <UiInput
            id="history-duration-lt"
            v-model.number="adminFilters.durationLtMinutes"
            type="number"
            min="1"
            step="1"
            inputmode="numeric"
            autocomplete="off"
            :disabled="loading"
            label="Длительность меньше, мин"
          />
          <UiInput
            id="history-duration-gt"
            v-model.number="adminFilters.durationGtMinutes"
            type="number"
            min="1"
            step="1"
            inputmode="numeric"
            autocomplete="off"
            :disabled="loading"
            label="Длительность больше, мин"
          />
          <UiInput
            id="history-number-from"
            v-model.number="adminFilters.gameNumberFrom"
            type="number"
            min="1"
            step="1"
            inputmode="numeric"
            autocomplete="off"
            :disabled="loading"
            label="Номер игры от"
          />
          <UiInput
            id="history-number-to"
            v-model.number="adminFilters.gameNumberTo"
            type="number"
            min="1"
            step="1"
            inputmode="numeric"
            autocomplete="off"
            :disabled="loading"
            label="Номер игры до"
          />
          <UiInput
            id="history-foul-removals"
            v-model.number="adminFilters.foulRemovals"
            type="number"
            min="0"
            step="1"
            inputmode="numeric"
            autocomplete="off"
            :disabled="loading"
            label="Удалений по фолам"
          />
          <UiInput
            id="history-suicides"
            v-model.number="adminFilters.suicides"
            type="number"
            min="0"
            step="1"
            inputmode="numeric"
            autocomplete="off"
            :disabled="loading"
            label="Самоубийств"
          />
          <UiDropdown
            id="history-result-filter"
            v-model="adminFilters.result"
            :options="resultFilterOptions"
            :disabled="loading"
            label="Результат"
          />
          <div class="history-admin-filters-actions">
            <UiButton
              class="history-filter-action"
              type="submit"
              text="Применить"
              :disabled="loading"
            />
            <UiButton
              class="history-filter-action"
              type="button"
              variant="white"
              text="Сбросить"
              :disabled="loading || !hasAnyAdminFilters"
              @click="resetAdminFilters"
            />
          </div>
        </div>
      </form>

      <div v-if="loading" class="history-state">Загрузка...</div>
      <div v-else-if="error" class="history-state history-state--error">{{ error }}</div>
      <div v-else-if="items.length === 0" class="history-state">История пока пуста</div>

      <ul v-else class="history-list">
        <li v-for="game in items" :key="game.id" class="history-item"
            :class="{ open: isExpanded(game.id), 'history-item--red': game.result === 'red', 'history-item--black': game.result === 'black' }">
          <button class="history-main" type="button" :aria-expanded="isExpanded(game.id)" @click="toggleExpanded(game.id)">
            <div class="history-main-left">
              <div class="game-number-row">
                <span class="game-number">Игра #{{ game.number }}</span>
                <HistoryActions
                  v-if="isExpanded(game.id)"
                  :game-id="game.id"
                  :game-number="game.number"
                  :game-result="game.result"
                  :details-slots="detailsSlots(game.id)"
                  :details-loading="isDetailsLoading(game.id)"
                  @result-updated="handleGameResultUpdated"
                  @ppk-updated="handleGamePpkUpdated"
                  @foul-removals-updated="handleGameFoulRemovalsUpdated"
                />
              </div>
              <div class="game-head">
                <span>Ведущий:</span>
                <template v-if="game.head.auto">
                  <span>Авто</span>
                </template>
                <template v-else>
                  <img v-minio-img="{ key: game.head.avatar_name ? `avatars/${game.head.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                  <span>{{ headName(game) }}</span>
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
              <HistoryDetails v-else :slots="detailsSlots(game.id)" />
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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '@/services/axios'
import { formatLocalDateTime } from '@/services/datetime'
import { useUserStore } from '@/store'
import HistoryDetails from '@/components/HistoryDetails.vue'
import HistoryActions from '@/components/HistoryActions.vue'
import UiButton from '@/components/UiButton.vue'
import UiDropdown from '@/components/UiDropdown.vue'
import UiInput from '@/components/UiInput.vue'

import defaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconArrowDown from '@/assets/svg/iconArrow.svg'

type GameHistoryRole = 'citizen' | 'mafia' | 'don' | 'sheriff'
type GameResult = 'red' | 'black' | 'draw'
type GameResultFilter = 'all' | GameResult
type AdminNumberFilterValue = number | ''
type LeaveReason = 'vote' | 'foul' | 'suicide' | 'night'
type FarewellVerdict = 'citizen' | 'mafia'
type NightCheckVerdict = 'citizen' | 'mafia' | 'sheriff'

interface AdminGameHistoryFilters {
  durationLtMinutes: AdminNumberFilterValue
  durationGtMinutes: AdminNumberFilterValue
  gameNumberFrom: AdminNumberFilterValue
  gameNumberTo: AdminNumberFilterValue
  foulRemovals: AdminNumberFilterValue
  suicides: AdminNumberFilterValue
  result: GameResultFilter
}

interface ResultFilterOption {
  value: GameResultFilter
  label: string
}

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
  profile_role?: string | null
  deleted?: boolean | null
  role?: GameHistoryRole | null
  points: number
  mmr: number
  leave_day?: number | null
  leave_reason?: LeaveReason | null
  leave_ppk?: boolean | null
  voted_by_slots?: number[] | null
  best_move_slots?: number[] | null
  farewell?: GameHistoryFarewellItem[] | null
  night_checks?: GameHistoryNightCheckItem[] | null
}

interface GameHistoryListItem {
  id: number
  number: number
  head: GameHistoryHost
  result: GameResult
  has_ppk?: boolean
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
  items: GameHistoryListItem[]
}

const loading = ref(false)
const error = ref('')
const page = ref(1)
const pages = ref(1)
const total = ref(0)
const totalRedWins = ref(0)
const totalBlackWins = ref(0)
const items = ref<GameHistoryListItem[]>([])
const expanded = ref<Set<number>>(new Set())
const detailsByGameId = ref<Record<number, GameHistorySlot[]>>({})
const detailsErrors = ref<Record<number, string>>({})
const detailsLoading = ref<Set<number>>(new Set())
const userStore = useUserStore()
const adminFilters = ref<AdminGameHistoryFilters>(emptyAdminFilters())
const appliedAdminFilters = ref<AdminGameHistoryFilters>(emptyAdminFilters())

let requestSeq = 0

const DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
}

const resultFilterOptions: ResultFilterOption[] = [
  { value: 'all', label: 'Все результаты' },
  { value: 'red', label: 'Победа красных' },
  { value: 'black', label: 'Победа чёрных' },
  { value: 'draw', label: 'Ничья' },
]

const isAdmin = computed(() => String(userStore.user?.role || '').trim().toLowerCase() === 'admin')
const hasAnyAdminFilters = computed(() => hasAdminFilterValues(adminFilters.value) || hasAdminFilterValues(appliedAdminFilters.value))

function emptyAdminFilters(): AdminGameHistoryFilters {
  return {
    durationLtMinutes: '',
    durationGtMinutes: '',
    gameNumberFrom: '',
    gameNumberTo: '',
    foulRemovals: '',
    suicides: '',
    result: 'all',
  }
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

function adjustResultTotal(result: GameResult, delta: number): void {
  if (delta === 0) return
  if (result === 'red') totalRedWins.value = Math.max(0, totalRedWins.value + delta)
  else if (result === 'black') totalBlackWins.value = Math.max(0, totalBlackWins.value + delta)
}

async function fetchGameDetails(gameId: number, force = false): Promise<void> {
  if (!force && detailsByGameId.value[gameId]) return
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

function reloadGameDetails(gameId: number): void {
  const nextDetails = { ...detailsByGameId.value }
  delete nextDetails[gameId]
  detailsByGameId.value = nextDetails
  void fetchGameDetails(gameId, true)
}

function resultLabel(game: GameHistoryListItem): string {
  if (game.result === 'red') return game.has_ppk ? 'Победа мирных (ППК)' : 'Победа мирных'
  if (game.result === 'black') {
    if (game.has_ppk) return 'Победа мафии (ППК)'
    const count_black = Math.max(0, intOr(game.black_alive_at_finish, 0))
    if (count_black <= 0) return 'Победа мафии'
    return `Победа мафии ${count_black}в${count_black}`
  }
  return 'Ничья'
}

function handleGameResultUpdated(payload: { gameId: number; result: GameResult; previousResult: GameResult }): void {
  if (payload.result === payload.previousResult) return
  items.value = items.value.map((game) => (
    game.id === payload.gameId ? { ...game, result: payload.result } : game
  ))
  adjustResultTotal(payload.previousResult, -1)
  adjustResultTotal(payload.result, 1)
}

function handleGamePpkUpdated(payload: { gameId: number; userId: number | null; previousUserId: number | null }): void {
  items.value = items.value.map((game) => (
    game.id === payload.gameId ? { ...game, has_ppk: payload.userId !== null } : game
  ))

  const currentSlots = detailsByGameId.value[payload.gameId]
  if (!Array.isArray(currentSlots) || currentSlots.length === 0) return

  const nextSlots = currentSlots.map((slot) => {
    const slotUserId = intOr(slot.user_id, 0)
    let nextLeavePpk = Boolean(slot.leave_ppk)
    if (payload.previousUserId !== null && slotUserId === payload.previousUserId) nextLeavePpk = false
    if (payload.userId !== null && slotUserId === payload.userId) nextLeavePpk = true
    if (nextLeavePpk === Boolean(slot.leave_ppk)) return slot
    return { ...slot, leave_ppk: nextLeavePpk }
  })

  detailsByGameId.value = {
    ...detailsByGameId.value,
    [payload.gameId]: nextSlots,
  }
}

function handleGameFoulRemovalsUpdated(payload: { gameId: number; ppkUserId: number | null }): void {
  items.value = items.value.map((game) => (
    game.id === payload.gameId ? { ...game, has_ppk: payload.ppkUserId !== null } : game
  ))
  reloadGameDetails(payload.gameId)
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

function normalizedNumberFilterValue(raw: AdminNumberFilterValue, allowZero = false): AdminNumberFilterValue {
  if (raw === '') return ''
  const value = Number(raw)
  if (!Number.isFinite(value)) return ''
  const normalized = Math.trunc(value)
  if (allowZero) return normalized >= 0 ? normalized : ''
  return normalized > 0 ? normalized : ''
}

function normalizeAdminFilters(raw: AdminGameHistoryFilters): AdminGameHistoryFilters {
  const result = raw.result === 'red' || raw.result === 'black' || raw.result === 'draw' ? raw.result : 'all'
  return {
    durationLtMinutes: normalizedNumberFilterValue(raw.durationLtMinutes),
    durationGtMinutes: normalizedNumberFilterValue(raw.durationGtMinutes),
    gameNumberFrom: normalizedNumberFilterValue(raw.gameNumberFrom),
    gameNumberTo: normalizedNumberFilterValue(raw.gameNumberTo),
    foulRemovals: normalizedNumberFilterValue(raw.foulRemovals, true),
    suicides: normalizedNumberFilterValue(raw.suicides, true),
    result,
  }
}

function hasAdminFilterValues(filters: AdminGameHistoryFilters): boolean {
  return filters.durationLtMinutes !== ''
    || filters.durationGtMinutes !== ''
    || filters.gameNumberFrom !== ''
    || filters.gameNumberTo !== ''
    || filters.foulRemovals !== ''
    || filters.suicides !== ''
    || filters.result !== 'all'
}

function appendNumberParam(params: Record<string, number | string>, key: string, value: AdminNumberFilterValue): void {
  if (value === '') return
  params[key] = value
}

function buildHistoryParams(): Record<string, number | string> {
  const params: Record<string, number | string> = { page: page.value }
  if (!isAdmin.value) return params

  const filters = appliedAdminFilters.value
  appendNumberParam(params, 'duration_lt_minutes', filters.durationLtMinutes)
  appendNumberParam(params, 'duration_gt_minutes', filters.durationGtMinutes)
  appendNumberParam(params, 'game_number_from', filters.gameNumberFrom)
  appendNumberParam(params, 'game_number_to', filters.gameNumberTo)
  appendNumberParam(params, 'foul_removals', filters.foulRemovals)
  appendNumberParam(params, 'suicides', filters.suicides)
  if (filters.result !== 'all') params.result = filters.result
  return params
}

function applyAdminFilters(): void {
  if (!isAdmin.value || loading.value) return
  const normalized = normalizeAdminFilters(adminFilters.value)
  adminFilters.value = { ...normalized }
  appliedAdminFilters.value = { ...normalized }
  page.value = 1
  void fetchHistory()
}

function resetAdminFilters(): void {
  if (!isAdmin.value || loading.value) return
  const nextFilters = emptyAdminFilters()
  adminFilters.value = { ...nextFilters }
  appliedAdminFilters.value = { ...nextFilters }
  page.value = 1
  void fetchHistory()
}

async function fetchHistory(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<GameHistoryResponse>('/users/games/history', {
      params: buildHistoryParams(),
    })
    if (seq !== requestSeq) return

    const responsePage = Math.max(1, intOr(data?.page, page.value))
    const responsePages = Math.max(1, intOr(data?.pages, 1))
    page.value = Math.min(responsePage, responsePages)
    pages.value = responsePages
    total.value = Math.max(0, intOr(data?.total, 0))
    totalRedWins.value = Math.max(0, intOr(data?.total_red_wins, 0))
    totalBlackWins.value = Math.max(0, intOr(data?.total_black_wins, 0))
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
  justify-content: center;
  padding: 10px;
  width: 100%;
  box-sizing: border-box;
  scrollbar-width: none;
  overflow: auto;
  .history-card {
    display: flex;
    flex-direction: column;
    margin-bottom: 10px;
    gap: 10px;
    width: min(1100px, 100%);
    .history-header {
      display: flex;
      position: relative;
      flex-direction: column;
      align-items: flex-start;
      padding: 50px 15px 15px;
      border-radius: 5px;
      background-color: $neutral-100;
      box-shadow: 0 15px 20px rgba($neutral-white, 0.1), 0 5px 10px rgba($neutral-white, 0.1);
      h1 {
        position: absolute;
        top: 15px;
        margin: 0;
        color: $neutral-black;
        font-size: 26px;
      }
      .history-header-stats {
        display: grid;
        grid-template-columns: repeat(1, minmax(0, 1fr));
        gap: 10px;
        width: 100%;
        .history-header-stat {
          display: flex;
          align-items: center;
          justify-self: flex-end;
          gap: 5px;
          min-width: 0;
        }
        .history-header-stat-label {
          text-align: center;
          color: $neutral-black;
          font-size: 14px;
          line-height: 1.2;
        }
        .history-header-stat-value {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0 10px;
          min-width: 50px;
          height: 25px;
          border-radius: 5px;
          color: $neutral-100;
          font-size: 14px;
          font-weight: bold;
          &.history-header-stat-value--red {
            background-color: $red-500;
          }
          &.history-header-stat-value--black {
            background-color: $neutral-800;
          }
        }
      }
    }
    .history-admin-filters {
      display: flex;
      flex-direction: column;
      padding: 15px;
      gap: 12px;
      border-radius: 5px;
      border: 1px solid rgba($neutral-500, 0.3);
      background-color: $neutral-900;
      .history-admin-filters-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        :deep(input),
        :deep(label),
        :deep(.ui-dropdown__trigger),
        :deep(.option),
        :deep(.empty) {
          letter-spacing: 0;
        }
      }
      .history-admin-filters-actions {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 10px;
        .history-filter-action {
          width: 120px;
          --ui-button-letter-spacing: 0;
        }
      }
    }
    .history-state {
      padding: 40px 10px;
      text-align: center;
      color: $neutral-300;
      &.history-state--error {
        color: $orange-500;
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
        background-color: $neutral-800;
        box-shadow: 0 5px 10px rgba(black, 0.25);
        overflow: hidden;
        transition: background-color 0.25s ease-in-out;
        &.history-item--red:not(.open) {
          background-color: rgba($red-500, 0.5);
        }
        &.history-item--black:not(.open) {
          background-color: $neutral-800;
        }
        &.open {
          background-color: $neutral-700;
        }
        .history-main {
          display: grid;
          grid-template-columns: minmax(220px, 1fr) minmax(320px, 1fr) 24px;
          align-items: center;
          padding: 15px;
          gap: 10px;
          width: 100%;
          border: none;
          background: none;
          color: inherit;
          text-align: left;
          cursor: pointer;
          .history-main-left,
          .history-main-mid {
            display: flex;
            flex-direction: column;
            gap: 5px;
            min-width: 0;
          }
          .history-main-left {
            .game-number-row {
              display: flex;
              align-items: center;
              gap: 10px;
              min-width: 0;
            }
            .game-number {
              color: $neutral-100;
              font-size: 16px;
            }
            .game-head {
              display: flex;
              align-items: center;
              gap: 5px;
              min-width: 0;
              color: $neutral-300;
              img {
                width: 20px;
                height: 20px;
                border-radius: 50%;
                object-fit: cover;
              }
              span {
                color: $neutral-100;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
              }
            }
          }
          .history-main-mid {
            span {
              color: $neutral-300;
              white-space: nowrap;
              overflow: hidden;
              text-overflow: ellipsis;
            }
            .game-result {
              color: $neutral-100;
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
            color: $neutral-300;
            font-size: 14px;
            &.history-extra-state--error {
              color: $orange-500;
            }
          }
        }
      }
    }
    .history-pager {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 10px 0 20px;
      gap: 10px;
      color: $neutral-300;
      font-size: 14px;
      .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 90px;
        height: 40px;
        border: none;
        border-radius: 5px;
        background-color: $neutral-800;
        color: $neutral-100;
        cursor: pointer;
        transition: background-color 0.25s ease-in-out, opacity 0.25s ease-in-out;
        &:hover {
          background-color: $neutral-700;
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

</style>
