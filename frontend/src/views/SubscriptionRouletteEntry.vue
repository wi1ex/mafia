<template>
  <Transition name="roulette-invitation">
    <aside v-if="showBanner" ref="banner" class="roulette-invitation" aria-label="Лотерея подписки">
      <span class="roulette-invitation__icon" :class="{ 'is-paused': !pageVisible }" aria-hidden="true">
        <UiIcon :icon="iconRoulette" />
      </span>
      <div class="roulette-invitation__copy">
        <strong>Испытайте удачу</strong>
        <span>От 1 до 30 дней подписки бесплатно</span>
      </div>
      <UiButton size="middle" text="Крутить" @click="openDialog" />
    </aside>
  </Transition>
  <SubscriptionRoulette
    v-if="hasOpened"
    :open="open"
    :phase="phase"
    :days="resultDays"
    :subscription-until="displayResult?.subscription_until || null"
    :can-spin="canSpin"
    :error="error"
    :sharing="sharing"
    :reduced-motion="reducedMotion"
    @start="start"
    @share="shareResult"
    @close="closeDialog"
  />
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore, useSettingsStore, useUserStore } from '@/store'
import { useGlobalChatStore } from '@/store/modules/globalChat'
import { type UserProfile } from '@/store/modules/user'
import { api } from '@/services/axios'
import UiButton from '@/components/UiButton.vue'
import UiIcon from '@/components/UiIcon.vue'
import iconRoulette from '@/assets/svg/iconRoulette.svg'
import {
  fetchRouletteStatus, holdRouletteNotifications, publishSiteNotification, releaseRouletteNotifications,
  ROULETTE_SPIN_MS, setRouletteNotificationAccount, spinRoulette, validRouletteDays, validRouletteRound,
  type RoulettePhase, type RouletteStatus,
} from '@/services/subscriptionRoulette'

const SubscriptionRoulette = defineAsyncComponent(() => import('@/views/SubscriptionRoulette.vue'))
const route = useRoute()
const auth = useAuthStore()
const user = useUserStore()
const settings = useSettingsStore()
const globalChat = useGlobalChatStore()
const banner = ref<HTMLElement | null>(null)
const open = ref(false)
const hasOpened = ref(false)
const phase = ref<RoulettePhase>('idle')
const status = ref<RouletteStatus | null>(null)
const displayResult = ref<RouletteStatus | null>(null)
const dialogRound = ref<number | null>(null)
const resultDays = ref<number | null>(null)
const error = ref('')
const sharing = ref(false)
let shareAttempt: { round: number; clientMessageId: string; image: File | null } | null = null
const pageVisible = ref(!document.hidden)
const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
const reducedMotion = ref(motionQuery.matches)
const userId = computed(() => auth.isAuthed ? user.user?.id ?? null : null)
const currentRound = computed(() => Math.max(
  settings.subscriptionRouletteRound,
  validRouletteRound(user.user?.subscription_roulette_round) ? user.user.subscription_roulette_round : 0,
))
const contextReady = computed(() => Boolean(
  auth.ready && auth.isAuthed && settings.ready
  && user.user && user.telegramVerified && route.name === 'home',
))
const invitationAllowed = computed(() => contextReady.value && settings.subscriptionRouletteEnabled)
const participated = computed(() => (
  user.user?.subscription_roulette_round === currentRound.value && validRouletteDays(user.user.subscription_roulette_days)
) || (
  status.value?.round_id === currentRound.value && validRouletteDays(status.value.subscription_roulette_days)
))
const busy = computed(() => phase.value === 'requesting' || phase.value === 'spinning' || phase.value === 'recovering')
const currentEligible = computed(() => invitationAllowed.value && status.value?.round_id === currentRound.value && status.value.eligible && !participated.value)
const showBanner = computed(() => currentEligible.value && !open.value && !busy.value)
const canSpin = computed(() => currentEligible.value && dialogRound.value === currentRound.value)
let generation = 0
let statusRequest = 0
let spinTimer: number | undefined
let resizeObserver: ResizeObserver | null = null

