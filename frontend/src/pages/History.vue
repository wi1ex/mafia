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
        <h2>Фильтры игр</h2>
        <div class="history-admin-filters-grid">
          <UiInput
            size="low"
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
            size="low"
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
            size="low"
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
            size="low"
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
            size="low"
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
            size="low"
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
            size="low"
            id="history-result-filter"
            v-model="adminFilters.result"
            :options="resultFilterOptions"
            :disabled="loading"
            label="Результат"
          />
          <UiDropdown
            size="low"
            id="history-mode-filter"
            v-model="adminFilters.mode"
            :options="modeFilterOptions"
            :disabled="loading"
            label="Режим игры"
          />
          <div class="history-admin-filters-actions">
            <UiButton
              size="low"
              class="history-filter-action"
              type="submit"
              text="Применить"
              :disabled="loading"
            />
            <UiButton
              size="low"
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
        <li v-for="game in items" :key="game.id" class="history-item" :class="{ open: isExpanded(game.id) }">
          <div class="history-main">
            <div class="history-main-left">
              <div class="game-number-row">
                <span class="game-number">Игра #{{ game.number }}</span>
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
              <span class="game-mode" :class="{ 'game-mode--rating': game.mode === 'rating' }">{{ game.mode === 'rating' ? 'Рейтинговая игра' : 'Обычная игра' }}</span>
            </div>

            <div class="history-main-mid">
              <span class="game-result">{{ resultLabel(game) }}</span>
              <span>Начало: {{ formatStart(game.started_at) }}</span>
              <span>Длительность: {{ formatDuration(game.duration_seconds) }}</span>
            </div>

            <button class="history-toggle" type="button" :aria-expanded="isExpanded(game.id)" :aria-controls="`history-details-${game.id}`" @click="toggleExpanded(game.id)">
              <span>{{ isExpanded(game.id) ? 'Свернуть' : 'Подробнее' }}</span>
              <img class="arrow" :class="{ open: isExpanded(game.id) }" :src="iconArrowDown" alt="" />
            </button>
          </div>
          <div v-if="isExpanded(game.id)" class="history-actions">
            <HistoryActions
              :game-id="game.id"
              :game-number="game.number"
              :game-result="game.result"
              :game-mode="game.mode"
              :details-slots="detailsSlots(game.id)"
              :details-loading="isDetailsLoading(game.id)"
              @result-updated="handleGameResultUpdated"
              @mode-updated="handleGameModeUpdated"
              @ppk-updated="handleGamePpkUpdated"
              @foul-removals-updated="handleGameFoulRemovalsUpdated"
              @scoring-marks-updated="reloadGameDetails"
            />
          </div>

          <Transition name="history-expand">
            <div v-if="isExpanded(game.id)" :id="`history-details-${game.id}`" class="history-extra">
              <div v-if="isDetailsLoading(game.id)" class="history-extra-state">Загрузка деталей игры...</div>
              <div v-else-if="detailsErrorFor(game.id)" class="history-extra-state history-extra-state--error">{{ detailsErrorFor(game.id) }}</div>
              <HistoryDetails v-else :slots="detailsSlots(game.id)" :mode="game.mode" />
            </div>
          </Transition>
        </li>
      </ul>

      <footer class="history-pager">
        <UiButton variant="white" size="middle" text="Назад" :disabled="loading || page <= 1" @click="prevPage" />
        <span>Страница {{ page }} из {{ pages }} · Игр: {{ total }}</span>
        <UiButton variant="white" size="middle" text="Вперёд" :disabled="loading || page >= pages" @click="nextPage" />
      </footer>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '@/services/axios'
import { formatLocalDateTime } from '@/services/datetime'
import { useUserStore } from '@/store'
import HistoryDetails from '@/views/HistoryDetails.vue'
import HistoryActions from '@/views/HistoryActions.vue'
import UiButton from '@/components/UiButton.vue'
import UiDropdown from '@/components/UiDropdown.vue'
import UiInput from '@/components/UiInput.vue'

import defaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconArrowDown from '@/assets/svg/iconArrow.svg'

