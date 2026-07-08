<template>
  <section class="profile">
    <header>
      <div class="tab-div">
        <UiButton
          size="middle"
          variant="white"
          width="100%"
          :href="homeHref"
          :icon="iconHome"
          text="На главную"
          aria-label="На главную"
          @click="navigateHome"
        />
        <div class="tab-div-line"></div>
        <nav class="tabs" aria-label="Навигация" role="tablist">
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'account' }" :aria-selected="activeTab === 'account'" @click="activeTab = 'account'">
            <UiIcon class="tab-btn-img" :icon="iconSettings" />
            <span class="tab-btn-text">Аккаунт</span>
          </button>
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'profile' }" :aria-selected="activeTab === 'profile'" :disabled="profileTabsDisabled" @click="activeTab = 'profile'">
            <UiIcon class="tab-btn-img" :icon="iconDefaultAvatar" />
            <span class="tab-btn-text">Аватар и никнейм</span>
          </button>
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'theme' }" :aria-selected="activeTab === 'theme'" :disabled="profileTabsDisabled" @click="activeTab = 'theme'">
            <UiIcon class="tab-btn-img" :icon="iconDesign" />
            <span class="tab-btn-text">Оформление профиля</span>
          </button>
          <button disabled class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'stats' }" :aria-selected="activeTab === 'stats'" :disabled="profileTabsDisabled" @click="activeTab = 'stats'">
            <UiIcon class="tab-btn-img" :icon="iconStats" />
            <span class="tab-btn-text">Статистика</span>
          </button>
          <button disabled class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'history' }" :aria-selected="activeTab === 'history'" :disabled="profileTabsDisabled" @click="activeTab = 'history'">
            <UiIcon class="tab-btn-img" :icon="iconHistory" />
            <span class="tab-btn-text">История игр</span>
          </button>
          <button disabled class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'sanctions' }" :aria-selected="activeTab === 'sanctions'" :disabled="profileTabsDisabled" @click="activeTab = 'sanctions'">
            <UiIcon class="tab-btn-img" :icon="iconJudgeHummer" />
            <span class="tab-btn-text">Санкции</span>
          </button>
          <button disabled class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'payments' }" :aria-selected="activeTab === 'payments'" :disabled="profileTabsDisabled" @click="activeTab = 'payments'">
            <UiIcon class="tab-btn-img" :icon="iconCard" />
            <span class="tab-btn-text">Платежи</span>
          </button>
          <button disabled class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'music' }" :aria-selected="activeTab === 'music'" :disabled="profileTabsDisabled" @click="activeTab = 'music'">
            <UiIcon class="tab-btn-img" :icon="iconMusic" />
            <span class="tab-btn-text">Музыка</span>
          </button>
          <button disabled class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'blacklist' }" :aria-selected="activeTab === 'blacklist'" :disabled="profileTabsDisabled" @click="activeTab = 'blacklist'">
            <UiIcon class="tab-btn-img" :icon="iconBlockPlayer" />
            <span class="tab-btn-text">Черный список</span>
          </button>
        </nav>
      </div>
      <div class="tab-div">
        <div v-if="!hasActiveSubscription" class="tab-subscribe">
          <span>ПОДПИСКА</span>
          <span>купить подписку</span>
          <UiButton
            size="middle"
            variant="white"
            type="button"
            text="Оформить"
            @click="openSubscriptionModal"
          />
        </div>
        <button class="tab-btn" type="button" @click="onLogoutClick">
          <UiIcon class="tab-btn-img" :icon="iconLeave" />
          <span class="tab-btn-text">Выход из аккаунта</span>
        </button>
      </div>
    </header>

    <Transition name="tab-fade" mode="out-in">
      <div :key="activeTab" class="tab-panel">
        <ProfileAccount
          v-if="activeTab === 'account'"
          :me="me"
          :registration-date-label="registrationDateLabel"
          :tg-invites-enabled="tgInvitesEnabled"
          :tg-invites-toggle-pending="tgInvitesTogglePending"
          :telegram-verified="telegramVerified"
          :unlink-tg-busy="unlinkTgBusy"
          :bot-name="botName"
          :bot-link="botLink"
          :delete-busy="deleteBusy"
          :is-delete-account-forbidden-self="isDeleteAccountForbiddenSelf"
          :password-temp="passwordTemp"
          :pwd="pwd"
          :password-max="PASSWORD_MAX"
          :current-password-invalid="currentPasswordInvalid"
          :new-password-invalid="newPasswordInvalid"
          :confirm-password-invalid="confirmPasswordInvalid"
          :pwd-busy="pwdBusy"
          :can-change-password="canChangePassword"
          @toggle-tg-invites="onToggleTgInvites"
          @unlink-telegram="unlinkTelegram"
          @delete-account="deleteAccount"
          @change-password="changePassword"
        />

        <ProfileAvatarNick
          v-if="activeTab === 'profile'"
          v-model:nick="nick"
          :me="me"
          :icon-default-avatar="iconDefaultAvatar"
          :icon-download="iconDownload"
          :icon-delete="iconDelete"
          :icon-time-history="iconTimeHistory"
          :icon-save="iconSave"
          :avatar-accept="avatarAccept"
          :avatar-format-hint="avatarFormatHint"
          :is-banned="isBanned"
          :busy-ava="busyAva"
          :busy-nick="busyNick"
          :is-protected-admin-self="isProtectedAdminSelf"
          :nick-max="NICK_MAX"
          :valid-nick="validNick"
          :can-edit-profile-theme="canEditProfileTheme"
          :nickname-history-access-text="nicknameHistoryAccessText"
          :nickname-history-clear-disabled="nicknameHistoryClearDisabled"
          :nickname-history-clear-busy="nicknameHistoryClearBusy"
          :nickname-history-loading="nicknameHistoryLoading"
          :nickname-history-error="nicknameHistoryError"
          :nickname-history-items="nicknameHistoryItems"
          :nickname-changes-left="nicknameChangesLeft"
          :save-nick-disabled="saveNickDisabled"
          :crop="crop"
          :gif-picker="gifPicker"
          :gif-frame-label="gifFrameLabel"
          @pick="onPick"
          @delete-avatar="onDeleteAvatar"
          @load-nickname-history="loadNicknameHistory"
          @clear-nickname-history="clearNicknameHistory"
          @save-nick="saveNick"
          @modal-ref="setProfileModalEl"
          @canvas-ref="setProfileCanvasEl"
          @gif-modal-ref="setProfileGifModalEl"
          @gif-canvas-ref="setProfileGifCanvasEl"
          @cancel-crop="cancelCrop"
          @drag-start="dragStart"
          @drag-move="dragMove"
          @drag-stop="dragStop"
          @wheel="onWheel"
          @scale-to="scaleTo"
          @cancel-gif-picker="cancelGifPicker"
          @gif-frame-range="onGifFrameRange"
          @apply-gif-picker="applyGifPicker"
          @apply-crop="applyCrop"
        />

        <ProfileTheme
          v-if="activeTab === 'theme'"
          :me="me"
          :icon-default-avatar="iconDefaultAvatar"
          :icon-save="iconSave"
          :theme-preview-style="themePreviewStyle"
          :theme-preview-icon-srcs="themePreviewIconSrcs"
          :profile-theme-options="profileThemeOptions"
          :selected-profile-theme-color="selectedProfileThemeColor"
          :theme-option-style="themeOptionStyle"
          :profile-theme-icon-options="profileThemeIconOptions"
          :selected-profile-theme-icon="selectedProfileThemeIcon"
          :theme-icon-src="themeIconSrc"
          :theme-save-busy="themeSaveBusy"
          :is-banned="isBanned"
          :can-edit-profile-theme="canEditProfileTheme"
          :theme-save-disabled="themeSaveDisabled"
          :profile-theme-message-text="profileThemeMessageText"
          @pick-profile-theme="pickProfileTheme"
          @pick-profile-theme-icon="pickProfileThemeIcon"
          @save-profile-theme="saveProfileTheme"
          @open-subscription-modal="openSubscriptionModal"
        />

        <div v-if="activeTab === 'stats'" class="profile-tab-block block-stats">
          <ProfileStats />
        </div>

        <div v-if="activeTab === 'history'" class="profile-tab-block block-history">
          <ProfileHistory />
        </div>

        <ProfileSanctions
          v-if="activeTab === 'sanctions'"
          :sanctions-loaded="sanctionsLoaded"
          :sanctions-summary="sanctionsSummary"
          :sanctions-loading="sanctionsLoading"
          :sanctions-error="sanctionsError"
          :sanctions="sanctions"
          :format-sanction-kind="formatSanctionKind"
          :format-local-date-time="formatLocalDateTime"
          :format-sanction-duration="formatSanctionDuration"
          :format-sanction-finished-at="formatSanctionFinishedAt"
          :format-sanction-completion-reason="formatSanctionCompletionReason"
          :format-duration-seconds="formatDurationSeconds"
        />

        <ProfilePayments
          v-if="activeTab === 'payments'"
          :payments-loading="paymentsLoading"
          :payments-error="paymentsError"
          :payments-items="paymentsItems"
          :format-payment-paid-at="formatPaymentPaidAt"
          :format-payment-subscription-term="formatPaymentSubscriptionTerm"
          :format-payment-money="formatPaymentMoney"
          :format-payment-promo-discount="formatPaymentPromoDiscount"
        />

        <ProfileMusic v-if="activeTab === 'music'" />

        <ProfileBlacklist
          v-if="activeTab === 'blacklist'"
          :blacklist-loading="blacklistLoading"
          :blacklist-error="blacklistError"
          :blacklist-items="blacklistItems"
          :blacklist-removing="blacklistRemoving"
          :icon-default-avatar="iconDefaultAvatar"
          :blacklist-avatar-key="blacklistAvatarKey"
          :format-local-date-time="formatLocalDateTime"
          @remove-from-blacklist="removeFromBlacklistProfile"
        />
      </div>
    </Transition>

    <Subscription v-model:open="subscriptionModalOpen" @select="onSubscriptionPaymentSelect" />
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { api, refreshAccessTokenFull } from '@/services/axios'
import { useAuthStore, useFriendsStore, useSettingsStore, useUserStore, type BlacklistItem } from '@/store'
import { confirmDialog, alertDialog } from '@/services/confirm'
import { formatModerationAlert } from '@/services/moderation'
import { formatLocalDateTime } from '@/services/datetime'
import {
  buildProfileThemeBgStyle,
  getProfileThemeOptions,
  normalizeProfileThemeColor,
  resolveProfileThemeColor,
  type ProfileThemeColor,
} from '@/constants/profileThemes'
import {
  PROFILE_THEME_ICON_OPTIONS,
  getProfileThemeBadgeSources,
  getProfileThemeIconSrc,
  normalizeProfileThemeIcon,
  type ProfileThemeIcon,
} from '@/constants/profileIcons'

