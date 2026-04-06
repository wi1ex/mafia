<template>
  <section class="moderation">
    <header>
      <nav class="tabs" aria-label="Модерация">
        <button class="tab active" type="button" disabled>
          Пользователи
        </button>
      </nav>
      <router-link class="btn nav" :to="{ name: 'home' }" aria-label="На главную">На главную</router-link>
    </header>

    <div class="panel">
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
              <th>
                <button class="th-sort" type="button" :class="{ active: usersSortBy === 'suspends_count' }" @click="setUsersSort('suspends_count')">
                  Огранич.
                  <span class="th-sort-mark" aria-hidden="true">▼</span>
                </button>
              </th>
              <th>Огранич.</th>
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
                <button class="btn" :class="row.suspend_active ? 'dark' : 'danger'" :disabled="isSanctionBusy(row.id)" @click="toggleSuspend(row)">
                  <img class="btn-img" :src="row.suspend_active ? iconClose : iconJudge" alt="" />
                </button>
              </td>
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

type UserRow = {
  id: number
  username?: string | null
  avatar_name?: string | null
  registered_at: string
  last_login_at: string
  last_visit_at: string
  last_game_at?: string | null
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

const users = ref<UserRow[]>([])
const usersLoading = ref(false)
const usersTotal = ref(0)
const usersPage = ref(1)
const usersLimit = ref(20)
const usersUser = ref('')
const usersSortBy = ref<UsersSortBy>('registered_at')
const usersSanctionBusy = reactive<Record<number, boolean>>({})
let usersUserTimer: number | undefined

const sanctionReasons = SANCTION_REASONS
const sanctionModalOpen = ref(false)
const sanctionSaving = ref(false)
const sanctionTarget = ref<UserRow | null>(null)
const sanctionForm = reactive({
  months: 0,
  days: 0,
  hours: 0,
  minutes: 0,
  reason: DEFAULT_SANCTION_REASON,
})

const usersPages = computed(() => Math.max(1, Math.ceil(usersTotal.value / usersLimit.value)))
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
  return `Ограничение: ${label}`
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

function isSanctionBusy(userId: number): boolean {
  return Boolean(usersSanctionBusy[userId])
}

function setSanctionBusy(userId: number, value: boolean): void {
  usersSanctionBusy[userId] = value
}

function resetSanctionForm(): void {
  sanctionForm.months = 0
  sanctionForm.days = 0
  sanctionForm.hours = 0
  sanctionForm.minutes = 0
  sanctionForm.reason = DEFAULT_SANCTION_REASON
}

function openSuspend(row: UserRow): void {
  sanctionTarget.value = row
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

async function saveSanction(): Promise<void> {
  const target = sanctionTarget.value
  if (!target || sanctionSaving.value || !sanctionCanSave.value) return
  sanctionSaving.value = true
  try {
    await api.post(`/moderation/users/${target.id}/suspend`, {
      months: sanctionForm.months,
      days: sanctionForm.days,
      hours: sanctionForm.hours,
      minutes: sanctionForm.minutes,
      reason: sanctionForm.reason,
    })
    sanctionModalOpen.value = false
    void alertDialog('Ограничение выдано')
    await loadUsers()
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 409 && d === 'sanction_active') {
      void alertDialog('Санкция уже активна')
    } else if (st === 422 && d === 'duration_required') {
      void alertDialog('Укажите срок санкции')
    } else {
      void alertDialog('Не удалось применить ограничение')
    }
  } finally {
    sanctionSaving.value = false
  }
}

async function revokeSuspend(row: UserRow): Promise<void> {
  if (isSanctionBusy(row.id)) return
  const userLabel = row.username ? `${row.username}` : `#${row.id}`
  const ok = await confirmDialog({
    title: 'Снять ограничение',
    text: `Снять ограничение у ${userLabel}?`,
    confirmText: 'Снять',
    cancelText: 'Отмена',
  })
  if (!ok) return
  setSanctionBusy(row.id, true)
  try {
    await api.delete(`/moderation/users/${row.id}/suspend`)
    void alertDialog('Ограничение снято')
    await loadUsers()
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 404 && d === 'sanction_not_found') {
      void alertDialog('Санкция не найдена')
    } else {
      void alertDialog('Не удалось снять ограничение')
    }
  } finally {
    setSanctionBusy(row.id, false)
  }
}

async function toggleSuspend(row: UserRow): Promise<void> {
  if (row.suspend_active) {
    await revokeSuspend(row)
    return
  }
  openSuspend(row)
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

watch([usersLimit, usersSortBy], () => {
  usersPage.value = 1
  void loadUsers()
})

watch(usersUser, () => {
  usersPage.value = 1
  if (usersUserTimer) window.clearTimeout(usersUserTimer)
  usersUserTimer = window.setTimeout(() => { void loadUsers() }, 500)
})

onMounted(() => {
  void loadUsers()
})

onBeforeUnmount(() => {
  if (usersUserTimer) window.clearTimeout(usersUserTimer)
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
        height: 40px;
        border: none;
        border-radius: 5px 5px 0 0;
        background-color: $lead;
        color: $fg;
        font-size: 18px;
        font-family: Manrope-Medium;
        line-height: 1;
        cursor: default;
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
  }
}
</style>
