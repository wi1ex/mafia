<template>
  <section class="moderation">
    <header>
      <nav class="tabs" aria-label="Модерация">
        <button class="tab" type="button" :class="{ active: activeTab === 'users' }" @click="activeTab = 'users'">
          Пользователи
        </button>
        <button class="tab" type="button" :class="{ active: activeTab === 'sanctions' }" @click="activeTab = 'sanctions'">
          Санкции
        </button>
        <button class="tab" type="button" :class="{ active: activeTab === 'contact_requests' }" @click="activeTab = 'contact_requests'">
          Обращения
        </button>
      </nav>
      <router-link class="btn nav" :to="{ name: 'home' }" aria-label="На главную">На главную</router-link>
    </header>

    <div class="panel">
      <div v-if="activeTab === 'users'">
        <div class="filters">
          <div class="field">
            <UiInput id="moderation-users-user" v-model.trim="usersUser" label="Никнейм" :disabled="usersLoading" />
          </div>
          <div class="field">
            <label for="moderation-users-limit">Отображать по</label>
            <select id="moderation-users-limit" :value="usersLimit" :disabled="usersLoading" @change="setUsersLimit">
              <option v-for="option in PAGE_LIMIT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
          </div>
        </div>

        <div v-if="usersLoading" class="loading">Загрузка...</div>
        <div v-else>
          <table class="table">
            <thead>
              <tr>
                <th>Никнейм</th>
                <th>
                  <button class="table-sort" :class="{ active: usersSort === 'registered_at' }" type="button" title="Сортировать по убыванию" @click="sortUsers('registered_at')">
                    Регистрация <span aria-hidden="true">↓</span>
                  </button>
                </th>
                <th>
                  <button class="table-sort" :class="{ active: usersSort === 'last_game' }" type="button" title="Сортировать по убыванию" @click="sortUsers('last_game')">
                    Последняя игра <span aria-hidden="true">↓</span>
                  </button>
                </th>
                <th>
                  <button class="table-sort" :class="{ active: usersSort === 'last_online' }" type="button" title="Сортировать по убыванию" @click="sortUsers('last_online')">
                    Последний онлайн <span aria-hidden="true">↓</span>
                  </button>
                </th>
                <th>
                  <button class="table-sort" :class="{ active: usersSort === 'last_room' }" type="button" title="Сортировать по убыванию" @click="sortUsers('last_room')">
                    Последнее общение <span aria-hidden="true">↓</span>
                  </button>
                </th>
                <th>
                  <button class="table-sort" :class="{ active: usersSort === 'last_spectator' }" type="button" title="Сортировать по убыванию" @click="sortUsers('last_spectator')">
                    Последний зритель <span aria-hidden="true">↓</span>
                  </button>
                </th>
                <th>
                  <button class="table-sort" :class="{ active: usersSort === 'suspends_count' }" type="button" title="Сортировать по убыванию" @click="sortUsers('suspends_count')">
                    Отстранения <span aria-hidden="true">↓</span>
                  </button>
                </th>
                <th>
                  <button class="table-sort" :class="{ active: usersSort === 'timeouts_count' }" type="button" title="Сортировать по убыванию" @click="sortUsers('timeouts_count')">
                    Таймауты <span aria-hidden="true">↓</span>
                  </button>
                </th>
                <th>
                  <button class="table-sort" :class="{ active: usersSort === 'bans_count' }" type="button" title="Сортировать по убыванию" @click="sortUsers('bans_count')">
                    Баны <span aria-hidden="true">↓</span>
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in users" :key="row.id">
                <td>
                  <div class="user-cell">
                    <button class="user-link user-profile-trigger" type="button" :disabled="!canOpenModerationUserMiniProfile(row)" @click="openUserMiniProfile(row)">
                      <img class="user-avatar" v-minio-img="{ key: row.avatar_name ? `avatars/${row.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                      <span>{{ row.username || `user${row.id}` }}</span>
                    </button>
                  </div>
                </td>
                <td>{{ formatLocalDateTime(row.registered_at) }}</td>
                <td>{{ formatModerationLastGame(row) }}</td>
                <td>{{ formatModerationLastOnline(row.last_visit_at, row.online) }}</td>
                <td>{{ formatRoomIdLabel(row.last_room_id) }}</td>
                <td>{{ formatRoomIdLabel(row.last_spectator_room_id) }}</td>
                <td>{{ row.suspends_count }}</td>
                <td>{{ row.timeouts_count }}</td>
                <td>{{ row.bans_count }}</td>
              </tr>
              <tr v-if="users.length === 0">
                <td colspan="9" class="muted">Нет данных</td>
              </tr>
            </tbody>
          </table>
          <div class="pager">
            <button class="btn" :disabled="usersPage <= 1" @click="prevUsers">Назад</button>
            <span>{{ usersPage }} / {{ usersPages }}</span>
            <button class="btn" :disabled="usersPage >= usersPages" @click="nextUsers">Вперед</button>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'sanctions'">
        <div class="filters">
          <div class="field">
            <UiInput id="moderation-sanctions-user" v-model.trim="sanctionsUser" label="Никнейм" :disabled="sanctionsLoading" />
          </div>
          <div class="field">
            <label for="moderation-sanctions-limit">Отображать по</label>
            <select id="moderation-sanctions-limit" :value="sanctionsLimit" :disabled="sanctionsLoading" @change="setSanctionsLimit">
              <option v-for="option in PAGE_LIMIT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
          </div>
        </div>

        <div v-if="sanctionsLoading" class="loading">Загрузка...</div>
        <div v-else>
          <table class="table sanctions-table">
            <thead>
              <tr>
                <th>Пользователь</th>
                <th>Тип санкции</th>
                <th>Статус</th>
                <th>Дата выдачи</th>
                <th>Дата окончания</th>
                <th>Кем выдана</th>
                <th>Кем снята</th>
                <th>Срок изначальный</th>
                <th>Срок по факту</th>
                <th>Отработка ведущим</th>
                <th>Пункт правил</th>
                <th>Описание</th>
                <th>Уменьшить</th>
                <th>Увеличить</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in sanctions" :key="row.id">
                <td>
                  <div class="user-cell">
                    <button class="user-link user-profile-trigger" type="button" :disabled="!canOpenSanctionUserMiniProfile(row)" @click="openSanctionUserMiniProfile(row)">
                      <img class="user-avatar" v-minio-img="{ key: row.avatar_name ? `avatars/${row.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                      <span>{{ row.username || `user${row.user_id}` }}</span>
                    </button>
                  </div>
                </td>
                <td>{{ formatSanctionKindLabel(row.kind) }}</td>
                <td>
                  <span class="status-badge" :class="sanctionStatusClass(row.status)">{{ formatSanctionStatusLabel(row.status) }}</span>
                </td>
                <td>{{ formatLocalDateTime(row.issued_at) }}</td>
                <td>{{ row.finished_at ? formatLocalDateTime(row.finished_at) : '-' }}</td>
                <td>{{ row.issued_by_display }}</td>
                <td>{{ row.revoked_by_display || '-' }}</td>
                <td>{{ formatSanctionDuration(row.duration_seconds) }}</td>
                <td>{{ formatSanctionDuration(row.served_seconds) }}</td>
                <td>{{ formatSanctionWorkoff(row) }}</td>
                <td class="rule-cell">{{ row.reason || '-' }}</td>
                <td class="description-cell">{{ row.description || '-' }}</td>
                <td class="actions-cell">
                  <button v-if="canAdjustSanction(row)" class="btn dark" :disabled="isSanctionAdjustBusy(row, 'decrease')" @click="openSanctionAdjust(row, 'decrease')">
                    Уменьшить
                  </button>
                  <span v-else>-</span>
                </td>
                <td class="actions-cell">
                  <button v-if="canAdjustSanction(row)" class="btn" :disabled="isSanctionAdjustBusy(row, 'increase')" @click="openSanctionAdjust(row, 'increase')">
                    Увеличить
                  </button>
                  <span v-else>-</span>
                </td>
              </tr>
              <tr v-if="sanctions.length === 0">
                <td colspan="14" class="muted">Нет данных</td>
              </tr>
            </tbody>
          </table>
          <div class="pager">
            <button class="btn" :disabled="sanctionsPage <= 1" @click="prevSanctions">Назад</button>
            <span>{{ sanctionsPage }} / {{ sanctionsPages }}</span>
            <button class="btn" :disabled="sanctionsPage >= sanctionsPages" @click="nextSanctions">Вперед</button>
          </div>
        </div>
      </div>

      <div v-else>
        <div class="filters">
          <div class="field">
            <UiInput id="moderation-contact-requests-user" v-model.trim="contactRequestsUser" label="Никнейм" :disabled="contactRequestsLoading" />
          </div>
          <div class="field">
            <label for="moderation-contact-requests-limit">Отображать по</label>
            <select id="moderation-contact-requests-limit" :value="contactRequestsLimit" :disabled="contactRequestsLoading" @change="setContactRequestsLimit">
              <option v-for="option in PAGE_LIMIT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
          </div>
        </div>

        <div v-if="contactRequestsLoading" class="loading">Загрузка...</div>
        <div v-else>
          <table class="table contact-requests-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Дата</th>
                <th>Никнейм</th>
                <th>Контактные данные</th>
                <th>Тема обращения</th>
                <th>Текст обращения</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in contactRequests" :key="row.id">
                <td>{{ row.id }}</td>
                <td>{{ formatLocalDateTime(row.created_at) }}</td>
                <td>
                  <div v-if="row.user_id" class="user-cell">
                    <button class="user-link user-profile-trigger" type="button" :disabled="!canOpenContactRequestUserMiniProfile(row)" @click="openContactRequestUserMiniProfile(row)">
                      <img class="user-avatar" v-minio-img="{ key: row.avatar_name ? `avatars/${row.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                      <span>{{ row.username || `user${row.user_id}` }}</span>
                    </button>
                  </div>
                  <span v-else>-</span>
                </td>
                <td class="contact-cell">{{ row.contact }}</td>
                <td class="topic-cell">{{ row.topic }}</td>
                <td class="text-cell">{{ row.text }}</td>
              </tr>
              <tr v-if="contactRequests.length === 0">
                <td colspan="6" class="muted">Нет данных</td>
              </tr>
            </tbody>
          </table>
          <div class="pager">
            <button class="btn" :disabled="contactRequestsPage <= 1" @click="prevContactRequests">Назад</button>
            <span>{{ contactRequestsPage }} / {{ contactRequestsPages }}</span>
            <button class="btn" :disabled="contactRequestsPage >= contactRequestsPages" @click="nextContactRequests">Вперед</button>
          </div>
        </div>
      </div>
    </div>

    <Sanction
      :open="sanctionAdjustModalOpen"
      :title="sanctionAdjustTitle"
      :saving="sanctionAdjustSaving"
      :can-save="sanctionAdjustCanSave"
      :show-duration="true"
      :show-reason="false"
      :show-description="false"
      :save-label="sanctionAdjustSaveLabel"
      :form="sanctionAdjustForm"
      :reasons="sanctionReasons"
      @update:open="onSanctionAdjustModalOpenUpdate"
      @save="saveSanctionAdjust"
    />
    <MiniProfile
      :open="userMiniProfileOpen"
      :user-id="userMiniProfileTarget?.id ?? null"
      :initial-profile="userMiniProfileTarget"
      :stats-url="userMiniProfileStatsUrl"
      :history-url="userMiniProfileHistoryUrl"
      show-stats-button
      admin-mode
      @update:open="onUserMiniProfileOpenUpdate"
      @staff-action-complete="onUserMiniProfileStaffActionComplete"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { formatLocalDateTime } from '@/services/datetime'
