<template>
  <section class="profile">
    <header>
      <nav class="tabs" aria-label="Личный кабинет" role="tablist">
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'profile' }" :aria-selected="activeTab === 'profile'" @click="activeTab = 'profile'">
          Профиль
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'stats' }" :aria-selected="activeTab === 'stats'" @click="activeTab = 'stats'">
          Статистика
        </button>
        <button v-if="showHistoryTab" class="tab" type="button" role="tab" :class="{ active: activeTab === 'history' }" :aria-selected="activeTab === 'history'" @click="activeTab = 'history'">
          История игр
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'sanctions' }" :aria-selected="activeTab === 'sanctions'" @click="activeTab = 'sanctions'">
          Санкции
        </button>
      </nav>
      <router-link class="btn nav" :to="{ name: 'home' }" aria-label="На главную">На главную</router-link>
    </header>

    <Transition name="tab-fade" mode="out-in">
      <div :key="activeTab" class="tab-panel">
        <div v-if="activeTab === 'profile'" class="grid">
          <div class="block avatar-block">
            <h3>Аватар и Никнейм</h3>
            <div class="avatar-row">
              <img class="avatar-img" v-minio-img="{ key: me.avatar_name ? `avatars/${me.avatar_name}` : '', placeholder: defaultAvatar, lazy: false, animated: true }" alt="Текущий аватар" />
              <div class="actions">
                <input ref="fileEl" type="file" :accept="avatarAccept" @change="onPick" :disabled="isBanned" hidden />
                <button class="btn dark" @click="fileEl?.click()" :disabled="busyAva || isBanned">
                  <img class="btn-img" :src="iconEdit" alt="edit" />
                  {{ me.avatar_name ? 'Изменить' : 'Загрузить' }}
                </button>
                <span class="hint center">{{ avatarFormatHint }}</span>
                <button class="btn danger" v-if="me.avatar_name" @click="onDeleteAvatar" :disabled="busyAva || isBanned">
                  <img class="btn-img" :src="iconDelete" alt="delete" />
                  Удалить
                </button>
              </div>
            </div>

            <div class="nick-row">
              <div class="nick-input-line">
                <UiInput class="profile-input" id="profile-nick" v-model.trim="nick" :maxlength="NICK_MAX" :disabled="busyNick || isBanned || isProtectedAdminSelf" autocomplete="off" inputmode="text" label="Никнейм"
                  :invalid="!!nick && !validNick" :aria-invalid="!!nick && !validNick" aria-describedby="profile-nick-hint" >
                  <template #meta>
                    <span id="profile-nick-hint">{{ nick.length }}/{{ NICK_MAX }}</span>
                  </template>
                </UiInput>
                <div v-if="me.id > 0" class="nickname-history-tooltip-wrap" tabindex="0" aria-label="История никнеймов" @mouseenter="loadNicknameHistory()" @focusin="loadNicknameHistory()">
                  <img class="nickname-history-icon" :src="iconTimeHistory" alt="" />
                  <div class="nickname-history-tooltip" role="tooltip" @click.stop>
                    <button class="btn danger nickname-history-clear" type="button" :disabled="nicknameHistoryClearDisabled" @click="clearNicknameHistory">
                      {{ nicknameHistoryClearBusy ? '...' : 'Очистить историю' }}
                    </button>
                    <span class="nickname-history-access-text" :class="{ disabled: !canEditProfileTheme }">{{ nicknameHistoryAccessText }}</span>
                    <span class="nickname-history-divider" aria-hidden="true"></span>
                    <span v-if="nicknameHistoryLoading" class="nickname-history-state">Загрузка...</span>
                    <span v-else-if="nicknameHistoryError" class="nickname-history-state danger">{{ nicknameHistoryError }}</span>
                    <span v-else class="nickname-history-list">
                      <span v-for="(nicknameItem, index) in nicknameHistoryItems" :key="`${nicknameItem}-${index}`" :class="{ current: index === 0 }">
                        {{ nicknameItem }}
                      </span>
                      <span v-if="!nicknameHistoryItems.length" class="nickname-history-state">-</span>
                    </span>
                  </div>
                </div>
              </div>
              <span class="hint"><code>латиница, кириллица, цифры, символы ()._-</code></span>
              <span class="hint" :class="{ red: nicknameChangesLeft <= 0 }">Осталось изменений никнейма: {{ nicknameChangesLeft }}</span>
              <button class="btn confirm" @click="saveNick" :disabled="saveNickDisabled">
                <img class="btn-img" :src="iconSave" alt="save" />
                {{ busyNick ? '...' : 'Сохранить' }}
              </button>
            </div>
            <p class="hint">Никнейм является логином для авторизации</p>
          </div>

          <div class="block theme-block">
            <h3>Оформление профиля</h3>
            <div class="theme-row">
              <div class="theme-preview-grid">
                <div class="theme-preview-card" :style="themePreviewStyle">
                  <img class="theme-preview-avatar" v-minio-img="{ key: me.avatar_name ? `avatars/${me.avatar_name}` : '', placeholder: defaultAvatar, lazy: false, animated: true }" alt="avatar" />
                  <div v-if="themePreviewIconSrcs.length" class="theme-preview-icons" aria-hidden="true">
                    <img v-for="badgeSrc in themePreviewIconSrcs" :key="badgeSrc" class="theme-preview-icon" :src="badgeSrc" alt="" />
                  </div>
                  <span>{{ me.username || 'User' }}</span>
                </div>
              </div>

              <div class="theme-palette">
                <button v-for="item in profileThemeOptions" :key="item.key" class="theme-option" type="button" :class="{ active: selectedProfileThemeColor === item.key }"
                        :style="themeOptionStyle(item.key)" :disabled="themeSaveBusy || isBanned" @click="pickProfileTheme(item.key)">
                </button>
              </div>

              <div class="theme-icon-palette">
                <button v-for="item in profileThemeIconOptions" :key="item.key" @click="pickProfileThemeIcon(item.key)"
                        class="theme-icon-option" type="button" :class="{ active: selectedProfileThemeIcon === item.key }" :disabled="themeSaveBusy || isBanned || !item.available">
                  <img v-if="themeIconSrc(item.key)" :src="themeIconSrc(item.key) || ''" alt="" aria-hidden="true" />
                  <span v-else class="theme-icon-none" aria-hidden="true"></span>
                </button>
              </div>

              <button v-if="canEditProfileTheme" class="btn confirm" @click="saveProfileTheme" :disabled="themeSaveDisabled">
                <img class="btn-img" :src="iconSave" alt="save" />
                {{ themeSaveBusy ? '...' : 'Сохранить' }}
              </button>
              <button v-else type="button" class="btn support-btn" @click="openSupportModal">
                Поддержать платформу
              </button>
            </div>
            <p class="hint">{{ profileThemeMessageText }}</p>
          </div>

          <div class="block account-block">
            <h3>Аккаунт</h3>
            <div class="verify-row">
              <p class="hint text">Дата регистрации: {{ registrationDateLabel }}</p>
              <UiSwitch
                class="profile-switch"
                :model-value="tgInvitesEnabled"
                label="Уведомления о приглашениях в TG"
                off-label="Запретить"
                on-label="Разрешить"
                :width="200"
                :disabled="tgInvitesTogglePending || !telegramVerified"
                @update:modelValue="onToggleTgInvites" />
              <button v-if="telegramVerified" class="btn danger" @click="unlinkTelegram" :disabled="unlinkTgBusy">
                {{ unlinkTgBusy ? '...' : 'Отвязать TG-аккаунт' }}
              </button>
              <a v-else-if="botName" class="btn confirm" :href="botLink" target="_blank" rel="noopener noreferrer">
                Пройти верификацию
              </a>
              <p v-if="telegramVerified" class="hint">Если отвязать TG-аккаунт верификация будет снята и вход в комнаты будет ограничен</p>
              <p v-else class="hint">В чате с ботом сначала введите никнейм, затем пароль. После успешной верификации ограничения на вход в комнаты будут сняты</p>
              <button class="btn danger" @click="deleteAccount" :disabled="deleteBusy || isDeleteAccountForbiddenSelf">
                {{ deleteBusy ? '...' : 'Удалить аккаунт' }}
              </button>
              <p class="hint red">Удаление произойдет навсегда без возможности восстановления</p>

              <div v-if="me.has_password" class="password-row">
                <p class="hint text">Пароль</p>
                <p v-if="passwordTemp" class="hint warn">У вас временный пароль — рекомендуем изменить его</p>
                <UiInput class="profile-input" id="profile-pass-current" v-model="pwd.current" type="password" autocomplete="current-password" minlength="8" maxlength="32" label="Текущий пароль"
                  :invalid="currentPasswordInvalid" :aria-invalid="currentPasswordInvalid" aria-describedby="profile-pass-current-hint">
                  <template #meta>
                    <span id="profile-pass-current-hint">{{ pwd.current.length }}/{{ PASSWORD_MAX }}</span>
                  </template>
                </UiInput>
                <UiInput class="profile-input" id="profile-pass-new" v-model="pwd.next" type="password" autocomplete="new-password" minlength="8" maxlength="32" label="Новый пароль"
                  :invalid="newPasswordInvalid" :aria-invalid="newPasswordInvalid" aria-describedby="profile-pass-new-hint">
                  <template #meta>
                    <span id="profile-pass-new-hint">{{ pwd.next.length }}/{{ PASSWORD_MAX }}</span>
                  </template>
                </UiInput>
                <UiInput class="profile-input" id="profile-pass-confirm" v-model="pwd.confirm" type="password" autocomplete="new-password" minlength="8" maxlength="32" label="Повторите пароль"
                  :invalid="confirmPasswordInvalid" :aria-invalid="confirmPasswordInvalid" aria-describedby="profile-pass-confirm-hint">
                  <template #meta>
                    <span id="profile-pass-confirm-hint">{{ pwd.confirm.length }}/{{ PASSWORD_MAX }}</span>
                  </template>
                </UiInput>
                <button class="btn confirm" @click="changePassword" :disabled="pwdBusy || !canChangePassword">
                  {{ pwdBusy ? '...' : 'Сменить пароль' }}
                </button>
                <p class="hint">
                  Сбросить пароль можно через
                  <a v-if="botName" :href="botLink" target="_blank" rel="noopener noreferrer">TG-бота</a>
                </p>
              </div>
            </div>
          </div>

          <div v-if="crop.show" ref="modalEl" class="modal" @keydown.esc="cancelCrop" tabindex="0" aria-modal="true" aria-label="Кадрирование аватара" >
            <div class="modal-body">
              <canvas ref="canvasEl" @mousedown="dragStart" @mousemove="dragMove" @mouseup="dragStop" @mouseleave="dragStop" @wheel.passive="onWheel" />
              <div class="range">
                <span>Масштаб</span>
                <UiSlider
                  :model-value="crop.scale"
                  :min="crop.min"
                  :max="crop.max"
                  :step="0.01"
                  :disabled="isBanned"
                  aria-label="Масштаб"
                  @update:modelValue="scaleTo" />
              </div>
              <div class="modal-actions">
                <button class="btn danger" @click="cancelCrop">Отменить</button>
                <button class="btn confirm" @click="applyCrop" :disabled="busyAva || isBanned">Загрузить</button>
              </div>
            </div>
          </div>

          <div v-if="gifPicker.show" ref="gifModalEl" class="modal gif-modal" @keydown.esc="cancelGifPicker" tabindex="0" aria-modal="true" aria-label="Выбор статичного кадра GIF">
            <div class="modal-body gif-modal-body">
              <div class="gif-preview-row">
                <div class="gif-preview-block">
                  <span>Анимация</span>
                  <img v-if="gifPicker.animatedUrl" :src="gifPicker.animatedUrl" alt="GIF-анимация" />
                </div>
                <div class="gif-preview-block">
                  <span>Статичный кадр</span>
                  <canvas ref="gifCanvasEl" />
                </div>
              </div>
              <p v-if="gifPicker.error" class="hint red">{{ gifPicker.error }}</p>
              <div class="range">
                <span>Кадр {{ gifFrameLabel }}</span>
                <UiSlider
                  :model-value="gifPicker.frameIndex"
                  :min="0"
                  :max="Math.max(0, gifPicker.frameCount - 1)"
                  :step="1"
                  :disabled="busyAva || isBanned || gifPicker.frameCount <= 1 || gifPicker.decoding"
                  aria-label="Кадр GIF"
                  @update:modelValue="onGifFrameRange" />
              </div>
              <div class="modal-actions">
                <button class="btn danger" @click="cancelGifPicker">Отменить</button>
                <button class="btn confirm" @click="applyGifPicker" :disabled="busyAva || isBanned || gifPicker.loading || gifPicker.decoding || !!gifPicker.error">Загрузить</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'stats'" class="grid grid-stats">
          <div class="block">
            <ProfileStats />
          </div>
        </div>

        <div v-else-if="activeTab === 'history' && showHistoryTab" class="grid grid-history">
          <div class="block history-block">
            <h3>Личная история игр</h3>
            <ProfileHistory />
          </div>
        </div>

        <div v-else-if="activeTab === 'sanctions'" class="grid grid-sanctions">
          <div class="block sanctions-block">
            <div class="sanctions-head">
              <h3>История отстранений от игр, таймаутов и банов</h3>
            </div>
            <div v-if="sanctionsLoaded" class="sanctions-summary">
              <span>Всего: {{ sanctionsSummary.total }}</span>
              <span>Таймауты: {{ sanctionsSummary.timeout }}</span>
              <span>Отстранения: {{ sanctionsSummary.suspend }}</span>
              <span>Баны: {{ sanctionsSummary.ban }}</span>
            </div>
            <div v-if="sanctionsLoading" class="sanctions-empty">Загрузка…</div>
            <div v-else-if="sanctionsError" class="sanctions-empty danger">{{ sanctionsError }}</div>
            <div v-else-if="sanctions.length === 0" class="sanctions-empty">Ограничений пока не было</div>
            <div v-else class="sanctions-list">
              <article v-for="item in sanctions" :key="item.id" class="sanction-card" :class="`sanction-card--${item.kind}`">
                <div class="sanction-head">
                  <div class="sanction-kind">
                    <span class="sanction-tag">{{ formatSanctionKind(item.kind) }}</span>
                  </div>
                </div>
                <div class="sanction-grid">
                  <div class="sanction-cell">
                    <span>Дата выдачи</span>
                    <strong>{{ formatLocalDateTime(item.issued_at) }}</strong>
                  </div>
                  <div class="sanction-cell">
                    <span>Пункт правил</span>
                    <strong>{{ item.reason || 'Причина не указана' }}</strong>
                  </div>
                  <div class="sanction-cell">
                    <span>Срок изначальный</span>
                    <strong>{{ formatSanctionDuration(item.duration_seconds) }}</strong>
                  </div>
                  <div class="sanction-cell">
                    <span>Дата снятия</span>
                    <strong>{{ formatSanctionFinishedAt(item) }}</strong>
                  </div>
                  <div class="sanction-cell">
                    <span>Причина снятия</span>
                    <strong>{{ formatSanctionCompletionReason(item) }}</strong>
                  </div>
                  <div class="sanction-cell">
                    <span>Срок по факту</span>
                    <strong>{{ formatDurationSeconds(item.served_seconds, '0м') }}</strong>
                  </div>
                  <div v-if="item.kind === 'suspend'" class="sanction-cell">
                    <span>Отработка ведущим</span>
                    <strong>{{ formatDurationSeconds(item.hosted_workoff_seconds, '0м') }}</strong>
                  </div>
                </div>
              </article>
            </div>
          </div>
        </div>

        <div v-else class="grid grid-empty">
          <!-- пока что пусто -->
        </div>
      </div>
    </Transition>
    <Donation v-model:open="supportModalOpen" @select="onSupportSiteSelect" />
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { api, refreshAccessTokenFull } from '@/services/axios'
import { useAuthStore, useSettingsStore, useUserStore } from '@/store'
import { confirmDialog, alertDialog } from '@/services/confirm'
import { formatModerationAlert } from '@/services/moderation'
import { formatLocalDateTime } from '@/services/datetime'

