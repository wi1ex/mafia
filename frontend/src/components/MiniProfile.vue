<template>
  <Teleport to="body">
    <Transition name="user-mini-profile-fade">
      <div v-if="canRenderOpen" class="user-mini-profile-overlay" role="presentation" @pointerdown.stop.self @click.stop.self="close">
        <section class="user-mini-profile-panel" :class="{ 'stats-mode': view === 'stats' }" :style="profilePanelStyle"
                 role="dialog" aria-modal="true" :aria-label="`Профиль ${displayName}`" @pointerdown.stop @click.stop>
          <header class="profile-top">
            <div class="profile-identity">
              <button class="profile-avatar-trigger" type="button" :disabled="!hasAvatar" aria-label="Open avatar" @click="openAvatarLightbox">
                <img ref="avatarImageEl" class="profile-avatar" v-minio-img="{ key: avatarKey, placeholder: defaultAvatar, lazy: false, animated: true }" alt="avatar" />
              </button>
              <div class="profile-icon-name">
                <div class="profile-title">
                  <div v-if="profileThemeIconSrcs.length" class="profile-theme-icons" aria-hidden="true">
                    <img v-for="badgeSrc in profileThemeIconSrcs" :key="badgeSrc" class="profile-theme-icon" :src="badgeSrc" alt="" />
                  </div>
                  <span class="profile-name">{{ displayName }}</span>
                </div>
                <div v-if="showProfileMeta" class="profile-meta">
                  <span v-if="friendsCount !== null" class="profile-tooltip-wrap profile-friends-tooltip-wrap" :class="{ enabled: showAdminFriendsTooltip }" :tabindex="showAdminFriendsTooltip ? 0 : undefined">
                    <span class="profile-friends-count" aria-label="Количество друзей">
                      Друзья: {{ friendsCount }}
                    </span>
                    <span v-if="showAdminFriendsTooltip" class="profile-tooltip profile-friends-tooltip" role="tooltip">
                      <span v-if="adminFriends.length === 0" class="profile-friends-empty">Нет друзей</span>
                      <span v-else class="profile-friends-list">
                        <span v-for="friend in adminFriends" :key="friend.id" class="profile-friend-row">
                          <img class="profile-friend-avatar" v-minio-img="{key: friendAvatarKey(friend), placeholder: defaultAvatar, lazy: false, animated: true}" alt="avatar" />
                          <span class="profile-friend-main">
                            <span class="profile-friend-name">{{ friend.username || `user${friend.id}` }}</span>
                            <span class="profile-friend-date">
                              {{ formatFriendshipStartedAt(friend.friendship_started_at) }}
                            </span>
                          </span>
                        </span>
                      </span>
                    </span>
                  </span>
                  <span v-for="nomination in profileNominations" :key="nomination.key" class="profile-tooltip-wrap profile-nomination-tooltip-wrap" :class="`level-${nomination.level}`"
                        tabindex="0" :aria-label="`${nomination.label}: ${nomination.valueLabel}, ${nomination.levelLabel}`">
                    <span class="profile-nomination-icon-shell">
                      <img class="profile-nomination-icon" :src="nomination.icon" alt="" />
                    </span>
                    <span class="profile-tooltip profile-nomination-tooltip" role="tooltip">
                      <span class="nomination-tooltip-head">
                        <strong>{{ nomination.label }}</strong>
                        <span class="nomination-level-badge">
                          {{ nomination.levelLabel }}
                        </span>
                      </span>
                      <span class="nomination-progress-caption">
                        <span>{{ nomination.progressStartLabel }}</span>
                        <span>{{ nomination.progressNextLabel }}</span>
                      </span>
                      <span class="nomination-progress-track">
                        <span class="nomination-progress-fill" :style="{ width: `${nomination.progressPct}%` }"></span>
                        <span class="nomination-progress-value">{{ nomination.valueLabel }}</span>
                      </span>
                    </span>
                  </span>

                  <span v-if="activeSanction" class="profile-tooltip-wrap sanction-tooltip-wrap" tabindex="0">
                    <img class="profile-meta-icon" :src="iconJudge" alt="" />
                    <span class="profile-tooltip sanction-tooltip" role="tooltip">
                      <strong>{{ activeSanctionKindLabel }}</strong>
                      <span>{{ activeSanctionExpiryLabel }}</span>
                    </span>
                  </span>
                  <span v-if="targetUserId > 0" class="profile-tooltip-wrap profile-history-tooltip-wrap" tabindex="0" @mouseenter="loadNicknameHistory" @focusin="loadNicknameHistory">
                    <img class="profile-meta-icon" :src="iconTimeHistory" alt="" />
                    <span class="profile-tooltip nickname-history-tooltip" role="tooltip">
                      <span v-if="nicknameHistoryLoading" class="nickname-history-state">Загрузка...</span>
                      <span v-else-if="nicknameHistoryError" class="nickname-history-state danger">{{ nicknameHistoryError }}</span>
                      <span v-else class="nickname-history-list">
                        <span v-for="(nickname, index) in nicknameHistoryItems" :key="`${nickname}-${index}`" :class="{ current: index === 0 }">
                          {{ nickname }}
                        </span>
                        <span v-if="!nicknameHistoryItems.length" class="nickname-history-state">-</span>
                      </span>
                    </span>
                  </span>
                </div>
              </div>
            </div>
            <div class="profile-side-tools">
              <button class="close-button" type="button" aria-label="Закрыть" @click="close">
                <img :src="iconClose" alt="" />
              </button>
            </div>
          </header>

          <template v-if="view === 'profile'">
            <p v-if="loading && !profileLoadedForTarget" class="state">Загрузка...</p>
            <p v-else-if="loadError" class="state state-danger">{{ loadError }}</p>

            <div v-else class="profile-dates" aria-label="Даты профиля">
              <div class="date-row">
                <span>Дата регистрации</span>
                <strong>{{ registeredAtLabel }}</strong>
              </div>
              <div class="date-row">
                <span>Последняя игра</span>
                <strong>{{ lastGameAtLabel }}</strong>
              </div>
              <div class="date-row">
                <span>Последний онлайн</span>
                <strong>{{ lastOnlineLabel }}</strong>
              </div>
            </div>

            <div v-if="showActionBlock" class="profile-actions">
              <button v-if="showStatsButton" class="profile-action secondary" type="button" @click="view = 'stats'">
                Статистика пользователя
              </button>
              <button v-if="showFriendAction" class="profile-action friend-action" :class="`status-${friendStatusClass}`"
                      type="button" :disabled="friendDisabled" @click="onFriendAction(friendActionKind)">
                <img :src="friendActionIcon" alt="" />
                <span>{{ friendActionLabel }}</span>
              </button>
            </div>

            <div v-if="showStaffActionBlock" class="profile-staff-actions" aria-label="Действия с пользователем">
              <div v-for="action in staffActionItems" :key="action.key" class="staff-action-item">
                <button class="btn staff-action-button" :class="action.buttonClass" type="button" :disabled="action.disabled"
                        :aria-label="action.ariaLabel" @click="onStaffAction(action.key)">
                  <img v-if="action.icon" class="btn-img" :src="action.icon" alt="" />
                  <span v-if="action.buttonText">{{ action.buttonText }}</span>
                </button>
                <span class="staff-action-label">{{ action.label }}</span>
              </div>
            </div>
          </template>

          <template v-else>
            <div class="stats-toolbar">
              <button class="profile-action secondary" type="button" @click="view = 'profile'">Назад к профилю</button>
            </div>
            <Stats :stats-url="resolvedStatsUrl" />
          </template>
        </section>
      </div>
    </Transition>
    <Transition name="avatar-lightbox-transition">
      <div v-if="avatarLightboxOpen && avatarLightboxSrc" class="avatar-lightbox-overlay" role="dialog"
           aria-modal="true" aria-label="Avatar preview" @pointerdown.stop @click.stop @click.self="closeAvatarLightbox">
        <img class="avatar-lightbox-image" :src="avatarLightboxSrc" alt="avatar" />
      </div>
    </Transition>
    <Sanction
      :open="staffSanctionModalOpen"
      :title="staffSanctionTitle"
      :saving="staffSanctionSaving"
      :can-save="staffSanctionCanSave"
      :show-duration="staffSanctionKind !== 'ban'"
      :form="staffSanctionForm"
      :reasons="staffSanctionReasons"
      :z-index="STAFF_MODAL_Z_INDEX"
      @update:open="onStaffSanctionModalOpenUpdate"
      @save="saveStaffSanction"
    />
    <Subscription
      :open="staffSubscriptionModalOpen"
      title="Выдать подписку"
      save-label="Выдать"
      :saving="staffSubscriptionSaving"
      :can-save="staffSubscriptionCanSave"
      :target="staffSubscriptionTarget"
      :form="staffSubscriptionForm"
      :z-index="STAFF_MODAL_Z_INDEX"
      @update:open="onStaffSubscriptionModalOpenUpdate"
      @save="saveStaffSubscription"
    />
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { isMiniProfilePrivilegedViewer, normalizeMiniProfileRole } from '@/services/miniProfile'
import { DEFAULT_SANCTION_REASON, SANCTION_REASONS } from '@/constants/sanctionReasons'
import { buildProfileThemeBgStyle } from '@/constants/profileThemes'
import { getProfileThemeBadgeSources } from '@/constants/profileIcons'
import {
  useFriendsStore,
  useSettingsStore,
  useUserStore,
  resolveFriendsApiError,
  shouldRefreshFriendsStateAfterError,
  type FriendApiAction,
  type FriendStatus,
} from '@/store'
import Stats from '@/components/Stats.vue'
import Sanction from '@/components/Sanction.vue'
import Subscription from '@/components/Subscription.vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconClose from '@/assets/svg/close.svg'
import iconAddFriends from '@/assets/svg/addFriends.svg'
import iconInFriends from '@/assets/svg/inFriends.svg'
import iconRecieveFriends from '@/assets/svg/recieveFriends.svg'
import iconSendFriends from '@/assets/svg/sendFriends.svg'
import iconJudge from '@/assets/svg/judge.svg'
import iconTimeHistory from '@/assets/svg/timeHistory.svg'
import nominationGames from '@/assets/svg/nominationGames.svg'
import nominationHead from '@/assets/svg/nominationHead.svg'
import nominationRoom from '@/assets/svg/nominationRoom.svg'
import nominationStream from '@/assets/svg/nominationStream.svg'
import nominationSpectator from '@/assets/svg/nominationSpectator.svg'