import { SANCTION_REASONS } from '@/constants/sanctionReasons'
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId } from '@/services/miniProfile'
import { useUserStore } from '@/store'

import MiniProfile from '@/components/MiniProfile.vue'
import Sanction from '@/components/Sanction.vue'
import UiInput from '@/components/UiInput.vue'

import defaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'

type TabKey = 'users' | 'sanctions' | 'contact_requests'
type SanctionListStatus = 'active' | 'expired_auto' | 'revoked'
type SanctionAdjustMode = 'increase' | 'decrease'
type SanctionsRow = {
  id: number
  user_id: number
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  deleted_at?: string | null
  kind: 'timeout' | 'ban' | 'suspend'
  status: SanctionListStatus
  issued_at: string
  finished_at?: string | null
  issued_by_id?: number | null
  issued_by_name?: string | null
  issued_by_display: string
  revoked_by_id?: number | null
  revoked_by_name?: string | null
  revoked_by_display?: string | null
  duration_seconds?: number | null
  served_seconds: number
  hosted_workoff_seconds?: number | null
  reason?: string | null
  description?: string | null
}

type UserRow = {
  id: number
  username?: string | null
  avatar_name?: string | null
  role: string
  registered_at: string
  last_visit_at?: string | null
  last_game_at?: string | null
  last_game_id?: number | null
  online: boolean
  last_room_id?: number | null
  last_spectator_room_id?: number | null
  timeouts_count: number
  bans_count: number
  suspends_count: number
}

