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
            <span>Отображать по</span>
            <select v-model.number="usersLimit" :disabled="usersLoading">
              <option :value="20">20</option>
              <option :value="100">100</option>
            </select>
          </div>
        </div>

        <div v-if="usersLoading" class="loading">Загрузка...</div>
        <div v-else>
          <table class="table">
            <thead>
              <tr>
                <th>
                  <button class="th-sort" type="button" :class="{ active: usersSortBy === 'username' }" @click="setUsersSort('username')">
                    Никнейм
                    <span class="th-sort-mark" aria-hidden="true">▼</span>
                  </button>
                </th>
                <th>
                  <button class="th-sort" type="button" :class="{ active: usersSortBy === 'registered_at' }" @click="setUsersSort('registered_at')">
                    Регистрация
                    <span class="th-sort-mark" aria-hidden="true">▼</span>
                  </button>
                </th>
                <th>
                  <button class="th-sort" type="button" :class="{ active: usersSortBy === 'last_login_at' }" @click="setUsersSort('last_login_at')">
                    Авторизация
                    <span class="th-sort-mark" aria-hidden="true">▼</span>
                  </button>
                </th>
                <th>
                  <button class="th-sort" type="button" :class="{ active: usersSortBy === 'last_visit_at' }" @click="setUsersSort('last_visit_at')">
                    Онлайн
                    <span class="th-sort-mark" aria-hidden="true">▼</span>
                  </button>
                </th>
                <th>
                  <button class="th-sort" type="button" :class="{ active: usersSortBy === 'last_game_at' }" @click="setUsersSort('last_game_at')">
                    Последняя игра
                    <span class="th-sort-mark" aria-hidden="true">▼</span>
                  </button>
                </th>
                <th>
                  <button class="th-sort" type="button" :class="{ active: usersSortBy === 'suspends_count' }" @click="setUsersSort('suspends_count')">
                    Отстранения
                    <span class="th-sort-mark" aria-hidden="true">▼</span>
                  </button>
                </th>
                <th>
                  <button class="th-sort" type="button" :class="{ active: usersSortBy === 'timeouts_count' }" @click="setUsersSort('timeouts_count')">
                    Таймауты
                    <span class="th-sort-mark" aria-hidden="true">▼</span>
                  </button>
                </th>
                <th>
                  <button class="th-sort" type="button" :class="{ active: usersSortBy === 'bans_count' }" @click="setUsersSort('bans_count')">
                    Баны
                    <span class="th-sort-mark" aria-hidden="true">▼</span>
                  </button>
                </th>
                <th>Отстранить</th>
                <th>Таймаут</th>
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
                <td>{{ formatLocalDateTime(row.last_login_at) }}</td>
                <td>{{ formatLocalDateTime(row.last_visit_at) }}</td>
                <td>{{ formatLocalDateTime(row.last_game_at) }}</td>
                <td>{{ row.suspends_count }}</td>
                <td>{{ row.timeouts_count }}</td>
                <td>{{ row.bans_count }}</td>
                <td>
                  <button class="btn" :class="row.suspend_active ? 'dark' : 'danger'" :disabled="!canModerateUser(row) || isSanctionBusy(row.id, 'suspend')" @click="toggleSuspend(row)">
                    <img class="btn-img" :src="row.suspend_active ? iconClose : iconJudge" alt="" />
                  </button>
                </td>
                <td>
                  <button class="btn" :class="row.timeout_active ? 'dark' : 'danger'" :disabled="!canModerateUser(row) || isSanctionBusy(row.id, 'timeout')" @click="toggleTimeout(row)">
                    <img class="btn-img" :src="row.timeout_active ? iconClose : iconJudge" alt="" />
                  </button>
                </td>
              </tr>
              <tr v-if="users.length === 0">
                <td colspan="10" class="muted">Нет данных</td>
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

      <div v-else>
        <div class="filters">
          <div class="field">
            <UiInput id="moderation-sanctions-user" v-model.trim="sanctionsUser" label="Никнейм" :disabled="sanctionsLoading" />
          </div>
          <div class="field">
            <span>Отображать по</span>
            <select v-model.number="sanctionsLimit" :disabled="sanctionsLoading">
              <option :value="20">20</option>
              <option :value="100">100</option>
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
                <td colspan="13" class="muted">Нет данных</td>
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
    </div>

    <SanctionModal
      v-model:open="sanctionModalOpen"
      :title="sanctionTitle"
      :saving="sanctionSaving"
      :can-save="sanctionCanSave"
      :show-duration="true"
      :form="sanctionForm"
      :reasons="sanctionReasons"
      @save="saveSanction"
    />
    <SanctionModal
      :open="sanctionAdjustModalOpen"
      :title="sanctionAdjustTitle"
      :saving="sanctionAdjustSaving"
      :can-save="sanctionAdjustCanSave"
      :show-duration="true"
      :show-reason="false"
      :save-label="sanctionAdjustSaveLabel"
      :form="sanctionAdjustForm"
      :reasons="sanctionReasons"
      @update:open="onSanctionAdjustModalOpenUpdate"
      @save="saveSanctionAdjust"
    />
    <UserMiniProfileModal
      :open="userMiniProfileOpen"
      :user-id="userMiniProfileTarget?.id ?? null"
      :initial-profile="userMiniProfileTarget"
      :allow-deleted="userMiniProfileAllowDeleted"
      :stats-url="userMiniProfileStatsUrl"
      show-stats-button
      admin-mode
      @update:open="onUserMiniProfileOpenUpdate"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { formatLocalDateTime } from '@/services/datetime'