import ProfileStats from '@/components/ProfileStats.vue'
import ProfileHistory from '@/components/ProfileHistory.vue'
import ProfileAccount from '@/components/ProfileAccount.vue'
import ProfileAvatarNick from '@/components/ProfileAvatarNick.vue'
import ProfileTheme from '@/components/ProfileTheme.vue'
import ProfileSanctions from '@/components/ProfileSanctions.vue'
import ProfilePayments from '@/components/ProfilePayments.vue'
import ProfileMusic from '@/components/ProfileMusic.vue'
import ProfileBlacklist from '@/components/ProfileBlacklist.vue'
import Subscription from '@/components/Subscription.vue'
import UiIcon from '@/components/UiIcon.vue'
import UiButton from '@/components/UiButton.vue'

import iconHome from '@/assets/svg/iconHome.svg'
import iconDefaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconSettings from '@/assets/svg/iconSettings.svg'
import iconDesign from '@/assets/svg/iconDesign.svg'
import iconStats from '@/assets/svg/iconStats.svg'
import iconHistory from '@/assets/svg/iconHistory.svg'
import iconJudgeHummer from '@/assets/svg/iconJudgeHummer.svg'
import iconCard from '@/assets/svg/iconCard.svg'
import iconMusic from '@/assets/svg/iconMusic.svg'
import iconBlockPlayer from '@/assets/svg/iconBlockPlayer.svg'
import iconLeave from '@/assets/svg/iconLeave.svg'
import iconTimeHistory from '@/assets/svg/iconTimeHistory.svg'
import iconDownload from '@/assets/svg/iconDownload.svg'
import iconDelete from '@/assets/svg/iconDelete.svg'
import iconSave from '@/assets/svg/save.svg'

const userStore = useUserStore()
const friendsStore = useFriendsStore()
const auth = useAuthStore()
const settings = useSettingsStore()
const isBanned = computed(() => userStore.banActive)
const { tgInvitesEnabled, now: userNow } = storeToRefs(userStore)
const { setTgInvitesEnabled, setProfileTheme } = userStore

const me = reactive({
  id: 0,
  username: '',
  avatar_name: null as string | null,
  role: '',
  registered_at: null as string | null,
  telegram_verified: false,
  has_password: false,
  password_temp: false,
  protected_user: false,
  tg_invites_enabled: true,
  subscription_active: false,
  subscription_started_at: null as string | null,
  subscription_until: null as string | null,
  nickname_changes_left: 0,
  profile_theme_color: null as ProfileThemeColor | null,
  profile_theme_icon: null as ProfileThemeIcon | null,
})

type NicknameHistoryResponse = {
  items?: string[] | null
}

const isProtectedAdminSelf = computed(() => Boolean(me.protected_user))
const isDeleteAccountForbiddenSelf = computed(() => {
  const role = String(me.role || '').trim().toLowerCase()
  return Boolean(me.protected_user) || role === 'admin' || role === 'moder'
})
const modalEl = ref<HTMLDivElement | null>(null)

const nick = ref('')
const busyNick = ref(false)
const nicknameHistoryLoading = ref(false)
const nicknameHistoryError = ref('')
const nicknameHistoryItems = ref<string[]>([])
const nicknameHistoryLoaded = ref(false)
const nicknameHistoryClearBusy = ref(false)
let nicknameHistorySeq = 0
const validNick = computed(() => {
  const value = nick.value
  const ok = new RegExp(`^[a-zA-Zа-яА-ЯёЁ0-9._\\-()]{2,${NICK_MAX}}$`).test(value)
  if (!ok) return false
  const lower = value.toLowerCase()
  return !lower.startsWith('deleted_') && !lower.startsWith('user_')
})
const nicknameChangesLeft = computed(() => normalizeNicknameChangesLeft(me.nickname_changes_left))
const saveNickDisabled = computed(() => (
  busyNick.value
  || isBanned.value
  || isProtectedAdminSelf.value
  || nick.value === me.username
  || !validNick.value
  || nicknameChangesLeft.value <= 0
))