type UserSortKey =
  | 'registered_at'
  | 'last_game'
  | 'last_online'
  | 'last_room'
  | 'last_spectator'
  | 'suspends_count'
  | 'timeouts_count'
  | 'bans_count'

type ContactRequestRow = {
  id: number
  user_id?: number | null
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  deleted_at?: string | null
  contact: string
  topic: string
  text: string
  created_at: string
}

type UserMiniProfileTarget = {
  id: number
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  deleted_at?: string | null
}

const PAGE_LIMIT_OPTIONS = [
  { value: 20, label: '20' },
  { value: 100, label: '100' },
] as const

const activeTab = ref<TabKey>('users')
const userStore = useUserStore()
const viewerUserId = computed(() => normalizeMiniProfileUserId(userStore.user?.id))
const users = ref<UserRow[]>([])
const usersLoading = ref(false)
const usersTotal = ref(0)
const usersPage = ref(1)
const usersLimit = ref(20)
const usersUser = ref('')
const usersSort = ref<UserSortKey>('registered_at')
const sanctions = ref<SanctionsRow[]>([])
const sanctionsLoading = ref(false)
const sanctionsTotal = ref(0)
const sanctionsPage = ref(1)
const sanctionsLimit = ref(20)
const sanctionsUser = ref('')
const sanctionsAdjusting = reactive<Record<string, boolean>>({})
const contactRequests = ref<ContactRequestRow[]>([])
const contactRequestsLoading = ref(false)
const contactRequestsTotal = ref(0)
const contactRequestsPage = ref(1)
const contactRequestsLimit = ref(20)
const contactRequestsUser = ref('')
let usersUserTimer: number | undefined
let sanctionsUserTimer: number | undefined
let contactRequestsUserTimer: number | undefined

