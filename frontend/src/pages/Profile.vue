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
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'profile' }" :aria-selected="activeTab === 'profile'" :disabled="isTabButtonDisabled('profile')" @click="activeTab = 'profile'">
            <UiIcon class="tab-btn-img" :icon="iconDefaultAvatar" />
            <span class="tab-btn-text">Аватар и никнейм</span>
          </button>
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'theme' }" :aria-selected="activeTab === 'theme'" :disabled="isTabButtonDisabled('theme')" @click="activeTab = 'theme'">
            <UiIcon class="tab-btn-img" :icon="iconDesign" />
            <span class="tab-btn-text">Оформление профиля</span>
          </button>
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'stats' }" :aria-selected="activeTab === 'stats'" :disabled="isTabButtonDisabled('stats')" @click="activeTab = 'stats'">
            <UiIcon class="tab-btn-img" :icon="iconStats" />
            <span class="tab-btn-text">Статистика</span>
          </button>
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'history' }" :aria-selected="activeTab === 'history'" :disabled="isTabButtonDisabled('history')" @click="activeTab = 'history'">
            <UiIcon class="tab-btn-img" :icon="iconHistory" />
            <span class="tab-btn-text">История игр</span>
          </button>
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'sanctions' }" :aria-selected="activeTab === 'sanctions'" :disabled="isTabButtonDisabled('sanctions')" @click="activeTab = 'sanctions'">
            <UiIcon class="tab-btn-img" :icon="iconJudgeHummer" />
            <span class="tab-btn-text">Санкции</span>
          </button>
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'payments' }" :aria-selected="activeTab === 'payments'" :disabled="isTabButtonDisabled('payments')" @click="activeTab = 'payments'">
            <UiIcon class="tab-btn-img" :icon="iconCard" />
            <span class="tab-btn-text">Платежи</span>
          </button>
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'music' }" :aria-selected="activeTab === 'music'" :disabled="isTabButtonDisabled('music')" @click="activeTab = 'music'">
            <UiIcon class="tab-btn-img" :icon="iconMusic" />
            <span class="tab-btn-text">Музыка</span>
          </button>
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'blacklist' }" :aria-selected="activeTab === 'blacklist'" :disabled="isTabButtonDisabled('blacklist')" @click="activeTab = 'blacklist'">
            <UiIcon class="tab-btn-img" :icon="iconBlockPlayer" />
            <span class="tab-btn-text">Черный список</span>
          </button>
        </nav>
      </div>
      <div class="tab-div">
        <div v-if="!hasActiveSubscription" class="tab-subscribe">
          <img class="background-image" :src="imageSlide9" alt="" aria-hidden="true" />
          <div class="tab-subscribe-div">
            <span class="tab-subscribe-title">Оформи подписку</span>
            <span class="tab-subscribe-text">Подписка откроет новые функции, персонализацию профиля и дополнительные привилегии.</span>
            <UiButton
              size="middle"
              variant="white"
              width="100%"
              type="button"
              text="Оформить"
              @click="openSubscriptionModal"
            />
          </div>
        </div>
        <button class="tab-btn" type="button" @click="onLogoutClick">
          <UiIcon class="tab-btn-img" :icon="iconLeave" />
          <span class="tab-btn-text">Выход из аккаунта</span>
        </button>
      </div>
    </header>

    <Transition name="tab-fade" mode="out-in">
      <div :key="activeTab" class="tab-panel">
        <ProfileAccount v-if="activeTab === 'account'" />

        <ProfileAvatarNick v-if="activeTab === 'profile'" />

        <ProfileTheme v-if="activeTab === 'theme'" />

        <ProfileStats v-if="activeTab === 'stats'" />

        <ProfileHistory v-if="activeTab === 'history'" />

        <ProfileSanctions v-if="activeTab === 'sanctions'" />

        <ProfilePayments v-if="activeTab === 'payments'" />

        <ProfileMusic v-if="activeTab === 'music'" />

        <ProfileBlacklist v-if="activeTab === 'blacklist'" />
      </div>
    </Transition>

    <Subscription v-model:open="subscriptionModalOpen" @select="onSubscriptionPaymentSelect" />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/services/axios'
import { useAuthStore, useFriendsStore, useSettingsStore, useUserStore } from '@/store'

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

import imageSlide9 from '@/assets/images/carousel-image9.png'
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

type SubscriptionSite = {
  id: string
  name: string
  url: string
}