const NICK_MAX = 20
const NICKNAME_CHANGES_MAX = 30
const PASSWORD_MIN = 8
const PASSWORD_MAX = 32
const PASSWORD_SPACE_RE = /\s/
const AVATAR_MAX_BYTES = 5 * 1024 * 1024
const MAX_AVATAR_GIF_FRAMES = 300
const CROP_CANVAS_DESKTOP_SIZE = 400
const CROP_CANVAS_MOBILE_SIZE = 200
const CROP_CANVAS_MOBILE_QUERY = '(max-width: 1280px)'
const STATIC_AVATAR_TYPES = new Set(['image/jpeg', 'image/png'])
const ANIMATED_AVATAR_TYPE = 'image/gif'
const route = useRoute()
const router = useRouter()
const homeHref = computed(() => router.resolve({ name: 'home' }).href)

const TAB_KEYS = ['profile', 'theme', 'music', 'account', 'stats', 'payments', 'history', 'sanctions', 'blacklist'] as const
type TabKey = typeof TAB_KEYS[number]
const DEFAULT_TAB: TabKey = 'account'

function normalizeTab(v: unknown): TabKey {
  if (typeof v === 'string' && (TAB_KEYS as readonly string[]).includes(v)) return v as TabKey
  return DEFAULT_TAB
}

function isProfileSettingsTab(tab: TabKey): boolean {
  return tab === 'profile' || tab === 'theme' || tab === 'account'
}

function navigateHome(event: MouseEvent) {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.altKey || event.ctrlKey || event.shiftKey) return
  event.preventDefault()
  router.push({ name: 'home' }).catch(() => {})
}

async function onLogoutClick() {
  try { await auth.logout() }
  finally {}
}

function parseDateMs(raw: string | null | undefined): number {
  if (!raw) return 0
  const ts = Date.parse(raw)
  return Number.isFinite(ts) ? ts : 0
}

function normalizeNicknameChangesLeft(raw: unknown): number {
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? Math.min(NICKNAME_CHANGES_MAX, Math.max(0, Math.floor(parsed))) : 0
}

const activeTab = ref<TabKey>(DEFAULT_TAB)
let onSanctionsUpdate: ((e: Event) => void) | null = null
let onProfileSync: ((e: Event) => void) | null = null

type SanctionItem = {
  id: number
  kind: 'timeout' | 'ban' | 'suspend'
  completion_reason: 'active' | 'expired' | 'revoked_staff' | 'hosted_game'
  reason?: string | null
  issued_at: string
  finished_at?: string | null
  duration_seconds?: number | null
  served_seconds: number
  hosted_workoff_seconds?: number | null
}

type SubscriptionPaymentPlan = 'month' | 'year'

type SubscriptionPaymentItem = {
  id: number
  paid_at: string
  email?: string | null
  plan?: SubscriptionPaymentPlan | null
  subscription_months: number
  amount?: string | null
  currency?: string | null
  promo_discount_percent?: number | null
}

type SubscriptionPaymentsResponse = {
  items?: SubscriptionPaymentItem[] | null
}

const sanctions = ref<SanctionItem[]>([])
const sanctionsLoading = ref(false)
const sanctionsLoaded = ref(false)
const sanctionsError = ref('')
const paymentsItems = ref<SubscriptionPaymentItem[]>([])
const paymentsLoading = ref(false)
const paymentsLoaded = ref(false)
const paymentsError = ref('')
const blacklistLoading = ref(false)
const blacklistError = ref('')
const blacklistRemoving = reactive<Record<number, boolean>>({})
const tgInvitesTogglePending = ref(false)
const themeSaveBusy = ref(false)
const subscriptionModalOpen = ref(false)
const telegramVerified = computed(() => userStore.telegramVerified)
const profileTabsDisabled = computed(() => settings.verificationRestrictions && !telegramVerified.value)
const passwordTemp = computed(() => userStore.passwordTemp)
const botName = (import.meta.env.VITE_TG_BOT_NAME as string || '').trim()
const botLink = botName ? `https://t.me/${botName}` : 'https://t.me'
const pwd = reactive({ current: '', next: '', confirm: '' })
const pwdBusy = ref(false)
const unlinkTgBusy = ref(false)
const canChangePassword = computed(() =>
  pwd.current.length >= PASSWORD_MIN &&
  pwd.current.length <= PASSWORD_MAX &&
  pwd.next.length >= PASSWORD_MIN &&
  pwd.next.length <= PASSWORD_MAX &&
  !hasPasswordWhitespace(pwd.next) &&
  pwd.confirm.length >= PASSWORD_MIN &&
  pwd.confirm.length <= PASSWORD_MAX &&
  !hasPasswordWhitespace(pwd.confirm) &&
  pwd.next === pwd.confirm
)

const currentPasswordInvalid = computed(() => {
  const len = pwd.current.length
  return len > 0 && len < PASSWORD_MIN
})
const newPasswordInvalid = computed(() => {
  const len = pwd.next.length
  return len > 0 && (len < PASSWORD_MIN || hasPasswordWhitespace(pwd.next))
})
const confirmPasswordInvalid = computed(() => {
  const len = pwd.confirm.length
  if (len === 0) return false
  if (hasPasswordWhitespace(pwd.confirm)) return true
  if (len < PASSWORD_MIN) return true
  return pwd.next !== pwd.confirm
})

function hasPasswordWhitespace(value: string) {
  return PASSWORD_SPACE_RE.test(value)
}

const selectedProfileThemeColor = ref<ProfileThemeColor>(resolveProfileThemeColor(null))
const selectedProfileThemeIcon = ref<ProfileThemeIcon | null>(null)
const subscriptionUntilMs = computed(() => parseDateMs(me.subscription_until))
const hasActiveSubscription = computed(() => {
  if (subscriptionUntilMs.value > 0) return subscriptionUntilMs.value > userNow.value
  return Boolean(me.subscription_active)
})
const canEditProfileTheme = computed(() => hasActiveSubscription.value)
const blacklistItems = computed<BlacklistItem[]>(() => (
  Array.isArray(friendsStore.blacklist) ? friendsStore.blacklist : []
))
const canUseAnimatedAvatar = computed(() => canEditProfileTheme.value)
const avatarAccept = computed(() => (
  canUseAnimatedAvatar.value ? 'image/jpeg,image/png,image/gif' : 'image/jpeg,image/png'
))
const avatarFormatHint = computed(() => (
  canUseAnimatedAvatar.value ? 'JPG/PNG/GIF, до 5 МБ' : 'JPG/PNG, до 5 МБ'
))
const currentProfileThemeColor = computed(() => resolveProfileThemeColor(me.profile_theme_color))
const currentProfileThemeIcon = computed(() => normalizeProfileThemeIcon(me.profile_theme_icon))
const profileThemeDirty = computed(() => (
  selectedProfileThemeColor.value !== currentProfileThemeColor.value
  || selectedProfileThemeIcon.value !== currentProfileThemeIcon.value
))
const themeSaveDisabled = computed(() => themeSaveBusy.value || isBanned.value || !canEditProfileTheme.value || !profileThemeDirty.value)
const profileThemeSaveDisabledText = computed(() => {
  if (!canEditProfileTheme.value) return 'Выбор оформления доступен только при наличии подписки'
  return ''
})
const themePreviewStyle = computed(() => buildProfileThemeBgStyle(selectedProfileThemeColor.value))
const themePreviewIconSrcs = computed(() => getProfileThemeBadgeSources(selectedProfileThemeIcon.value, me.role))
const profileThemeOptions = computed(() => getProfileThemeOptions(me.role))
const profileThemeIconOptions = computed(() => PROFILE_THEME_ICON_OPTIONS.filter((item) => item.available || item.key === selectedProfileThemeIcon.value))
const profileThemeAvailabilityText = computed(() => {
  const raw = me.subscription_until
  if (!raw) return 'Доступно, пока активна подписка'
  const dt = new Date(raw)
  if (Number.isNaN(dt.getTime())) return 'Доступно, пока активна подписка'
  return `Доступно для Вас до ${dt.toLocaleDateString('ru-RU')}`
})
const profileThemeMessageText = computed(() => canEditProfileTheme.value ? profileThemeAvailabilityText.value : profileThemeSaveDisabledText.value)
const nicknameHistoryAccessText = computed(() => (
  canEditProfileTheme.value
    ? profileThemeAvailabilityText.value
    : 'Очистка истории никнеймов доступна только при наличии подписки'
))
const nicknameHistoryHasDeletableItems = computed(() => nicknameHistoryItems.value.length > 1)
const nicknameHistoryClearDisabled = computed(() => (
  nicknameHistoryClearBusy.value
  || nicknameHistoryLoading.value
  || !nicknameHistoryLoaded.value
  || isBanned.value
  || !canEditProfileTheme.value
))
const registrationDateLabel = computed(() => {
  const raw = me.registered_at
  if (!raw) return '-'
  const dt = new Date(raw)
  if (Number.isNaN(dt.getTime())) return '-'
  return dt.toLocaleDateString('ru-RU')
})
const PAYMENT_DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
}
let paymentsRequestSeq = 0

