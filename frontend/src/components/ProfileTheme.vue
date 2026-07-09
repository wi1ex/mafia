<template>
  <div class="profile-tab-block block-theme">
    <h3>Оформление профиля</h3>
    <div class="theme-row">
      <div class="theme-preview-grid">
        <div class="theme-preview-card" :style="themePreviewStyle">
          <img class="theme-preview-avatar" v-minio-img="{ key: me.avatar_name ? `avatars/${me.avatar_name}` : '', placeholder: iconDefaultAvatar, lazy: false, animated: true }" alt="avatar" />
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
        {{ themeSaveBusy ? '...' : 'Сохранить' }}
      </button>
      <button v-else type="button" class="btn subscription-btn" @click="openSubscriptionModal">
        Оформить подписку
      </button>
    </div>
    <p class="hint">{{ profileThemeMessageText }}</p>
    <Subscription v-model:open="subscriptionModalOpen" @select="onSubscriptionPaymentSelect" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { useUserStore } from '@/store'
import Subscription from '@/components/Subscription.vue'
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

import iconDefaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'

type SubscriptionSite = {
  id: string
  name: string
  url: string
}

const userStore = useUserStore()
const { now: userNow } = storeToRefs(userStore)

const me = reactive({
  username: '',
  avatar_name: null as string | null,
  role: '',
  subscription_active: false,
  subscription_started_at: null as string | null,
  subscription_until: null as string | null,
  profile_theme_color: null as ProfileThemeColor | null,
  profile_theme_icon: null as ProfileThemeIcon | null,
})
const selectedProfileThemeColor = ref<ProfileThemeColor>(resolveProfileThemeColor(null))
const selectedProfileThemeIcon = ref<ProfileThemeIcon | null>(null)
const subscriptionModalOpen = ref(false)
const themeSaveBusy = ref(false)
const isBanned = computed(() => userStore.banActive)
let onProfileSync: ((e: Event) => void) | null = null

function parseDateMs(raw: string | null | undefined): number {
  if (!raw) return 0
  const ts = Date.parse(raw)
  return Number.isFinite(ts) ? ts : 0
}

const subscriptionUntilMs = computed(() => parseDateMs(me.subscription_until))
const hasActiveSubscription = computed(() => {
  if (subscriptionUntilMs.value > 0) return subscriptionUntilMs.value > userNow.value
  return Boolean(me.subscription_active)
})
const canEditProfileTheme = computed(() => hasActiveSubscription.value)
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

function applyProfileThemePayload(data: any, options: { keepDraft?: boolean } = {}) {
  me.subscription_active = Boolean(data?.subscription_active)
  me.subscription_started_at = data?.subscription_started_at || null
  me.subscription_until = data?.subscription_until || null
  me.profile_theme_color = normalizeProfileThemeColor(data?.profile_theme_color)
  me.profile_theme_icon = normalizeProfileThemeIcon(data?.profile_theme_icon)
  userStore.setProfileTheme({
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

function applyMePayload(data: any, options: { keepThemeDraft?: boolean } = {}) {
  me.username = data?.username || ''
  me.avatar_name = data?.avatar_name || null
  me.role = data?.role || ''
  applyProfileThemePayload(data, { keepDraft: options.keepThemeDraft })
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

function openSubscriptionModal() {
  subscriptionModalOpen.value = true
}

function onSubscriptionPaymentSelect(site: SubscriptionSite) {
  if (site.id === 'kassa') return
  void api.post('/users/support_link_click', {
    source: 'profile_theme',
    site_id: site.id,
    site_name: site.name,
    url: site.url,
  }).catch(() => {})
}

async function loadMe(options: { keepThemeDraft?: boolean } = {}) {
  const { data } = await api.get('/users/profile_info')
  applyMePayload(data, { keepThemeDraft: options.keepThemeDraft })
  userStore.applyProfile(data)
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

onMounted(() => {
  void loadMe()
  onProfileSync = (e: Event) => {
    const payload = (e as CustomEvent)?.detail
    if (!payload) return
    applyMePayload(payload, { keepThemeDraft: true })
  }
  window.addEventListener('auth-profile_sync', onProfileSync)
})

onBeforeUnmount(() => {
  if (onProfileSync) window.removeEventListener('auth-profile_sync', onProfileSync)
})
</script>

<style scoped lang="scss">
.block-theme {
  .theme-row {
    display: inline-flex;
    flex-direction: column;
    margin-bottom: 10px;
    .theme-preview-grid {
      display: grid;
      gap: 10px;
      .theme-preview-card {
        display: flex;
        align-items: center;
        padding: 10px 15px;
        gap: 5px;
        width: fit-content;
        border-radius: 15px;
        background-color: var(--user-theme-bg, rgba($neutral-900, 0.75));
        box-shadow: 3px 3px 5px rgba(black, 0.25);
        transition: background-color 0.25s ease-in-out;
        .theme-preview-avatar {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          object-fit: cover;
        }
        .theme-preview-icons {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          flex: 0 0 auto;
          .theme-preview-icon {
            width: 40px;
            height: 40px;
            object-fit: contain;
          }
        }
        span {
          min-width: 0;
          color: $neutral-100;
          font-size: 22px;
          font-family: Hauora-SemiBold;
          line-height: 1.3;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }
    }
    .theme-palette {
      display: inline-grid;
      grid-template-columns: repeat(10, 1fr);
      margin: 15px 0;
      padding: 10px;
      gap: 5px;
      background-color: $neutral-800;
      border-radius: 10px;
      box-shadow: 3px 3px 5px rgba(black, 0.25);
      .theme-option {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        border: 2px solid $neutral-800;
        border-radius: 999px;
        background-color: var(--user-theme-bg, $neutral-800);
        cursor: pointer;
        transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out;
        &:hover:enabled {
          border-color: rgba($neutral-white, 0.5);
        }
        &.active {
          border-color: $neutral-100;
        }
        &:disabled {
          cursor: not-allowed;
        }
      }
    }
    .theme-icon-palette {
      display: inline-grid;
      grid-template-columns: repeat(10, 1fr);
      margin-bottom: 15px;
      padding: 10px;
      gap: 5px;
      background-color: $neutral-800;
      border-radius: 10px;
      box-shadow: 3px 3px 5px rgba(black, 0.25);
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
          background-color: rgba($neutral-white, 0.75);
        }
        &:hover:enabled {
          border-color: rgba($neutral-white, 0.5);
        }
        &.active {
          border-color: $neutral-100;
        }
        &:disabled {
          cursor: not-allowed;
        }
      }
    }
  }
}
</style>