function stopSpinTimer(): void {
  if (spinTimer !== undefined) window.clearTimeout(spinTimer)
  spinTimer = undefined
}

function saveCurrentStatus(data: RouletteStatus): boolean {
  if (!validRouletteRound(data.round_id) || data.round_id < currentRound.value) return false
  settings.applyRouletteRound(data.round_id, data.enabled)
  status.value = data
  if (user.user) user.applyProfile({
    ...user.user,
    subscription_roulette_round: data.round_id,
    subscription_roulette_days: data.subscription_roulette_days,
  })
  return true
}

async function loadStatus(): Promise<RouletteStatus | null> {
  const id = userId.value
  if (!id) return null
  const current = generation
  const request = ++statusRequest
  const data = await fetchRouletteStatus()
  if (current !== generation || id !== userId.value || request !== statusRequest) return null
  if (!saveCurrentStatus(data)) return null
  if (open.value && dialogRound.value === data.round_id && !busy.value && validRouletteDays(data.subscription_roulette_days)) {
    displayResult.value = data
    resultDays.value = data.subscription_roulette_days
    phase.value = 'result'
  }
  return data
}

function clearClosedDialog(): void {
  if (open.value || busy.value) return
  phase.value = 'idle'
  displayResult.value = null
  resultDays.value = null
  dialogRound.value = null
  error.value = ''
}

function finishSpin(id: number): void {
  stopSpinTimer()
  if (id !== userId.value) return
  phase.value = 'result'
  releaseRouletteNotifications(id)
  if (!open.value) {
    clearClosedDialog()
    if (contextReady.value) void loadStatus().catch(() => {})
  }
}

function acceptSpin(data: RouletteStatus, id: number): void {
  if (!validRouletteDays(data.subscription_roulette_days) || data.round_id !== dialogRound.value) throw new Error('Invalid roulette response')
  saveCurrentStatus(data)
  displayResult.value = data
  resultDays.value = data.subscription_roulette_days
  if (data.notification) publishSiteNotification(data.notification)
  const current = generation
  void api.get<UserProfile>('/users/profile_info').then(({ data: profile }) => {
    if (current === generation && id === userId.value && profile.id === id) user.applyProfile(profile)
  }).catch(() => {})
  if (!open.value) {
    finishSpin(id)
    return
  }
  phase.value = 'spinning'
  spinTimer = window.setTimeout(() => finishSpin(id), reducedMotion.value ? 250 : ROULETTE_SPIN_MS)
}