const sanctionReasons = SANCTION_REASONS
const SANCTION_DURATION_LIMITS = {
  months: 240,
  days: 31,
  hours: 23,
} as const
const userMiniProfileOpen = ref(false)
const userMiniProfileTarget = ref<UserMiniProfileTarget | null>(null)
const userMiniProfileStatsUrl = computed(() => {
  const target = userMiniProfileTarget.value
  return target ? `/moderation/users/${target.id}/stats` : null
})
const userMiniProfileHistoryUrl = computed(() => {
  const target = userMiniProfileTarget.value
  return target ? `/moderation/users/${target.id}/games/history` : null
})
function isSanctionDurationPartValid(value: number, max: number): boolean {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 0 && parsed <= max
}

const usersPages = computed(() => Math.max(1, Math.ceil(usersTotal.value / usersLimit.value)))
const sanctionsPages = computed(() => Math.max(1, Math.ceil(sanctionsTotal.value / sanctionsLimit.value)))
const contactRequestsPages = computed(() => Math.max(1, Math.ceil(contactRequestsTotal.value / contactRequestsLimit.value)))
const sanctionAdjustModalOpen = ref(false)
const sanctionAdjustSaving = ref(false)
const sanctionAdjustMode = ref<SanctionAdjustMode>('increase')
const sanctionAdjustTarget = ref<SanctionsRow | null>(null)
const sanctionAdjustForm = reactive({
  months: 0,
  days: 0,
  hours: 0,
  reason: '',
  description: '',
})
const sanctionAdjustDurationValid = computed(() => (
  isSanctionDurationPartValid(sanctionAdjustForm.months, SANCTION_DURATION_LIMITS.months)
  && isSanctionDurationPartValid(sanctionAdjustForm.days, SANCTION_DURATION_LIMITS.days)
  && isSanctionDurationPartValid(sanctionAdjustForm.hours, SANCTION_DURATION_LIMITS.hours)
))
const sanctionAdjustTotalSeconds = computed(() => {
  const months = Math.max(0, Number(sanctionAdjustForm.months) || 0)
  const days = Math.max(0, Number(sanctionAdjustForm.days) || 0)
  const hours = Math.max(0, Number(sanctionAdjustForm.hours) || 0)
  const totalMinutes = (months * 30 * 24 * 60) + (days * 24 * 60) + (hours * 60)
  return totalMinutes * 60
})
const sanctionAdjustCanSave = computed(() => {
  const target = sanctionAdjustTarget.value
  return Boolean(target && canAdjustSanction(target) && sanctionAdjustDurationValid.value && sanctionAdjustTotalSeconds.value > 0)
})
const sanctionAdjustSaveLabel = computed(() => sanctionAdjustMode.value === 'increase' ? 'Увеличить' : 'Уменьшить')
const sanctionAdjustTitle = computed(() => {
  const target = sanctionAdjustTarget.value
  const actionLabel = sanctionAdjustSaveLabel.value
  if (!target) return `${actionLabel} срок санкции`
  const userLabel = target.username || `user${target.user_id}`
  return `${actionLabel} ${formatSanctionKindLabel(target.kind).toLowerCase()}: ${userLabel}`
})

function selectValue(event: Event): string {
  return (event.target as HTMLSelectElement).value
}

function normalizePageLimit(value: string): number {
  return Number(value) === 100 ? 100 : 20
}

function setUsersLimit(event: Event): void {
  usersLimit.value = normalizePageLimit(selectValue(event))
}

function sortUsers(sort: UserSortKey): void {
  usersSort.value = sort
}

function setSanctionsLimit(event: Event): void {
  sanctionsLimit.value = normalizePageLimit(selectValue(event))
}

function setContactRequestsLimit(event: Event): void {
  contactRequestsLimit.value = normalizePageLimit(selectValue(event))
}

function formatRoomIdLabel(value?: number | null): string {
  const roomId = Number(value)
  return Number.isFinite(roomId) && roomId > 0 ? `Комната ${Math.trunc(roomId)}` : '-'
}

