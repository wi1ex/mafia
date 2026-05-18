<template>
  <Teleport to="body">
    <Transition name="user-mini-profile-fade">
      <div v-if="canRenderOpen" class="user-mini-profile-overlay" role="presentation" @pointerdown.stop.self @click.stop.self="close">
        <section class="user-mini-profile-panel" :class="{ 'stats-mode': view === 'stats' }" :style="profilePanelStyle"
                 role="dialog" aria-modal="true" :aria-label="`Мини-профиль ${displayName}`" @pointerdown.stop @click.stop>
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
                        <span>{{ nomination.levelLabel }}</span>
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
          </template>

          <template v-else>
            <div class="stats-toolbar">
              <button class="profile-action secondary" type="button" @click="view = 'profile'">Назад к профилю</button>
            </div>
            <ProfileStatsTab :stats-url="resolvedStatsUrl" />
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
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { isMiniProfilePrivilegedViewer, normalizeMiniProfileRole } from '@/services/miniProfile'
import { buildProfileThemeBgStyle } from '@/constants/profileThemes'
import { getProfileThemeBadgeSources } from '@/constants/profileThemeIcons'
import {
  useFriendsStore,
  useSettingsStore,
  useUserStore,
  resolveFriendsApiError,
  shouldRefreshFriendsStateAfterError,
  type FriendApiAction,
  type FriendStatus,
} from '@/store'
import ProfileStatsTab from '@/components/ProfileStatsTab.vue'

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
type NominationLevel = 1 | 2 | 3 | 4 | 5
type NominationStatKey = 'games_played' | 'games_hosted' | 'room_minutes' | 'stream_minutes' | 'spectator_minutes'

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
  deleted?: boolean
  registered_at?: string | null
  last_visit_at?: string | null
  last_game_at?: string | null
  last_game_id?: number | null
  online?: boolean
  subscription_active?: boolean
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
let requestSeq = 0
let nicknameHistorySeq = 0

const MINUTES_IN_DAY = 24 * 60
const nominationIntFmt = new Intl.NumberFormat('ru-RU')
const PROFILE_NOMINATION_DEFINITIONS: readonly ProfileNominationDefinition[] = [
  {
    key: 'games-played',
    label: 'Игры',
    icon: nominationGames,
    statKey: 'games_played',
    unit: 'count',
    levelStarts: [0, 50, 200, 500, 1001],
    startLabels: ['0', '50', '200', '500', '1000+'],
    nextLabels: ['50', '200', '500', '1000+'],
  },
  {
    key: 'games-hosted',
    label: 'Ведущий',
    icon: nominationHead,
    statKey: 'games_hosted',
    unit: 'count',
    levelStarts: [0, 20, 50, 100, 301],
    startLabels: ['0', '20', '50', '100', '300+'],
    nextLabels: ['20', '50', '100', '300+'],
  },
  {
    key: 'room-time',
    label: 'В комнатах',
    icon: nominationRoom,
    statKey: 'room_minutes',
    unit: 'minutes',
    levelStarts: [0, 3 * MINUTES_IN_DAY, 6 * MINUTES_IN_DAY, 9 * MINUTES_IN_DAY, 12 * MINUTES_IN_DAY + 1],
    startLabels: ['0', '3д', '6д', '9д', '12д+'],
    nextLabels: ['3д', '6д', '9д', '12д+'],
    // levelStarts: [0, 7 * MINUTES_IN_DAY, 14 * MINUTES_IN_DAY, 30 * MINUTES_IN_DAY, 60 * MINUTES_IN_DAY + 1],
    // startLabels: ['0', '7д', '14д', '30д', '60д+'],
    // nextLabels: ['7д', '14д', '30д', '60д+'],
  },
  {
    key: 'stream-time',
    label: 'Трансляции',
    icon: nominationStream,
    statKey: 'stream_minutes',
    unit: 'minutes',
    levelStarts: [0, Math.round(0.25 * MINUTES_IN_DAY), MINUTES_IN_DAY, 2 * MINUTES_IN_DAY, 5 * MINUTES_IN_DAY + 1],
    startLabels: ['0', '6ч', '1д', '2д', '5д+'],
    nextLabels: ['6ч', '1д', '2д', '5д+'],
  },
  {
    key: 'spectator-time',
    label: 'Зритель',
    icon: nominationSpectator,
    statKey: 'spectator_minutes',
    unit: 'minutes',
    levelStarts: [0, Math.round(0.05 * MINUTES_IN_DAY), Math.round(0.15 * MINUTES_IN_DAY), Math.round(0.25 * MINUTES_IN_DAY), Math.round(0.33 * MINUTES_IN_DAY) + 1],
    startLabels: ['0', '2ч', '4ч', '6ч', '8ч+'],
    nextLabels: ['2ч', '4ч', '6ч', '8ч+'],
    // levelStarts: [0, MINUTES_IN_DAY, 7 * MINUTES_IN_DAY, 14 * MINUTES_IN_DAY, 30 * MINUTES_IN_DAY + 1],
    // startLabels: ['0', '1д', '7д', '14д', '30д+'],
    // nextLabels: ['1д', '7д', '14д', '30д+'],
  },
]