function errorMessage(cause: unknown): string {
  const detail = (cause as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  if (detail === 'subscription_roulette_round_changed') return 'Начался новый розыгрыш. Закройте окно, чтобы открыть новую попытку.'
  if (detail === 'subscription_roulette_disabled') return 'Лотерея сейчас выключена. Уже начисленный подарок сохранён.'
  if (detail === 'subscription_roulette_verification_required') return 'Для участия подтвердите аккаунт через Telegram.'
  return 'Не удалось подтвердить результат. Проверьте соединение и нажмите «Проверить результат».'
}

async function recover(id: number, current: number, round: number): Promise<void> {
  phase.value = 'recovering'
  try {
    const data = await fetchRouletteStatus(round)
    if (id !== userId.value || current !== generation) return
    if (data.round_id !== round) throw new Error('Invalid roulette round')
    saveCurrentStatus(data)
    if (validRouletteDays(data.subscription_roulette_days)) {
      acceptSpin(data, id)
      return
    }
    phase.value = 'idle'
    error.value = data.eligible ? 'Выигрыш ещё не начислен. Ваша попытка доступна.' : 'Участие сейчас недоступно.'
  } catch (cause) {
    if (id !== userId.value || current !== generation) return
    const detail = (cause as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    phase.value = detail === 'subscription_roulette_round_changed' ? 'idle' : 'error'
    error.value = errorMessage(cause)
    if (detail === 'subscription_roulette_round_changed') void loadStatus().catch(() => {})
  } finally {
    if (id === userId.value && !['spinning', 'requesting'].includes(phase.value)) releaseRouletteNotifications(id)
    if (!open.value && id === userId.value && current === generation) clearClosedDialog()
  }
}

async function start(): Promise<void> {
  if (busy.value) return
  const id = userId.value
  const round = dialogRound.value
  if (!id || round === null) return
  const current = generation
  if (phase.value === 'error') {
    holdRouletteNotifications(id)
    await recover(id, current, round)
    return
  }
  if (!canSpin.value) return
  error.value = ''
  phase.value = 'requesting'
  holdRouletteNotifications(id)
  try {
    const data = await spinRoulette(round)
    if (id !== userId.value || current !== generation) return
    acceptSpin(data, id)
  } catch (cause) {
    if (id !== userId.value || current !== generation) return
    error.value = errorMessage(cause)
    await recover(id, current, round)
  }
}

function openDialog(): void {
  if (!showBanner.value) return
  dialogRound.value = currentRound.value
  displayResult.value = null
  resultDays.value = null
  phase.value = 'idle'
  hasOpened.value = true
  open.value = true
  error.value = ''
}

async function shareResult(): Promise<void> {
  if (!open.value || sharing.value || phase.value !== 'result') return
  const id = userId.value
  const round = dialogRound.value
  const days = resultDays.value
  const current = generation
  if (!id || round === null || !validRouletteDays(days)) return

  if (shareAttempt?.round !== round) {
    const clientMessageId = globalThis.crypto?.randomUUID?.() || 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, part => {
      const random = Math.floor(Math.random() * 16)
      return (part === 'x' ? random : (random & 0x3) | 0x8).toString(16)
    })
    shareAttempt = { round, clientMessageId, image: null }
  }
  const attempt = shareAttempt
  sharing.value = true
  error.value = ''
  try {
    if (!attempt.image) {
      const { createRouletteShareImage } = await import('@/services/subscriptionRouletteCard')
      attempt.image = await createRouletteShareImage(days)
    }
    if (current !== generation || id !== userId.value || round !== dialogRound.value || !open.value) return
    const sent = await globalChat.sendImage(attempt.image, attempt.clientMessageId)
    if (current !== generation || id !== userId.value || round !== dialogRound.value || !open.value) return
    if (sent) closeDialog()
    else error.value = 'Карточка не отправлена. Проверьте доступ к чату и попробуйте ещё раз.'
  } catch {
    if (current === generation && id === userId.value && round === dialogRound.value && open.value) {
      error.value = 'Не удалось подготовить карточку. Попробуйте ещё раз.'
    }
  } finally {
    if (current === generation && id === userId.value) sharing.value = false
  }
}

function closeDialog(): void {
  open.value = false
  const id = userId.value
  if (id) releaseRouletteNotifications(id)
  if (phase.value === 'spinning') finishSpin(id || 0)
  clearClosedDialog()
  if (!busy.value && contextReady.value) void loadStatus().catch(() => {})
}

function updateBannerOffset(): void {
  const height = showBanner.value ? banner.value?.offsetHeight ?? 0 : 0
  document.documentElement.style.setProperty('--subscription-roulette-banner-offset', height ? `${height + 16}px` : '0px')
}

watch(userId, id => {
  generation++
  statusRequest++
  stopSpinTimer()
  open.value = false
  hasOpened.value = false
  phase.value = 'idle'
  status.value = null
  displayResult.value = null
  dialogRound.value = null
  resultDays.value = null
  error.value = ''
  sharing.value = false
  shareAttempt = null
  setRouletteNotificationAccount(id)
}, { immediate: true, flush: 'sync' })

watch([userId, currentRound], ([id, round]) => {
  statusRequest++
  if (status.value && status.value.round_id < round) status.value = null
  if (id && user.user && (user.user.subscription_roulette_round ?? 0) < round) {
    user.applyProfile({ ...user.user, subscription_roulette_round: round, subscription_roulette_days: null })
  }
  clearClosedDialog()
  if (open.value && dialogRound.value !== round && !busy.value && phase.value !== 'result') {
    error.value = 'Начался новый розыгрыш. Закройте окно, чтобы открыть новую попытку.'
  }
}, { immediate: true })

watch([contextReady, currentRound, () => settings.subscriptionRouletteEnabled], ([ready]) => {
  if (ready) void loadStatus().catch(() => {})
}, { immediate: true })

watch(() => [user.user?.subscription_roulette_round, user.user?.subscription_roulette_days] as const, ([round, days]) => {
  if (round !== currentRound.value || !validRouletteDays(days) || busy.value || !open.value || dialogRound.value !== round) return
  displayResult.value = status.value?.round_id === round ? status.value : null
  resultDays.value = days
  phase.value = 'result'
})

watch(() => route.name, () => { if (open.value) closeDialog() })
watchEffect(() => {
  if (!settings.subscriptionRouletteEnabled && open.value && !busy.value && phase.value !== 'result') {
    error.value = 'Лотерея сейчас выключена.'
  }
})
watch([showBanner, banner], async () => {
  resizeObserver?.disconnect()
  await nextTick()
  if (banner.value) resizeObserver?.observe(banner.value)
  updateBannerOffset()
}, { flush: 'post' })

function onVisibility(): void {
  pageVisible.value = !document.hidden
  if (pageVisible.value && contextReady.value) void loadStatus().catch(() => {})
}
function onMotion(event: MediaQueryListEvent): void { reducedMotion.value = event.matches }

onMounted(() => {
  resizeObserver = new ResizeObserver(updateBannerOffset)
  if (banner.value) resizeObserver.observe(banner.value)
  document.addEventListener('visibilitychange', onVisibility)
  motionQuery.addEventListener('change', onMotion)
})
onBeforeUnmount(() => {
  generation++
  stopSpinTimer()
  resizeObserver?.disconnect()
  document.removeEventListener('visibilitychange', onVisibility)
  motionQuery.removeEventListener('change', onMotion)
  const id = userId.value
  if (id) releaseRouletteNotifications(id)
  document.documentElement.style.removeProperty('--subscription-roulette-banner-offset')
})
</script>

<style scoped lang="scss">
.roulette-invitation {
  position: fixed;
  left: 40px;
  bottom: 40px;
  z-index: 900;
  display: flex;
  align-items: center;
  gap: 14px;
  width: 450px;
  padding: 18px;
  box-sizing: border-box;
  border: 1px solid $neutral-white;
  border-radius: 20px;
  background-color: $neutral-50;
  color: $soft-purple-900;
  box-shadow: 0 8px 24px rgba($neutral-black, 0.2);
  .roulette-invitation__icon {
    display: grid;
    place-items: center;
    flex: 0 0 44px;
    height: 44px;
    border-radius: 50%;
    color: $soft-purple-800;
    background-color: rgba($red-500, 0.12);
    --ui-icon-width: 36px;
    --ui-icon-height: 36px;
    animation: roulette-invite-turn 5s cubic-bezier(0.16, 1, 0.3, 1) infinite;
    &.is-paused {
      animation-play-state: paused;
    }
  }
  .roulette-invitation__copy {
    display: flex;
    flex: 1;
    min-width: 0;
    flex-direction: column;
    gap: 6px;
    strong {
      font-family: Involve-Medium;
      font-weight: 500;
      font-size: 16px;
      line-height: 20px;
    }
    span {
      color: $soft-purple-700;
      font-family: Hauora-Regular;
      font-size: 13px;
      line-height: 18px;
    }
  }
  :deep(.ui-button:focus-visible) {
    outline: 3px solid $soft-purple-500;
    outline-offset: 3px;
  }
}
.roulette-invitation-enter-active,
.roulette-invitation-leave-active {
  transition: opacity 0.25s, transform 0.25s;
}
.roulette-invitation-enter-from,
.roulette-invitation-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
@keyframes roulette-invite-turn {
  0%,
  16% {
    transform: rotate(0);
  }
  38%,
  100% {
    transform: rotate(360deg);
  }
}
</style>