type FriendActionKind = 'add' | 'remove' | 'incoming' | 'outgoing'
type MiniProfileSanctionKind = 'timeout' | 'ban' | 'suspend'
type StaffActionKey = 'subscription' | 'role' | 'account' | 'avatar' | 'nickname' | 'suspend' | 'timeout' | 'ban'
type StaffActionScope = 'admin' | 'moderation'
type NominationLevel = 1 | 2 | 3 | 4 | 5
type NominationStatKey = 'games_played' | 'games_hosted' | 'room_minutes' | 'stream_minutes' | 'spectator_minutes'

type StaffActionItem = {
  key: StaffActionKey
  label: string
  buttonClass: string
  disabled: boolean
  ariaLabel: string
  icon?: string
  buttonText?: string
}

type MiniProfileSanction = {
  kind?: MiniProfileSanctionKind | string | null
  expires_at?: string | null
}

type MiniProfileAdminFriend = {
  id: number
  username?: string | null
  avatar_name?: string | null
  friendship_started_at?: string | null
}

type MiniProfileNominationStats = {
  games_played?: number | null
  games_hosted?: number | null
  room_minutes?: number | null
  stream_minutes?: number | null
  spectator_minutes?: number | null
}

type ProfileNominationDefinition = {
  key: string
  label: string
  icon: string
  statKey: NominationStatKey
  unit: 'count' | 'minutes'
  levelStarts: readonly [number, number, number, number, number]
  startLabels: readonly [string, string, string, string, string]
  nextLabels: readonly [string, string, string, string]
}

type ProfileNomination = {
  key: string
  label: string
  level: NominationLevel
  levelLabel: string
  icon: string
  valueLabel: string
  progressPct: number
  progressStartLabel: string
  progressNextLabel: string
}

type MiniProfileInitial = {
  id?: number | null
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  theme_color?: string | null
  theme_icon?: string | null
  profile_theme_color?: string | null
  profile_theme_icon?: string | null
  friend_status?: FriendStatus | null
  deleted?: boolean | null
  deleted_at?: string | null
  kind?: 'incoming' | 'outgoing' | 'online' | 'offline' | string | null
}

type MiniProfileResponse = {
  id: number
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  protected_user?: boolean
  deleted?: boolean
  registered_at?: string | null
  last_visit_at?: string | null
  last_game_at?: string | null
  last_game_id?: number | null
  online?: boolean
  subscription_active?: boolean
  timeout_active?: boolean
  timeout_until?: string | null
  ban_active?: boolean
  suspend_active?: boolean
  suspend_until?: string | null
  profile_theme_color?: string | null
  profile_theme_icon?: string | null
  friend_status?: FriendStatus | null
  friends_count?: number | null
  admin_friends?: MiniProfileAdminFriend[] | null
  active_sanction?: MiniProfileSanction | null
  nomination_stats?: MiniProfileNominationStats | null
}

type NicknameHistoryResponse = {
  items?: string[] | null
}

const props = withDefaults(defineProps<{
  open: boolean
  userId?: number | null
  initialProfile?: MiniProfileInitial | null
  showStatsButton?: boolean
  adminMode?: boolean
  allowDeleted?: boolean
  statsUrl?: string | null
  refreshFriendsListOnAction?: boolean
  refreshFriendsRoomId?: number | null
}>(), {
  userId: null,
  initialProfile: null,
  showStatsButton: false,
  adminMode: false,
  allowDeleted: false,
  statsUrl: null,
  refreshFriendsListOnAction: false,
  refreshFriendsRoomId: null,
})

const emit = defineEmits<{
  'update:open': [value: boolean]
  'friend-status-change': [userId: number, status: FriendStatus]
  'staff-action-complete': [payload: { userId: number, action: StaffActionKey | 'sanction' }]
}>()

const friends = useFriendsStore()
const settingsStore = useSettingsStore()
const userStore = useUserStore()
const loading = ref(false)
const loadError = ref('')
const profile = ref<MiniProfileResponse | null>(null)
const friendStatus = ref<FriendStatus>('none')
const friendBusy = ref(false)
const view = ref<'profile' | 'stats'>('profile')
const avatarImageEl = ref<HTMLImageElement | null>(null)
const avatarLightboxOpen = ref(false)
const avatarLightboxSrc = ref('')
const nicknameHistoryLoading = ref(false)
const nicknameHistoryError = ref('')
const nicknameHistoryItems = ref<string[]>([])
const nicknameHistoryLoadedForTarget = ref(0)
const staffRoleBusy = ref(false)
const staffAccountBusy = ref(false)
const staffAvatarBusy = ref(false)
const staffNicknameBusy = ref(false)
const staffSanctionBusy = reactive<Record<string, boolean>>({})
const staffSanctionModalOpen = ref(false)
const staffSanctionSaving = ref(false)
const staffSanctionKind = ref<MiniProfileSanctionKind>('timeout')
const staffSanctionReasons = SANCTION_REASONS
const staffSanctionForm = reactive({
  months: 0,
  days: 0,
  hours: 0,
  reason: DEFAULT_SANCTION_REASON,
  description: '',
})
const staffSubscriptionModalOpen = ref(false)
const staffSubscriptionSaving = ref(false)
const staffSubscriptionForm = reactive({
  months: 0,
  days: 0,
})
let requestSeq = 0
let nicknameHistorySeq = 0

const MINUTES_IN_DAY = 24 * 60
const STAFF_MODAL_Z_INDEX = 1700
const STAFF_SANCTION_DURATION_LIMITS = {
  months: 240,
  days: 31,
  hours: 23,
} as const
const nominationIntFmt = new Intl.NumberFormat('ru-RU')
const PROFILE_NOMINATION_DEFINITIONS: readonly ProfileNominationDefinition[] = [
  {
    key: 'games-played',
    label: 'Игры',
    icon: nominationGames,
    statKey: 'games_played',
    unit: 'count',
    levelStarts: [0, 50, 200, 500, 1001],
    startLabels: ['0', '50', '200', '500', '1000'],
    nextLabels: ['50', '200', '500', '1000'],
  },
  {
    key: 'games-hosted',
    label: 'Ведущий',
    icon: nominationHead,
    statKey: 'games_hosted',
    unit: 'count',
    levelStarts: [0, 20, 50, 100, 301],
    startLabels: ['0', '20', '50', '100', '300'],
    nextLabels: ['20', '50', '100', '300'],
  },
  {
    key: 'room-time',
    label: 'В комнатах',
    icon: nominationRoom,
    statKey: 'room_minutes',
    unit: 'minutes',
    levelStarts: [0, 7 * MINUTES_IN_DAY, 14 * MINUTES_IN_DAY, 30 * MINUTES_IN_DAY, 60 * MINUTES_IN_DAY + 1],
    startLabels: ['0', '7д', '14д', '30д', '60д'],
    nextLabels: ['7д', '14д', '30д', '60д'],
  },
  {
    key: 'stream-time',
    label: 'Трансляции',
    icon: nominationStream,
    statKey: 'stream_minutes',
    unit: 'minutes',
    levelStarts: [0, Math.round(0.25 * MINUTES_IN_DAY), MINUTES_IN_DAY, 2 * MINUTES_IN_DAY, 5 * MINUTES_IN_DAY + 1],
    startLabels: ['0', '6ч', '1д', '2д', '5д'],
    nextLabels: ['6ч', '1д', '2д', '5д'],
  },
  {
    key: 'spectator-time',
    label: 'Зритель',
    icon: nominationSpectator,
    statKey: 'spectator_minutes',
    unit: 'minutes',
    levelStarts: [0, MINUTES_IN_DAY, 7 * MINUTES_IN_DAY, 14 * MINUTES_IN_DAY, 30 * MINUTES_IN_DAY + 1],
    startLabels: ['0', '1д', '7д', '14д', '30д'],
    nextLabels: ['1д', '7д', '14д', '30д'],
  },
]

const targetUserId = computed(() => {
  const raw = props.userId ?? props.initialProfile?.id ?? 0
  const uid = Number(raw)
  return Number.isFinite(uid) && uid > 0 ? Math.trunc(uid) : 0
})
const initialProfileForTarget = computed<MiniProfileInitial | null>(() => {
  const initial = props.initialProfile
  const initialId = Number(initial?.id || 0)
  if (!initial || !Number.isFinite(initialId) || initialId <= 0) return null
  return Math.trunc(initialId) === targetUserId.value ? initial : null
})
const profileLoadedForTarget = computed(() => Boolean(profile.value && profile.value.id === targetUserId.value))
const viewerUserId = computed(() => Number(userStore.user?.id || 0))
const viewerRole = computed(() => normalizeMiniProfileRole(userStore.user?.role))
const viewerVerificationRestricted = computed(() => Boolean(settingsStore.verificationRestrictions && !userStore.telegramVerified))
const canRenderOpen = computed(() => props.open && !viewerVerificationRestricted.value)
const isSelfProfile = computed(() => targetUserId.value > 0 && viewerUserId.value === targetUserId.value)
const privilegedViewer = computed(() => isMiniProfilePrivilegedViewer(viewerRole.value, props.adminMode))
const initialTargetDeleted = computed(() => {
  const initial = initialProfileForTarget.value
  return Boolean(initial?.deleted || initial?.deleted_at)
})
const targetDeleted = computed(() => Boolean(
  (profileLoadedForTarget.value && profile.value?.deleted)
  || (!profileLoadedForTarget.value && initialTargetDeleted.value)
))