function parseModerationDate(value?: string | number | Date | null): Date | null {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatModerationDateOnly(value?: string | number | Date | null): string {
  const date = parseModerationDate(value)
  if (!date) return '-'
  return `${String(date.getDate()).padStart(2, '0')}.${String(date.getMonth() + 1).padStart(2, '0')}.${date.getFullYear()}`
}

function formatModerationLastGame(row: UserRow): string {
  const dateLabel = formatModerationDateOnly(row.last_game_at)
  if (dateLabel === '-') return '-'
  const gameId = Number(row.last_game_id || 0)
  return Number.isFinite(gameId) && gameId > 0 ? `Игра #${Math.trunc(gameId)} от ${dateLabel}` : dateLabel
}

function formatModerationLastOnline(value?: string | null, online = false): string {
  if (online) return 'Онлайн'
  const date = parseModerationDate(value)
  if (!date) return '-'
  const totalMinutes = Math.floor((Date.now() - date.getTime()) / 60000)
  if (totalMinutes < 1) return 'Только что'
  if (totalMinutes < 60) return `${totalMinutes}м назад`
  if (totalMinutes < 24 * 60) return `${Math.floor(totalMinutes / 60)}ч ${totalMinutes % 60}м назад`
  if (totalMinutes < 30 * 24 * 60) return `${Math.floor(totalMinutes / (24 * 60))}д назад`
  return formatModerationDateOnly(date)
}

function formatDurationSeconds(seconds?: number | null, zeroLabel = 'без срока'): string {
  if (!seconds) return zeroLabel
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  const mins = Math.floor(total / 60)
  const days = Math.floor(mins / 1440)
  const hours = Math.floor((mins % 1440) / 60)
  const minutes = mins % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days}д`)
  if (hours > 0) parts.push(`${hours}ч`)
  if (minutes > 0 || parts.length === 0) parts.push(`${minutes}м`)
  return parts.join(' ')
}

function formatSanctionDuration(seconds?: number | null): string {
  return formatDurationSeconds(seconds, 'без срока')
}

function formatSanctionWorkoff(row: SanctionsRow): string {
  if (row.kind !== 'suspend') return '-'
  return formatDurationSeconds(row.hosted_workoff_seconds, '0м')
}

function formatSanctionKindLabel(kind: 'timeout' | 'ban' | 'suspend'): string {
  if (kind === 'timeout') return 'Таймаут'
  if (kind === 'ban') return 'Бан'
  return 'Отстранение'
}

function formatSanctionStatusLabel(status: SanctionListStatus): string {
  if (status === 'active') return 'Активна'
  if (status === 'expired_auto') return 'Истекла'
  return 'Снята'
}

function sanctionStatusClass(status: SanctionListStatus): string {
  if (status === 'active') return 'status-active'
  if (status === 'expired_auto') return 'status-expired'
  return 'status-revoked'
}

function getPositiveUserId(value: unknown): number {
  const id = Number(value ?? 0)
  return Number.isFinite(id) && id > 0 ? Math.trunc(id) : 0
}

function openUserMiniProfile(row: UserMiniProfileTarget): void {
  userMiniProfileTarget.value = row
  userMiniProfileOpen.value = true
}

function canOpenMiniProfileOnModerationPage(value: {
  id?: unknown
  role?: unknown
  deleted_at?: unknown
}): boolean {
  return canOpenMiniProfileTarget({
    targetId: value.id,
    viewerId: viewerUserId.value,
    viewerRole: userStore.user?.role,
    targetRole: value.role,
    targetDeletedAt: value.deleted_at,
  })
}

function canOpenModerationUserMiniProfile(row: UserRow): boolean {
  return canOpenMiniProfileOnModerationPage({
    id: row.id,
    role: row.role,
  })
}

function canOpenSanctionUserMiniProfile(row: SanctionsRow): boolean {
  return canOpenMiniProfileOnModerationPage({
    id: row.user_id,
    role: row.role,
    deleted_at: row.deleted_at,
  })
}

function canOpenContactRequestUserMiniProfile(row: ContactRequestRow): boolean {
  return canOpenMiniProfileOnModerationPage({
    id: row.user_id,
    role: row.role,
    deleted_at: row.deleted_at,
  })
}

function canAdjustSanction(row: SanctionsRow): boolean {
  return row.status === 'active'
    && (row.kind === 'timeout' || row.kind === 'suspend')
    && String(row.role || '') === 'user'
    && !row.deleted_at
}

function sanctionAdjustBusyKey(row: SanctionsRow, mode: SanctionAdjustMode): string {
  return `${row.id}:${mode}`
}

function isSanctionAdjustBusy(row: SanctionsRow, mode: SanctionAdjustMode): boolean {
  return Boolean(sanctionsAdjusting[sanctionAdjustBusyKey(row, mode)])
}

function openSanctionUserMiniProfile(row: SanctionsRow): void {
  const id = getPositiveUserId(row.user_id)
  if (id <= 0) return
  openUserMiniProfile({
    id,
    username: row.username ?? null,
    avatar_name: row.avatar_name ?? null,
    role: row.role ?? null,
    deleted_at: row.deleted_at ?? null,
  })
}

function openContactRequestUserMiniProfile(row: ContactRequestRow): void {
  const id = getPositiveUserId(row.user_id)
  if (id <= 0) return
  openUserMiniProfile({
    id,
    username: row.username ?? null,
    avatar_name: row.avatar_name ?? null,
    role: row.role ?? null,
    deleted_at: row.deleted_at ?? null,
  })
}

function onUserMiniProfileOpenUpdate(open: boolean): void {
  userMiniProfileOpen.value = open
  if (!open) userMiniProfileTarget.value = null
}

function onUserMiniProfileStaffActionComplete(): void {
  refreshActiveTab(activeTab.value)
}

async function loadUsers(): Promise<void> {
  if (usersLoading.value) return
  usersLoading.value = true
  try {
    const params: Record<string, unknown> = {
      page: usersPage.value,
      limit: usersLimit.value,
      sort: usersSort.value,
    }
    if (usersUser.value) params.username = usersUser.value
    const { data } = await api.get('/moderation/users', { params })
    const items = Array.isArray(data?.items) ? data.items : []
    users.value = items.map((item: any) => ({
      ...item,
      avatar_name: item?.avatar_name ?? null,
      role: String(item?.role || ''),
      last_visit_at: item?.last_visit_at ?? null,
      last_game_at: item?.last_game_at ?? null,
      last_game_id: Number.isFinite(item?.last_game_id) ? item.last_game_id : null,
      online: Boolean(item?.online),
      last_room_id: Number.isFinite(item?.last_room_id) ? item.last_room_id : null,
      last_spectator_room_id: Number.isFinite(item?.last_spectator_room_id) ? item.last_spectator_room_id : null,
    }))
    usersTotal.value = Number.isFinite(data?.total) ? data.total : 0
  } catch {
    void alertDialog('Не удалось загрузить пользователей')
  } finally {
    usersLoading.value = false
  }
}

async function loadSanctions(): Promise<void> {
  if (sanctionsLoading.value) return
  sanctionsLoading.value = true
  try {
    const params: Record<string, unknown> = {
      page: sanctionsPage.value,
      limit: sanctionsLimit.value,
    }
    if (sanctionsUser.value) params.username = sanctionsUser.value
    const { data } = await api.get('/moderation/sanctions', { params })
    const items = Array.isArray(data?.items) ? data.items : []
    sanctions.value = items.map((item: any) => ({
      ...item,
      username: item?.username ?? null,
      avatar_name: item?.avatar_name ?? null,
      finished_at: item?.finished_at ?? null,
      issued_by_display: String(item?.issued_by_display || '-'),
      revoked_by_display: item?.revoked_by_display ? String(item.revoked_by_display) : null,
      duration_seconds: Number.isFinite(item?.duration_seconds) ? item.duration_seconds : null,
      served_seconds: Math.max(0, Number(item?.served_seconds) || 0),
      hosted_workoff_seconds: Number.isFinite(item?.hosted_workoff_seconds)
        ? Math.max(0, Number(item.hosted_workoff_seconds))
        : null,
      reason: item?.reason ?? null,
      description: item?.description ?? null,
    }))
    sanctionsTotal.value = Number.isFinite(data?.total) ? data.total : 0
  } catch {
    sanctions.value = []
    void alertDialog('Не удалось загрузить санкции')
  } finally {
    sanctionsLoading.value = false
  }
}

async function loadContactRequests(): Promise<void> {
  if (contactRequestsLoading.value) return
  contactRequestsLoading.value = true
  try {
    const { data } = await api.get('/moderation/contact_requests', {
      params: {
        page: contactRequestsPage.value,
        limit: contactRequestsLimit.value,
        username: contactRequestsUser.value || undefined,
      },
    })
    contactRequests.value = Array.isArray(data?.items) ? data.items : []
    contactRequestsTotal.value = Number.isFinite(data?.total) ? data.total : 0
  } catch {
    contactRequests.value = []
    void alertDialog('Не удалось загрузить обращения')
  } finally {
    contactRequestsLoading.value = false
  }
}

function resetSanctionAdjustForm(): void {
  sanctionAdjustForm.months = 0
  sanctionAdjustForm.days = 0
  sanctionAdjustForm.hours = 0
  sanctionAdjustForm.reason = ''
  sanctionAdjustForm.description = ''
}

function clearSanctionAdjustModalState(): void {
  sanctionAdjustModalOpen.value = false
  sanctionAdjustTarget.value = null
  resetSanctionAdjustForm()
}

function onSanctionAdjustModalOpenUpdate(open: boolean): void {
  sanctionAdjustModalOpen.value = open
  if (!open) clearSanctionAdjustModalState()
}

function openSanctionAdjust(row: SanctionsRow, mode: SanctionAdjustMode): void {
  if (!canAdjustSanction(row) || isSanctionAdjustBusy(row, mode)) return
  sanctionAdjustTarget.value = row
  sanctionAdjustMode.value = mode
  resetSanctionAdjustForm()
  sanctionAdjustModalOpen.value = true
}

async function saveSanctionAdjust(): Promise<void> {
  const target = sanctionAdjustTarget.value
  if (!target || sanctionAdjustSaving.value || !sanctionAdjustCanSave.value) return
  const mode = sanctionAdjustMode.value
  const busyKey = sanctionAdjustBusyKey(target, mode)
  sanctionAdjustSaving.value = true
  sanctionsAdjusting[busyKey] = true
  const duration = {
    months: Math.max(0, Math.trunc(Number(sanctionAdjustForm.months) || 0)),
    days: Math.max(0, Math.trunc(Number(sanctionAdjustForm.days) || 0)),
    hours: Math.max(0, Math.trunc(Number(sanctionAdjustForm.hours) || 0)),
  }
  try {
    await api.patch(`/moderation/sanctions/${target.id}/${mode}`, duration)
    await loadSanctions()
    await loadUsers()
    clearSanctionAdjustModalState()
    void alertDialog(mode === 'increase' ? 'Срок санкции увеличен' : 'Срок санкции уменьшен')
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 404 && d === 'sanction_not_found') void alertDialog('Санкция не найдена')
    else if (st === 404 && d === 'user_not_found') void alertDialog('Пользователь не найден')
    else if (st === 403 && d === 'forbidden') void alertDialog('Нельзя изменить санкцию этого пользователя')
    else if (st === 409 && d === 'sanction_not_active') void alertDialog('Санкция уже не активна')
    else if (st === 422 && d === 'duration_required') void alertDialog('Укажите срок изменения')
    else if (st === 422 && d === 'sanction_not_timed') void alertDialog('Для этой санкции нельзя изменить срок')
    else if (st === 422 && d === 'sanction_decrease_too_large') void alertDialog('Нельзя уменьшить срок на все оставшееся время санкции или больше')
    else void alertDialog('Не удалось изменить срок санкции')
  } finally {
    sanctionsAdjusting[busyKey] = false
    sanctionAdjustSaving.value = false
  }
}

function nextUsers(): void {
  if (usersPage.value >= usersPages.value) return
  usersPage.value += 1
  void loadUsers()
}

function prevUsers(): void {
  if (usersPage.value <= 1) return
  usersPage.value -= 1
  void loadUsers()
}

function nextSanctions(): void {
  if (sanctionsPage.value >= sanctionsPages.value) return
  sanctionsPage.value += 1
  void loadSanctions()
}

function prevSanctions(): void {
  if (sanctionsPage.value <= 1) return
  sanctionsPage.value -= 1
  void loadSanctions()
}

function nextContactRequests(): void {
  if (contactRequestsPage.value >= contactRequestsPages.value) return
  contactRequestsPage.value += 1
  void loadContactRequests()
}

function prevContactRequests(): void {
  if (contactRequestsPage.value <= 1) return
  contactRequestsPage.value -= 1
  void loadContactRequests()
}

function refreshActiveTab(tab: TabKey): void {
  if (tab === 'users') {
    void loadUsers()
    return
  }
  if (tab === 'sanctions') {
    void loadSanctions()
    return
  }
  void loadContactRequests()
}

watch(activeTab, (tab) => {
  refreshActiveTab(tab)
})

watch([usersLimit, usersSort], () => {
  usersPage.value = 1
  if (activeTab.value !== 'users') return
  void loadUsers()
})

watch(usersUser, () => {
  usersPage.value = 1
  if (activeTab.value !== 'users') return
  if (usersUserTimer) window.clearTimeout(usersUserTimer)
  usersUserTimer = window.setTimeout(() => { void loadUsers() }, 500)
})

watch(sanctionsLimit, () => {
  sanctionsPage.value = 1
  if (activeTab.value !== 'sanctions') return
  void loadSanctions()
})

watch(sanctionsUser, () => {
  sanctionsPage.value = 1
  if (activeTab.value !== 'sanctions') return
  if (sanctionsUserTimer) window.clearTimeout(sanctionsUserTimer)
  sanctionsUserTimer = window.setTimeout(() => { void loadSanctions() }, 500)
})

watch(contactRequestsLimit, () => {
  contactRequestsPage.value = 1
  if (activeTab.value !== 'contact_requests') return
  void loadContactRequests()
})

watch(contactRequestsUser, () => {
  contactRequestsPage.value = 1
  if (activeTab.value !== 'contact_requests') return
  if (contactRequestsUserTimer) window.clearTimeout(contactRequestsUserTimer)
  contactRequestsUserTimer = window.setTimeout(() => { void loadContactRequests() }, 500)
})

onMounted(() => {
  refreshActiveTab(activeTab.value)
})

onBeforeUnmount(() => {
  if (usersUserTimer) window.clearTimeout(usersUserTimer)
  if (sanctionsUserTimer) window.clearTimeout(sanctionsUserTimer)
  if (contactRequestsUserTimer) window.clearTimeout(contactRequestsUserTimer)
})
</script>

<style scoped lang="scss">
.moderation {
  display: flex;
  flex-direction: column;
  margin: 0 10px 10px;
  padding: 10px;
  border-radius: 5px;
  background-color: $neutral-900;
  overflow: auto;
  scrollbar-width: none;
  user-select: text;
  header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    border-bottom: 3px solid $neutral-700;
    .tabs {
      display: flex;
      align-items: flex-end;
      width: 80%;
      height: 30px;
      .tab {
        width: 200px;
        height: 30px;
        border: none;
        border-radius: 5px 5px 0 0;
        background-color: $neutral-800;
        color: $neutral-100;
        font-size: 18px;
        font-family: Hauora-Regular;
        line-height: 1;
        cursor: pointer;
        transition: opacity 0.25s ease-in-out, height 0.25s ease-in-out, background-color 0.25s ease-in-out;
        &.active {
          height: 40px;
          background-color: $neutral-700;
        }
      }
    }
  }
  .panel {
    margin-top: 10px;
  }
  .btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 20px;
    gap: 5px;
    height: 40px;
    border: none;
    border-radius: 5px;
    background-color: $neutral-100;
    font-size: 14px;
    color: $neutral-black;
    font-family: Hauora-Regular;
    line-height: 1;
    text-decoration: none;
    cursor: pointer;
    transition: opacity 0.25s ease-in-out, color 0.25s ease-in-out, border-radius 0.25s ease-in-out, background-color 0.25s ease-in-out;
    &:hover {
      background-color: $neutral-white;
    }
    &.nav {
      font-size: 16px;
      border-radius: 5px 5px 0 0;
    }
    &.dark {
      background-color: $neutral-700;
      color: $neutral-100;
      &:hover {
        background-color: rgba($neutral-500, 0.5);
      }
    }
    &.danger {
      background-color: rgba($red-500, 0.75);
      color: $neutral-100;
      &:hover {
        background-color: $red-500;
      }
    }
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
  .loading {
    padding: 20px;
  }
  .filters {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 10px;
    margin: 10px 0;
    .field {
      display: flex;
      flex-direction: column;
      gap: 5px;
      min-width: 160px;
    }
  }
  .table {
    width: 100%;
    border-collapse: collapse;
    color: $neutral-100;
    font-family: Hauora-Regular;
    th {
      padding: 10px;
      border-bottom: 1px solid $neutral-700;
      font-size: 16px;
      color: $neutral-500;
      text-align: left;
    }
    .table-sort {
      display: inline-flex;
      align-items: center;
      padding: 0;
      gap: 5px;
      border: none;
      background: transparent;
      color: inherit;
      font: inherit;
      cursor: pointer;
      span {
        opacity: 0.5;
        transition: opacity 0.25s ease-in-out;
      }
      &:hover span,
      &.active span {
        opacity: 1;
      }
      &.active {
        color: $neutral-100;
      }
    }
    td {
      padding: 10px;
      border-bottom: 1px solid $neutral-700;
      font-size: 14px;
    }
    .user-cell {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      .user-link {
        padding: 0;
        border: none;
        background: transparent;
        color: $neutral-100;
        font: inherit;
        text-align: left;
        cursor: pointer;
        transition: color 0.25s ease-in-out;
        &:hover {
          color: $neutral-white;
          text-decoration: underline;
        }
      }
      .user-profile-trigger {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        min-width: 0;
        &:disabled {
          cursor: default;
          &:hover {
            color: $neutral-100;
            text-decoration: none;
          }
        }
      }
    }
    .user-avatar {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      object-fit: cover;
    }
  }
  .sanctions-table .rule-cell,
  .sanctions-table .description-cell {
    max-width: 520px;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .contact-requests-table .contact-cell,
  .contact-requests-table .topic-cell,
  .contact-requests-table .text-cell {
    max-width: 520px;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .status-badge {
    display: inline-flex;
    align-items: center;
    padding: 5px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-family: Hauora-SemiBold;
    line-height: 1;
    white-space: nowrap;
    &.status-active {
      background-color: rgba($green-500, 0.25);
    }
    &.status-expired {
      background-color: rgba($yellow-500, 0.25);
    }
    &.status-revoked {
      background-color: rgba($red-500, 0.25);
    }
  }
  .pager {
    margin-top: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: $neutral-100;
    font-family: Hauora-Regular;
  }
  .muted {
    color: $neutral-500;
    text-align: center;
  }
}

</style>