import { DEFAULT_SANCTION_REASON, SANCTION_REASONS } from '@/constants/sanctionReasons'
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId } from '@/services/miniProfile'
import { useUserStore } from '@/store'

import UserMiniProfileModal from '@/components/UserMiniProfileModal.vue'
import SanctionModal from '@/components/SanctionModal.vue'
import UiInput from '@/components/UiInput.vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconClose from '@/assets/svg/close.svg'
import iconJudge from '@/assets/svg/judge.svg'

type TabKey = 'users' | 'sanctions'
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
}

type UserRow = {
  id: number
  username?: string | null
  avatar_name?: string | null
  role: string
  registered_at: string
  last_login_at: string
  last_visit_at: string
  last_game_at?: string | null
  timeout_active: boolean
  timeout_until?: string | null
  suspend_active: boolean
  suspend_until?: string | null
  timeouts_count: number
  bans_count: number
  suspends_count: number
}

type UserMiniProfileTarget = {
  id: number
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  deleted_at?: string | null
}

type UsersSortBy =
  | 'username'
  | 'registered_at'
  | 'last_login_at'
  | 'last_visit_at'
  | 'last_game_at'
  | 'timeouts_count'
  | 'bans_count'
  | 'suspends_count'

const activeTab = ref<TabKey>('users')
const userStore = useUserStore()
const viewerUserId = computed(() => normalizeMiniProfileUserId(userStore.user?.id))
const users = ref<UserRow[]>([])
const usersLoading = ref(false)
const usersTotal = ref(0)
const usersPage = ref(1)
const usersLimit = ref(20)
const usersUser = ref('')
const usersSortBy = ref<UsersSortBy>('registered_at')
const usersSanctionBusy = reactive<Record<string, boolean>>({})
const sanctions = ref<SanctionsRow[]>([])
const sanctionsLoading = ref(false)
const sanctionsTotal = ref(0)
const sanctionsPage = ref(1)
const sanctionsLimit = ref(20)
const sanctionsUser = ref('')
const sanctionsAdjusting = reactive<Record<string, boolean>>({})
let usersUserTimer: number | undefined
let sanctionsUserTimer: number | undefined

const sanctionReasons = SANCTION_REASONS
const sanctionModalOpen = ref(false)
const sanctionSaving = ref(false)
const sanctionKind = ref<'timeout' | 'suspend'>('suspend')
const sanctionTarget = ref<UserRow | null>(null)
const SANCTION_DURATION_LIMITS = {
  months: 240,
  days: 31,
  hours: 23,
} as const
const userMiniProfileOpen = ref(false)
const userMiniProfileTarget = ref<UserMiniProfileTarget | null>(null)
const userMiniProfileAllowDeleted = computed(() => activeTab.value === 'sanctions')
const userMiniProfileStatsUrl = computed(() => {
  const target = userMiniProfileTarget.value
  return target ? `/moderation/users/${target.id}/stats` : null
})
const sanctionForm = reactive({
  months: 0,
  days: 0,
  hours: 0,
  reason: DEFAULT_SANCTION_REASON,
})
function isSanctionDurationPartValid(value: number, max: number): boolean {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 0 && parsed <= max
}