async function onToggleTgInvites(next: boolean) {
  if (tgInvitesTogglePending.value || !telegramVerified.value) return
  tgInvitesTogglePending.value = true
  try { await setTgInvitesEnabled(next) }
  finally { tgInvitesTogglePending.value = false }
}

const sanctionsSummary = computed(() => {
  const out = { total: sanctions.value.length, timeout: 0, ban: 0, suspend: 0 }
  for (const item of sanctions.value) {
    if (item.kind === 'timeout') out.timeout += 1
    else if (item.kind === 'ban') out.ban += 1
    else if (item.kind === 'suspend') out.suspend += 1
  }
  return out
})

function applyProfileThemePayload(data: any, options: { keepDraft?: boolean } = {}) {
  me.subscription_active = Boolean(data?.subscription_active)
  me.subscription_started_at = data?.subscription_started_at || null
  me.subscription_until = data?.subscription_until || null
  me.profile_theme_color = normalizeProfileThemeColor(data?.profile_theme_color)
  me.profile_theme_icon = normalizeProfileThemeIcon(data?.profile_theme_icon)
  setProfileTheme({
    subscription_active: me.subscription_active,
    subscription_started_at: me.subscription_started_at,
    subscription_until: me.subscription_until,
    profile_theme_color: me.profile_theme_color,
    profile_theme_icon: me.profile_theme_icon,
  })
  if (!options.keepDraft) {
    selectedProfileThemeColor.value = resolveProfileThemeColor(me.profile_theme_color)
    selectedProfileThemeIcon.value = me.profile_theme_icon
  }
}

function applyMePayload(data: any, options: { keepNickDraft?: boolean; keepThemeDraft?: boolean } = {}) {
  const prevUserId = me.id
  const prevUsername = me.username
  me.id = Number(data?.id || 0)
  me.username = data?.username || ''
  me.avatar_name = data?.avatar_name || null
  me.role = data?.role || ''
  me.registered_at = data?.registered_at || null
  me.telegram_verified = Boolean(data?.telegram_verified)
  me.has_password = Boolean(data?.has_password)
  me.password_temp = Boolean(data?.password_temp)
  me.protected_user = Boolean(data?.protected_user)
  me.tg_invites_enabled = data?.tg_invites_enabled !== false
  me.nickname_changes_left = normalizeNicknameChangesLeft(data?.nickname_changes_left)
  applyProfileThemePayload(data, { keepDraft: options.keepThemeDraft })
  const hasNickDraft = Boolean(options.keepNickDraft) && nick.value !== prevUsername
  if (!hasNickDraft) nick.value = me.username
  if (me.id !== prevUserId || me.username !== prevUsername) resetNicknameHistory()
}

function themeOptionStyle(color: ProfileThemeColor): Record<string, string> {
  return buildProfileThemeBgStyle(color)
}

function themeIconSrc(icon: ProfileThemeIcon): string | null {
  return getProfileThemeIconSrc(icon)
}

function pickProfileTheme(color: ProfileThemeColor) {
  if (themeSaveBusy.value || isBanned.value) return
  selectedProfileThemeColor.value = color
}

function pickProfileThemeIcon(icon: ProfileThemeIcon) {
  if (themeSaveBusy.value || isBanned.value) return
  selectedProfileThemeIcon.value = icon
}

async function loadMe(options: { keepNickDraft?: boolean } = {}) {
  const { data } = await api.get('/users/profile_info')
  applyMePayload(data, { keepNickDraft: options.keepNickDraft })
  userStore.applyProfile(data)
}

async function loadSanctions(force = false) {
  if (sanctionsLoading.value) return
  if (sanctionsLoaded.value && !force) return
  sanctionsLoading.value = true
  sanctionsError.value = ''
  try {
    const { data } = await api.get<{ items: SanctionItem[] }>('/users/sanctions')
    sanctions.value = Array.isArray(data?.items) ? data.items : []
    sanctionsLoaded.value = true
  } catch {
    sanctionsError.value = 'Не удалось загрузить историю ограничений'
  } finally {
    sanctionsLoading.value = false
  }
}

function paymentMonths(raw: unknown): number {
  const value = Number(raw)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.trunc(value))
}

function paymentMonthWord(value: number): string {
  const mod100 = value % 100
  const mod10 = value % 10
  if (mod100 >= 11 && mod100 <= 14) return 'месяцев'
  if (mod10 === 1) return 'месяц'
  if (mod10 >= 2 && mod10 <= 4) return 'месяца'
  return 'месяцев'
}

function formatPaymentPaidAt(value: string): string {
  return formatLocalDateTime(value, PAYMENT_DATE_OPTIONS)
}

function formatPaymentSubscriptionTerm(item: SubscriptionPaymentItem): string {
  if (item.plan === 'month') return '1 месяц'
  if (item.plan === 'year') return '1 год'

  const months = paymentMonths(item.subscription_months)
  if (months <= 0) return '-'
  return `${months} ${paymentMonthWord(months)}`
}

function formatPaymentMoney(amountRaw?: string | null, currencyRaw?: string | null): string {
  const amountText = String(amountRaw || '').trim()
  if (!amountText) return '-'

  const currency = String(currencyRaw || '').trim().toUpperCase()
  const value = Number(amountText)
  if (Number.isFinite(value) && /^[A-Z]{3}$/.test(currency)) {
    try {
      return new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      }).format(value)
    } catch {
      return `${amountText} ${currency}`.trim()
    }
  }

  return `${amountText} ${currency}`.trim()
}

function formatPaymentPromoDiscount(valueRaw?: number | null): string {
  const value = Number(valueRaw)
  if (!Number.isFinite(value) || value <= 0) return 'нет'

  const formatted = new Intl.NumberFormat('ru-RU', {
    maximumFractionDigits: 2,
  }).format(value)
  return `${formatted}%`
}

async function loadPayments(force = false): Promise<void> {
  if (paymentsLoading.value) return
  if (paymentsLoaded.value && !force) return
  const seq = ++paymentsRequestSeq
  paymentsLoading.value = true
  paymentsError.value = ''
  try {
    const { data } = await api.get<SubscriptionPaymentsResponse>('/users/payments/subscriptions')
    if (seq !== paymentsRequestSeq) return
    paymentsItems.value = Array.isArray(data?.items) ? data.items : []
    paymentsLoaded.value = true
  } catch {
    if (seq !== paymentsRequestSeq) return
    paymentsItems.value = []
    paymentsError.value = 'Не удалось загрузить платежи'
  } finally {
    if (seq === paymentsRequestSeq) paymentsLoading.value = false
  }
}

