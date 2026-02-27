<template>
  <section class="profile-history">
    <div class="history-filters">
      <button v-for="option in roleFilterOptions" :key="option.value" class="history-filter-btn" type="button"
              :class="{ active: roleFilter === option.value }" @click="setRoleFilter(option.value)">
        <span v-if="option.value === 'all'">{{ option.label }}</span>
        <img v-else class="history-filter-icon" :src="filterOptionIcon(option)" :alt="option.label" />
      </button>
    </div>

    <div v-if="loading" class="history-state">Загрузка...</div>
    <div v-else-if="error" class="history-state history-state--error">{{ error }}</div>
    <div v-else-if="items.length === 0" class="history-state">Личная история пока пуста</div>

    <ul v-else class="history-list">
      <li v-for="game in items" :key="game.id" class="history-item"
          :class="{ open: isExpanded(game.id), 'history-item--red': game.result === 'red', 'history-item--black': game.result === 'black' }">
        <button class="history-main" type="button" :aria-expanded="isExpanded(game.id)" @click="toggleExpanded(game.id)">
          <div class="history-main-div">
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
            </div>
            <img v-if="game.player_role" class="game-role-icon" :src="playerRoleIcon(game.player_role)" :alt="roleLabel(game.player_role)" />
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
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '@/services/axios'
import { formatLocalDateTime } from '@/services/datetime'
import GameHistoryDetails from '@/components/GameHistoryDetails.vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconArrowDown from '@/assets/svg/arrowDown.svg'
import iconRoleCitizen from '@/assets/images/roleCitizen.png'
import iconRoleMafia from '@/assets/images/roleMafia.png'
import iconRoleDon from '@/assets/images/roleDon.png'
import iconRoleSheriff from '@/assets/images/roleSheriff.png'

type GameHistoryRole = 'citizen' | 'mafia' | 'don' | 'sheriff'
type GameHistoryRoleFilter = 'all' | GameHistoryRole
type LeaveReason = 'vote' | 'foul' | 'suicide' | 'night'
type FarewellVerdict = 'citizen' | 'mafia'
type NightCheckVerdict = 'citizen' | 'mafia' | 'sheriff'

interface RoleFilterOption {
  value: GameHistoryRoleFilter
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
  player_role?: GameHistoryRole | null
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
const roleFilter = ref<GameHistoryRoleFilter>('all')
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

const roleFilterOptions: RoleFilterOption[] = [
  { value: 'all', label: 'Все игры' },
  { value: 'citizen', label: 'Мирный' },
  { value: 'sheriff', label: 'Шериф' },
  { value: 'mafia', label: 'Мафия' },
  { value: 'don', label: 'Дон' },
]

const roleIcons: Record<GameHistoryRole, string> = {
  citizen: iconRoleCitizen,
  sheriff: iconRoleSheriff,
  mafia: iconRoleMafia,
  don: iconRoleDon,
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
    const countBlack = Math.max(0, intOr(game.black_alive_at_finish, 0))
    return `Победа мафии ${countBlack}в${countBlack}`
  }
  return 'Ничья'
}

function roleLabel(role: GameHistoryRole): string {
  if (role === 'citizen') return 'Мирный'
  if (role === 'sheriff') return 'Шериф'
  if (role === 'mafia') return 'Мафия'
  return 'Дон'
}

function playerRoleIcon(role: GameHistoryRole): string {
  return roleIcons[role]
}

function filterOptionIcon(option: RoleFilterOption): string {
  if (option.value === 'all') return ''
  return roleIcons[option.value]
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

function setRoleFilter(nextRole: GameHistoryRoleFilter): void {
  if (roleFilter.value === nextRole) return
  roleFilter.value = nextRole
  page.value = 1
  void fetchHistory()
}

async function fetchHistory(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  error.value = ''
  try {
    const params: { page: number; role?: GameHistoryRole } = { page: page.value }
    if (roleFilter.value !== 'all') {
      params.role = roleFilter.value
    }
    const { data } = await api.get<GameHistoryResponse>('/users/games/history/personal', {
      params,
    })
    if (seq !== requestSeq) return

    const responsePage = Math.max(1, intOr(data?.page, page.value))
    const responsePages = Math.max(1, intOr(data?.pages, 1))
    page.value = Math.min(responsePage, responsePages)
    pages.value = responsePages
    total.value = Math.max(0, intOr(data?.total, 0))
    items.value = Array.isArray(data?.items) ? data.items : []
    clearDetailsCache()
    clearExpanded()
  } catch (e: any) {
    if (seq !== requestSeq) return
    const status = Number(e?.response?.status || 0)
    if (status === 429) {
      error.value = 'Слишком много запросов, попробуйте позже'
    } else {
      error.value = 'Не удалось загрузить личную историю игр'
    }
    items.value = []
    total.value = 0
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
.profile-history {
  display: flex;
  flex-direction: column;
  justify-self: center;
  gap: 10px;
  width: min(1100px, 100%);
  .history-filters {
    display: flex;
    justify-content: center;
    gap: 10px;
    .history-filter-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0 10px;
      height: 30px;
      border: none;
      border-radius: 5px;
      background-color: $graphite;
      color: $fg;
      font-size: 14px;
      cursor: pointer;
      transition: background-color 0.25s ease-in-out, color 0.25s ease-in-out;
      &:hover {
        background-color: $lead;
      }
      &.active {
        background-color: $fg;
        color: $bg;
      }
      .history-filter-icon {
        width: 20px;
        height: 20px;
        object-fit: contain;
      }
    }
  }
  .history-state {
    padding: 20px 10px;
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
      transition: background-color 0.25s ease-in-out;
      &.history-item--red:not(.open) {
        background-color: rgba($red, 0.5);
      }
      &.history-item--black:not(.open) {
        background-color: $graphite;
      }
      &.open {
        background-color: $lead;
      }
      .history-main {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 15px;
        gap: 10px;
        width: 100%;
        border: none;
        background: none;
        color: inherit;
        text-align: left;
        cursor: pointer;
        .history-main-div {
          display: flex;
          align-items: center;
          justify-content: space-between;
          min-width: 450px;
          .history-main-left {
            display: flex;
            flex-direction: column;
            gap: 5px;
            min-width: 0;
            .game-number-row {
              display: flex;
              align-items: center;
              gap: 10px;
            }
            .game-number {
              color: $fg;
              font-size: 16px;
            }
            .game-head {
              display: flex;
              align-items: center;
              gap: 5px;
              min-width: 0;
              color: $ashy;
              img {
                width: 20px;
                height: 20px;
                border-radius: 50%;
                object-fit: cover;
              }
              span {
                color: $fg;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
              }
            }
          }
          .game-role-icon {
            margin-right: 175px;
            width: 45px;
            height: 45px;
          }
        }
        .history-main-mid {
          display: flex;
          flex-direction: column;
          gap: 5px;
          min-width: 0;
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
    padding-top: 10px;
    gap: 10px;
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
}

</style>
