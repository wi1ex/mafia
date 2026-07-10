<template>
  <div class="block-theme">
    <div class="theme-div">
      <div class="theme-header">
        <div class="theme-title">
          <span class="title">Кастомизация профиля</span>
          <UiTooltip
            text="Кастомизация профиля доступна только при наличии подписки."
            placement="bottom-right"
            bubble-width="320px"
          />
        </div>
        <UiButton
          v-if="canEditProfileTheme"
          variant="green"
          size="middle"
          :text="themeSaveBusy ? '...' : 'Сохранить изменения'"
          :disabled="themeSaveDisabled"
          @click="saveProfileTheme"
        />
        <UiButton
          v-else
          variant="green"
          size="middle"
          text="Оформить подписку"
          @click="openSubscriptionModal"
        />
      </div>
      <div class="theme-changes">
        <div class="theme-palette">
          <button class="theme-option" v-for="item in profileThemeOptions" :key="item.key" type="button" :class="{ active: selectedProfileThemeColor === item.key }"
                  :style="themeOptionStyle(item.key)" :disabled="themeSaveBusy || isBanned" @click="pickProfileTheme(item.key)">
          </button>
        </div>
        <div class="theme-palette">
          <button class="theme-option icon" v-for="item in profileThemeIconOptions" :key="item.key" @click="pickProfileThemeIcon(item.key)"
                  type="button" :class="{ active: selectedProfileThemeIcon === item.key }" :disabled="themeSaveBusy || isBanned || !item.available">
            <img v-if="themeIconSrc(item.key)" class="theme-icon-img" :src="themeIconSrc(item.key) || ''" alt="" aria-hidden="true" />
            <img v-else class="theme-icon-img" :src="iconDush" alt="" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
    <div class="theme-preview">
      <div class="theme-preview-div">
        <span class="theme-title">Предпросмотр</span>
        <div class="theme-preview-profile" :style="themePreviewStyle">
          <header class="profile-top">
            <div class="profile-identity">
              <img class="theme-preview-avatar" v-minio-img="{ key: me.avatar_name ? `avatars/${me.avatar_name}` : '', placeholder: iconDefaultAvatar, lazy: false, animated: true }" alt="avatar" />
              <div class="profile-block">
                <div class="profile-div">
                  <div class="profile-title">
                    <div v-if="themePreviewIconSrcs.length" class="theme-preview-icons" aria-hidden="true">
                      <img class="theme-preview-icon" v-for="badgeSrc in themePreviewIconSrcs" :key="badgeSrc" :src="badgeSrc" alt="" />
                    </div>
                    <span class="theme-preview-name">{{ me.username || 'User' }}</span>
                  </div>
                  <div class="profile-meta">
                    <div class="profile-friends"></div>
                    <div class="profile-history"></div>
                    <div class="profile-nomination"></div>
                    <div class="profile-nomination"></div>
                    <div class="profile-nomination"></div>
                    <div class="profile-nomination"></div>
                    <div class="profile-nomination"></div>
                  </div>
                </div>
              </div>
            </div>
            <UiIcon class="close-icon" :icon="iconClose" />
          </header>
          <div class="profile-dates"></div>
          <div class="profile-preview-action">Пример кнопки</div>
        </div>
      </div>
      <div class="theme-preview-div">
        <span class="theme-title">Бейджик</span>
        <div class="theme-preview-card" :style="themePreviewStyle">
          <img class="theme-preview-avatar" v-minio-img="{ key: me.avatar_name ? `avatars/${me.avatar_name}` : '', placeholder: iconDefaultAvatar, lazy: false, animated: true }" alt="avatar" />
          <div v-if="themePreviewIconSrcs.length" class="theme-preview-icons" aria-hidden="true">
            <img class="theme-preview-icon" v-for="badgeSrc in themePreviewIconSrcs" :key="badgeSrc" :src="badgeSrc" alt="" />
          </div>
          <span class="theme-preview-name">{{ me.username || 'User' }}</span>
        </div>
      </div>
    </div>
    <Subscription v-model:open="subscriptionModalOpen" @select="onSubscriptionPaymentSelect" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { useUserStore } from '@/store'
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

import Subscription from '@/components/Subscription.vue'
import UiTooltip from '@/components/UiTooltip.vue'
import UiButton from '@/components/UiButton.vue'
import UiIcon from '@/components/UiIcon.vue'

import iconDefaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconDush from '@/assets/svg/iconDush.svg'
import iconClose from '@/assets/svg/iconClose.svg'

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
const themePreviewStyle = computed(() => buildProfileThemeBgStyle(selectedProfileThemeColor.value))
const themePreviewIconSrcs = computed(() => getProfileThemeBadgeSources(selectedProfileThemeIcon.value, me.role))
const profileThemeOptions = computed(() => getProfileThemeOptions(me.role))
const profileThemeIconOptions = computed(() => PROFILE_THEME_ICON_OPTIONS.filter((item) => item.available || item.key === selectedProfileThemeIcon.value))

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
  display: flex;
  gap: 10px;
  width: 100%;
  .theme-div {
    display: flex;
    box-sizing: border-box;
    flex-direction: column;
    padding: 24px;
    gap: 24px;
    width: calc(50% - 5px);
    height: fit-content;
    border-radius: 24px;
    background-color: $soft-purple-900;
    .theme-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      height: 32px;
      .theme-title {
        display: flex;
        align-items: center;
        gap: 8px;
        .title {
          color: $neutral-white;
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
      }
    }
    .theme-changes {
      display: flex;
      flex-direction: column;
      gap: 10px;
      .theme-palette {
        display: inline-grid;
        grid-template-columns: repeat(10, 1fr);
        padding: 16px;
        gap: 10px;
        border-radius: 20px;
        background-color: $soft-purple-800;
        .theme-option {
          position: relative;
          border: 2px solid $soft-purple-800;
          border-radius: 10px;
          cursor: pointer;
          aspect-ratio: 1;
          transition: border-color 0.25s ease-in-out, opacity 0.25s ease-in-out;
          &::before {
            content: "";
            position: absolute;
            inset: -2px;
            padding: 2px;
            border-radius: 8px;
            background: linear-gradient(90deg, rgba(91, 0, 255, 1) 0%, rgba(255, 19, 97, 1) 50%, rgba(255, 248, 0, 1) 100%);
            -webkit-mask-image: -webkit-linear-gradient($neutral-white, $neutral-white), -webkit-linear-gradient($neutral-white, $neutral-white);
            -webkit-mask-clip: content, border;
            -webkit-mask-composite: xor;
            mask: linear-gradient($neutral-white, $neutral-white) content-box, linear-gradient($neutral-white, $neutral-white);
            mask-composite: exclude;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.25s ease-in-out;
          }
          &.icon {
            background: none;
          }
          &:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
          &.active {
            border-color: transparent;
            &::before {
              opacity: 1;
            }
          }
          &:not(:disabled):not(.active):hover,
          &:not(:disabled):not(.active):focus-visible,
          &:not(:disabled):not(.active):active {
            border-color: $neutral-white;
          }
          .theme-icon-img {
            width: 100%;
          }
        }
      }
    }
  }
  .theme-preview {
    display: flex;
    box-sizing: border-box;
    flex-direction: column;
    padding: 24px;
    gap: 40px;
    width: calc(50% - 5px);
    height: fit-content;
    border-radius: 24px;
    background-color: $soft-purple-900;
    .theme-preview-div {
      display: flex;
      flex-direction: column;
      gap: 24px;
      .theme-title {
        color: $neutral-white;
        font-family: Involve-Medium;
        font-size: 24px;
        line-height: 26px;
        letter-spacing: -0.48px;
      }
      .theme-preview-profile {
        display: flex;
        box-sizing: border-box;
        flex-direction: column;
        padding: 24px;
        gap: 40px;
        width: 100%;
        min-width: 0;
        border-radius: 24px;
        background-color: var(--user-theme-bg, $neutral-black);
        overflow: hidden;
        .profile-top {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
          .profile-identity {
            display: flex;
            align-items: flex-start;
            gap: 16px;
            min-width: 0;
            .theme-preview-avatar {
              flex: 0 0 auto;
              width: 182px;
              height: 182px;
              border-radius: 50%;
              object-fit: cover;
            }
            .profile-block {
              display: flex;
              flex-direction: column;
              gap: 8px;
              min-width: 0;
              height: 182px;
              .profile-div {
                display: flex;
                flex-direction: column;
                gap: 8px;
                min-width: 0;
                .profile-title {
                  display: flex;
                  align-items: center;
                  gap: 8px;
                  height: 30px;
                  min-width: 0;
                  .theme-preview-icons {
                    display: inline-flex;
                    align-items: center;
                    flex: 0 0 auto;
                    height: 30px;
                    .theme-preview-icon {
                      width: 28px;
                      height: 28px;
                      object-fit: contain;
                    }
                  }
                  .theme-preview-name {
                    max-width: 240px;
                    color: $neutral-white;
                    font-family: Involve-Medium;
                    font-size: 24px;
                    line-height: 26px;
                    letter-spacing: -0.48px;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                  }
                }
                .profile-meta {
                  display: flex;
                  align-items: center;
                  flex-wrap: wrap;
                  gap: 4px;
                  .profile-friends,
                  .profile-history,
                  .profile-nomination {
                    height: 32px;
                    border-radius: 8px;
                    background-color: rgba($soft-purple-900, 0.65);
                  }
                  .profile-friends {
                    width: 97px;
                  }
                  .profile-history,
                  .profile-nomination {
                    width: 32px;
                  }
                }
              }
            }
          }
          .close-icon {
            flex: 0 0 auto;
            --ui-icon-width: 24px;
            --ui-icon-height: 24px;
            --ui-icon-color: #{$neutral-white};
          }
        }
        .profile-dates {
          height: 96px;
          border-radius: 20px;
          background-color: rgba($soft-purple-900, 0.65);
        }
        .profile-preview-action {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0 16px;
          width: calc(100% - 32px);
          height: 40px;
          border-radius: 12px;
          color: $neutral-900;
          background-color: $green-500;
          font-family: Hauora-Regular;
          font-size: 18px;
          line-height: 20px;
          letter-spacing: -0.36px;
        }
      }
      .theme-preview-card {
        display: flex;
        align-items: center;
        padding: 0 16px;
        gap: 8px;
        width: fit-content;
        height: 64px;
        border-radius: 16px;
        .theme-preview-avatar {
          width: 24px;
          height: 24px;
        }
        .theme-preview-icons {
          display: flex;
          align-items: center;
          margin-left: -8px;
          .theme-preview-icon {
            width: 24px;
            height: 24px;
          }
        }
        .theme-preview-name {
          color: $neutral-100;
          font-family: Hauora-Regular;
          font-size: 18px;
          line-height: 20px;
          letter-spacing: -0.36px;
        }
      }
    }
  }
}
</style>