async function loadBlacklist(): Promise<void> {
  if (blacklistLoading.value) return
  blacklistLoading.value = true
  blacklistError.value = ''
  try {
    await friendsStore.fetchBlacklist()
  } catch (e: any) {
    const detail = String(e?.response?.data?.detail || '').trim()
    if (detail === 'subscription_required') {
      blacklistError.value = ''
      return
    }
    blacklistError.value = 'Не удалось загрузить черный список'
  } finally {
    blacklistLoading.value = false
  }
}

function blacklistAvatarKey(item: BlacklistItem): string {
  const name = String(item.avatar_name || '').trim()
  if (!name) return ''
  return name.startsWith('avatars/') ? name : `avatars/${name}`
}

async function removeFromBlacklistProfile(item: BlacklistItem): Promise<void> {
  const uid = Number(item?.id || 0)
  if (!Number.isFinite(uid) || uid <= 0 || blacklistRemoving[Math.trunc(uid)]) return
  const userLabel = item.username || `user${Math.trunc(uid)}`
  const ok = await confirmDialog({
    title: 'Удалить из Черного списка',
    text: `Вы уверены, что хотите удалить пользователя ${userLabel} из ЧС?`,
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  const id = Math.trunc(uid)
  blacklistRemoving[id] = true
  try {
    await friendsStore.removeFromBlacklist(id)
  } catch (e: any) {
    const detail = String(e?.response?.data?.detail || '').trim()
    if (detail === 'subscription_required') {
      void loadMe({ keepNickDraft: true }).catch(() => {})
      void alertDialog('Черный список доступен только при активной подписке')
    } else {
      void alertDialog('Не удалось удалить пользователя из ЧС')
    }
  } finally {
    delete blacklistRemoving[id]
  }
}

function normalizeNicknameHistoryItems(items: string[] | null | undefined): string[] {
  return Array.isArray(items)
    ? items.map((item) => String(item || '').trim()).filter(Boolean)
    : []
}

function resetNicknameHistory() {
  nicknameHistorySeq += 1
  nicknameHistoryLoading.value = false
  nicknameHistoryError.value = ''
  nicknameHistoryItems.value = []
  nicknameHistoryLoaded.value = false
}

async function loadNicknameHistory(force = false) {
  if (me.id <= 0 || nicknameHistoryLoading.value) return
  if (nicknameHistoryLoaded.value && !force) return

  const seq = ++nicknameHistorySeq
  nicknameHistoryLoading.value = true
  nicknameHistoryError.value = ''
  try {
    const { data } = await api.get<NicknameHistoryResponse>(`/users/${me.id}/nickname_history`)
    if (seq !== nicknameHistorySeq) return
    nicknameHistoryItems.value = normalizeNicknameHistoryItems(data?.items)
    nicknameHistoryLoaded.value = true
  } catch {
    if (seq !== nicknameHistorySeq) return
    nicknameHistoryError.value = 'Не удалось загрузить историю'
  } finally {
    if (seq === nicknameHistorySeq) nicknameHistoryLoading.value = false
  }
}

async function clearNicknameHistory() {
  if (nicknameHistoryClearDisabled.value) return
  if (!nicknameHistoryHasDeletableItems.value) {
    void alertDialog('История никнеймов уже пуста')
    return
  }

  const ok = await confirmDialog({
    title: 'Очистить историю никнеймов',
    text: 'Вы уверены, что хотите очистить историю никнеймов, оставив только текущий никнейм?',
    confirmText: 'Подтвердить',
    cancelText: 'Отмена',
  })
  if (!ok) return

  nicknameHistoryClearBusy.value = true
  try {
    const { data } = await api.delete<NicknameHistoryResponse>('/users/nickname_history')
    nicknameHistoryItems.value = normalizeNicknameHistoryItems(data?.items)
    nicknameHistoryLoaded.value = true
    void alertDialog('История никнеймов успешно очищена')
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 403 && d === 'subscription_required') {
      void loadMe({ keepNickDraft: true }).catch(() => {})
      void alertDialog('Очистка истории никнеймов доступна только при активной подписке')
    } else if (st === 403 && d === 'user_banned') {
      void alertDialog('Аккаунт забанен. Очистка истории никнеймов недоступна')
    } else if (st === 403 && d === 'user_deleted') {
      void alertDialog('Аккаунт удален. Очистка истории никнеймов недоступна')
    } else {
      void alertDialog('Не удалось очистить историю никнеймов')
    }
  } finally {
    nicknameHistoryClearBusy.value = false
  }
}

async function saveNick() {
  if (saveNickDisabled.value) return
  busyNick.value = true
  try {
    const { data } = await api.patch('/users/username', { username: nick.value })
    me.username = data.username
    me.nickname_changes_left = normalizeNicknameChangesLeft(data?.nickname_changes_left)
    userStore.setUsername(data.username)
    userStore.setNicknameChangesLeft(me.nickname_changes_left)
    resetNicknameHistory()
    try { await refreshAccessTokenFull(false) } catch {}
  } catch (e: any) {
    const st = e?.response?.status
    const d  = e?.response?.data?.detail
    const moderationText = formatModerationAlert(d)
    if (st === 409 && d === 'username_taken')               void alertDialog('Данный никнейм уже занят')
    else if (st === 403 && d === 'user_banned')             void alertDialog('Аккаунт забанен. Изменение никнейма недоступно')
    else if (st === 403 && d === 'nickname_change_limit_exhausted') {
      me.nickname_changes_left = 0
      userStore.setNicknameChangesLeft(0)
      void alertDialog('Лимит изменений никнейма исчерпан')
    }
    else if (st === 422 && moderationText)                  void alertDialog({ title: 'Отказ в сохранении', text: moderationText })
    else if (st === 422 && d === 'invalid_username_format') void alertDialog('Никнейм не должен начинаться с deleted_ или user_ и не должен содержать символы кроме ()._-')
    else                                                    void alertDialog('Не удалось сохранить никнейм')
  } finally { busyNick.value = false }
}

async function saveProfileTheme() {
  if (themeSaveDisabled.value) return
  themeSaveBusy.value = true
  try {
    const { data } = await api.patch('/users/profile_theme', {
      color: selectedProfileThemeColor.value,
      icon: selectedProfileThemeIcon.value,
    })
    applyProfileThemePayload(data)
    return void alertDialog('Оформление профиля сохранено')
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 403 && d === 'subscription_required') return void alertDialog('Выбор оформления доступен только при активной подписке')
    if (st === 403 && d === 'user_banned') return void alertDialog('Аккаунт забанен. Изменение оформления профиля недоступно')
    if (st === 422 && d === 'profile_theme_invalid') return void alertDialog('Выбран недопустимый цвет профиля')
    if (st === 422 && d === 'profile_theme_icon_invalid') return void alertDialog('Выбрана недопустимая иконка профиля')
    void alertDialog('Не удалось сохранить оформление профиля')
  } finally {
    themeSaveBusy.value = false
  }
}

function openSubscriptionModal() {
  subscriptionModalOpen.value = true
}

function onSubscriptionPaymentSelect(site: { id: string; name: string; url: string }) {
  if (site.id === 'lava') return
  void api.post('/users/support_link_click', {
    source: 'profile_theme',
    site_id: site.id,
    site_name: site.name,
    url: site.url,
  }).catch(() => {})
}

