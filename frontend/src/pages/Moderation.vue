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
                    Отстранения от игр
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
                  <div v-if="row.username" class="user-cell">
                    <img class="user-avatar" v-minio-img="{ key: row.avatar_name ? `avatars/${row.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                    <span>{{ row.username }}</span>
                  </div>
                  <span v-else>-</span>
                </td>
                <td>{{ formatLocalDateTime(row.registered_at) }}</td>
                <td>{{ formatLocalDateTime(row.last_login_at) }}</td>
                <td>{{ formatLocalDateTime(row.last_visit_at) }}</td>
                <td>{{ formatLocalDateTime(row.last_game_at) }}</td>
                <td>
                  <div class="tooltip" tabindex="0">
                    <span class="tooltip-value">{{ row.suspends_count }}</span>
                    <div class="tooltip-body">
                      <div v-if="row.suspends.length === 0" class="tooltip-empty">Нет данных</div>
                      <div v-else class="tooltip-list">
                        <div v-for="item in row.suspends" :key="`suspend-${item.id}`" class="tooltip-row">
                          {{ formatSanctionLine(item) }}
                        </div>
                      </div>
                    </div>
                  </div>
                </td>
                <td>
                  <div class="tooltip" tabindex="0">
                    <span class="tooltip-value">{{ row.timeouts_count }}</span>
                    <div class="tooltip-body">
                      <div v-if="row.timeouts.length === 0" class="tooltip-empty">Нет данных</div>
                      <div v-else class="tooltip-list">
                        <div v-for="item in row.timeouts" :key="`timeout-${item.id}`" class="tooltip-row">
                          {{ formatSanctionLine(item) }}
                        </div>
                      </div>
                    </div>
                  </div>
                </td>
                <td>
                  <div class="tooltip" tabindex="0">
                    <span class="tooltip-value">{{ row.bans_count }}</span>
                    <div class="tooltip-body">
                      <div v-if="row.bans.length === 0" class="tooltip-empty">Нет данных</div>
                      <div v-else class="tooltip-list">
                        <div v-for="item in row.bans" :key="`ban-${item.id}`" class="tooltip-row">
                          {{ formatSanctionLine(item) }}
                        </div>
                      </div>
                    </div>
                  </div>
                </td>
                <td>
                  <button class="btn" :class="row.suspend_active ? 'dark' : 'danger'" :disabled="isSanctionBusy(row.id, 'suspend')" @click="toggleSuspend(row)">
                    <img class="btn-img" :src="row.suspend_active ? iconClose : iconJudge" alt="" />
                  </button>
                </td>
                <td>
                  <button class="btn" :class="row.timeout_active ? 'dark' : 'danger'" :disabled="isSanctionBusy(row.id, 'timeout')" @click="toggleTimeout(row)">
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
                <th>Никнейм</th>
                <th>Тип санкции</th>
                <th>Статус</th>
                <th>Дата выдачи</th>
                <th>Дата окончания</th>
                <th>Кем выдана</th>
                <th>Кем снята</th>
                <th>Срок изначальный</th>
                <th>Срок по факту</th>
                <th>Пункт правил</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in sanctions" :key="row.id">
                <td>{{ row.username || `user${row.user_id}` }}</td>
                <td>{{ formatSanctionKindLabel(row.kind) }}</td>
                <td>{{ formatSanctionStatusLabel(row.status) }}</td>
                <td>{{ formatLocalDateTime(row.issued_at) }}</td>
                <td>{{ row.finished_at ? formatLocalDateTime(row.finished_at) : '-' }}</td>
                <td>{{ row.issued_by_display }}</td>
                <td>{{ row.revoked_by_display || '-' }}</td>
                <td>{{ formatSanctionDuration(row.duration_seconds) }}</td>
                <td>{{ formatSanctionDuration(row.served_seconds) }}</td>
                <td class="rule-cell">{{ row.reason || '-' }}</td>
              </tr>
              <tr v-if="sanctions.length === 0">
                <td colspan="10" class="muted">Нет данных</td>
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
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { formatLocalDateTime } from '@/services/datetime'
import { DEFAULT_SANCTION_REASON, SANCTION_REASONS } from '@/constants/sanctionReasons'

import SanctionModal from '@/components/SanctionModal.vue'
import UiInput from '@/components/UiInput.vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconClose from '@/assets/svg/close.svg'
import iconJudge from '@/assets/svg/judge.svg'

type TabKey = 'users' | 'sanctions'
type SanctionListStatus = 'active' | 'expired_auto' | 'revoked'

type SanctionRow = {
  id: number
  kind: 'timeout' | 'ban' | 'suspend'
  reason?: string | null
  issued_at: string
  issued_by_id?: number | null
  issued_by_name?: string | null
  duration_seconds?: number | null
  expires_at?: string | null
  revoked_at?: string | null
  revoked_by_id?: number | null
  revoked_by_name?: string | null
}

type SanctionsRow = {
  id: number
  user_id: number
  username?: string | null
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
  reason?: string | null
}