const usersPages = computed(() => Math.max(1, Math.ceil(usersTotal.value / usersLimit.value)))
const sanctionsPages = computed(() => Math.max(1, Math.ceil(sanctionsTotal.value / sanctionsLimit.value)))
const sanctionDurationValid = computed(() => (
  isSanctionDurationPartValid(sanctionForm.months, SANCTION_DURATION_LIMITS.months)
  && isSanctionDurationPartValid(sanctionForm.days, SANCTION_DURATION_LIMITS.days)
  && isSanctionDurationPartValid(sanctionForm.hours, SANCTION_DURATION_LIMITS.hours)
))
const sanctionTotalSeconds = computed(() => {
  const months = Math.max(0, Number(sanctionForm.months) || 0)
  const days = Math.max(0, Number(sanctionForm.days) || 0)
  const hours = Math.max(0, Number(sanctionForm.hours) || 0)
  const totalMinutes = (months * 30 * 24 * 60) + (days * 24 * 60) + (hours * 60)
  return totalMinutes * 60
})
const sanctionCanSave = computed(() => Boolean(sanctionForm.reason) && sanctionDurationValid.value && sanctionTotalSeconds.value > 0)
const sanctionTitle = computed(() => {
  const target = sanctionTarget.value
  const label = target?.username || (target ? `user${target.id}` : 'пользователю')
  return sanctionKind.value === 'timeout' ? `Таймаут: ${label}` : `Отстранение от игр: ${label}`
})
const sanctionAdjustModalOpen = ref(false)
const sanctionAdjustSaving = ref(false)
const sanctionAdjustMode = ref<SanctionAdjustMode>('increase')
const sanctionAdjustTarget = ref<SanctionsRow | null>(null)
const sanctionAdjustForm = reactive({
  months: 0,
  days: 0,
  hours: 0,
  reason: '',
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

function setUsersSort(sortBy: UsersSortBy): void {
  if (usersSortBy.value === sortBy) return
  usersSortBy.value = sortBy
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

function isSanctionBusy(userId: number, kind: 'timeout' | 'suspend'): boolean {
  return Boolean(usersSanctionBusy[`${userId}:${kind}`])
}

function setSanctionBusy(userId: number, kind: 'timeout' | 'suspend', value: boolean): void {
  usersSanctionBusy[`${userId}:${kind}`] = value
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
}, opts?: { allowDeleted?: boolean }): boolean {
  return canOpenMiniProfileTarget({
    targetId: value.id,
    viewerId: viewerUserId.value,
    targetRole: value.role,
    targetDeletedAt: value.deleted_at,
    allowDeleted: Boolean(opts?.allowDeleted),
  })
}

function canOpenModerationUserMiniProfile(row: UserRow): boolean {
  return canOpenMiniProfileOnModerationPage({
    id: row.id,
    role: row.role,
  })
}

function canModerateUser(row: UserRow): boolean {
  return String(row.role || '') === 'user'
}

function canOpenSanctionUserMiniProfile(row: SanctionsRow): boolean {
  return canOpenMiniProfileOnModerationPage({
    id: row.user_id,
    role: row.role,
    deleted_at: row.deleted_at,
  }, { allowDeleted: true })
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

function onUserMiniProfileOpenUpdate(open: boolean): void {
  userMiniProfileOpen.value = open
  if (!open) userMiniProfileTarget.value = null
}

function resetSanctionForm(): void {
  sanctionForm.months = 0
  sanctionForm.days = 0
  sanctionForm.hours = 0
  sanctionForm.reason = DEFAULT_SANCTION_REASON
}

function openSanction(row: UserRow, kind: 'timeout' | 'suspend'): void {
  sanctionTarget.value = row
  sanctionKind.value = kind
  resetSanctionForm()
  sanctionModalOpen.value = true
}

async function loadUsers(): Promise<void> {
  if (usersLoading.value) return
  usersLoading.value = true
  try {
    const params: Record<string, unknown> = {
      page: usersPage.value,
      limit: usersLimit.value,
      sort_by: usersSortBy.value,
    }
    if (usersUser.value) params.username = usersUser.value
    const { data } = await api.get('/moderation/users', { params })
    const items = Array.isArray(data?.items) ? data.items : []
    users.value = items.map((item: any) => ({
      ...item,
      avatar_name: item?.avatar_name ?? null,
      role: String(item?.role || ''),
      last_game_at: item?.last_game_at ?? null,
      timeout_until: item?.timeout_until ?? null,
      suspend_until: item?.suspend_until ?? null,
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
    }))
    sanctionsTotal.value = Number.isFinite(data?.total) ? data.total : 0
  } catch {
    sanctions.value = []
    void alertDialog('Не удалось загрузить санкции')
  } finally {
    sanctionsLoading.value = false
  }
}

async function saveSanction(): Promise<void> {
  const target = sanctionTarget.value
  if (!target || sanctionSaving.value || !sanctionCanSave.value) return
  sanctionSaving.value = true
  const kind = sanctionKind.value
  try {
    await api.post(`/moderation/users/${target.id}/${kind}`, {
      months: sanctionForm.months,
      days: sanctionForm.days,
      hours: sanctionForm.hours,
      reason: sanctionForm.reason,
    })
    sanctionModalOpen.value = false
    void alertDialog(kind === 'timeout' ? 'Таймаут выдан' : 'Отстранение от игр выдано')
    await loadUsers()
    if (activeTab.value === 'sanctions') await loadSanctions()
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 409 && d === 'sanction_active') {
      void alertDialog('Санкция уже активна')
    } else if (st === 422 && d === 'duration_required') {
      void alertDialog('Укажите срок санкции')
    } else {
      void alertDialog(kind === 'timeout' ? 'Не удалось выдать таймаут' : 'Не удалось выдать отстранение от игр')
    }
  } finally {
    sanctionSaving.value = false
  }
}

function resetSanctionAdjustForm(): void {
  sanctionAdjustForm.months = 0
  sanctionAdjustForm.days = 0
  sanctionAdjustForm.hours = 0
  sanctionAdjustForm.reason = ''
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

async function revokeSanction(row: UserRow, kind: 'timeout' | 'suspend'): Promise<void> {
  if (isSanctionBusy(row.id, kind)) return
  const userLabel = row.username ? `${row.username}` : `#${row.id}`
  const title = kind === 'timeout' ? 'Снять таймаут' : 'Снять отстранение от игр'
  const text = kind === 'timeout'
    ? `Снять таймаут у ${userLabel}?`
    : `Снять отстранение от игр у ${userLabel}?`
  const ok = await confirmDialog({
    title,
    text,
    confirmText: 'Снять',
    cancelText: 'Отмена',
  })
  if (!ok) return
  setSanctionBusy(row.id, kind, true)
  try {
    await api.delete(`/moderation/users/${row.id}/${kind}`)
    void alertDialog(kind === 'timeout' ? 'Таймаут снят' : 'Отстранение от игр снято')
    await loadUsers()
    if (activeTab.value === 'sanctions') await loadSanctions()
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 404 && d === 'sanction_not_found') {
      void alertDialog('Санкция не найдена')
    } else {
      void alertDialog(kind === 'timeout' ? 'Не удалось снять таймаут' : 'Не удалось снять отстранение от игр')
    }
  } finally {
    setSanctionBusy(row.id, kind, false)
  }
}

async function toggleSuspend(row: UserRow): Promise<void> {
  if (row.suspend_active) {
    await revokeSanction(row, 'suspend')
    return
  }
  openSanction(row, 'suspend')
}

async function toggleTimeout(row: UserRow): Promise<void> {
  if (row.timeout_active) {
    await revokeSanction(row, 'timeout')
    return
  }
  openSanction(row, 'timeout')
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

function refreshActiveTab(tab: TabKey): void {
  if (tab === 'users') {
    void loadUsers()
    return
  }
  void loadSanctions()
}

watch(activeTab, (tab) => {
  refreshActiveTab(tab)
})

watch([usersLimit, usersSortBy], () => {
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

onMounted(() => {
  refreshActiveTab(activeTab.value)
})

onBeforeUnmount(() => {
  if (usersUserTimer) window.clearTimeout(usersUserTimer)
  if (sanctionsUserTimer) window.clearTimeout(sanctionsUserTimer)
})
</script>

<style scoped lang="scss">
.moderation {
  display: flex;
  flex-direction: column;
  margin: 0 10px 10px;
  padding: 10px;
  border-radius: 5px;
  background-color: $dark;
  overflow: auto;
  scrollbar-width: none;
  user-select: text;
  header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    border-bottom: 3px solid $lead;
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
        background-color: $graphite;
        color: $fg;
        font-size: 18px;
        font-family: Manrope-Medium;
        line-height: 1;
        cursor: pointer;
        transition: opacity 0.25s ease-in-out, height 0.25s ease-in-out, background-color 0.25s ease-in-out;
        &.active {
          height: 40px;
          background-color: $lead;
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
    background-color: $fg;
    font-size: 14px;
    color: $bg;
    font-family: Manrope-Medium;
    line-height: 1;
    text-decoration: none;
    cursor: pointer;
    transition: opacity 0.25s ease-in-out, color 0.25s ease-in-out, border-radius 0.25s ease-in-out, background-color 0.25s ease-in-out;
    &:hover {
      background-color: $white;
    }
    &.nav {
      font-size: 16px;
      border-radius: 5px 5px 0 0;
    }
    &.dark {
      background-color: $lead;
      color: $fg;
      &:hover {
        background-color: rgba($grey, 0.5);
      }
    }
    &.danger {
      background-color: rgba($red, 0.75);
      color: $fg;
      &:hover {
        background-color: $red;
      }
    }
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .btn-img {
      width: 20px;
      height: 20px;
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
      > span {
        font-size: 14px;
        color: $grey;
      }
      > input,
      > select {
        height: 35px;
        padding: 0 10px;
        border: 1px solid $lead;
        border-radius: 5px;
        background-color: $graphite;
        color: $fg;
        font-size: 14px;
        font-family: Manrope-Medium;
        outline: none;
      }
    }
  }
  .table {
    width: 100%;
    border-collapse: collapse;
    color: $fg;
    font-family: Manrope-Medium;
    th {
      padding: 10px;
      border-bottom: 1px solid $lead;
      font-size: 16px;
      color: $grey;
      text-align: left;
    }
    td {
      padding: 10px;
      border-bottom: 1px solid $lead;
      font-size: 14px;
    }
    .th-sort {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 0;
      border: none;
      background: transparent;
      color: inherit;
      font: inherit;
      cursor: pointer;
    }
    .th-sort-mark {
      opacity: 0.5;
      font-size: 10px;
    }
    .th-sort.active {
      color: $fg;
    }
    .th-sort.active .th-sort-mark {
      opacity: 1;
    }
    .user-cell {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      .user-link {
        padding: 0;
        border: none;
        background: transparent;
        color: $fg;
        font: inherit;
        text-align: left;
        cursor: pointer;
        transition: color 0.25s ease-in-out;
        &:hover {
          color: $white;
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
            color: $fg;
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
  .sanctions-table .rule-cell {
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
    font-family: Manrope-SemiBold;
    line-height: 1;
    white-space: nowrap;
    &.status-active {
      background-color: rgba($green, 0.25);
    }
    &.status-expired {
      background-color: rgba($yellow, 0.25);
    }
    &.status-revoked {
      background-color: rgba($red, 0.25);
    }
  }
  .pager {
    margin-top: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: $fg;
    font-family: Manrope-Medium;
  }
  .muted {
    color: $grey;
    text-align: center;
  }
}

@media (max-width: 1280px) {
  .moderation {
    header {
      .tabs {
        .tab {
          height: 30px;
          font-size: 12px;
          &.active {
            height: 35px;
          }
        }
      }
    }
    .btn {
      padding: 0 5px;
      gap: 3px;
      height: 25px;
      font-size: 14px;
      &.nav {
        padding: 0 10px;
        font-size: 12px;
      }
      .btn-img {
        width: 16px;
        height: 16px;
      }
    }
    .table {
      th {
        padding: 3px;
        font-size: 12px;
      }
      td {
        padding: 3px;
        font-size: 10px;
      }
      .user-avatar {
        width: 16px;
        height: 16px;
      }
    }
    .sanctions-table .rule-cell {
      min-width: 220px;
    }
  }
}
</style>