const displayName = computed(() => {
  if (profileLoadedForTarget.value && profile.value?.username) return profile.value.username
  if (initialProfileForTarget.value?.username) return initialProfileForTarget.value.username
  return targetUserId.value > 0 ? `user${targetUserId.value}` : 'Пользователь'
})
const avatarName = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.avatar_name || ''
  return initialProfileForTarget.value?.avatar_name || ''
})
const avatarKey = computed(() => {
  const name = String(avatarName.value || '').trim()
  if (!name) return ''
  return name.startsWith('avatars/') ? name : `avatars/${name}`
})
const hasAvatar = computed(() => Boolean(avatarKey.value))
const profileThemeColor = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.profile_theme_color || null
  const initial = initialProfileForTarget.value
  return initial?.profile_theme_color || initial?.theme_color || null
})
const profileThemeIcon = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.profile_theme_icon || null
  const initial = initialProfileForTarget.value
  return initial?.profile_theme_icon || initial?.theme_icon || null
})
const profileRole = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.role || null
  return initialProfileForTarget.value?.role || null
})
const profilePanelStyle = computed(() => buildProfileThemeBgStyle(profileThemeColor.value))
const profileThemeIconSrcs = computed(() => getProfileThemeBadgeSources(profileThemeIcon.value, profileRole.value))
const activeSanction = computed(() => (profileLoadedForTarget.value ? profile.value?.active_sanction || null : null))
const friendsCount = computed(() => {
  if (!profileLoadedForTarget.value) return null
  const value = Number(profile.value?.friends_count ?? 0)
  return Number.isFinite(value) ? Math.max(0, Math.trunc(value)) : 0
})
const adminFriends = computed(() => (
  profileLoadedForTarget.value && Array.isArray(profile.value?.admin_friends)
    ? profile.value.admin_friends
    : []
))
const nominationStats = computed(() => (
  profileLoadedForTarget.value
    ? profile.value?.nomination_stats || null
    : null
))
const profileNominations = computed<ProfileNomination[]>(() => {
  const stats = nominationStats.value
  if (!stats) return []

  return PROFILE_NOMINATION_DEFINITIONS.map((definition) => buildProfileNomination(definition, stats))
})
const showAdminFriendsTooltip = computed(() => (
  viewerRole.value === 'admin'
  && profileLoadedForTarget.value
  && Array.isArray(profile.value?.admin_friends)
))
const showProfileMeta = computed(() => Boolean(activeSanction.value || targetUserId.value > 0 || friendsCount.value !== null || profileNominations.value.length))
const activeSanctionKindLabel = computed(() => sanctionKindLabel(activeSanction.value?.kind))
const activeSanctionExpiryLabel = computed(() => {
  const expiresAt = activeSanction.value?.expires_at
  const label = formatDateTimeMinute(expiresAt)
  return label !== '-' ? `Истекает ${label}` : 'Бессрочно'
})
const registeredAtLabel = computed(() => formatDateWithMonthName(profile.value?.registered_at))
const lastGameAtLabel = computed(() => {
  const dateLabel = formatDateOnly(profile.value?.last_game_at)
  if (dateLabel === '-') return '-'
  const gameId = Number(profile.value?.last_game_id || 0)
  return Number.isFinite(gameId) && gameId > 0 ? `Игра #${Math.trunc(gameId)} от ${dateLabel}` : dateLabel
})
const lastOnlineLabel = computed(() => formatLastOnline(profile.value?.last_visit_at, Boolean(profile.value?.online)))
const resolvedStatsUrl = computed(() => {
  const provided = String(props.statsUrl || '').trim()
  return provided || `/users/${targetUserId.value}/stats`
})

const friendStatusClass = computed(() => (friendStatus.value === 'self' ? 'none' : friendStatus.value))
const friendActionLabel = computed(() => {
  if (loading.value && !profileLoadedForTarget.value && friendStatus.value === 'none') return 'Загрузка...'
  if (friendStatus.value === 'none') return 'Добавить в друзья'
  if (friendStatus.value === 'friends') return 'В друзьях'
  if (friendStatus.value === 'outgoing') return 'Отменить заявку'
  if (friendStatus.value === 'incoming') return 'Входящий запрос'
  return ''
})
const friendActionIcon = computed(() => {
  if (friendStatus.value === 'friends') return iconInFriends
  if (friendStatus.value === 'outgoing') return iconSendFriends
  if (friendStatus.value === 'incoming') return iconRecieveFriends
  return iconAddFriends
})
const friendActionKind = computed<FriendActionKind>(() => {
  if (friendStatus.value === 'none') return 'add'
  if (friendStatus.value === 'friends') return 'remove'
  if (friendStatus.value === 'outgoing') return 'outgoing'
  return 'incoming'
})
const friendDisabled = computed(() => (
  friendBusy.value
  || friendStatus.value === 'self'
  || targetDeleted.value
  || (loading.value && !profileLoadedForTarget.value && friendStatus.value === 'none')
))
const showFriendAction = computed(() => (
  targetUserId.value > 0
  && !isSelfProfile.value
  && !targetDeleted.value
  && friendActionLabel.value !== ''
))
const showStatsButton = computed(() => Boolean(
  props.showStatsButton
  && targetUserId.value > 0
  && (isSelfProfile.value || privilegedViewer.value || friendStatus.value === 'friends')
))
const showActionBlock = computed(() => showStatsButton.value || showFriendAction.value)
const isAdminViewer = computed(() => viewerRole.value === 'admin')
const isModerViewer = computed(() => viewerRole.value === 'moder')
const staffActionScope = computed<StaffActionScope | null>(() => {
  if (isAdminViewer.value) return 'admin'
  if (isModerViewer.value) return 'moderation'
  return null
})
const targetRoleNormalized = computed(() => normalizeMiniProfileRole(profileRole.value))
const targetUsername = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.username || ''
  return initialProfileForTarget.value?.username || ''
})
const targetProtectedUser = computed(() => Boolean(profileLoadedForTarget.value && profile.value?.protected_user))
const targetSubscriptionActive = computed(() => Boolean(profileLoadedForTarget.value && profile.value?.subscription_active))
const targetTimeoutActive = computed(() => Boolean(profileLoadedForTarget.value && profile.value?.timeout_active))
const targetBanActive = computed(() => Boolean(profileLoadedForTarget.value && profile.value?.ban_active))
const targetSuspendActive = computed(() => Boolean(profileLoadedForTarget.value && profile.value?.suspend_active))
const targetNicknameDefault = computed(() => targetUserId.value > 0 && targetUsername.value === `user_${targetUserId.value}`)
const staffAdminUserActionsLocked = computed(() => targetProtectedUser.value)
const staffAdminDeletedUserActionsLocked = computed(() => staffAdminUserActionsLocked.value || targetDeleted.value)
const staffModerationTargetAllowed = computed(() => targetRoleNormalized.value === 'user' && !targetDeleted.value)
const staffSubscriptionTarget = computed(() => {
  const uid = targetUserId.value
  if (uid <= 0) return null
  return {
    user_id: uid,
    username: targetUsername.value || displayName.value,
    avatar_name: avatarName.value || null,
  }
})
const staffSubscriptionCanSave = computed(() => {
  const months = Number(staffSubscriptionForm.months) || 0
  const days = Number(staffSubscriptionForm.days) || 0
  return Boolean(staffSubscriptionTarget.value && (months > 0 || days > 0))
})
const staffSanctionDurationValid = computed(() => (
  isStaffSanctionDurationPartValid(staffSanctionForm.months, STAFF_SANCTION_DURATION_LIMITS.months)
  && isStaffSanctionDurationPartValid(staffSanctionForm.days, STAFF_SANCTION_DURATION_LIMITS.days)
  && isStaffSanctionDurationPartValid(staffSanctionForm.hours, STAFF_SANCTION_DURATION_LIMITS.hours)
))
const staffSanctionTotalSeconds = computed(() => {
  const months = Math.max(0, Number(staffSanctionForm.months) || 0)
  const days = Math.max(0, Number(staffSanctionForm.days) || 0)
  const hours = Math.max(0, Number(staffSanctionForm.hours) || 0)
  return ((months * 30 * 24 * 60) + (days * 24 * 60) + (hours * 60)) * 60
})
const staffSanctionCanSave = computed(() => {
  if (!staffSanctionForm.reason || !staffSanctionForm.description.trim()) return false
  if (staffSanctionKind.value === 'ban') return isAdminViewer.value
  return staffSanctionDurationValid.value && staffSanctionTotalSeconds.value > 0
})
const staffSanctionTitle = computed(() => {
  const label = displayName.value
  if (staffSanctionKind.value === 'timeout') return `Таймаут: ${label}`
  if (staffSanctionKind.value === 'ban') return `Бан: ${label}`
  return `Отстранение от игр: ${label}`
})
const staffActionItems = computed<StaffActionItem[]>(() => {
  if (!profileLoadedForTarget.value || targetUserId.value <= 0) return []

  const avatarDisabled = staffAvatarBusy.value || !avatarName.value
  const nicknameDisabled = staffNicknameBusy.value || targetNicknameDefault.value
  const suspendDisabled = isStaffSanctionBusy('suspend')
  const timeoutDisabled = isStaffSanctionBusy('timeout')

  if (isAdminViewer.value) {
    return [
      {
        key: 'subscription',
        label: 'Подписка',
        buttonText: 'Выдать',
        buttonClass: 'confirm',
        disabled: staffSubscriptionSaving.value || targetDeleted.value || targetSubscriptionActive.value,
        ariaLabel: `Выдать подписку ${displayName.value}`,
      },
      {
        key: 'role',
        label: 'Модерка',
        icon: targetRoleNormalized.value === 'moder' ? iconClose : iconJudge,
        buttonClass: targetRoleNormalized.value === 'moder' ? 'dark' : 'danger',
        disabled: staffAdminDeletedUserActionsLocked.value || staffRoleBusy.value || targetRoleNormalized.value === 'admin',
        ariaLabel: targetRoleNormalized.value === 'moder' ? `Снять модерку ${displayName.value}` : `Выдать модерку ${displayName.value}`,
      },
      {
        key: 'account',
        label: 'Аккаунт',
        icon: targetDeleted.value ? iconClose : iconJudge,
        buttonClass: targetDeleted.value ? 'dark' : 'danger',
        disabled: staffAdminUserActionsLocked.value || staffAccountBusy.value,
        ariaLabel: targetDeleted.value ? `Восстановить аккаунт ${displayName.value}` : `Удалить аккаунт ${displayName.value}`,
      },
      {
        key: 'avatar',
        label: 'Аватар',
        icon: iconClose,
        buttonClass: avatarName.value ? 'danger' : 'dark',
        disabled: staffAdminDeletedUserActionsLocked.value || avatarDisabled,
        ariaLabel: `Удалить аватар ${displayName.value}`,
      },
      {
        key: 'nickname',
        label: 'Никнейм',
        icon: iconClose,
        buttonClass: targetNicknameDefault.value ? 'dark' : 'danger',
        disabled: staffAdminDeletedUserActionsLocked.value || nicknameDisabled,
        ariaLabel: `Сбросить никнейм ${displayName.value}`,
      },
      {
        key: 'suspend',
        label: 'Отстран.',
        icon: targetSuspendActive.value ? iconClose : iconJudge,
        buttonClass: targetSuspendActive.value ? 'dark' : 'danger',
        disabled: staffAdminDeletedUserActionsLocked.value || suspendDisabled,
        ariaLabel: targetSuspendActive.value ? `Снять отстранение ${displayName.value}` : `Выдать отстранение ${displayName.value}`,
      },
      {
        key: 'timeout',
        label: 'Таймаут',
        icon: targetTimeoutActive.value ? iconClose : iconJudge,
        buttonClass: targetTimeoutActive.value ? 'dark' : 'danger',
        disabled: staffAdminDeletedUserActionsLocked.value || timeoutDisabled,
        ariaLabel: targetTimeoutActive.value ? `Снять таймаут ${displayName.value}` : `Выдать таймаут ${displayName.value}`,
      },
      {
        key: 'ban',
        label: 'Бан',
        icon: targetBanActive.value ? iconClose : iconJudge,
        buttonClass: targetBanActive.value ? 'dark' : 'danger',
        disabled: staffAdminDeletedUserActionsLocked.value || isStaffSanctionBusy('ban'),
        ariaLabel: targetBanActive.value ? `Снять бан ${displayName.value}` : `Выдать бан ${displayName.value}`,
      },
    ]
  }

  if (isModerViewer.value) {
    const moderationLocked = !staffModerationTargetAllowed.value
    return [
      {
        key: 'avatar',
        label: 'Удалить аватар',
        icon: iconClose,
        buttonClass: avatarName.value ? 'danger' : 'dark',
        disabled: moderationLocked || avatarDisabled,
        ariaLabel: `Удалить аватар ${displayName.value}`,
      },
      {
        key: 'nickname',
        label: 'Сбросить никнейм',
        icon: iconClose,
        buttonClass: targetNicknameDefault.value ? 'dark' : 'danger',
        disabled: moderationLocked || nicknameDisabled,
        ariaLabel: `Сбросить никнейм ${displayName.value}`,
      },
      {
        key: 'suspend',
        label: 'Отстранить от игр',
        icon: targetSuspendActive.value ? iconClose : iconJudge,
        buttonClass: targetSuspendActive.value ? 'dark' : 'danger',
        disabled: moderationLocked || suspendDisabled,
        ariaLabel: targetSuspendActive.value ? `Снять отстранение ${displayName.value}` : `Выдать отстранение ${displayName.value}`,
      },
      {
        key: 'timeout',
        label: 'Выдать таймаут',
        icon: targetTimeoutActive.value ? iconClose : iconJudge,
        buttonClass: targetTimeoutActive.value ? 'dark' : 'danger',
        disabled: moderationLocked || timeoutDisabled,
        ariaLabel: targetTimeoutActive.value ? `Снять таймаут ${displayName.value}` : `Выдать таймаут ${displayName.value}`,
      },
    ]
  }

  return []
})
const showStaffActionBlock = computed(() => staffActionItems.value.length > 0)