const targetUserId = computed(() => {
  const raw = props.userId ?? props.initialProfile?.id ?? 0
  const uid = Number(raw)
  return Number.isFinite(uid) && uid > 0 ? Math.trunc(uid) : 0
})
const profileLoadedForTarget = computed(() => Boolean(profile.value && profile.value.id === targetUserId.value))
const viewerUserId = computed(() => Number(userStore.user?.id || 0))
const viewerRole = computed(() => normalizeMiniProfileRole(userStore.user?.role))
const viewerVerificationRestricted = computed(() => Boolean(settingsStore.verificationRestrictions && !userStore.telegramVerified))
const canRenderOpen = computed(() => props.open && !viewerVerificationRestricted.value)
const isSelfProfile = computed(() => targetUserId.value > 0 && viewerUserId.value === targetUserId.value)
const privilegedViewer = computed(() => isMiniProfilePrivilegedViewer(viewerRole.value, props.adminMode))
const initialTargetDeleted = computed(() => {
  const initialId = Number(props.initialProfile?.id || 0)
  if (!Number.isFinite(initialId) || initialId <= 0 || Math.trunc(initialId) !== targetUserId.value) return false
  return Boolean(props.initialProfile?.deleted || props.initialProfile?.deleted_at)
})
const targetDeleted = computed(() => Boolean(
  (profileLoadedForTarget.value && profile.value?.deleted)
  || (!profileLoadedForTarget.value && initialTargetDeleted.value)
))

const displayName = computed(() => {
  if (profileLoadedForTarget.value && profile.value?.username) return profile.value.username
  if (props.initialProfile?.username) return props.initialProfile.username
  return targetUserId.value > 0 ? `user${targetUserId.value}` : 'Пользователь'
})
const avatarName = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.avatar_name || ''
  return props.initialProfile?.avatar_name || ''
})
const avatarKey = computed(() => {
  const name = String(avatarName.value || '').trim()
  if (!name) return ''
  return name.startsWith('avatars/') ? name : `avatars/${name}`
})
const hasAvatar = computed(() => Boolean(avatarKey.value))
const profileThemeColor = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.profile_theme_color || null
  return props.initialProfile?.profile_theme_color || props.initialProfile?.theme_color || null
})
const profileThemeIcon = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.profile_theme_icon || null
  return props.initialProfile?.profile_theme_icon || props.initialProfile?.theme_icon || null
})
const profileRole = computed(() => {
  if (profileLoadedForTarget.value) return profile.value?.role || null
  return props.initialProfile?.role || null
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
  const start = levelStarts[level - 1]
  const next = levelStarts[level]
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
    levelLabel: `${level} уровень`,
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
  const direct = normalizeFriendStatus(props.initialProfile?.friend_status)
  if (direct !== 'none') return direct
  const kind = String(props.initialProfile?.kind || '')
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
      deleted: Boolean(data?.deleted),
      registered_at: data?.registered_at ?? null,
      last_visit_at: data?.last_visit_at ?? null,
      last_game_at: data?.last_game_at ?? null,
      last_game_id: Number.isFinite(Number(data?.last_game_id)) ? Math.trunc(Number(data?.last_game_id)) : null,
      online: Boolean(data?.online),
      subscription_active: Boolean(data?.subscription_active),
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
  applyFriendStatus(inferInitialFriendStatus())
  if (uid > 0) void loadProfile()
}, { immediate: true })

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('auth-friends_update', onFriendsUpdate)
})