import ProfileStats from '@/components/ProfileStats.vue'
import ProfileHistory from '@/components/ProfileHistory.vue'
import UiSwitch from '@/components/UiSwitch.vue'
import UiInput from '@/components/UiInput.vue'
import UiSlider from '@/components/UiSlider.vue'
import Donation from '@/components/Donation.vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconSave from '@/assets/svg/save.svg'
import iconEdit from '@/assets/svg/edit.svg'
import iconDelete from '@/assets/svg/delete.svg'
import iconTimeHistory from '@/assets/svg/timeHistory.svg'
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

const userStore = useUserStore()
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
const fileEl = ref<HTMLInputElement | null>(null)
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

const TAB_KEYS = ['profile', 'stats', 'history', 'sanctions'] as const
type TabKey = typeof TAB_KEYS[number]

function normalizeTab(v: unknown): TabKey {
  if (typeof v === 'string' && (TAB_KEYS as readonly string[]).includes(v)) return v as TabKey
  return 'profile'
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

const activeTab = ref<TabKey>('profile')
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

const sanctions = ref<SanctionItem[]>([])
const sanctionsLoading = ref(false)
const sanctionsLoaded = ref(false)
const sanctionsError = ref('')
const tgInvitesTogglePending = ref(false)
const themeSaveBusy = ref(false)
const supportModalOpen = ref(false)
const telegramVerified = computed(() => userStore.telegramVerified)
const showHistoryTab = computed(() => !(settings.verificationRestrictions && !telegramVerified.value))
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
const canEditProfileTheme = computed(() => {
  if (subscriptionUntilMs.value > 0) return subscriptionUntilMs.value > userNow.value
  return Boolean(me.subscription_active)
})
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
  if (!canEditProfileTheme.value) return 'Выбор оформления доступен пользователям, поддержавшим платформу'
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
    : 'Очистка истории никнеймов доступна пользователям, поддержавшим платформу'
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
    text: 'Очистить историю никнеймов, оставив только текущий никнейм?',
    confirmText: 'Очистить',
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

function openSupportModal() {
  supportModalOpen.value = true
}

function onSupportSiteSelect(site: { id: string; name: string; url: string }) {
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
    text: 'После отвязки Telegram-верификация будет снята. Продолжить?',
    confirmText: 'Отвязать',
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
    text: 'Вы уверены что хотите навсегда удалить свой аккаунт?',
    confirmText: 'Удалить',
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
  else if (st === 403 && d === 'subscription_required')   void alertDialog('GIF-аватары доступны только при активной подписке')
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
    text: 'Вы уверены что хотите удалить аватар?',
    confirmText: 'Удалить',
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

watch(() => route.query.tab, (tab) => {
  const requested = normalizeTab(tab)
  const next = requested === 'history' && !showHistoryTab.value ? 'profile' : requested
  if (next !== activeTab.value) activeTab.value = next
})

watch(showHistoryTab, ok => {
  if (!ok && activeTab.value === 'history') activeTab.value = 'profile'
})

watch(activeTab, (tab) => {
  if (normalizeTab(route.query.tab) !== tab) {
    router.replace({ query: { ...route.query, tab } }).catch(() => {})
  }
  if (tab === 'sanctions') {
    void loadSanctions(true)
    return
  }
  if (tab === 'profile') void loadMe({ keepNickDraft: true })
})

onMounted(async () => {
  try { await loadMe() } catch {}
  const normalizedRequestedTab = normalizeTab(route.query.tab)
  const requestedTab = normalizedRequestedTab === 'history' && !showHistoryTab.value ? 'profile' : normalizedRequestedTab
  if (typeof route.query.tab === 'string' && requestedTab !== activeTab.value) {
    Promise.resolve().then(() => {
      activeTab.value = requestedTab
    })
  } else if (activeTab.value === 'sanctions') {
    void loadSanctions(true)
  }
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
  resetGifPicker()
  document.body.style.overflow = ''
})
</script>

<style scoped lang="scss">
.profile {
  display: flex;
  flex-direction: column;
  margin: 0 10px;
  padding: 10px;
  border-radius: 5px;
  background-color: $dark;
  overflow: auto;
  scrollbar-width: none;
  .btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 15px;
    gap: 5px;
    max-width: 200px;
    height: 40px;
    border: none;
    border-radius: 5px;
    background-color: $fg;
    box-shadow: 3px 3px 5px rgba($black, 0.25);
    font-size: 16px;
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
    &.support-btn {
      max-width: 240px;
      background-color: $fg;
      color: $bg;
      font-family: Manrope-SemiBold;
      &:hover,
      &:focus-visible {
        background-color: $white;
        box-shadow: 0 15px 30px rgba($black, 0.25);
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
        min-width: 150px;
        width: auto;
        padding: 0 20px;
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
        &:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      }
    }
  }
  .tab-panel {
    margin-top: 10px;
    .grid {
      display: grid;
      gap: 10px;
      grid-template-columns: 1fr 1fr 1fr;
      .block {
        padding: 15px;
        min-height: 190px;
        border: 3px solid $lead;
        border-radius: 5px;
        h3 {
          margin: 0 0 20px;
          font-size: 20px;
          color: $fg;
        }
        .hint {
          margin: 0;
          color: $grey;
          font-size: 14px;
          &.center {
            text-align: center;
          }
          &.text {
            font-size: 16px;
            color: $fg;
          }
          &.warn {
            color: $yellow;
          }
          &.red {
            color: $red;
          }
          a {
            color: $fg;
            text-decoration: none;
          }
        }
        &.avatar-block {
          .avatar-row {
            display: flex;
            gap: 20px;
            align-items: center;
            .avatar-img {
              width: 150px;
              height: 150px;
              object-fit: cover;
              border-radius: 50%;
            }
            .actions {
              display: flex;
              flex-direction: column;
              gap: 10px;
            }
          }
          .nick-row {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            margin-bottom: 5px;
            gap: 10px;
            .nick-input-line {
              display: flex;
              align-items: center;
              gap: 10px;
              width: 100%;
              :deep(.profile-input) {
                flex: 1 1 auto;
                max-width: 300px;
                width: 100%;
              }
              .nickname-history-tooltip-wrap {
                display: inline-flex;
                position: relative;
                flex: 0 0 auto;
                align-items: center;
                justify-content: center;
                width: 40px;
                height: 40px;
                outline: none;
                &:hover,
                &:focus-within {
                  &::after {
                    display: block;
                  }
                  .nickname-history-tooltip {
                    display: flex;
                  }
                }
                &::after {
                  content: '';
                  display: none;
                  position: absolute;
                  top: 100%;
                  right: 0;
                  width: 300px;
                  height: 10px;
                  z-index: 4;
                }
                .nickname-history-icon {
                  width: 24px;
                  height: 24px;
                  object-fit: contain;
                }
                .nickname-history-tooltip {
                  display: none;
                  position: absolute;
                  top: calc(100% + 10px);
                  right: 0;
                  flex-direction: column;
                  gap: 10px;
                  width: 300px;
                  max-height: 250px;
                  padding: 10px;
                  border-radius: 5px;
                  background-color: $graphite;
                  box-shadow: 3px 3px 5px rgba($black, 0.25);
                  color: $fg;
                  font-size: 14px;
                  line-height: 1.2;
                  z-index: 5;
                  .nickname-history-clear {
                    width: 100%;
                    max-width: none;
                    min-height: 30px;
                    font-size: 14px;
                  }
                  .nickname-history-access-text {
                    color: $ashy;
                    overflow-wrap: anywhere;
                    &.disabled {
                      color: $grey;
                    }
                  }
                  .nickname-history-divider {
                    width: 100%;
                    height: 1px;
                    background-color: rgba($white, 0.1);
                  }
                  .nickname-history-list {
                    display: flex;
                    flex-direction: column;
                    gap: 5px;
                    overflow-y: auto;
                    scrollbar-width: thin;
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
        &.theme-block {
          .theme-row {
            display: inline-flex;
            flex-direction: column;
            margin-bottom: 10px;
            .theme-preview-grid {
              display: grid;
              gap: 10px;
            }
            .theme-preview-card {
              display: flex;
              align-items: center;
              padding: 10px 15px;
              gap: 5px;
              width: fit-content;
              border-radius: 15px;
              background-color: var(--user-theme-bg, rgba($dark, 0.75));
              box-shadow: 3px 3px 5px rgba($black, 0.25);
              transition: background-color 0.25s ease-in-out;
              .theme-preview-avatar {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                object-fit: cover;
              }
              .theme-preview-icon {
                width: 40px;
                height: 40px;
                object-fit: contain;
              }
              .theme-preview-icons {
                display: inline-flex;
                align-items: center;
                gap: 5px;
                flex: 0 0 auto;
              }
              span {
                min-width: 0;
                color: $fg;
                font-size: 22px;
                font-family: Manrope-SemiBold;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
              }
            }
            .theme-palette {
              display: inline-grid;
              grid-template-columns: repeat(10, 1fr);
              margin: 15px 0;
              padding: 10px;
              gap: 5px;
              background-color: $graphite;
              border-radius: 10px;
              box-shadow: 3px 3px 5px rgba($black, 0.25);
            }
            .theme-icon-palette {
              display: inline-grid;
              grid-template-columns: repeat(10, 1fr);
              margin-bottom: 15px;
              padding: 10px;
              gap: 5px;
              background-color: $graphite;
              border-radius: 10px;
              box-shadow: 3px 3px 5px rgba($black, 0.25);
            }
            .theme-option {
              display: flex;
              align-items: center;
              justify-content: center;
              width: 30px;
              height: 30px;
              border: 2px solid $graphite;
              border-radius: 999px;
              background-color: var(--user-theme-bg, $graphite);
              cursor: pointer;
              transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out;
              &:hover:enabled {
                border-color: rgba($white, 0.5);
              }
              &.active {
                border-color: $fg;
              }
              &:disabled {
                cursor: not-allowed;
              }
            }
            .theme-icon-option {
              display: flex;
              align-items: center;
              justify-content: center;
              width: 30px;
              height: 30px;
              border: 2px solid transparent;
              border-radius: 999px;
              background: none;
              cursor: pointer;
              transition: border-color 0.25s ease-in-out;
              img {
                width: 24px;
                height: 24px;
                object-fit: contain;
              }
              .theme-icon-none {
                width: 10px;
                height: 2px;
                border-radius: 2px;
                background-color: rgba($white, 0.75);
              }
              &:hover:enabled {
                border-color: rgba($white, 0.5);
              }
              &.active {
                border-color: $fg;
              }
              &:disabled {
                cursor: not-allowed;
              }
            }
          }
        }
        &.account-block {
          .verify-row {
            display: flex;
            flex-direction: column;
            gap: 10px;
          }
          .password-row {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            margin-top: 5px;
            gap: 10px;
            --ui-input-label-bg: #{$dark};
            :deep(.profile-input) {
              max-width: 320px;
              width: 100%;
            }
          }
        }
        &.sanctions-block {
          .sanctions-head {
            display: flex;
            flex-wrap: wrap;
            align-items: flex-start;
            justify-content: space-between;
            gap: 10px;
          }
          .sanctions-summary {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            font-size: 14px;
            color: $fg;
          }
          .sanctions-empty {
            padding: 20px 0;
            color: $ashy;
            &.danger {
              color: $red;
            }
          }
          .sanctions-list {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
            .sanction-card {
              border: 3px solid $lead;
              border-radius: 5px;
              padding: 10px;
              &.sanction-card--timeout {
                border-color: rgba($yellow, 0.5);
                background-color: rgba($yellow, 0.25);
              }
              &.sanction-card--suspend {
                border-color: rgba($orange, 0.5);
                background-color: rgba($orange, 0.25);
              }
              &.sanction-card--ban {
                border-color: rgba($red, 0.5);
                background-color: rgba($red, 0.25);
              }
              .sanction-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                .sanction-kind {
                  display: flex;
                  align-items: center;
                  gap: 5px;
                  flex-wrap: wrap;
                  .sanction-tag {
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    padding: 5px 10px;
                    min-width: 30px;
                    border-radius: 999px;
                    background-color: $dark;
                    font-size: 12px;
                    color: $fg;
                  }
                }
              }
              .sanction-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 10px;
                margin-top: 10px;
                .sanction-cell {
                  display: flex;
                  flex-direction: column;
                  gap: 3px;
                  font-size: 14px;
                  span {
                    color: $ashy;
                    font-size: 12px;
                  }
                  strong {
                    color: $fg;
                    overflow-wrap: anywhere;
                  }
                }
              }
            }
          }
        }
      }
      .modal {
        display: flex;
        position: fixed;
        align-items: center;
        justify-content: center;
        inset: 0;
        background-color: rgba($black, 0.25);
        backdrop-filter: blur(5px);
        overscroll-behavior: contain;
        z-index: 50;
        .modal-body {
          display: flex;
          flex-direction: column;
          padding: 10px;
          gap: 10px;
          border: 1px solid $graphite;
          border-radius: 5px;
          background-color: $dark;
          .gif-preview-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: stretch;
            justify-content: center;
          }
          .gif-preview-block {
            display: flex;
            flex-direction: column;
            gap: 5px;
            align-items: center;
            span {
              color: $grey;
              font-size: 18px;
            }
            img {
              width: 300px;
              height: 300px;
              border-radius: 5px;
              background-color: $black;
              object-fit: contain;
            }
          }
          .hint {
            margin: 0;
            color: $grey;
            font-size: 14px;
            &.red {
              color: $red;
            }
          }
          canvas {
            align-self: center;
            width: 300px;
            height: 300px;
            border-radius: 5px;
            background-color: $black;
          }
          .range {
            display: flex;
            flex-direction: column;
            gap: 5px;
          }
          .modal-actions {
            display: flex;
            justify-content: space-between;
            gap: 10px;
          }
        }
      }
      &.grid-sanctions {
        grid-template-columns: 1fr;
      }
      &.grid-history {
        grid-template-columns: 1fr;
      }
      &.grid-stats {
        grid-template-columns: 1fr;
      }
    }
    .grid-empty {
      min-height: 200px;
    }
  }
}

.tab-fade-enter-active,
.tab-fade-leave-active {
  transition: opacity 0.15s ease-in-out;
}
.tab-fade-enter-from,
.tab-fade-leave-to {
  opacity: 0;
}

</style>