function safeNonNegativeInt(raw: unknown): number {
  const value = Number(raw)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.trunc(value))
}

function resolveNominationLevel(value: number, levelStarts: readonly [number, number, number, number, number]): NominationLevel {
  if (value >= levelStarts[4]) return 5
  if (value >= levelStarts[3]) return 4
  if (value >= levelStarts[2]) return 3
  if (value >= levelStarts[1]) return 2
  return 1
}

function nominationProgressPct(value: number, level: NominationLevel, levelStarts: readonly [number, number, number, number, number]): number {
  if (level >= 5) return 100
  const progressLevel = level as 1 | 2 | 3 | 4
  const start = levelStarts[progressLevel - 1]
  const next = levelStarts[progressLevel]
  if (next <= start) return 100
  return Math.max(0, Math.min(100, ((value - start) / (next - start)) * 100))
}

function formatNominationCount(raw: unknown): string {
  return nominationIntFmt.format(safeNonNegativeInt(raw))
}

function formatNominationMinutes(raw: unknown): string {
  const totalMinutes = safeNonNegativeInt(raw)
  const days = Math.floor(totalMinutes / MINUTES_IN_DAY)
  const hours = Math.floor((totalMinutes % MINUTES_IN_DAY) / 60)
  const minutes = totalMinutes % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days}д`)
  if (hours > 0) parts.push(`${hours}ч`)
  if (minutes > 0 || parts.length === 0) parts.push(`${minutes}м`)
  return parts.join(' ')
}

function formatNominationValue(value: number, unit: ProfileNominationDefinition['unit']): string {
  return unit === 'minutes' ? formatNominationMinutes(value) : formatNominationCount(value)
}

function buildProfileNomination(definition: ProfileNominationDefinition, stats: MiniProfileNominationStats): ProfileNomination {
  const value = safeNonNegativeInt(stats[definition.statKey])
  const level = resolveNominationLevel(value, definition.levelStarts)
  const levelIndex = level - 1

  return {
    key: definition.key,
    label: definition.label,
    level,
    levelLabel: `${level} ур.`,
    icon: definition.icon,
    valueLabel: formatNominationValue(value, definition.unit),
    progressPct: nominationProgressPct(value, level, definition.levelStarts),
    progressStartLabel: definition.startLabels[levelIndex],
    progressNextLabel: level >= 5 ? 'макс.' : definition.nextLabels[levelIndex],
  }
}

function parseDate(value?: string | number | Date | null): Date | null {
  if (!value) return null
  const dt = value instanceof Date ? value : new Date(value)
  return Number.isNaN(dt.getTime()) ? null : dt
}

function pad2(value: number): string {
  return String(value).padStart(2, '0')
}

const RU_MONTHS_GENITIVE = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
]

function formatDateOnly(value?: string | number | Date | null): string {
  const dt = parseDate(value)
  if (!dt) return '-'
  return `${pad2(dt.getDate())}.${pad2(dt.getMonth() + 1)}.${dt.getFullYear()}`
}

function formatDateWithMonthName(value?: string | number | Date | null): string {
  const dt = parseDate(value)
  if (!dt) return '-'
  return `${dt.getDate()} ${RU_MONTHS_GENITIVE[dt.getMonth()]} ${dt.getFullYear()}`
}

function formatDateTimeMinute(value?: string | number | Date | null): string {
  const dt = parseDate(value)
  if (!dt) return '-'
  return `${formatDateOnly(dt)} ${pad2(dt.getHours())}:${pad2(dt.getMinutes())}`
}

function formatLastOnline(value?: string | number | Date | null, online = false): string {
  if (online) return 'Онлайн'

  const dt = parseDate(value)
  if (!dt) return '-'

  const diffMs = Date.now() - dt.getTime()
  if (diffMs < 0) return 'Только что'

  const totalMinutes = Math.floor(diffMs / 60000)
  const minutesInDay = 24 * 60
  const minutesInMonth = 30 * minutesInDay

  if (totalMinutes < 1) return 'Только что'

  if (totalMinutes < 60) {
    return `${totalMinutes}м назад`
  }

  if (totalMinutes < minutesInDay) {
    const hours = Math.floor(totalMinutes / 60)
    const minutes = totalMinutes % 60
    return `${hours}ч ${minutes}м назад`
  }

  if (totalMinutes < minutesInMonth) {
    const days = Math.floor(totalMinutes / minutesInDay)
    return `${days}д назад`
  }

  return formatDateOnly(dt)
}

function sanctionKindLabel(kind?: string | null): string {
  if (kind === 'suspend') return 'Отстранение от игр'
  if (kind === 'timeout') return 'Таймаут'
  if (kind === 'ban') return 'Бан'
  return 'Санкция'
}

function normalizeFriendStatus(value: unknown): FriendStatus {
  if (value === 'self' || value === 'friends' || value === 'outgoing' || value === 'incoming' || value === 'none') return value
  return 'none'
}

function normalizeAdminFriends(value: unknown): MiniProfileAdminFriend[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const raw = item && typeof item === 'object' ? (item as Record<string, unknown>) : {}
    const id = Number(raw.id || 0)
    return {
      id: Number.isFinite(id) && id > 0 ? Math.trunc(id) : 0,
      username: typeof raw.username === 'string' ? raw.username : null,
      avatar_name: typeof raw.avatar_name === 'string' ? raw.avatar_name : null,
      friendship_started_at: (
        typeof raw.friendship_started_at === 'string' ? raw.friendship_started_at : null
      ),
    }
  }).filter((item) => item.id > 0)
}

function normalizeMiniProfileNominationStats(value: unknown): MiniProfileNominationStats | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  return {
    games_played: safeNonNegativeInt(raw.games_played),
    games_hosted: safeNonNegativeInt(raw.games_hosted),
    room_minutes: safeNonNegativeInt(raw.room_minutes),
    stream_minutes: safeNonNegativeInt(raw.stream_minutes),
    spectator_minutes: safeNonNegativeInt(raw.spectator_minutes),
  }
}

function friendAvatarKey(friend: MiniProfileAdminFriend): string {
  const name = String(friend.avatar_name || '').trim()
  if (!name) return ''
  return name.startsWith('avatars/') ? name : `avatars/${name}`
}

function formatFriendshipStartedAt(value?: string | number | Date | null): string {
  return formatDateOnly(value)
}

function inferInitialFriendStatus(): FriendStatus {
  if (isSelfProfile.value) return 'self'
  const initial = initialProfileForTarget.value
  const direct = normalizeFriendStatus(initial?.friend_status)
  if (direct !== 'none') return direct
  const kind = String(initial?.kind || '')
  if (kind === 'incoming') return 'incoming'
  if (kind === 'outgoing') return 'outgoing'
  if (kind === 'online' || kind === 'offline') return 'friends'
  return 'none'
}

function close() {
  closeAvatarLightbox()
  emit('update:open', false)
}

function closeAvatarLightbox() {
  avatarLightboxOpen.value = false
  avatarLightboxSrc.value = ''
}

function openAvatarLightbox() {
  if (!hasAvatar.value) return
  const src = avatarImageEl.value?.currentSrc || avatarImageEl.value?.src || ''
  if (!src) return
  avatarLightboxSrc.value = src
  avatarLightboxOpen.value = true
}

function isStaffSanctionDurationPartValid(value: number, max: number): boolean {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 0 && parsed <= max
}

function staffSanctionBusyKey(kind: MiniProfileSanctionKind): string {
  return `${targetUserId.value}:${kind}`
}

function isStaffSanctionBusy(kind: MiniProfileSanctionKind): boolean {
  return Boolean(staffSanctionBusy[staffSanctionBusyKey(kind)])
}

function setStaffSanctionBusy(kind: MiniProfileSanctionKind, value: boolean): void {
  staffSanctionBusy[staffSanctionBusyKey(kind)] = value
}

function staffActionDisabled(key: StaffActionKey): boolean {
  return Boolean(staffActionItems.value.find(item => item.key === key)?.disabled ?? true)
}

function staffApiPrefix(): string {
  const scope = staffActionScope.value
  return scope ? `/${scope}` : ''
}

function currentTargetLabel(): string {
  return targetUsername.value || (targetUserId.value > 0 ? `#${targetUserId.value}` : displayName.value)
}