type UserRow = {
  id: number
  username?: string | null
  avatar_name?: string | null
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
  timeouts: SanctionRow[]
  bans: SanctionRow[]
  suspends: SanctionRow[]
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
let usersUserTimer: number | undefined
let sanctionsUserTimer: number | undefined

const sanctionReasons = SANCTION_REASONS
const sanctionModalOpen = ref(false)
const sanctionSaving = ref(false)
const sanctionKind = ref<'timeout' | 'suspend'>('suspend')
const sanctionTarget = ref<UserRow | null>(null)
const sanctionForm = reactive({
  months: 0,
  days: 0,
  hours: 0,
  minutes: 0,
  reason: DEFAULT_SANCTION_REASON,
})

const usersPages = computed(() => Math.max(1, Math.ceil(usersTotal.value / usersLimit.value)))
const sanctionsPages = computed(() => Math.max(1, Math.ceil(sanctionsTotal.value / sanctionsLimit.value)))
const sanctionTotalSeconds = computed(() => {
  const months = Math.max(0, Number(sanctionForm.months) || 0)
  const days = Math.max(0, Number(sanctionForm.days) || 0)
  const hours = Math.max(0, Number(sanctionForm.hours) || 0)
  const minutes = Math.max(0, Number(sanctionForm.minutes) || 0)
  const totalMinutes = (months * 30 * 24 * 60) + (days * 24 * 60) + (hours * 60) + minutes
  return totalMinutes * 60
})
const sanctionCanSave = computed(() => Boolean(sanctionForm.reason) && sanctionTotalSeconds.value > 0)
const sanctionTitle = computed(() => {
  const target = sanctionTarget.value
  const label = target?.username || (target ? `user${target.id}` : 'пользователю')
  return sanctionKind.value === 'timeout' ? `Таймаут: ${label}` : `Отстранение от игр: ${label}`
})

function setUsersSort(sortBy: UsersSortBy): void {
  if (usersSortBy.value === sortBy) return
  usersSortBy.value = sortBy
}

function formatSanctionDuration(seconds?: number | null): string {
  if (!seconds) return 'без срока'
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

function formatSanctionActor(name?: string | null, id?: number | null): string {
  if (name) return name
  if (Number.isFinite(id)) return `#${id}`
  return '-'
}

function formatSanctionLine(item: SanctionRow): string {
  const issuedBy = formatSanctionActor(item.issued_by_name, item.issued_by_id)
  const issuedAt = formatLocalDateTime(item.issued_at)
  const duration = formatSanctionDuration(item.duration_seconds)
  let end = 'активен'
  if (item.revoked_at) {
    const revokedBy = formatSanctionActor(item.revoked_by_name, item.revoked_by_id)
    end = `снял: ${revokedBy} ${formatLocalDateTime(item.revoked_at)}`
  } else if (item.expires_at) {
    end = `авто: ${formatLocalDateTime(item.expires_at)}`
  }
  return `${issuedAt} • ${duration} • выдал: ${issuedBy} • ${end}`
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

function isSanctionBusy(userId: number, kind: 'timeout' | 'suspend'): boolean {
  return Boolean(usersSanctionBusy[`${userId}:${kind}`])
}

function setSanctionBusy(userId: number, kind: 'timeout' | 'suspend', value: boolean): void {
  usersSanctionBusy[`${userId}:${kind}`] = value
}

function resetSanctionForm(): void {
  sanctionForm.months = 0
  sanctionForm.days = 0
  sanctionForm.hours = 0
  sanctionForm.minutes = 0
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
      last_game_at: item?.last_game_at ?? null,
      timeout_until: item?.timeout_until ?? null,
      suspend_until: item?.suspend_until ?? null,
      timeouts: Array.isArray(item?.timeouts) ? item.timeouts : [],
      bans: Array.isArray(item?.bans) ? item.bans : [],
      suspends: Array.isArray(item?.suspends) ? item.suspends : [],
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
      finished_at: item?.finished_at ?? null,
      issued_by_display: String(item?.issued_by_display || '-'),
      revoked_by_display: item?.revoked_by_display ? String(item.revoked_by_display) : null,
      duration_seconds: Number.isFinite(item?.duration_seconds) ? item.duration_seconds : null,
      served_seconds: Math.max(0, Number(item?.served_seconds) || 0),
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
      minutes: sanctionForm.minutes,
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
      gap: 10px;
    }
    .user-avatar {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      object-fit: cover;
    }
    .tooltip {
      position: relative;
      display: inline-flex;
      align-items: center;
      cursor: default;
      width: fit-content;
      .tooltip-value {
        border-bottom: 1px dashed $grey;
      }
      .tooltip-body {
        position: absolute;
        top: calc(100% - 35px);
        right: 15px;
        min-width: 220px;
        max-width: 320px;
        max-height: 200px;
        overflow: auto;
        padding: 10px;
        border: 1px solid $lead;
        border-radius: 5px;
        background-color: $graphite;
        box-shadow: 0 5px 15px rgba($black, 0.25);
        opacity: 0;
        transform: translateY(-5px);
        pointer-events: none;
        transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
        z-index: 10;
      }
      .tooltip-list {
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      .tooltip-row {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 5px;
        font-size: 12px;
        color: $fg;
      }
      .tooltip-empty {
        font-size: 12px;
        color: $grey;
      }
      &:hover .tooltip-body,
      &:focus-within .tooltip-body {
        opacity: 1;
        transform: translateY(0);
        pointer-events: auto;
      }
    }
  }
  .sanctions-table .rule-cell {
    max-width: 520px;
    white-space: pre-wrap;
    word-break: break-word;
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
      .tooltip {
        .tooltip-body {
          padding: 5px;
        }
      }
    }
    .sanctions-table .rule-cell {
      min-width: 220px;
    }
  }
}
</style>
