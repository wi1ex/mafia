<template>
  <section class="moderation">
    <header>
      <h1>Модерация</h1>
      <nav class="tabs" aria-label="Модерация">
        <button class="tab" type="button" :class="{ active: activeTab === 'users' }" :aria-pressed="activeTab === 'users'" @click="activeTab = 'users'">
          Пользователи
        </button>
        <button class="tab" type="button" :class="{ active: activeTab === 'sanctions' }" :aria-pressed="activeTab === 'sanctions'" @click="activeTab = 'sanctions'">
          Санкции
        </button>
        <button class="tab" type="button" :class="{ active: activeTab === 'contact_requests' }" :aria-pressed="activeTab === 'contact_requests'" @click="activeTab = 'contact_requests'">
          Обращения
        </button>
      </nav>
      <router-link class="home-link" :to="{ name: 'home' }" aria-label="На главную">На главную</router-link>
    </header>

    <div class="panel">
      <div v-if="activeTab === 'users'" class="tab-panel">
        <div class="filters">
          <div class="field">
            <UiInput id="moderation-users-user" v-model.trim="usersUser" label="Никнейм" size="low" :disabled="usersLoading" />
          </div>
          <div class="field">
            <label for="moderation-users-limit">Отображать по</label>
            <select id="moderation-users-limit" :value="usersLimit" :disabled="usersLoading" @change="setUsersLimit">
              <option v-for="option in PAGE_LIMIT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
          </div>
        </div>

        <div v-if="usersLoading" class="loading">Загрузка...</div>
        <div v-else class="results">
          <div class="table-wrap">
            <table class="table">
              <colgroup>
                <col class="user-column" />
                <col class="registered-column" />
                <col class="last-game-column" />
                <col class="online-column" />
                <col class="room-column" />
                <col class="spectator-column" />
                <col class="count-column" />
                <col class="count-column" />
                <col class="count-column" />
              </colgroup>
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
          </div>
          <div class="pager">
            <UiButton variant="white" size="middle" text="Назад" :disabled="usersPage <= 1" @click="prevUsers" />
            <span>Страница {{ usersPage }} из {{ usersPages }}</span>
            <UiButton variant="white" size="middle" text="Вперёд" :disabled="usersPage >= usersPages" @click="nextUsers" />
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'sanctions'" class="tab-panel">
        <div class="filters">
          <div class="field">
            <UiInput id="moderation-sanctions-user" v-model.trim="sanctionsUser" label="Никнейм" size="low" :disabled="sanctionsLoading" />
          </div>
          <div class="field">
            <label for="moderation-sanctions-limit">Отображать по</label>
            <select id="moderation-sanctions-limit" :value="sanctionsLimit" :disabled="sanctionsLoading" @change="setSanctionsLimit">
              <option v-for="option in PAGE_LIMIT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
          </div>
        </div>

        <div v-if="sanctionsLoading" class="loading">Загрузка...</div>
        <div v-else class="results">
          <div class="table-wrap">
            <table class="table sanctions-table">
              <colgroup>
                <col class="user-column" />
                <col class="kind-column" />
                <col class="status-column" />
                <col class="date-column" />
                <col class="date-column" />
                <col class="author-column" />
                <col class="author-column" />
                <col class="duration-column" />
                <col class="duration-column" />
                <col class="workoff-column" />
                <col class="rule-column" />
                <col class="description-column" />
                <col class="action-column" />
                <col class="action-column" />
              </colgroup>
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
                  <td class="rule-cell">
                    <select :value="row.reason || ''" :disabled="isSanctionReasonChanging(row)" :aria-label="`Пункт правил для санкции ${row.id}`" @change="updateSanctionReason(row, $event)">
                      <option v-if="!row.reason" value="" disabled>Пункт не указан</option>
                      <option v-else-if="!isCurrentSanctionReason(row.reason)" :value="row.reason">
                        Устаревший пункт: {{ row.reason }}
                      </option>
                      <option v-for="reason in sanctionReasons" :key="reason.value" :value="reason.value">
                        {{ reason.label }}
                      </option>
                    </select>
                  </td>
                  <td class="description-cell">{{ row.description || '-' }}</td>
                  <td class="actions-cell">
                    <UiButton v-if="canAdjustSanction(row)" variant="white" size="low" text="Уменьшить" :disabled="isSanctionAdjustBusy(row, 'decrease')" @click="openSanctionAdjust(row, 'decrease')" />
                    <span v-else>-</span>
                  </td>
                  <td class="actions-cell">
                    <UiButton v-if="canAdjustSanction(row)" size="low" text="Увеличить" :disabled="isSanctionAdjustBusy(row, 'increase')" @click="openSanctionAdjust(row, 'increase')" />
                    <span v-else>-</span>
                  </td>
                </tr>
                <tr v-if="sanctions.length === 0">
                  <td colspan="14" class="muted">Нет данных</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="pager">
            <UiButton variant="white" size="middle" text="Назад" :disabled="sanctionsPage <= 1" @click="prevSanctions" />
            <span>Страница {{ sanctionsPage }} из {{ sanctionsPages }}</span>
            <UiButton variant="white" size="middle" text="Вперёд" :disabled="sanctionsPage >= sanctionsPages" @click="nextSanctions" />
          </div>
        </div>
      </div>

      <div v-else class="tab-panel">
        <div class="filters">
          <div class="field">
            <UiInput id="moderation-contact-requests-user" v-model.trim="contactRequestsUser" label="Никнейм" size="low" :disabled="contactRequestsLoading" />
          </div>
          <div class="field">
            <label for="moderation-contact-requests-limit">Отображать по</label>
            <select id="moderation-contact-requests-limit" :value="contactRequestsLimit" :disabled="contactRequestsLoading" @change="setContactRequestsLimit">
              <option v-for="option in PAGE_LIMIT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
          </div>
        </div>

        <div v-if="contactRequestsLoading" class="loading">Загрузка...</div>
        <div v-else class="results">
          <div class="table-wrap">
            <table class="table contact-requests-table">
              <colgroup>
                <col class="id-column" />
                <col class="date-column" />
                <col class="user-column" />
                <col class="contact-column" />
                <col class="topic-column" />
                <col class="text-column" />
                <col class="replies-column" />
                <col class="action-column" v-if="isSeniorModerator" />
              </colgroup>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Дата</th>
                  <th>Никнейм</th>
                  <th>Контактные данные</th>
                  <th>Тема обращения</th>
                  <th>Текст обращения</th>
                  <th>Ответы</th>
                  <th v-if="isSeniorModerator">Связь</th>
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
                  <td class="replies-cell">
                    <div v-for="reply in row.replies" :key="reply.id" class="contact-reply">
                      <div class="contact-reply__meta">{{ reply.author_username }} (ID: {{ reply.author_id }}) · {{ formatLocalDateTime(reply.created_at) }}</div>
                      <div class="contact-reply__text">{{ reply.text }}</div>
                    </div>
                    <span v-if="!row.replies?.length" class="muted">—</span>
                  </td>
                  <td v-if="isSeniorModerator">
                    <UiButton v-if="canReplyToContactRequest(row)" size="low" text="Ответить" :disabled="contactRequestReplySaving" @click="openContactRequestReply(row)" />
                    <span v-else>-</span>
                  </td>
                </tr>
                <tr v-if="contactRequests.length === 0">
                  <td :colspan="isSeniorModerator ? 8 : 7" class="muted">Нет данных</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="pager">
            <UiButton variant="white" size="middle" text="Назад" :disabled="contactRequestsPage <= 1" @click="prevContactRequests" />
            <span>Страница {{ contactRequestsPage }} из {{ contactRequestsPages }}</span>
            <UiButton variant="white" size="middle" text="Вперёд" :disabled="contactRequestsPage >= contactRequestsPages" @click="nextContactRequests" />
          </div>
        </div>
      </div>
    </div>

    <SanctionModal
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
      :duration-hint="sanctionAdjustDurationHint"
      @update:open="onSanctionAdjustModalOpenUpdate"
      @save="saveSanctionAdjust"
    />
    <ContactModal
      :open="contactRequestReplyModalOpen && Boolean(contactRequestReplyTarget)"
      :saving="contactRequestReplySaving"
      :can-save="contactRequestReplyCanSave"
      :target="contactRequestReplyTarget"
      :message="contactRequestReplyText"
      @update:open="onContactRequestReplyModalOpenUpdate"
      @update:message="contactRequestReplyText = $event"
      @save="sendContactRequestReply"
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
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId } from '@/services/miniProfile'
import { useSettingsStore, useUserStore } from '@/store'