async function changePassword() {
  if (!canChangePassword.value || pwdBusy.value) return
  pwdBusy.value = true
  try {
    await api.patch('/users/password', {
      current_password: pwd.current,
      new_password: pwd.next,
    })
    pwd.current = ''
    pwd.next = ''
    pwd.confirm = ''
    await userStore.fetchMe?.()
    void alertDialog('Пароль обновлен')
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 401 && d === 'invalid_credentials') void alertDialog('Текущий пароль неверный')
    else if (st === 403 && d === 'password_not_set') void alertDialog('Пароль не установлен. Восстановите его через TG-бота.')
    else if (st === 403 && d === 'user_deleted') void alertDialog('Аккаунт удален')
    else if (st === 422 && d === 'invalid_password') void alertDialog('Пароль должен быть от 8 до 32 символов и без пробелов')
    else void alertDialog('Не удалось изменить пароль')
  } finally { pwdBusy.value = false }
}

async function unlinkTelegram() {
  if (!telegramVerified.value || unlinkTgBusy.value) return
  const ok = await confirmDialog({
    title: 'Отвязать TG-аккаунт',
    text: 'Вы уверены, что хотите отвязать Telegram-аккаунт? После отвязки верификация будет снята.',
    confirmText: 'Подтвердить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  unlinkTgBusy.value = true
  try {
    await api.post('/users/unverify')
    userStore.setTelegramVerified(false)
    await loadMe({ keepNickDraft: true })
    void alertDialog('TG-аккаунт отвязан. Верификация снята.')
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 403 && d === 'sanction_active') void alertDialog('Нельзя отвязать TG-аккаунт, пока действует наказание.')
    if (st === 403 && d === 'user_deleted') void alertDialog('Аккаунт удален')
    else void alertDialog('Не удалось отвязать TG-аккаунт')
  } finally {
    unlinkTgBusy.value = false
  }
}

async function deleteAccount() {
  if (deleteBusy.value || isDeleteAccountForbiddenSelf.value) return
  const ok = await confirmDialog({
    title: 'Удаление аккаунта',
    text: 'Вы уверены, что хотите навсегда удалить аккаунт?',
    confirmText: 'Подтвердить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  deleteBusy.value = true
  try {
    await api.delete('/users/account')
    await auth.logout()
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 403 && (d === 'protected_user' || d === 'staff_self_delete_forbidden')) {
      void alertDialog('Модераторам и администраторам нельзя удалять свой аккаунт')
    } else {
      void alertDialog('Не удалось удалить аккаунт')
    }
  } finally {
    deleteBusy.value = false
  }
}

function formatSanctionKind(kind: SanctionItem['kind']): string {
  if (kind === 'timeout') return 'Таймаут'
  if (kind === 'suspend') return 'Отстранение'
  if (kind === 'ban') return 'Бан'
  return kind
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

function isSanctionCompleted(item: SanctionItem): boolean {
  return item.completion_reason !== 'active'
}

function formatSanctionFinishedAt(item: SanctionItem): string {
  if (!isSanctionCompleted(item) || !item.finished_at) return '-'
  return formatLocalDateTime(item.finished_at)
}

function formatSanctionCompletionReason(item: SanctionItem): string {
  if (item.completion_reason === 'expired') return 'Истекла'
  if (item.completion_reason === 'revoked_staff') return 'Досрочное снятие'
  if (item.completion_reason === 'hosted_game') return 'Проведение игры'
  return '-'
}

type Crop = {
  show: boolean
  img?: HTMLImageElement
  scale: number
  min: number
  max: number
  x: number
  y: number
  dragging: boolean
  sx: number
  sy: number
  type: 'image/jpeg'|'image/png'
}
const crop = reactive<Crop>({ show: false, scale: 1, min: 0.5, max: 3, x: 0, y: 0, dragging: false, sx: 0, sy: 0, type: 'image/jpeg' })
const canvasEl = ref<HTMLCanvasElement | null>(null)

type GifPicker = {
  show: boolean
  file?: File
  animatedUrl: string
  frameCount: number
  frameIndex: number
  loading: boolean
  decoding: boolean
  error: string
}
const gifPicker = reactive<GifPicker>({
  show: false,
  animatedUrl: '',
  frameCount: 1,
  frameIndex: 0,
  loading: false,
  decoding: false,
  error: '',
})
const gifModalEl = ref<HTMLDivElement | null>(null)
const gifCanvasEl = ref<HTMLCanvasElement | null>(null)
let gifDecoder: any = null
let gifDecodeSeq = 0

const busyAva = ref(false)
const deleteBusy = ref(false)

function setProfileModalEl(el: HTMLDivElement | null) {
  modalEl.value = el
}

function setProfileCanvasEl(el: HTMLCanvasElement | null) {
  canvasEl.value = el
}

function setProfileGifModalEl(el: HTMLDivElement | null) {
  gifModalEl.value = el
}

function setProfileGifCanvasEl(el: HTMLCanvasElement | null) {
  gifCanvasEl.value = el
}

function clamp(v:number, lo:number, hi:number) { return Math.min(hi, Math.max(lo, v)) }

function fitContain(imgW: number, imgH: number, boxW: number, boxH: number) {
  return Math.min(boxW / imgW, boxH / imgH)
}

function cropCanvasDisplaySize(): number {
  return window.matchMedia(CROP_CANVAS_MOBILE_QUERY).matches
    ? CROP_CANVAS_MOBILE_SIZE
    : CROP_CANVAS_DESKTOP_SIZE
}

function gifCanvasDisplaySize(canvas: HTMLCanvasElement): number {
  canvas.style.width = ''
  canvas.style.height = ''
  const cssWidth = Number.parseFloat(window.getComputedStyle(canvas).width)
  return Number.isFinite(cssWidth) && cssWidth > 0 ? Math.round(cssWidth) : 300
}

const gifFrameLabel = computed(() => `${gifPicker.frameIndex + 1}/${Math.max(1, gifPicker.frameCount)}`)

function scaleTo(next: number) {
  if (!crop.img || !canvasEl.value) return
  const c = canvasEl.value!
  const Cx = c.width / 2, Cy = c.height / 2
  const u = (Cx - crop.x) / crop.scale
  const v = (Cy - crop.y) / crop.scale
  crop.scale = next
  crop.x = Cx - u * next
  crop.y = Cy - v * next
  clampPosition()
  redraw()
}

function closeGifDecoder() {
  try { gifDecoder?.close?.() } catch {}
  gifDecoder = null
}

function resetGifPicker() {
  closeGifDecoder()
  gifDecodeSeq += 1
  if (gifPicker.animatedUrl) {
    try { URL.revokeObjectURL(gifPicker.animatedUrl) } catch {}
  }
  gifPicker.show = false
  gifPicker.file = undefined
  gifPicker.animatedUrl = ''
  gifPicker.frameCount = 1
  gifPicker.frameIndex = 0
  gifPicker.loading = false
  gifPicker.decoding = false
  gifPicker.error = ''
}

function cancelGifPicker() {
  resetGifPicker()
  document.body.style.overflow = ''
}

async function drawGifFrame(frameIndex: number) {
  const decoder = gifDecoder
  if (!decoder || !gifCanvasEl.value) return
  const seq = ++gifDecodeSeq
  gifPicker.decoding = true
  try {
    const decoded = await decoder.decode({ frameIndex })
    const image = decoded?.image
    if (!image) throw new Error('decode_failed')
    if (seq !== gifDecodeSeq) {
      try { image.close?.() } catch {}
      return
    }

    const canvas = gifCanvasEl.value
    const dpr = Math.max(1, window.devicePixelRatio || 1)
    const size = gifCanvasDisplaySize(canvas)
    canvas.width = Math.round(size * dpr)
    canvas.height = Math.round(size * dpr)

    const width = Number(image.displayWidth || image.codedWidth || image.width || 1)
    const height = Number(image.displayHeight || image.codedHeight || image.height || 1)
    const scale = Math.min(canvas.width / width, canvas.height / height)
    const drawW = width * scale
    const drawH = height * scale
    const dx = (canvas.width - drawW) / 2
    const dy = (canvas.height - drawH) / 2
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.fillStyle = '#000'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.imageSmoothingEnabled = true
    ctx.imageSmoothingQuality = 'high' as any
    ctx.drawImage(image as CanvasImageSource, dx, dy, drawW, drawH)
    try { image.close?.() } catch {}
  } catch {
    if (seq === gifDecodeSeq) gifPicker.error = 'Не удалось показать выбранный кадр GIF'
  } finally {
    if (seq === gifDecodeSeq) gifPicker.decoding = false
  }
}

async function openGifFramePicker(file: File) {
  const ImageDecoderCtor = (window as any).ImageDecoder
  if (!ImageDecoderCtor) {
    await alertDialog('В этом браузере недоступен выбор кадра GIF. Будет использован первый кадр.')
    await uploadAvatarFile(file, 0)
    return
  }

  resetGifPicker()
  gifPicker.file = file
  gifPicker.animatedUrl = URL.createObjectURL(file)
  gifPicker.show = true
  gifPicker.loading = true
  document.body.style.overflow = 'hidden'
  await nextTick()
  gifModalEl.value?.focus()

  try {
    const buffer = await file.arrayBuffer()
    const decoder = new ImageDecoderCtor({ data: buffer, type: file.type || ANIMATED_AVATAR_TYPE })
    if (decoder.tracks?.ready) await decoder.tracks.ready
    const track = decoder.tracks?.selectedTrack
    const frameCountRaw = Number(track?.frameCount || 1)
    if (!Number.isFinite(frameCountRaw) || frameCountRaw <= 0) throw new Error('bad_frame_count')
    if (frameCountRaw > MAX_AVATAR_GIF_FRAMES) throw new Error('too_many_frames')
    gifDecoder = decoder
    gifPicker.frameCount = Math.max(1, Math.trunc(frameCountRaw))
    gifPicker.frameIndex = 0
    gifPicker.loading = false
    await nextTick()
    await drawGifFrame(0)
  } catch (e: any) {
    closeGifDecoder()
    gifPicker.loading = false
    gifPicker.error = e?.message === 'too_many_frames'
      ? `В GIF больше ${MAX_AVATAR_GIF_FRAMES} кадров`
      : 'Не удалось прочитать кадры GIF'
  }
}

function onGifFrameRange(value: number) {
  const next = clamp(Math.trunc(Number(value)), 0, Math.max(0, gifPicker.frameCount - 1))
  gifPicker.frameIndex = next
  void drawGifFrame(next)
}

async function applyGifPicker() {
  if (!gifPicker.file || gifPicker.loading || gifPicker.decoding || gifPicker.error) return
  const ok = await uploadAvatarFile(gifPicker.file, gifPicker.frameIndex)
  if (ok) cancelGifPicker()
}

async function onPick(e: Event) {
  if (isBanned.value) return
  const f = (e.target as HTMLInputElement).files?.[0]
  ;(e.target as HTMLInputElement).value = ''
  if (!f) return
  if (!STATIC_AVATAR_TYPES.has(f.type) && f.type !== ANIMATED_AVATAR_TYPE) {
    void alertDialog('К загрузке допустимы только форматы JPG/PNG/GIF')
    return
  }
  if (f.size > AVATAR_MAX_BYTES) {
    void alertDialog('К загрузке допустимы только файлы менее 5 Мбайт')
    return
  }
  if (f.type === ANIMATED_AVATAR_TYPE) {
    if (!canUseAnimatedAvatar.value) {
      void alertDialog('GIF-аватары доступны только при активной подписке')
      return
    }
    await openGifFramePicker(f)
    return
  }
  const url = URL.createObjectURL(f)
  const img = new Image()
  img.onload = async () => {
    URL.revokeObjectURL(url)
    crop.img = img
    crop.type = (f.type === 'image/png' ? 'image/png' : 'image/jpeg')
    crop.show = true
    await nextTick()
    modalEl.value?.focus()
    document.body.style.overflow = 'hidden'
    const canvas = canvasEl.value!
    const dpr = Math.max(1, window.devicePixelRatio || 1)
    const S = cropCanvasDisplaySize()
    canvas.width = Math.round(S * dpr)
    canvas.height = Math.round(S * dpr)
    canvas.style.width = S + 'px'
    canvas.style.height = S + 'px'
    const s = fitContain(img.width, img.height, canvas.width, canvas.height)
    crop.min = s
    crop.max = s * 3
    crop.scale = s
    crop.x = (canvas.width - img.width * s) / 2
    crop.y = (canvas.height - img.height * s) / 2
    clampPosition()
    requestAnimationFrame(redraw)
  }
  img.onerror = () => {
    URL.revokeObjectURL(url)
    void alertDialog('Не удалось открыть изображение')
  }
  img.src = url
}

function redraw() {
  const c = canvasEl.value
  const img = crop.img
  if (!c || !img) return
  const ctx = c.getContext('2d')!
  ctx.clearRect(0,0,c.width,c.height)
  ctx.fillStyle = '#000'
  ctx.fillRect(0,0,c.width,c.height)
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high' as any
  ctx.drawImage(img, crop.x, crop.y, img.width * crop.scale, img.height * crop.scale)
}

function clampPosition() {
  const c = canvasEl.value!, img = crop.img!
  const w = img.width * crop.scale, h = img.height * crop.scale
  crop.x = w <= c.width  ? (c.width - w)/2  : Math.min(0, Math.max(c.width - w, crop.x))
  crop.y = h <= c.height ? (c.height - h)/2 : Math.min(0, Math.max(c.height - h, crop.y))
}

function dragStart(ev: MouseEvent) {
  crop.dragging = true
  crop.sx = ev.clientX - crop.x
  crop.sy = ev.clientY - crop.y
}

function dragMove(ev: MouseEvent) {
  if (!crop.dragging) return
  crop.x = ev.clientX - crop.sx
  crop.y = ev.clientY - crop.sy
  clampPosition()
  redraw()
}

function dragStop() {
  crop.dragging = false
}

function onWheel(ev: WheelEvent) {
  const dir = ev.deltaY > 0 ? -1 : 1
  const next = Math.min(crop.max, Math.max(crop.min, crop.scale * (1 + dir * 0.04)))
  if (next === crop.scale) return
  scaleTo(next)
}

function cancelCrop() {
  crop.show = false
  crop.img = undefined
  document.body.style.overflow = ''
}

function showAvatarUploadError(e: any) {
  const st = e?.response?.status
  const d  = e?.response?.data?.detail
  if (st === 403 && d === 'user_banned')                 void alertDialog('Аккаунт забанен. Изменение аватара недоступно')
  else if (st === 403 && d === 'subscription_required')  void alertDialog('GIF-аватары доступны только при активной подписке')
  else if (st === 415 || d === 'unsupported_media_type') void alertDialog('К загрузке допустимы только форматы JPG/PNG/GIF')
  else if (st === 413)                                   void alertDialog('К загрузке допустимы только файлы менее 5 Мбайт')
  else if (st === 422 && d === 'empty_file')             void alertDialog('Не удалось прочитать файл')
  else if (st === 422 && d === 'bad_image')              void alertDialog('Некорректное изображение')
  else                                                   void alertDialog('Не удалось загрузить аватар')
}

async function uploadAvatarFile(file: File, staticFrameIndex?: number): Promise<boolean> {
  busyAva.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    if (typeof staticFrameIndex === 'number') fd.append('static_frame_index', String(Math.max(0, Math.trunc(staticFrameIndex))))
    const { data } = await api.post('/users/avatar', fd)
    me.avatar_name = data.avatar_name || null
    userStore.setAvatarName(me.avatar_name)
    return true
  } catch (e: any) {
    showAvatarUploadError(e)
    return false
  } finally {
    busyAva.value = false
  }
}

async function applyCrop() {
  if (!canvasEl.value) return
  busyAva.value = true
  try {
    const OUT = 512
    const dpr = 1
    const src = canvasEl.value
    const tmp = document.createElement('canvas')
    tmp.width = OUT * dpr
    tmp.height = OUT * dpr
    const tctx = tmp.getContext('2d')!
    const img = crop.img!
    tctx.imageSmoothingEnabled = true
    tctx.imageSmoothingQuality = 'high' as any
    const k = (tmp.width / src.width)
    tctx.drawImage(img, crop.x * k, crop.y * k, img.width * crop.scale * k, img.height * crop.scale * k)
    const blob: Blob = await new Promise((res, rej) => tmp.toBlob(b => b ? res(b) : rej(new Error('toBlob')), crop.type === 'image/png' ? 'image/png' : 'image/jpeg', 0.92))
    if (blob.size > AVATAR_MAX_BYTES) {
      void alertDialog('Получившийся файл оказался больше 5 Мбайт')
      return
    }
    const fd = new FormData()
    fd.append('file', new File([blob], crop.type === 'image/png' ? 'avatar.png' : 'avatar.jpg', { type: crop.type }))
    const { data } = await api.post('/users/avatar', fd)
    me.avatar_name = data.avatar_name || null
    userStore.setAvatarName(me.avatar_name)
    cancelCrop()
  } catch (e: any) {
    showAvatarUploadError(e)
  } finally { busyAva.value = false }
}

async function onDeleteAvatar() {
  const ok = await confirmDialog({
    title: 'Удаление аватара',
    text: 'Вы уверены, что хотите удалить аватар?',
    confirmText: 'Подтвердить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  busyAva.value = true
  try {
    await api.delete('/users/avatar')
    me.avatar_name = null
    userStore.setAvatarName(null)
  }
  catch (e: any) {
    const st = e?.response?.status
    const d  = e?.response?.data?.detail
    if (st === 403 && d === 'user_banned') void alertDialog('Аккаунт забанен. Изменение аватара недоступно')
    else void alertDialog('Не удалось удалить аватар')
  }
  finally { busyAva.value = false }
}

function sanitizeUsername(s: string, max = NICK_MAX): string {
  return (s ?? "").normalize("NFKC").trim().slice(0, max)
}

watch(nick, (v) => {
  const clean = sanitizeUsername(v, NICK_MAX)
  if (v !== clean) nick.value = clean
})

function resolveProfileTabAccess(tab: TabKey): TabKey {
  return profileTabsDisabled.value && tab !== 'account' ? 'account' : tab
}

watch(() => route.query.tab, (tab) => {
  const next = resolveProfileTabAccess(normalizeTab(tab))
  if (next !== activeTab.value) activeTab.value = next
})

watch(profileTabsDisabled, disabled => {
  if (disabled && activeTab.value !== 'account') activeTab.value = 'account'
}, { immediate: true })

watch(canEditProfileTheme, () => {
  if (activeTab.value === 'blacklist') void loadBlacklist()
})

watch(activeTab, (tab) => {
  if (profileTabsDisabled.value && tab !== 'account') {
    activeTab.value = 'account'
    return
  }
  if (normalizeTab(route.query.tab) !== tab) {
    router.replace({ query: { ...route.query, tab } }).catch(() => {})
  }
  if (tab === 'sanctions') {
    void loadSanctions(true)
    return
  }
  if (tab === 'payments') {
    void loadPayments(true)
    return
  }
  if (tab === 'blacklist') {
    void loadBlacklist()
    return
  }
  if (isProfileSettingsTab(tab)) void loadMe({ keepNickDraft: true })
})

onMounted(async () => {
  try { await loadMe() } catch {}
  const requestedTab = resolveProfileTabAccess(normalizeTab(route.query.tab))
  if (typeof route.query.tab === 'string' && requestedTab !== activeTab.value) {
    Promise.resolve().then(() => {
      activeTab.value = requestedTab
    })
  } else if (activeTab.value === 'sanctions') {
    void loadSanctions(true)
  } else if (activeTab.value === 'payments') {
    void loadPayments(true)
  } else if (activeTab.value === 'blacklist') {
    void loadBlacklist()
  }
  friendsStore.ensureWS()
  onSanctionsUpdate = () => {
    if (activeTab.value === 'sanctions') void loadSanctions(true)
  }
  window.addEventListener('auth-sanctions_update', onSanctionsUpdate)
  onProfileSync = (e: Event) => {
    const payload = (e as CustomEvent)?.detail
    if (!payload) return
    applyMePayload(payload, { keepNickDraft: true })
  }
  window.addEventListener('auth-profile_sync', onProfileSync)
})

onBeforeUnmount(() => {
  if (onSanctionsUpdate) window.removeEventListener('auth-sanctions_update', onSanctionsUpdate)
  if (onProfileSync) window.removeEventListener('auth-profile_sync', onProfileSync)
  paymentsRequestSeq += 1
  resetGifPicker()
  document.body.style.overflow = ''
})
</script>

<style scoped lang="scss">
.profile {
  display: flex;
  padding: 40px 40px 10px;
  gap: 10px;
  height: 100%;
  overflow: auto;
  scrollbar-width: none;
  header {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    .tab-div {
      display: flex;
      flex-direction: column;
      gap: 4px;
      .tab-btn {
        display: flex;
        position: relative;
        align-items: center;
        padding: 0 16px;
        gap: 4px;
        width: 266px;
        height: 40px;
        border: none;
        border-radius: 12px;
        background: transparent;
        text-decoration: none;
        cursor: pointer;
        overflow: hidden;
        transition: opacity 0.25s ease-in-out;
        &::before {
          content: '';
          position: absolute;
          inset: 0;
          border-radius: inherit;
          background: linear-gradient(261deg, $soft-purple-800 0%, $green-700 100%);
          opacity: 0;
          transition: opacity 0.25s ease-in-out;
          z-index: 0;
        }
        .tab-btn-img {
          position: relative;
          --ui-icon-width: 24px;
          --ui-icon-height: 24px;
          --ui-icon-color: #{$neutral-500};
          z-index: 1;
        }
        .tab-btn-text {
          position: relative;
          color: $neutral-500;
          font-family: Hauora-Regular;
          font-size: 18px;
          line-height: 20px;
          letter-spacing: -0.36px;
          transition: color 0.25s ease-in-out;
          z-index: 1;
        }
        &:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        &:not(:disabled):hover,
        &:not(:disabled):focus-visible,
        &:not(:disabled):active {
          .tab-btn-img {
            --ui-icon-color: #{$neutral-white};
          }
          .tab-btn-text {
            color: $neutral-white;
          }
        }
        &.active {
          &::before {
            opacity: 1;
          }
          .tab-btn-img {
            --ui-icon-color: #{$neutral-white};
          }
          .tab-btn-text {
            color: $neutral-white;
          }
        }
      }
      .tab-div-line {
        margin: 12px 0;
        width: 100%;
        border-bottom: 1px solid $neutral-600;
      }
      .tabs {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .tab-subscribe {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
    }
  }
  .tab-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
}

.tab-fade-enter-active,
.tab-fade-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.tab-fade-enter-from,
.tab-fade-leave-to {
  opacity: 0;
}

</style>