function patchProfile(values: Partial<MiniProfileResponse>): void {
  if (!profileLoadedForTarget.value || !profile.value) return
  Object.assign(profile.value, values)
}

function emitStaffActionComplete(action: StaffActionKey | 'sanction'): void {
  if (targetUserId.value <= 0) return
  emit('staff-action-complete', { userId: targetUserId.value, action })
}

function resetStaffSanctionForm(): void {
  staffSanctionForm.months = 0
  staffSanctionForm.days = 0
  staffSanctionForm.hours = 0
  staffSanctionForm.reason = DEFAULT_SANCTION_REASON
  staffSanctionForm.description = ''
}

function closeStaffSanctionModal(): void {
  if (staffSanctionSaving.value) return
  staffSanctionModalOpen.value = false
  resetStaffSanctionForm()
}

function onStaffSanctionModalOpenUpdate(open: boolean): void {
  if (open) return
  closeStaffSanctionModal()
}

function resetStaffSubscriptionForm(): void {
  staffSubscriptionForm.months = 0
  staffSubscriptionForm.days = 0
}

function closeStaffSubscriptionModal(): void {
  if (staffSubscriptionSaving.value) return
  staffSubscriptionModalOpen.value = false
  resetStaffSubscriptionForm()
}

function onStaffSubscriptionModalOpenUpdate(open: boolean): void {
  if (open) return
  closeStaffSubscriptionModal()
}

function openStaffSubscription(): void {
  if (!isAdminViewer.value || staffActionDisabled('subscription')) return
  resetStaffSubscriptionForm()
  staffSubscriptionModalOpen.value = true
}

function openStaffSanction(kind: MiniProfileSanctionKind): void {
  if (kind === 'ban' && !isAdminViewer.value) return
  if (staffActionDisabled(kind)) return
  staffSanctionKind.value = kind
  resetStaffSanctionForm()
  staffSanctionModalOpen.value = true
}

async function saveStaffSubscription(): Promise<void> {
  if (!isAdminViewer.value || staffSubscriptionSaving.value || !staffSubscriptionCanSave.value) return
  const uid = targetUserId.value
  if (uid <= 0) return
  const hadActiveSubscription = targetSubscriptionActive.value
  staffSubscriptionSaving.value = true
  try {
    await api.post('/admin/subscriptions', {
      user_id: uid,
      months: Math.max(0, Math.trunc(Number(staffSubscriptionForm.months) || 0)),
      days: Math.max(0, Math.trunc(Number(staffSubscriptionForm.days) || 0)),
    })
    staffSubscriptionModalOpen.value = false
    resetStaffSubscriptionForm()
    patchProfile({ subscription_active: true })
    emitStaffActionComplete('subscription')
    void alertDialog(hadActiveSubscription ? 'Подписка продлена' : 'Подписка выдана')
    void loadProfile()
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 404 && d === 'user_not_found') void alertDialog('Пользователь не найден')
    else if (st === 422 && d === 'duration_required') void alertDialog('Укажите срок подписки')
    else void alertDialog('Не удалось сохранить подписку')
  } finally {
    staffSubscriptionSaving.value = false
  }
}

async function toggleStaffRole(): Promise<void> {
  if (!isAdminViewer.value || staffActionDisabled('role')) return
  const uid = targetUserId.value
  if (uid <= 0 || staffRoleBusy.value) return
  const isModer = targetRoleNormalized.value === 'moder'
  const targetRole = isModer ? 'user' : 'moder'
  const userLabel = currentTargetLabel()
  const ok = await confirmDialog({
    title: isModer ? 'Снять MODER' : 'Выдать MODER',
    text: `${isModer ? 'Снять' : 'Выдать'} права модератора пользователю ${userLabel}?`,
    confirmText: isModer ? 'Снять' : 'Выдать',
    cancelText: 'Отмена',
  })
  if (!ok) return
  staffRoleBusy.value = true
  try {
    const { data } = await api.patch(`/admin/users/${uid}/role`, { role: targetRole })
    patchProfile({ role: data?.role || targetRole })
    emitStaffActionComplete('role')
  } catch (e: any) {
    const d = e?.response?.data?.detail
    if (d === 'protected_user') void alertDialog('Пользователь защищен от админ-действий')
    else if (d === 'user_deleted') void alertDialog('Аккаунт удален')
    else if (d === 'admin_role_locked') void alertDialog('Нельзя изменить роль администратора')
    else void alertDialog('Не удалось обновить роль пользователя')
  } finally {
    staffRoleBusy.value = false
  }
}