onBeforeUnmount(() => {
  resetNicknameHistory()
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
          gap: 5px;
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
                .profile-nomination-icon-shell {
                  background: linear-gradient(135deg, rgba($graphite, 0.5) 0%, rgba($lead, 0.5) 100%);
                }
              }
              &.level-2 {
                .profile-nomination-icon-shell {
                  background: linear-gradient(135deg, rgba(122, 74, 36, 0.5) 0%, rgba(184, 121, 66, 0.5) 100%);
                }
              }
              &.level-3 {
                .profile-nomination-icon-shell {
                  background: linear-gradient(135deg, rgba(143, 150, 159, 0.5) 0%, rgba(216, 221, 228, 0.5) 100%);
                }
              }
              &.level-4 {
                .profile-nomination-icon-shell {
                  background: linear-gradient(135deg, rgba(179, 122, 19, 0.5) 0%, rgba(243, 208, 91, 0.5) 100%);
                }
              }
              &.level-5 {
                .profile-nomination-icon-shell {
                  background: linear-gradient(135deg, rgba(229, 247, 244, 0.5) 0%, rgba(73, 199, 192, 0.5) 52%, rgba(217, 212, 189, 1) 100%);
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
                width: 16px;
                height: 16px;
                object-fit: contain;
              }
              .profile-nomination-tooltip {
                top: calc(100% + 10px);
                gap: 5px;
                width: 200px;
                font-size: 12px;
                .nomination-tooltip-head,
                .nomination-progress-caption {
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  gap: 10px;
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
                .nomination-progress-caption {
                  color: $ashy;
                  font-size: 11px;
                }
                .nomination-progress-track {
                  display: block;
                  position: relative;
                  width: 100%;
                  height: 18px;
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
                  font-size: 11px;
                  font-family: Manrope-SemiBold;
                  white-space: nowrap;
                }
              }
            }
            .sanction-tooltip-wrap {
              .profile-meta-icon {
                width: 24px;
                height: 24px;
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
                width: 24px;
                height: 24px;
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

@media (max-width: 1280px) {
  .user-mini-profile-overlay {
    .user-mini-profile-panel {
      padding: 10px;
      gap: 10px;
      width: 350px;
      &.stats-mode {
        gap: 10px;
        width: min(750px, calc(100vw - 40px));
        height: calc(100dvh - 40px);
      }
      .profile-top {
        .profile-identity {
          gap: 5px;
          .profile-avatar-trigger {
            .profile-avatar {
              width: 80px;
              height: 80px;
            }
          }
          .profile-icon-name {
            gap: 3px;
            .profile-title {
              gap: 3px;
              height: 20px;
              .profile-theme-icons {
                gap: 3px;
                .profile-theme-icon {
                  width: 16px;
                  height: 16px;
                }
              }
              .profile-name {
                max-width: 200px;
                font-size: 14px;
              }
            }
            .profile-meta {
              .profile-tooltip-wrap {
                &::after {
                  height: 5px;
                }
                .profile-tooltip {
                  top: calc(100% + 5px);
                  padding: 5px;
                }
              }
              .profile-friends-tooltip-wrap {
                .profile-friends-count {
                  padding: 3px 8px;
                  font-size: 10px;
                }
                .profile-friends-tooltip {
                  max-height: 125px;
                  font-size: 10px;
                  .profile-friends-list {
                    gap: 3px;
                    .profile-friend-row {
                      gap: 3px;
                      .profile-friend-avatar {
                        width: 20px;
                        height: 20px;
                      }
                      .profile-friend-main {
                        .profile-friend-name {
                          font-size: 9px;
                        }
                        .profile-friend-date {
                          font-size: 7px;
                        }
                      }
                    }
                  }
                }
              }
              .profile-nomination-tooltip-wrap {
                .profile-nomination-icon-shell {
                  width: 18px;
                  height: 18px;
                  border-radius: 4px;
                }
                .profile-nomination-icon {
                  width: 12px;
                  height: 12px;
                }
                .profile-nomination-tooltip {
                  gap: 5px;
                  width: 210px;
                  padding: 5px;
                  font-size: 10px;
                  .nomination-tooltip-head,
                  .nomination-progress-caption {
                    gap: 5px;
                  }
                  .nomination-progress-caption {
                    font-size: 9px;
                  }
                  .nomination-progress-track {
                    height: 14px;
                  }
                  .nomination-progress-value {
                    padding: 0 5px;
                    font-size: 9px;
                  }
                }
              }
              .sanction-tooltip-wrap {
                .profile-meta-icon {
                  width: 14px;
                  height: 14px;
                }
                .sanction-tooltip {
                  padding: 3px 5px;
                  font-size: 10px;
                }
              }
              .profile-history-tooltip-wrap {
                .profile-meta-icon {
                  width: 14px;
                  height: 14px;
                }
                .nickname-history-tooltip {
                  max-height: 150px;
                  padding: 3px 5px;
                  font-size: 10px;
                  .nickname-history-list {
                    gap: 3px;
                  }
                }
              }
            }
          }
        }
        .profile-side-tools {
          .close-button {
            width: 20px;
            height: 20px;
            img {
              width: 14px;
              height: 14px;
            }
          }
        }
      }
      .state {
        font-size: 14px;
        &.state-danger {
        }
      }
      .profile-dates {
        gap: 5px;
        .date-row {
          padding: 5px 8px;
          span {
            font-size: 10px;
          }
          strong {
            font-size: 10px;
          }
        }
      }
      .profile-actions,
      .stats-toolbar {
        gap: 5px;
        .profile-action {
          gap: 3px;
          min-height: 30px;
          font-size: 12px;
          img {
            width: 16px;
            height: 16px;
          }
        }
      }
    }
  }
  .avatar-lightbox-overlay {
    .avatar-lightbox-image {
      width: min(75vw, 75vh, 500px);
      height: min(75vw, 75vh, 500px);
    }
  }
}
</style>