type GameHistoryRole = 'citizen' | 'mafia' | 'don' | 'sheriff'
type GameResult = 'red' | 'black' | 'draw'
type GameMode = 'normal' | 'rating'
type GameResultFilter = 'all' | GameResult
type GameModeFilter = 'all' | GameMode
type AdminNumberFilterValue = number | ''
type LeaveReason = 'vote' | 'foul' | 'suicide' | 'night'
type FarewellVerdict = 'citizen' | 'mafia'
type NightCheckVerdict = 'citizen' | 'mafia' | 'sheriff'
type PointsBaseReason = 'win' | 'loss' | 'draw'

interface AdminGameHistoryFilters {
  durationLtMinutes: AdminNumberFilterValue
  durationGtMinutes: AdminNumberFilterValue
  gameNumberFrom: AdminNumberFilterValue
  gameNumberTo: AdminNumberFilterValue
  foulRemovals: AdminNumberFilterValue
  suicides: AdminNumberFilterValue
  result: GameResultFilter
  mode: GameModeFilter
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

interface GameHistoryPointsAdjustment {
  rule_key: string
  label: string
  points: number
}

interface GameHistoryPointsBreakdown {
  base_points: number
  base_reason: PointsBaseReason
  adjustments: GameHistoryPointsAdjustment[]
  additional_points_raw: number
  additional_points: number
  additional_points_min?: number | null
  additional_points_max?: number | null
  additional_points_capped: boolean
  rules_available: boolean
  final_points: number
}

interface GameHistorySlot {
  slot: number
  user_id?: number | null
  username?: string | null
  avatar_name?: string | null
  profile_role?: string | null
  deleted?: boolean | null
  role?: GameHistoryRole | null
  points?: number | null
  points_breakdown?: GameHistoryPointsBreakdown | null
  mmr?: number | null
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
  mode: GameMode
  result: GameResult
  has_ppk?: boolean
  black_alive_at_finish: number
  started_at: string
  finished_at: string
  duration_seconds: number
}

interface GameHistoryDetailsResponse {
  id: number
  mode: GameMode
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
  { value: 'black', label: 'Победа черных' },
  { value: 'draw', label: 'Ничья' },
]

const modeFilterOptions: { value: GameModeFilter; label: string }[] = [
  { value: 'all', label: 'Все режимы' },
  { value: 'normal', label: 'Обычный' },
  { value: 'rating', label: 'Рейтинг' },
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
    mode: 'all',
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

function handleGameModeUpdated(payload: { gameId: number; mode: GameMode }): void {
  items.value = items.value.map((game) => (
    game.id === payload.gameId ? { ...game, mode: payload.mode } : game
  ))
  reloadGameDetails(payload.gameId)
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
    mode: raw.mode === 'normal' || raw.mode === 'rating' ? raw.mode : 'all',
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
    || filters.mode !== 'all'
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
  if (filters.mode !== 'all') params.mode = filters.mode
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
  box-sizing: border-box;
  padding: 30px 40px 20px;
  width: 100%;
  min-height: 0;
  overflow: auto;
  scrollbar-width: none;
  color: $neutral-100;
  font-family: Hauora-Regular;
  line-height: 1.4;
  .history-card {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: min(1600px, 100%);
    min-width: 0;
    height: fit-content;
    .history-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      padding: 24px;
      gap: 24px;
      border-radius: 24px;
      background-color: $soft-purple-900;
      h1 {
        margin: 0;
        color: $neutral-white;
        font-family: Involve-Medium;
        font-weight: 500;
        font-size: 24px;
        line-height: 26px;
        letter-spacing: -0.48px;
      }
      .history-header-stats {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        .history-header-stat {
          display: flex;
          align-items: center;
          padding: 12px 16px;
          gap: 16px;
          border-radius: 20px;
          background-color: $soft-purple-800;
          .history-header-stat-label {
            color: $neutral-300;
            font-size: 14px;
          }
          .history-header-stat-value {
            color: $neutral-white;
            font-family: Involve-Medium;
            font-size: 24px;
            line-height: 26px;
            &--red {
              color: $red-400;
            }
          }
        }
      }
    }
    .history-admin-filters {
      display: flex;
      flex-direction: column;
      padding: 24px;
      gap: 24px;
      border-radius: 24px;
      background-color: $soft-purple-900;
      --ui-input-label-bg: #{$soft-purple-900};
      h2 {
        margin: 0;
        color: $neutral-white;
        font-family: Involve-Medium;
        font-weight: 500;
        font-size: 24px;
        line-height: 26px;
        letter-spacing: -0.48px;
      }
      .history-admin-filters-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 16px;
        .ui-input {
          :deep(input) {
            box-sizing: content-box;
          }
        }
        .history-admin-filters-actions {
          display: flex;
          grid-column: 1 / -1;
          align-items: center;
          justify-content: flex-end;
          flex-wrap: wrap;
          gap: 10px;
          .history-filter-action {
            width: 120px;
          }
        }
      }
    }
    .history-state {
      box-sizing: border-box;
      padding: 24px;
      border-radius: 24px;
      background: $soft-purple-900;
      display: grid;
      place-content: center;
      min-height: 180px;
      color: $neutral-300;
      text-align: center;
      &--error {
        color: $orange-400;
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
        min-width: 0;
        border-radius: 24px;
        background: $soft-purple-900;
        .history-main {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
          align-items: center;
          padding: 12px 24px;
          gap: 24px;
          .history-main-left {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: 6px;
            min-width: 0;
            .game-number-row {
              display: flex;
              align-items: center;
              min-width: 0;
              .game-number {
                color: $neutral-white;
                font-family: Involve-Medium;
                font-size: 20px;
                line-height: 24px;
                letter-spacing: -0.4px;
              }
            }
            .game-mode {
              padding: 6px 10px;
              border-radius: 8px;
              background: $soft-purple-800;
              color: $neutral-100;
              font-size: 12px;
              line-height: 16px;
              &--rating {
                background: rgba($green-500, 0.12);
                color: $green-500;
              }
            }
            .game-head {
              display: flex;
              align-items: center;
              gap: 4px;
              max-width: 100%;
              min-width: 0;
              font-size: 14px;
              img {
                flex: 0 0 20px;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                object-fit: cover;
              }
              span {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
              }
              span:first-child {
                flex-shrink: 0;
                color: $neutral-300;
              }
            }
          }
          .history-main-mid {
            display: flex;
            flex-direction: column;
            gap: 4px;
            color: $neutral-300;
            font-size: 14px;
            min-width: 0;
            overflow-wrap: anywhere;
            .game-result {
              color: $neutral-100;
              font-size: 16px;
            }
          }
          .history-toggle {
            display: inline-flex;
            grid-column: 3;
            align-items: center;
            justify-content: center;
            gap: 8px;
            min-width: 130px;
            min-height: 40px;
            padding: 0 12px;
            border: 1px solid $soft-purple-700;
            border-radius: 12px;
            background: transparent;
            color: $neutral-100;
            font-family: Hauora-Regular;
            font-size: 14px;
            cursor: pointer;
            transition: background-color 0.2s, border-color 0.2s;
            &:hover {
              background: $soft-purple-800;
              border-color: $neutral-300;
            }
            &:focus-visible {
              outline: 2px solid $green-500;
              outline-offset: 3px;
            }
            .arrow {
              width: 16px;
              height: 16px;
              transition: transform 0.25s;
              &.open {
                transform: rotate(180deg);
              }
            }
          }
        }
        .history-actions {
          display: flex;
          justify-content: flex-end;
          padding: 0 24px 12px;
          &:empty {
            display: none;
          }
        }
        .history-extra {
          margin: 0 24px 24px;
          padding-top: 16px;
          border-top: 1px solid $soft-purple-800;
          .history-extra-state {
            padding: 24px;
            text-align: center;
            color: $neutral-300;
            &--error {
              color: $orange-400;
            }
          }
        }
        .history-expand-enter-active, .history-expand-leave-active {
          transition: opacity 0.15s ease;
        }
        .history-expand-enter-from, .history-expand-leave-to {
          opacity: 0;
        }
      }
    }
    .history-pager {
      box-sizing: border-box;
      padding: 24px;
      border-radius: 24px;
      background: $soft-purple-900;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 16px;
      color: $neutral-300;
      font-size: 14px;
    }
  }
}
</style>