import ContactModal from '@/views/ContactModal.vue'
import MiniProfile from '@/views/MiniProfile.vue'
import SanctionModal from '@/views/SanctionModal.vue'
import UiInput from '@/components/UiInput.vue'
import UiButton from '@/components/UiButton.vue'

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
  replies: Array<{ id: number; author_id: number; author_username: string; created_at: string; text: string }>
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

type ContactRequestReplyTarget = ContactRequestRow & {
  user_id: number
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
const settingsStore = useSettingsStore()
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
const sanctionsReasonChanging = reactive<Record<number, boolean>>({})
const contactRequests = ref<ContactRequestRow[]>([])
const contactRequestsLoading = ref(false)
const contactRequestsTotal = ref(0)
const contactRequestsPage = ref(1)
const contactRequestsLimit = ref(20)
const contactRequestsUser = ref('')
const contactRequestReplyModalOpen = ref(false)
const contactRequestReplyTarget = ref<ContactRequestReplyTarget | null>(null)
const contactRequestReplyText = ref('')
const contactRequestReplySaving = ref(false)
let usersUserTimer: number | undefined
let sanctionsUserTimer: number | undefined
let contactRequestsUserTimer: number | undefined

const sanctionReasons = computed(() => settingsStore.sanctionReasons)
const sanctionReasonValues = computed(() => new Set(sanctionReasons.value.map(({ value }) => value)))
const MODERATION_MAX_TIMED_SANCTION_SECONDS = 7 * 24 * 60 * 60
const canIssueExtendedModerationSanctions = computed(() => viewerUserId.value === settingsStore.seniorModeratorUserId)
const isSeniorModerator = computed(() => viewerUserId.value === settingsStore.seniorModeratorUserId)
const contactRequestReplyCanSave = computed(() => contactRequestReplyText.value.trim().length > 0)
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
const sanctionAdjustDurationWithinLimit = computed(() => {
  const target = sanctionAdjustTarget.value
  if (!target || sanctionAdjustMode.value !== 'increase' || canIssueExtendedModerationSanctions.value) return true

  const issuedAt = Date.parse(target.issued_at)
  const expiresAt = Date.parse(target.finished_at || '')
  if (!Number.isFinite(issuedAt) || !Number.isFinite(expiresAt)) return false

  return expiresAt + sanctionAdjustTotalSeconds.value <= issuedAt + MODERATION_MAX_TIMED_SANCTION_SECONDS * 1000
})
const sanctionAdjustDurationHint = computed(() => (
  sanctionAdjustMode.value === 'increase' && !canIssueExtendedModerationSanctions.value
    ? 'Срок санкции не может превышать 7 дней.'
    : ''
))
const sanctionAdjustCanSave = computed(() => {
  const target = sanctionAdjustTarget.value
  return Boolean(
    target
    && canAdjustSanction(target)
    && sanctionAdjustDurationValid.value
    && sanctionAdjustTotalSeconds.value > 0
    && sanctionAdjustDurationWithinLimit.value,
  )
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

function canReplyToContactRequest(row: ContactRequestRow): boolean {
  return isSeniorModerator.value && getPositiveUserId(row.user_id) > 0
}

function clearContactRequestReplyModalState(): void {
  contactRequestReplyModalOpen.value = false
  contactRequestReplyTarget.value = null
  contactRequestReplyText.value = ''
}

function closeContactRequestReplyModal(): void {
  if (contactRequestReplySaving.value) return
  clearContactRequestReplyModalState()
}

function onContactRequestReplyModalOpenUpdate(open: boolean): void {
  if (open) {
    contactRequestReplyModalOpen.value = true
    return
  }
  closeContactRequestReplyModal()
}

function openContactRequestReply(row: ContactRequestRow): void {
  const userId = getPositiveUserId(row.user_id)
  if (!isSeniorModerator.value || userId <= 0 || contactRequestReplySaving.value) return
  contactRequestReplyTarget.value = { ...row, user_id: userId }
  contactRequestReplyText.value = ''
  contactRequestReplyModalOpen.value = true
}

async function sendContactRequestReply(): Promise<void> {
  const target = contactRequestReplyTarget.value
  const text = contactRequestReplyText.value.trim()
  if (!isSeniorModerator.value || !target || contactRequestReplySaving.value || !text) return

  contactRequestReplySaving.value = true
  try {
    await api.post(`/moderation/contact_requests/${target.id}/reply`, { text }, { timeout: 60_000 })
    clearContactRequestReplyModalState()
    await loadContactRequests()
    void alertDialog('Ответ отправлен пользователю')
  } catch (e: any) {
    const status = Number(e?.response?.status || 0)
    const detail = String(e?.response?.data?.detail || '')
    if (status === 403) void alertDialog('Отвечать на обращения может только старший модератор')
    else if (status === 404 && detail === 'contact_request_not_found') void alertDialog('Обращение не найдено')
    else if (status === 404 && detail === 'contact_request_user_not_found') void alertDialog('Пользователь не найден')
    else if (detail === 'contact_request_telegram_missing') void alertDialog('У пользователя не привязан Telegram. Ответ не отправлен и не сохранён')
    else if (detail === 'contact_request_telegram_failed') void alertDialog('Telegram не подтвердил отправку. Ответ не сохранён')
    else if (status === 409 && detail === 'contact_request_guest') void alertDialog('На обращение гостя ответить через сайт нельзя')
    else if (status === 422 && detail === 'contact_request_reply_empty') void alertDialog('Введите текст ответа')
    else void alertDialog('Не удалось отправить ответ')
  } finally {
    contactRequestReplySaving.value = false
  }
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

function isCurrentSanctionReason(reason: string | null | undefined): boolean {
  return Boolean(reason && sanctionReasonValues.value.has(reason))
}

function isSanctionReasonChanging(row: SanctionsRow): boolean {
  return Boolean(sanctionsReasonChanging[row.id])
}

async function updateSanctionReason(row: SanctionsRow, event: Event): Promise<void> {
  const nextReason = selectValue(event).trim()
  const previousReason = row.reason || ''
  const select = event.target as HTMLSelectElement
  if (!nextReason || nextReason === previousReason || isSanctionReasonChanging(row)) return

  sanctionsReasonChanging[row.id] = true
  try {
    await api.patch(`/moderation/sanctions/${row.id}/reason`, { reason: nextReason })
    row.reason = nextReason
    void alertDialog('Пункт правил изменён')
  } catch (e: any) {
    select.value = previousReason
    const status = Number(e?.response?.status || 0)
    const detail = String(e?.response?.data?.detail || '')
    if (status === 403 && detail === 'forbidden') {
      void alertDialog('Нельзя изменить санкцию этого пользователя')
    } else if (status === 404 && detail === 'sanction_not_found') {
      void loadSanctions()
      void alertDialog('Санкция не найдена')
    } else if (status === 422 && detail === 'reason_required') {
      void alertDialog('Выберите пункт правил')
    } else {
      void alertDialog('Не удалось изменить пункт правил')
    }
  } finally {
    sanctionsReasonChanging[row.id] = false
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
    else if (st === 422 && d === 'moderation_sanction_duration_limit') void alertDialog('Модератор не может увеличить срок санкции более чем до 7 дней')
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
  flex: 1;
  min-height: 0;
  box-sizing: border-box;
  width: 100%;
  padding: 30px 40px;
  gap: 10px;
  color: $neutral-100;
  font-family: Hauora-Regular;
  line-height: 1.4;
  overflow: hidden;
  user-select: text;
  > header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
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
    .tabs {
      display: flex;
      align-items: center;
      flex: 1;
      gap: 10px;
      .tab {
        padding: 10px 24px;
        border: none;
        border-radius: 12px;
        background-color: $soft-purple-800;
        color: $neutral-300;
        font-family: Hauora-Medium;
        font-size: 16px;
        line-height: 20px;
        cursor: pointer;
        transition: background-color 0.25s ease-in-out, color 0.25s ease-in-out;
        &:hover {
          background-color: $soft-purple-700;
          color: $neutral-white;
        }
        &.active {
          background-color: rgba($green-500, 0.12);
          color: $green-500;
        }
        &:focus-visible {
          outline: 2px solid $green-500;
          outline-offset: 3px;
        }
      }
    }
    .home-link {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 10px 24px;
      border-radius: 12px;
      background-color: $neutral-100;
      color: $neutral-black;
      font-family: Hauora-Medium;
      font-size: 16px;
      line-height: 20px;
      text-decoration: none;
      transition: background-color 0.25s ease-in-out;
      &:hover {
        background-color: $neutral-white;
      }
      &:focus-visible {
        outline: 2px solid $green-500;
        outline-offset: 3px;
      }
    }
  }
  .panel {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    padding: 24px;
    border-radius: 24px;
    background-color: $soft-purple-900;
    .tab-panel {
      display: flex;
      flex-direction: column;
      flex: 1;
      min-height: 0;
      gap: 24px;
      .filters {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        flex-shrink: 0;
        gap: 24px;
        --ui-input-label-bg: #{$soft-purple-900};
        .field {
          display: flex;
          flex-direction: column;
          width: 160px;
          gap: 10px;
          &:first-child {
            width: 360px;
          }
          > label {
            color: $neutral-300;
            font-size: 14px;
            line-height: 20px;
          }
          select {
            box-sizing: border-box;
            width: 100%;
            height: 40px;
            padding: 0 12px;
            border: 1px solid $green-200;
            border-radius: 12px;
            background-color: $soft-purple-900;
            color: $neutral-100;
            font-family: Hauora-Regular;
            font-size: 16px;
            line-height: 20px;
            color-scheme: dark;
            cursor: pointer;
            &:not(:disabled):hover {
              border-color: $green-500;
            }
            &:focus-visible {
              outline: 2px solid $green-500;
              outline-offset: 3px;
            }
            &:disabled {
              opacity: 0.5;
              cursor: not-allowed;
            }
            option {
              background-color: $soft-purple-900;
              color: $neutral-100;
            }
          }
        }
      }
      .loading {
        padding: 24px;
        border-radius: 20px;
        background-color: $soft-purple-800;
        color: $neutral-300;
        text-align: center;
      }
      .results {
        display: flex;
        flex-direction: column;
        flex: 1;
        min-height: 0;
        gap: 24px;
        .table-wrap {
          flex: 1;
          min-height: 0;
          border-radius: 20px;
          background-color: $soft-purple-800;
          overflow: auto;
          overscroll-behavior: contain;
          scrollbar-width: thin;
          scrollbar-color: $soft-purple-700 transparent;
          .table {
            width: 100%;
            min-width: 1400px;
            border-collapse: separate;
            border-spacing: 0;
            table-layout: fixed;
            colgroup {
              .user-column {
                width: 18%;
              }
              .registered-column {
                width: 15%;
              }
              .last-game-column {
                width: 16%;
              }
              .online-column {
                width: 12%;
              }
              .room-column,
              .spectator-column {
                width: 9%;
              }
              .count-column {
                width: 7%;
              }
            }
            &.sanctions-table {
              min-width: 2260px;
              colgroup {
                .user-column {
                  width: 170px;
                }
                .kind-column {
                  width: 115px;
                }
                .status-column {
                  width: 105px;
                }
                .date-column,
                .author-column {
                  width: 150px;
                }
                .duration-column {
                  width: 110px;
                }
                .workoff-column {
                  width: 120px;
                }
                .rule-column {
                  width: 260px;
                }
                .description-column {
                  width: 300px;
                }
                .action-column {
                  width: 135px;
                }
              }
            }
            &.contact-requests-table {
              min-width: 1440px;
              colgroup {
                .id-column {
                  width: 4%;
                }
                .date-column {
                  width: 11%;
                }
                .user-column {
                  width: 13%;
                }
                .contact-column {
                  width: 12%;
                }
                .topic-column {
                  width: 11%;
                }
                .text-column {
                  width: 18%;
                }
                .replies-column {
                  width: 21%;
                }
                .action-column {
                  width: 10%;
                }
              }
            }
            thead {
              position: sticky;
              top: 0;
              z-index: 1;
              tr {
                th {
                  padding: 16px;
                  border-bottom: 1px solid $soft-purple-700;
                  background-color: $soft-purple-800;
                  color: $neutral-300;
                  font-family: Hauora-Medium;
                  font-weight: 500;
                  font-size: 14px;
                  line-height: 20px;
                  text-align: left;
                  .table-sort {
                    display: inline-flex;
                    align-items: flex-start;
                    padding: 0;
                    gap: 6px;
                    border: none;
                    background: transparent;
                    color: inherit;
                    font: inherit;
                    text-align: left;
                    cursor: pointer;
                    span {
                      opacity: 0.5;
                    }
                    &:hover,
                    &.active {
                      color: $green-500;
                    }
                    &.active span {
                      opacity: 1;
                    }
                    &:focus-visible {
                      outline: 2px solid $green-500;
                      outline-offset: 3px;
                      border-radius: 4px;
                    }
                  }
                }
              }
            }
            tbody {
              tr {
                &:last-child td {
                  border-bottom: none;
                }
                td {
                  padding: 16px;
                  border-bottom: 1px solid $soft-purple-700;
                  vertical-align: top;
                  font-size: 14px;
                  line-height: 20px;
                  overflow-wrap: anywhere;
                  &.muted {
                    padding: 32px 24px;
                    color: $neutral-300;
                    text-align: center;
                  }
                  .user-cell {
                    min-width: 0;
                    .user-profile-trigger {
                      display: flex;
                      align-items: center;
                      width: 100%;
                      min-width: 0;
                      padding: 0;
                      gap: 8px;
                      border: none;
                      background: transparent;
                      color: $neutral-100;
                      font: inherit;
                      text-align: left;
                      transition: color 0.25s ease-in-out;
                      &:not(:disabled) {
                        cursor: pointer;
                      }
                      &:not(:disabled):hover {
                        color: $green-500;
                      }
                      &:disabled {
                        cursor: default;
                        opacity: 1;
                      }
                      &:focus-visible {
                        outline: 2px solid $green-500;
                        outline-offset: 4px;
                        border-radius: 8px;
                      }
                      .user-avatar {
                        flex: 0 0 24px;
                        width: 24px;
                        height: 24px;
                        border-radius: 50%;
                        object-fit: cover;
                      }
                      span {
                        min-width: 0;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        white-space: nowrap;
                      }
                    }
                  }
                  .status-badge {
                    display: inline-flex;
                    align-items: center;
                    padding: 6px 10px;
                    border-radius: 12px;
                    font-family: Hauora-Medium;
                    font-size: 12px;
                    line-height: 16px;
                    white-space: nowrap;
                    &.status-active {
                      background-color: rgba($green-500, 0.12);
                      color: $green-500;
                    }
                    &.status-expired {
                      background-color: rgba($yellow-500, 0.12);
                      color: $yellow-500;
                    }
                    &.status-revoked {
                      background-color: rgba($red-500, 0.12);
                      color: $red-300;
                    }
                  }
                  &.rule-cell {
                    select {
                      box-sizing: border-box;
                      width: 100%;
                      min-width: 0;
                      height: 40px;
                      padding: 0 12px;
                      border: 1px solid $green-200;
                      border-radius: 12px;
                      background-color: $soft-purple-800;
                      color: $neutral-100;
                      font-family: Hauora-Regular;
                      font-size: 14px;
                      line-height: 20px;
                      text-overflow: ellipsis;
                      color-scheme: dark;
                      cursor: pointer;
                      &:not(:disabled):hover {
                        border-color: $green-500;
                      }
                      &:focus-visible {
                        outline: 2px solid $green-500;
                        outline-offset: 3px;
                      }
                      &:disabled {
                        opacity: 0.5;
                        cursor: not-allowed;
                      }
                      option {
                        background-color: $soft-purple-900;
                        color: $neutral-100;
                      }
                    }
                  }
                  &.description-cell,
                  &.contact-cell,
                  &.topic-cell,
                  &.text-cell {
                    white-space: pre-wrap;
                  }
                  &.replies-cell {
                    .contact-reply {
                      & + .contact-reply {
                        margin-top: 16px;
                        padding-top: 16px;
                        border-top: 1px solid $soft-purple-700;
                      }
                      .contact-reply__meta {
                        margin-bottom: 8px;
                        color: $neutral-300;
                        font-size: 12px;
                        line-height: 18px;
                      }
                      .contact-reply__text {
                        white-space: pre-wrap;
                      }
                    }
                    .muted {
                      color: $neutral-300;
                    }
                  }
                }
              }
            }
          }
        }
        .pager {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-shrink: 0;
          gap: 16px;
          span {
            color: $neutral-300;
            font-size: 14px;
            line-height: 20px;
          }
        }
      }
    }
  }
}
</style>