const TAB_KEYS = ['profile', 'theme', 'music', 'account', 'stats', 'payments', 'history', 'sanctions', 'blacklist'] as const
type TabKey = typeof TAB_KEYS[number]
const DEFAULT_TAB: TabKey = 'account'
const DISABLED_FEATURE_TABS = new Set<TabKey>(['stats', 'history', 'sanctions', 'payments', 'music', 'blacklist'])

const userStore = useUserStore()
const auth = useAuthStore()
const friendsStore = useFriendsStore()
const settings = useSettingsStore()
const route = useRoute()
const router = useRouter()

const activeTab = ref<TabKey>(DEFAULT_TAB)
const subscriptionModalOpen = ref(false)
const homeHref = computed(() => router.resolve({ name: 'home' }).href)
const hasActiveSubscription = computed(() => userStore.subscriptionActive)
const profileTabsDisabled = computed(() => settings.verificationRestrictions && !userStore.telegramVerified)
let onProfileSync: ((e: Event) => void) | null = null

function normalizeTab(value: unknown): TabKey {
  if (typeof value === 'string' && (TAB_KEYS as readonly string[]).includes(value)) return value as TabKey
  return DEFAULT_TAB
}

function resolveProfileTabAccess(tab: TabKey): TabKey {
  return profileTabsDisabled.value && tab !== 'account' ? 'account' : tab
}

function isTabButtonDisabled(tab: TabKey): boolean {
  return profileTabsDisabled.value || DISABLED_FEATURE_TABS.has(tab)
}

function navigateHome(event: MouseEvent) {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.altKey || event.ctrlKey || event.shiftKey) return
  event.preventDefault()
  router.push({ name: 'home' }).catch(() => {})
}

async function onLogoutClick() {
  try {
    await auth.logout()
  } finally {}
}

function openSubscriptionModal() {
  subscriptionModalOpen.value = true
}

function onSubscriptionPaymentSelect(site: SubscriptionSite) {
  if (site.id === 'lava') return
  void api.post('/users/support_link_click', {
    source: 'profile_theme',
    site_id: site.id,
    site_name: site.name,
    url: site.url,
  }).catch(() => {})
}

watch(() => route.query.tab, (tab) => {
  const next = resolveProfileTabAccess(normalizeTab(tab))
  if (next !== activeTab.value) activeTab.value = next
})

watch(profileTabsDisabled, (disabled) => {
  if (disabled && activeTab.value !== 'account') activeTab.value = 'account'
}, { immediate: true })

watch(activeTab, (tab) => {
  if (profileTabsDisabled.value && tab !== 'account') {
    activeTab.value = 'account'
    return
  }
  if (normalizeTab(route.query.tab) !== tab) {
    router.replace({ query: { ...route.query, tab } }).catch(() => {})
  }
})

onMounted(async () => {
  try {
    await userStore.fetchMe()
  } catch {}

  friendsStore.ensureWS()

  const requestedTab = resolveProfileTabAccess(normalizeTab(route.query.tab))
  if (typeof route.query.tab === 'string' && requestedTab !== activeTab.value) {
    Promise.resolve().then(() => {
      activeTab.value = requestedTab
    })
  }

  onProfileSync = (e: Event) => {
    const payload = (e as CustomEvent)?.detail
    if (!payload) return
    userStore.applyProfile(payload)
  }
  window.addEventListener('auth-profile_sync', onProfileSync)
})

onBeforeUnmount(() => {
  if (onProfileSync) window.removeEventListener('auth-profile_sync', onProfileSync)
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
    width: 298px;
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
        position: relative;
        flex-direction: column;
        padding: 16px;
        gap: 10px;
        border-radius: 24px;
        .background-image {
          position: absolute;
          left: 0;
          top: 0;
          width: 100%;
          height: 100%;
          border-radius: inherit;
          object-fit: cover;
        }
        .tab-subscribe-div {
          display: flex;
          z-index: 5;
          .tab-subscribe-title {
            color: $neutral-white;
            font-family: Hauora-Bold;
            font-size: 18px;
            line-height: 20px;
            letter-spacing: -0.36px;
          }
          .tab-subscribe-text {
            color: $neutral-100;
            font-family: Hauora-Regular;
            font-size: 14px;
            line-height: 14px;
            letter-spacing: -0.28px;
          }
        }
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
  transition: opacity 0.15s ease-in-out;
}
.tab-fade-enter-from,
.tab-fade-leave-to {
  opacity: 0;
}

</style>
