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
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'sanctions' }" :aria-selected="activeTab === 'sanctions'" :disabled="profileTabsDisabled" @click="activeTab = 'sanctions'">
            <UiIcon class="tab-btn-img" :icon="iconJudgeHummer" />
            <span class="tab-btn-text">Санкции</span>
          </button>
          <button class="tab-btn" type="button" role="tab" :class="{ active: activeTab === 'subscription' }" :aria-selected="activeTab === 'subscription'" :disabled="profileTabsDisabled" @click="activeTab = 'subscription'">
            <UiIcon class="tab-btn-img" :icon="iconCard" />
            <span class="tab-btn-text">Платежи и ЧС</span>
          </button>
        </nav>
      </div>
      <div class="tab-div">
        <div class="tab-subscribe">
          <img class="background-image" :src="imageSlide8" alt="" aria-hidden="true" />
          <div class="tab-subscribe-div">
            <span class="tab-subscribe-title">Оформи подписку</span>
            <span class="tab-subscribe-text">Подписка откроет оформление профиля и другие новые функции.</span>
            <UiButton
              size="middle"
              variant="white"
              width="100%"
              type="button"
              text="Оформить"
              @click="openWalletModal()"
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

        <ProfileSanctions v-if="activeTab === 'sanctions'" />

        <ProfileSubscription v-if="activeTab === 'subscription'" />
      </div>
    </Transition>

    <WalletModal v-model:open="walletModalOpen" open-source="profile" initial-tab="subscription" />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore, useFriendsStore, useUserStore } from '@/store'

import ProfileAccount from '@/views/ProfileAccount.vue'
import ProfileAvatarNick from '@/views/ProfileAvatarNick.vue'
import ProfileTheme from '@/views/ProfileTheme.vue'
import ProfileSanctions from '@/views/ProfileSanctions.vue'
import ProfileSubscription from '@/views/ProfileSubscription.vue'
import WalletModal from '@/views/WalletModal.vue'
import UiIcon from '@/components/UiIcon.vue'
import UiButton from '@/components/UiButton.vue'

import imageSlide8 from '@/assets/images/carousel-image8.png'
import iconHome from '@/assets/svg/iconHome.svg'
import iconDefaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconSettings from '@/assets/svg/iconSettings.svg'
import iconDesign from '@/assets/svg/iconDesign.svg'
import iconJudgeHummer from '@/assets/svg/iconJudgeHummer.svg'
import iconCard from '@/assets/svg/iconCard.svg'
import iconLeave from '@/assets/svg/iconLeave.svg'

const TAB_KEYS = ['profile', 'theme', 'account', 'subscription', 'sanctions'] as const
type TabKey = typeof TAB_KEYS[number]
const DEFAULT_TAB: TabKey = 'account'

const userStore = useUserStore()
const auth = useAuthStore()
const friendsStore = useFriendsStore()
const route = useRoute()
const router = useRouter()

const activeTab = ref<TabKey>(DEFAULT_TAB)
const walletModalOpen = ref(false)
const homeHref = computed(() => router.resolve({ name: 'home' }).href)
const hasActiveSubscription = computed(() => userStore.subscriptionActive)
const profileTabsDisabled = computed(() => userStore.accountRestricted)
let onProfileSync: ((e: Event) => void) | null = null

function normalizeTab(value: unknown): TabKey {
  if (typeof value === 'string' && (TAB_KEYS as readonly string[]).includes(value)) return value as TabKey
  return DEFAULT_TAB
}

function resolveProfileTabAccess(tab: TabKey): TabKey {
  return profileTabsDisabled.value && tab !== 'account' ? 'account' : tab
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

function openWalletModal() {
  walletModalOpen.value = true
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
  padding: 30px 40px 10px;
  gap: 10px;
  height: 100%;
  overflow: auto;
  scrollbar-width: none;
  header {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 24px;
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
          flex-direction: column;
          gap: 8px;
          z-index: 5;
          .tab-subscribe-title {
            color: $neutral-white;
            font-family: Hauora-Bold;
            font-size: 18px;
            line-height: 20px;
            letter-spacing: -0.36px;
          }
          .tab-subscribe-text {
            margin-bottom: 8px;
            max-width: 250px;
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
    width: calc(100% - 308px);
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