async function toggleStaffAccount(): Promise<void> {
  if (!isAdminViewer.value || staffActionDisabled('account')) return
  const uid = targetUserId.value
  if (uid <= 0 || staffAccountBusy.value) return
  const isDeleted = targetDeleted.value
  const userLabel = currentTargetLabel()
  const ok = await confirmDialog({
    title: isDeleted ? 'Восстановить аккаунт' : 'Удалить аккаунт',
    text: isDeleted
      ? `Восстановить доступ для ${userLabel}?`
      : `Удаление аккаунта ${userLabel} произойдет навсегда без возможности восстановления.`,
    confirmText: isDeleted ? 'Восстановить' : 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  staffAccountBusy.value = true
  try {
    await api.post(`/admin/users/${uid}/${isDeleted ? 'restore' : 'delete'}`)
    patchProfile({ deleted: !isDeleted })
    emitStaffActionComplete('account')
  } catch (e: any) {
    const d = e?.response?.data?.detail
    if (d === 'protected_user') void alertDialog('Пользователь защищен от админ-действий')
    else void alertDialog(isDeleted ? 'Не удалось восстановить аккаунт' : 'Не удалось удалить аккаунт')
  } finally {
    staffAccountBusy.value = false
  }
}

async function deleteStaffAvatar(): Promise<void> {
  if (staffActionDisabled('avatar')) return
  const prefix = staffApiPrefix()
  const uid = targetUserId.value
  if (!prefix || uid <= 0 || staffAvatarBusy.value) return
  const userLabel = currentTargetLabel()
  const ok = await confirmDialog({
    title: 'Удалить аватар',
    text: `Удалить аватар у ${userLabel}?`,
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  staffAvatarBusy.value = true
  try {
    await api.post(`${prefix}/users/${uid}/avatar_delete`)
    patchProfile({ avatar_name: null })
    emitStaffActionComplete('avatar')
    void alertDialog('Аватар удален')
  } catch (e: any) {
    const d = e?.response?.data?.detail
    if (d === 'forbidden') void alertDialog('Нельзя удалить аватар этого пользователя')
    else if (d === 'protected_user') void alertDialog('Пользователь защищен от админ-действий')
    else void alertDialog('Не удалось удалить аватар')
  } finally {
    staffAvatarBusy.value = false
  }
}

async function resetStaffNickname(): Promise<void> {
  if (staffActionDisabled('nickname')) return
  const prefix = staffApiPrefix()
  const uid = targetUserId.value
  if (!prefix || uid <= 0 || staffNicknameBusy.value) return
  const userLabel = currentTargetLabel()
  const ok = await confirmDialog({
    title: 'Сбросить никнейм',
    text: `Сбросить никнейм ${userLabel} на user_${uid}?`,
    confirmText: 'Сбросить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  staffNicknameBusy.value = true
  try {
    const { data } = await api.post(`${prefix}/users/${uid}/nickname_reset`)
    patchProfile({ username: data?.username || `user_${uid}` })
    resetNicknameHistory()
    emitStaffActionComplete('nickname')
    void alertDialog('Никнейм сброшен')
  } catch (e: any) {
    const d = e?.response?.data?.detail
    if (e?.response?.status === 409 && d === 'username_taken') void alertDialog('Не удалось сбросить никнейм: имя уже занято')
    else if (d === 'forbidden') void alertDialog('Нельзя сбросить никнейм этого пользователя')
    else if (d === 'protected_user') void alertDialog('Пользователь защищен от админ-действий')
    else void alertDialog('Не удалось сбросить никнейм')
  } finally {
    staffNicknameBusy.value = false
  }
}

async function saveStaffSanction(): Promise<void> {
  const kind = staffSanctionKind.value
  if (staffSanctionSaving.value || !staffSanctionCanSave.value || staffActionDisabled(kind)) return
  const prefix = staffApiPrefix()
  const uid = targetUserId.value
  if (!prefix || uid <= 0 || (kind === 'ban' && !isAdminViewer.value)) return
  staffSanctionSaving.value = true
  setStaffSanctionBusy(kind, true)
  const payload = kind === 'ban'
    ? { reason: staffSanctionForm.reason, description: staffSanctionForm.description.trim() }
    : {
      months: staffSanctionForm.months,
      days: staffSanctionForm.days,
      hours: staffSanctionForm.hours,
      reason: staffSanctionForm.reason,
      description: staffSanctionForm.description.trim(),
    }
  try {
    await api.post(`${prefix}/users/${uid}/${kind}`, payload)
    staffSanctionModalOpen.value = false
    resetStaffSanctionForm()
    emitStaffActionComplete('sanction')
    void alertDialog(kind === 'timeout' ? 'Таймаут выдан' : kind === 'ban' ? 'Бан выдан' : 'Отстранение выдано')
    await loadProfile()
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 409 && d === 'sanction_active') void alertDialog('Санкция уже активна')
    else if (st === 422 && d === 'duration_required') void alertDialog('Укажите срок санкции')
    else if (d === 'forbidden') void alertDialog('Нельзя применить санкцию к этому пользователю')
    else if (d === 'protected_user') void alertDialog('Пользователь защищен от админ-действий')
    else void alertDialog(kind === 'timeout' ? 'Не удалось выдать таймаут' : kind === 'ban' ? 'Не удалось выдать бан' : 'Не удалось выдать отстранение')
  } finally {
    setStaffSanctionBusy(kind, false)
    staffSanctionSaving.value = false
  }
}

async function revokeStaffSanction(kind: MiniProfileSanctionKind): Promise<void> {
  if (staffActionDisabled(kind)) return
  const prefix = staffApiPrefix()
  const uid = targetUserId.value
  if (!prefix || uid <= 0 || isStaffSanctionBusy(kind) || (kind === 'ban' && !isAdminViewer.value)) return
  const userLabel = currentTargetLabel()
  const title = kind === 'ban' ? 'Разбанить' : kind === 'timeout' ? 'Снять таймаут' : 'Снять отстранение'
  const text = kind === 'ban'
    ? `Разбанить ${userLabel}?`
    : kind === 'timeout'
      ? `Снять таймаут у ${userLabel}?`
      : `Снять отстранение у ${userLabel}?`
  const ok = await confirmDialog({
    title,
    text,
    confirmText: title,
    cancelText: 'Отмена',
  })
  if (!ok) return
  setStaffSanctionBusy(kind, true)
  try {
    await api.delete(`${prefix}/users/${uid}/${kind}`)
    emitStaffActionComplete('sanction')
    void alertDialog(kind === 'ban' ? 'Бан снят' : kind === 'timeout' ? 'Таймаут снят' : 'Отстранение снято')
    await loadProfile()
  } catch (e: any) {
    const d = e?.response?.data?.detail
    if (d === 'sanction_not_found') void alertDialog('Санкция не найдена')
    else if (d === 'forbidden') void alertDialog('Нельзя снять санкцию этого пользователя')
    else if (d === 'protected_user') void alertDialog('Пользователь защищен от админ-действий')
    else void alertDialog(kind === 'ban' ? 'Не удалось снять бан' : kind === 'timeout' ? 'Не удалось снять таймаут' : 'Не удалось снять отстранение')
  } finally {
    setStaffSanctionBusy(kind, false)
  }
}

async function toggleStaffSanction(kind: MiniProfileSanctionKind): Promise<void> {
  if ((kind === 'timeout' && targetTimeoutActive.value)
    || (kind === 'ban' && targetBanActive.value)
    || (kind === 'suspend' && targetSuspendActive.value)) {
    await revokeStaffSanction(kind)
    return
  }
  openStaffSanction(kind)
}

function onStaffAction(key: StaffActionKey): void {
  if (staffActionDisabled(key)) return
  if (key === 'subscription') {
    openStaffSubscription()
    return
  }
  if (key === 'role') {
    void toggleStaffRole()
    return
  }
  if (key === 'account') {
    void toggleStaffAccount()
    return
  }
  if (key === 'avatar') {
    void deleteStaffAvatar()
    return
  }
  if (key === 'nickname') {
    void resetStaffNickname()
    return
  }
  void toggleStaffSanction(key)
}

function resetStaffActionState(): void {
  staffRoleBusy.value = false
  staffAccountBusy.value = false
  staffAvatarBusy.value = false
  staffNicknameBusy.value = false
  for (const key of Object.keys(staffSanctionBusy)) delete staffSanctionBusy[key]
  staffSanctionSaving.value = false
  staffSanctionModalOpen.value = false
  resetStaffSanctionForm()
  staffSubscriptionSaving.value = false
  staffSubscriptionModalOpen.value = false
  resetStaffSubscriptionForm()
}

function applyFriendStatus(status: FriendStatus) {
  friendStatus.value = status
  if (targetUserId.value > 0) emit('friend-status-change', targetUserId.value, status)
}

function adjustProfileFriendsCount(delta: number) {
  if (!profileLoadedForTarget.value || !profile.value) return
  const current = Number(profile.value.friends_count ?? 0)
  profile.value.friends_count = Math.max(0, Math.trunc((Number.isFinite(current) ? current : 0) + delta))
}

async function refreshFriendStatus() {
  const uid = targetUserId.value
  if (uid <= 0 || uid === viewerUserId.value) {
    applyFriendStatus('self')
    return
  }

  try {
    applyFriendStatus(await friends.fetchStatus(uid))
  } catch {}
}

async function refreshFriendsListIfNeeded() {
  if (!props.refreshFriendsListOnAction) return
  await friends.fetchList(props.refreshFriendsRoomId)
  await friends.fetchIncomingCount()
}

async function loadProfile() {
  const uid = targetUserId.value
  if (uid <= 0) return

  const seq = ++requestSeq
  loading.value = true
  loadError.value = ''
  try {
    const reqConfig = props.allowDeleted ? { params: { allow_deleted: 1 } } : undefined
    const { data } = await api.get<MiniProfileResponse>(`/users/${uid}/mini_profile`, reqConfig)
    if (seq !== requestSeq) return
    profile.value = {
      id: Number(data?.id || uid),
      username: data?.username ?? null,
      avatar_name: data?.avatar_name ?? null,
      role: data?.role ?? null,
      protected_user: Boolean(data?.protected_user),
      deleted: Boolean(data?.deleted),
      registered_at: data?.registered_at ?? null,
      last_visit_at: data?.last_visit_at ?? null,
      last_game_at: data?.last_game_at ?? null,
      last_game_id: Number.isFinite(Number(data?.last_game_id)) ? Math.trunc(Number(data?.last_game_id)) : null,
      online: Boolean(data?.online),
      subscription_active: Boolean(data?.subscription_active),
      timeout_active: Boolean(data?.timeout_active),
      timeout_until: data?.timeout_until ?? null,
      ban_active: Boolean(data?.ban_active),
      suspend_active: Boolean(data?.suspend_active),
      suspend_until: data?.suspend_until ?? null,
      profile_theme_color: data?.profile_theme_color ?? null,
      profile_theme_icon: data?.profile_theme_icon ?? null,
      friend_status: normalizeFriendStatus(data?.friend_status),
      friends_count: Number.isFinite(Number(data?.friends_count)) ? Math.max(0, Math.trunc(Number(data?.friends_count))) : 0,
      admin_friends: (
        Array.isArray(data?.admin_friends) ? normalizeAdminFriends(data.admin_friends) : null
      ),
      active_sanction: data?.active_sanction ?? null,
      nomination_stats: normalizeMiniProfileNominationStats(data?.nomination_stats),
    }
    applyFriendStatus(normalizeFriendStatus(data?.friend_status))
  } catch {
    if (seq !== requestSeq) return
    loadError.value = 'Не удалось загрузить профиль'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function resetNicknameHistory() {
  nicknameHistorySeq += 1
  nicknameHistoryLoading.value = false
  nicknameHistoryError.value = ''
  nicknameHistoryItems.value = []
  nicknameHistoryLoadedForTarget.value = 0
}

async function loadNicknameHistory() {
  const uid = targetUserId.value
  if (uid <= 0 || nicknameHistoryLoading.value || nicknameHistoryLoadedForTarget.value === uid) return

  const seq = ++nicknameHistorySeq
  nicknameHistoryLoading.value = true
  nicknameHistoryError.value = ''
  try {
    const reqConfig = props.allowDeleted ? { params: { allow_deleted: 1 } } : undefined
    const { data } = await api.get<NicknameHistoryResponse>(`/users/${uid}/nickname_history`, reqConfig)
    if (seq !== nicknameHistorySeq) return
    nicknameHistoryItems.value = Array.isArray(data?.items)
      ? data.items.map((item) => String(item || '').trim()).filter(Boolean)
      : []
    nicknameHistoryLoadedForTarget.value = uid
  } catch {
    if (seq !== nicknameHistorySeq) return
    nicknameHistoryError.value = 'Не удалось загрузить историю'
  } finally {
    if (seq === nicknameHistorySeq) nicknameHistoryLoading.value = false
  }
}

async function onFriendAction(kind: FriendActionKind) {
  const uid = targetUserId.value
  if (uid <= 0 || friendBusy.value) return

  friendBusy.value = true
  let actionForError: FriendApiAction = 'unknown'
  try {
    if (kind === 'add') {
      actionForError = 'send'
      await friends.sendRequest(uid)
      applyFriendStatus('outgoing')
    } else if (kind === 'remove') {
      const ok = await confirmDialog({
        title: 'Удалить из друзей',
        text: 'Вы уверены, что хотите удалить пользователя из друзей?',
        confirmText: 'Удалить',
        cancelText: 'Отмена',
      })
      if (!ok) return
      actionForError = 'remove'
      await friends.removeFriend(uid)
      applyFriendStatus('none')
      adjustProfileFriendsCount(-1)
    } else if (kind === 'outgoing') {
      const ok = await confirmDialog({
        title: 'Отменить заявку',
        text: `Вы уверены, что хотите отменить заявку в друзья для пользователя ${displayName.value}?`,
        confirmText: 'Отменить',
        cancelText: 'Отмена',
      })
      if (!ok) return
      actionForError = 'cancel'
      await friends.cancelOutgoingRequest(uid)
      applyFriendStatus('none')
    } else if (kind === 'incoming') {
      const ok = await confirmDialog({
        title: 'Запрос в друзья',
        text: 'Принять запрос в друзья?',
        confirmText: 'Принять',
        cancelText: 'Отклонить',
      })
      if (ok) {
        actionForError = 'accept'
        await friends.acceptRequest(uid)
        applyFriendStatus('friends')
        adjustProfileFriendsCount(1)
      } else {
        actionForError = 'decline'
        await friends.declineRequest(uid)
        applyFriendStatus('none')
      }
    }
    await refreshFriendsListIfNeeded()
  } catch (e: any) {
    if (shouldRefreshFriendsStateAfterError(e)) void refreshFriendStatus()
    void alertDialog(resolveFriendsApiError(e, actionForError))
  } finally {
    friendBusy.value = false
  }
}

function onKeydown(e: KeyboardEvent) {
  if (!props.open || e.key !== 'Escape') return
  if (avatarLightboxOpen.value) {
    closeAvatarLightbox()
    return
  }
  close()
}

function onFriendsUpdate(e: Event) {
  const detail = (e as CustomEvent)?.detail || {}
  const uid = Number(detail.user_id)
  if (!props.open || uid !== targetUserId.value) return
  const previousStatus = friendStatus.value
  const nextStatus = normalizeFriendStatus(detail.status)
  applyFriendStatus(nextStatus)
  if (previousStatus !== 'friends' && nextStatus === 'friends') adjustProfileFriendsCount(1)
  if (previousStatus === 'friends' && nextStatus !== 'friends') adjustProfileFriendsCount(-1)
}

watch([() => props.open, targetUserId, viewerVerificationRestricted], ([open, uid, restricted]) => {
  if (!open) {
    requestSeq += 1
    loading.value = false
    loadError.value = ''
    view.value = 'profile'
    closeAvatarLightbox()
    resetNicknameHistory()
    resetStaffActionState()
    return
  }

  if (restricted) {
    emit('update:open', false)
    return
  }

  profile.value = null
  view.value = 'profile'
  loadError.value = ''
  closeAvatarLightbox()
  resetNicknameHistory()
  resetStaffActionState()
  applyFriendStatus(inferInitialFriendStatus())
  if (uid > 0) void loadProfile()
}, { immediate: true })

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('auth-friends_update', onFriendsUpdate)
})

onBeforeUnmount(() => {
  resetNicknameHistory()
  resetStaffActionState()
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('auth-friends_update', onFriendsUpdate)
})
</script>

<style scoped lang="scss">
.user-mini-profile-overlay {
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($black, 0.5);
  backdrop-filter: blur(5px);
  z-index: 1500;
  .user-mini-profile-panel {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 20px;
    gap: 20px;
    width: 500px;
    height: min-content;
    border-radius: 10px;
    background-color: var(--user-theme-bg, $dark);
    overflow-y: auto;
    scrollbar-width: none;
    transition: width 0.25s ease-in-out, height 0.25s ease-in-out;
    &.stats-mode {
      gap: 20px;
      width: min(1250px, calc(100vw - 80px));
      height: calc(100dvh - 80px);
    }
    .profile-top {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      .profile-identity {
        display: flex;
        align-items: flex-start;
        min-width: 0;
        gap: 10px;
        .profile-avatar-trigger {
          display: flex;
          position: relative;
          flex: 0 0 auto;
          align-items: center;
          justify-content: center;
          padding: 0;
          border: none;
          border-radius: 50%;
          background: transparent;
          cursor: zoom-in;
          &:disabled {
            cursor: default;
          }
          .profile-avatar {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            object-fit: cover;
          }
        }
        .profile-icon-name {
          display: flex;
          flex-direction: column;
          min-width: 0;
          padding: 5px 10px 10px;
          gap: 5px;
          border-radius: 10px;
          background-color: rgba($graphite, 0.5);
          box-shadow: 3px 3px 5px rgba($black, 0.25);
          .profile-title {
            display: flex;
            min-width: 0;
            height: 30px;
            gap: 5px;
            .profile-theme-icons {
              display: inline-flex;
              flex: 0 0 auto;
              align-items: center;
              gap: 5px;
              .profile-theme-icon {
                width: 24px;
                height: 24px;
                object-fit: contain;
              }
            }
            .profile-name {
              max-width: 280px;
              font-size: 22px;
              line-height: 1.3;
              font-family: Manrope-SemiBold;
              white-space: nowrap;
              overflow: hidden;
              text-overflow: ellipsis;
            }
          }
          .profile-meta {
            display: flex;
            align-items: center;
            gap: 5px;
            .profile-tooltip-wrap {
              display: inline-flex;
              position: relative;
              flex: 0 0 auto;
              align-items: center;
              justify-content: center;
              outline: none;
              &:hover,
              &:focus-within {
                &::after {
                  opacity: 1;
                  pointer-events: auto;
                }
                .profile-tooltip {
                  opacity: 1;
                  visibility: visible;
                  pointer-events: auto;
                  transform: translateX(-50%) translateY(0);
                }
              }
              &::after {
                content: '';
                position: absolute;
                top: 100%;
                left: 50%;
                width: max(100%, 100px);
                height: 10px;
                transform: translateX(-50%);
                opacity: 0;
                pointer-events: none;
                z-index: 2;
              }
              .profile-tooltip {
                display: flex;
                position: absolute;
                top: calc(100% + 10px);
                left: 50%;
                flex-direction: column;
                padding: 10px;
                border-radius: 5px;
                background-color: $graphite;
                box-shadow: 3px 3px 5px rgba($black, 0.25);
                color: $fg;
                line-height: 1.2;
                opacity: 0;
                visibility: hidden;
                pointer-events: none;
                transform: translateX(-50%) translateY(5px);
                transition:
                  opacity 0.25s ease-in-out,
                  visibility 0.25s ease-in-out,
                  transform 0.25s ease-in-out;
                z-index: 3;
              }
            }
            .profile-friends-tooltip-wrap {
              &.enabled {
                cursor: default;
              }
              &:hover,
              &:focus-within {
                .profile-friends-tooltip {
                  transform: translateX(0) translateY(0);
                }
              }
              .profile-friends-count {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 5px 10px;
                border-radius: 5px;
                background-color: rgba($graphite, 0.5);
                color: $fg;
                font-size: 14px;
                line-height: 1;
                font-family: Manrope-SemiBold;
              }
              .profile-friends-tooltip {
                left: 0;
                top: calc(100% + 10px);
                width: max-content;
                max-height: 200px;
                overflow-y: auto;
                scrollbar-width: thin;
                font-size: 13px;
                transform: translateX(0) translateY(5px);
                .profile-friends-empty {
                  color: $ashy;
                }
                .profile-friends-list {
                  display: flex;
                  flex-direction: column;
                  gap: 5px;
                  .profile-friend-row {
                    display: flex;
                    align-items: center;
                    gap: 5px;
                    min-width: 0;
                    .profile-friend-avatar {
                      flex: 0 0 auto;
                      width: 30px;
                      height: 30px;
                      border-radius: 50%;
                      object-fit: cover;
                    }
                    .profile-friend-main {
                      display: flex;
                      flex-direction: column;
                      min-width: 0;
                      gap: 1px;
                      .profile-friend-name {
                        color: $fg;
                        font-family: Manrope-SemiBold;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        white-space: nowrap;
                      }
                      .profile-friend-date {
                        color: $ashy;
                        font-size: 12px;
                      }
                    }
                  }
                }
              }
            }
            .profile-nomination-tooltip-wrap {
              &.level-1 {
                .profile-nomination-icon-shell,
                .nomination-level-badge {
                  background: linear-gradient(135deg, rgba($bg, 0.5) 0%, rgba($graphite, 0.5) 100%);
                }
              }
              &.level-2 {
                .profile-nomination-icon-shell,
                .nomination-level-badge {
                  background: linear-gradient(135deg, rgba(200, 75, 0, 0.5) 0%, rgba(225, 150, 75, 0.5) 100%);
                }
              }
              &.level-3 {
                .profile-nomination-icon-shell,
                .nomination-level-badge {
                  background: linear-gradient(135deg, rgba(125, 125, 125, 0.5) 0%, rgba(200, 200, 200, 0.5) 100%);
                }
              }
              &.level-4 {
                .profile-nomination-icon-shell,
                .nomination-level-badge {
                  background: linear-gradient(135deg, rgba(200, 150, 25, 0.5) 0%, rgba(255, 255, 50, 0.5) 100%);
                }
              }
              &.level-5 {
                .profile-nomination-icon-shell,
                .nomination-level-badge {
                  background: linear-gradient(135deg, rgba(0, 255, 200, 0.5) 0%, rgba(150, 100, 255, 0.5) 100%);
                }
              }
              .profile-nomination-icon-shell {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 24px;
                height: 24px;
                border-radius: 5px;
              }
              .profile-nomination-icon {
                width: 18px;
                height: 18px;
                object-fit: contain;
              }
              .profile-nomination-tooltip {
                top: calc(100% + 10px);
                gap: 10px;
                width: 200px;
                font-size: 12px;
                .nomination-tooltip-head,
                .nomination-progress-caption {
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  gap: 10px;
                  font-size: 14px;
                  min-width: 0;
                  span,
                  strong {
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                  }
                  strong {
                    font-family: Manrope-SemiBold;
                    font-weight: normal;
                  }
                }
                .nomination-level-badge {
                  display: inline-flex;
                  align-items: center;
                  justify-content: center;
                  padding: 3px 8px;
                  border-radius: 999px;
                  color: $fg;
                  font-size: 12px;
                  line-height: 1;
                  font-family: Manrope-SemiBold;
                  white-space: nowrap;
                }
                .nomination-progress-caption {
                  margin-bottom: -5px;
                  color: $ashy;
                  font-size: 12px;
                }
                .nomination-progress-track {
                  display: block;
                  position: relative;
                  width: 100%;
                  height: 24px;
                  overflow: hidden;
                  border-radius: 999px;
                  background-color: $dark;
                }
                .nomination-progress-fill {
                  position: absolute;
                  top: 0;
                  left: 0;
                  height: 100%;
                  border-radius: inherit;
                  background: linear-gradient(90deg, $lead 0%, $grey 100%);
                }
                .nomination-progress-value {
                  display: flex;
                  position: absolute;
                  align-items: center;
                  justify-content: center;
                  inset: 0;
                  padding: 0 5px;
                  color: $fg;
                  font-size: 12px;
                  font-family: Manrope-SemiBold;
                  line-height: 1;
                  white-space: nowrap;
                }
              }
            }
            .sanction-tooltip-wrap {
              .profile-meta-icon {
                width: 22px;
                height: 22px;
                object-fit: contain;
              }
              .sanction-tooltip {
                top: calc(100% + 10px);
                width: max-content;
                font-size: 12px;
                strong {
                  font-family: Manrope-SemiBold;
                  font-weight: normal;
                }
              }
            }
            .profile-history-tooltip-wrap {
              .profile-meta-icon {
                width: 22px;
                height: 22px;
                object-fit: contain;
              }
              .nickname-history-tooltip {
                top: calc(100% + 10px);
                width: max-content;
                max-height: 200px;
                overflow-y: auto;
                scrollbar-width: thin;
                font-size: 14px;
                .nickname-history-list {
                  display: flex;
                  flex-direction: column;
                  gap: 5px;
                  span {
                    color: $ashy;
                    overflow-wrap: anywhere;
                    &.current {
                      color: $fg;
                      font-family: Manrope-SemiBold;
                    }
                  }
                }
                .nickname-history-state {
                  color: $ashy;
                  &.danger {
                    color: $red;
                  }
                }
              }
            }
          }
        }
      }
      .profile-side-tools {
        display: flex;
        flex: 0 0 auto;
        flex-direction: column;
        align-items: flex-end;
        .close-button {
          display: flex;
          flex: 0 0 auto;
          align-items: center;
          justify-content: center;
          padding: 0;
          width: 30px;
          height: 30px;
          border: none;
          border-radius: 5px;
          background-color: $graphite;
          box-shadow: 3px 3px 5px rgba($black, 0.25);
          cursor: pointer;
          transition: background-color 0.25s ease-in-out;
          &:hover {
            background-color: $lead;
          }
          img {
            width: 20px;
            height: 20px;
          }
        }
      }
    }
    .state {
      margin: 0;
      color: $ashy;
      text-align: center;
      font-size: 16px;
      &.state-danger {
        color: $red;
      }
    }
    .profile-dates {
      display: flex;
      flex-direction: column;
      gap: 10px;
      .date-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px;
        border-radius: 5px;
        background-color: rgba($graphite, 0.5);
        box-shadow: 3px 3px 5px rgba($black, 0.25);
        span {
          color: $fg;
          font-size: 14px;
        }
        strong {
          color: $fg;
          text-align: right;
          font-size: 14px;
          font-family: Manrope-SemiBold;
          font-weight: normal;
        }
      }
    }
    .profile-actions,
    .stats-toolbar {
      display: flex;
      flex-direction: column;
      gap: 10px;
      .profile-action {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 5px;
        min-height: 40px;
        border: none;
        border-radius: 5px;
        box-shadow: 3px 3px 5px rgba($black, 0.25);
        color: $bg;
        font-size: 16px;
        font-family: Manrope-SemiBold;
        cursor: pointer;
        transition: background-color 0.25s ease-in-out, opacity 0.25s ease-in-out;
        &:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        img {
          width: 24px;
          height: 24px;
        }
        &.secondary {
          background-color: $fg;
          &:not(:disabled):hover {
            background-color: $white;
          }
        }
        &.status-none {
          background-color: $fg;
          &:not(:disabled):hover {
            background-color: $white;
          }
        }
        &.status-friends {
          background-color: rgba($green, 0.75);
          &:not(:disabled):hover {
            background-color: $green;
          }
        }
        &.status-outgoing {
          background-color: rgba($yellow, 0.75);
          &:not(:disabled):hover {
            background-color: $yellow;
          }
        }
        &.status-incoming {
          background-color: rgba($orange, 0.75);
          &:not(:disabled):hover {
            background-color: $orange;
          }
        }
      }
    }
    .profile-staff-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      .staff-action-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 5px;
      }
      .staff-action-label {
        color: $fg;
        text-align: center;
        font-size: 12px;
        line-height: 1.2;
        overflow-wrap: anywhere;
      }
      .btn {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 12px;
        gap: 5px;
        min-width: 54px;
        height: 40px;
        border: none;
        border-radius: 5px;
        background-color: $fg;
        color: $bg;
        font-size: 14px;
        font-family: Manrope-Medium;
        line-height: 1;
        text-decoration: none;
        cursor: pointer;
        transition: opacity 0.25s ease-in-out, color 0.25s ease-in-out, border-radius 0.25s ease-in-out, background-color 0.25s ease-in-out;
        &:hover {
          background-color: $white;
        }
        &.dark {
          background-color: $lead;
          color: $fg;
          &:hover {
            background-color: rgba($grey, 0.5);
          }
        }
        &.confirm {
          background-color: rgba($green, 0.75);
          &:hover {
            background-color: $green;
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
    }
  }
}
.avatar-lightbox-overlay {
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  overflow: hidden;
  background:
    radial-gradient(circle at top, rgba($white, 0.1) 0%, rgba($white, 0) 100%),
    rgba($black, 0.25);
  backdrop-filter: blur(15px);
  z-index: 1600;
  &::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: min(75vw, 75vh, 750px);
    height: min(75vw, 75vh, 750px);
    border-radius: 50%;
    background: radial-gradient(circle, rgba($white, 0.25) 0%, rgba($white, 0.1) 25%, rgba($white, 0) 75%);
    transform: translate(-50%, -50%);
    z-index: 0;
  }
  .avatar-lightbox-image {
    position: relative;
    z-index: 1;
    width: min(75vw, 75vh, 750px);
    height: min(75vw, 75vh, 750px);
    object-fit: cover;
  }
}

.user-mini-profile-fade-enter-active,
.user-mini-profile-fade-leave-active {
  transition: opacity 0.25s ease-in-out;
  .user-mini-profile-panel {
    transition: transform 0.25s ease-in-out;
  }
}
.user-mini-profile-fade-enter-from,
.user-mini-profile-fade-leave-to {
  opacity: 0;
  .user-mini-profile-panel {
    transform: translateY(10px) scale(0.9);
  }
}

.avatar-lightbox-transition-enter-active,
.avatar-lightbox-transition-leave-active {
  transition: opacity 0.25s ease-in-out;
  .avatar-lightbox-image {
    transition: transform 0.25s ease-in-out, opacity 0.25s ease-in-out;
  }
}
.avatar-lightbox-transition-enter-from,
.avatar-lightbox-transition-leave-to {
  opacity: 0;
  .avatar-lightbox-image {
    opacity: 0;
    transform: translateY(10px) scale(0.9);
  }
}

</style>
