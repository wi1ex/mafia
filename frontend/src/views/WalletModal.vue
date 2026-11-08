<template>
  <Teleport to="#desktop-teleport-root">
    <Transition name="wallet-overlay">
      <div v-if="open && !restriction" class="wallet-overlay" :style="{ zIndex }" @pointerdown.self="armed = true" @pointerup.self="armed && requestClose()" @pointerleave.self="armed = false">
        <section ref="dialog" class="wallet-modal" role="dialog" aria-modal="true" :aria-labelledby="settings.paymentsEnabled ? 'wallet-title' : 'wallet-unavailable-title'" tabindex="-1" @keydown="onDialogKeydown">
          <template v-if="!settings.paymentsEnabled">
            <div class="wallet-unavailable">
              <div class="wallet-unavailable-copy">
                <h2 id="wallet-unavailable-title">Упс! Что-то пошло не так.</h2>
                <p>В данный момент платежи не принимаются</p>
              </div>
              <img class="wallet-unavailable-art" :src="paymentsUnavailableImage" alt="" aria-hidden="true" />
            </div>
            <div class="wallet-unavailable-actions">
              <UiButton size="low" text="Закрыть" @click="requestClose" />
            </div>
          </template>
          <template v-else>
            <header :class="{ 'wallet-header--gift': isGift }">
              <div class="wallet-header-balance" :class="{ 'wallet-header-balance--long': balanceText.length > 12 }" role="status" aria-live="polite" aria-atomic="true" :aria-label="`Баланс: ${balanceText} DC`">
                <strong>{{ balanceText }}</strong>
                <UiIcon class="wallet-balance-icon" :icon="iconCoin" />
              </div>
              <div class="wallet-heading">
                <h2 id="wallet-title">{{ isGift ? lockedTab === 'gifts' ? 'Отправить подарок' : 'Подарить подписку' : 'Магазин' }}</h2>
              </div>
              <UiButton class="wallet-close" variant="white" size="low" :icon="iconClose" aria-label="Закрыть" :disabled="busy" @click="requestClose" />
            </header>
            <div v-if="isGift" class="wallet-gift-recipient">
              <span>Пользователю</span>
              <div class="wallet-gift-user">
                <img v-minio-img="{ key: giftAvatarKey, placeholder: defaultAvatar, lazy: false }" alt="" />
                <strong>{{ giftRecipientName }}</strong>
              </div>
            </div>
            <div v-else class="wallet-tabs" role="group" aria-label="Разделы магазина">
              <UiButton v-for="item in walletTabs" :key="item.id" class="wallet-choice" size="middle" width="100%"
                        :class="{ 'wallet-choice--brand': item.id === 'coins' }"
                        :variant="tab === item.id ? 'green' : 'white'" :icon="item.icon" :text="item.label"
                        :aria-pressed="tab === item.id" :disabled="busy || opening" @click="changeTab(item.id)" />
            </div>
            <p v-if="opening" class="wallet-state" role="status">Загрузка…</p>
            <p v-if="error" class="wallet-error" role="alert">{{ error }}</p>
            <p v-if="isGift && !giftRecipientValid" class="wallet-error" role="alert">Выберите другого пользователя для подарка.</p>

            <div v-if="!isGift" v-show="tab === 'coins'" id="wallet-coins" role="region" aria-label="Пополнение баланса" class="wallet-panel">
              <form class="wallet-form" @submit.prevent="payCoins">
                <div class="wallet-package-grid" role="group" aria-label="Пакет монет">
                  <button v-for="coinPackage in COIN_PACKAGES" :key="coinPackage.quantity" class="wallet-package-card wallet-package-card--coins" type="button"
                          :class="{ active: quantity === coinPackage.quantity }" :aria-pressed="quantity === coinPackage.quantity"
                          :disabled="busy || opening" @click="quantity = coinPackage.quantity">
                    <span v-if="coinPackage.discount" class="wallet-discount">−{{ coinPackage.discount }}%</span>
                    <img class="wallet-coin-illustration" :src="coinPackageImages[coinPackage.quantity]" width="512" height="384" alt="" aria-hidden="true" loading="lazy" decoding="async" />
                    <strong>{{ coinPackage.quantity }} DC</strong>
                    <span>{{ dcMoney(settings.dcCoinPackages[coinPackage.quantity][currency], 1, currency) }}</span>
                  </button>
                </div>
                <div class="wallet-payment-fields">
                  <div class="wallet-payment-field">
                    <label for="dc-email" class="wallet-payment-label">Ваш Email</label>
                    <UiInput id="dc-email" v-model.trim="email" type="email" autocomplete="email" label="" label-mode="placeholder"
                             placeholder="mail@example.com" mode="light" size="low" :disabled="busy || opening" />
                  </div>
                  <div class="wallet-payment-field">
                    <span id="wallet-currency-label" class="wallet-payment-label">Валюта оплаты</span>
                    <div class="wallet-currencies" role="group" aria-labelledby="wallet-currency-label">
                      <UiButton v-for="item in currencies" :key="item" class="wallet-choice" size="low"
                                :variant="currency === item ? 'green' : 'white'" :icon="currencyIcons[item]" :text="item"
                                :aria-pressed="currency === item" :disabled="busy" @click="selectCurrency(item)" />
                    </div>
                  </div>
                  <div class="wallet-payment-field">
                    <span id="wallet-payment-method-label" class="wallet-payment-label">Способ оплаты</span>
                    <div class="wallet-payment-methods" role="group" aria-labelledby="wallet-payment-method-label">
                      <UiButton v-for="method in paymentMethods" :key="method.id" class="wallet-choice" size="low"
                                :class="{ 'wallet-choice--brand': method.colorIcon }"
                                :variant="paymentMethod === method.id ? 'green' : 'white'" :icon="method.icon" :text="method.label"
                                :aria-pressed="paymentMethod === method.id" :disabled="busy || opening" @click="paymentMethod = method.id" />
                    </div>
                  </div>
                </div>
                <UiButton class="wallet-action" type="submit" size="big" :text="wallet.invoiceBusy ? 'Создаём счёт…' : `Оплатить ${totalPrice}`" :disabled="!canPay" width="100%" />
              </form>
            </div>

            <div v-if="!lockedTab || lockedTab === 'subscription'" v-show="tab === 'subscription'" id="wallet-subscription" role="region" :aria-label="isGift ? 'Подарить подписку' : 'Покупка подписки'" class="wallet-panel">
              <form class="wallet-form" @submit.prevent="purchaseSubscription">
                <div class="wallet-package-grid" role="group" aria-label="Тариф подписки">
                  <button v-for="plan in SUBSCRIPTION_PLANS" :key="plan.id" class="wallet-package-card" type="button"
                          :class="{ active: subscriptionPlan === plan.id }" :aria-pressed="subscriptionPlan === plan.id"
                          :disabled="busy || opening" @click="subscriptionPlan = plan.id">
                    <span v-if="plan.discount" class="wallet-discount">−{{ plan.discount }}%</span>
                    <strong>{{ plan.label }}</strong><span>{{ plan.cost }} DC</span>
                  </button>
                </div>
                <div class="wallet-benefits-card">
                  <img class="background-image" :src="imageSlide8" alt="" aria-hidden="true" />
                  <ul class="wallet-benefits" aria-label="Привилегии подписки">
                    <li v-for="benefit in subscriptionBenefits" :key="benefit">
                      <UiIcon class="wallet-benefit-icon" :icon="iconCheckCircle" />
                      <span>{{ benefit }}</span>
                    </li>
                  </ul>
                </div>
                <UiButton class="wallet-action" type="submit" size="big" :text="wallet.subscriptionBusy ? 'Покупаем…' : `${isGift ? 'Подарить' : 'Купить'} за ${selectedPlan.cost} DC${canAffordSubscription ? '' : ' — недостаточно монет'}`" :disabled="!canAffordSubscription || !giftRecipientValid || busy || opening" width="100%" />
              </form>
            </div>

            <div v-if="tab === 'gifts'" id="wallet-gifts" role="region" aria-label="Подарки" class="wallet-panel"
                 :class="{ 'wallet-panel--gift-detail': selectedGift && !catalogError }">
              <p v-if="catalogLoading && !selectedGift" class="wallet-state" role="status">Загружаем подарки…</p>
              <template v-else-if="catalogError">
                <p class="wallet-error" role="alert">Не удалось загрузить подарки.</p>
                <UiButton size="low" text="Повторить" @click="refreshGiftCatalog" />
              </template>
              <form v-else-if="selectedGift" class="wallet-form wallet-gift-detail" @submit.prevent="purchaseGift">
                <GiftMedia :key="selectedGift.id" class="wallet-gift-preview" :media="selectedGift" animated
                           :label="`Подарок №${selectedGift.id}`" />
                <UiSwitch v-if="isGift" v-model="anonymousGift" label="Отправить анонимно" off-label="Выкл"
                          on-label="Вкл" theme="light" size="low" :width="128" :disabled="busy || opening" />
                <div class="wallet-gift-actions">
                  <UiButton class="wallet-gift-back" type="button" variant="white" size="low" text="К подаркам"
                            :disabled="busy || opening" @click="closeGiftPreview" />
                  <UiButton class="wallet-action" type="submit" size="big" :text="giftButtonText" :disabled="!canBuyGift" width="100%" />
                </div>
              </form>
              <p v-else-if="!giftCatalog.length" class="wallet-state">Подарков пока нет</p>
              <div v-else class="wallet-gift-grid" role="group" aria-label="Выберите подарок">
                <button v-for="gift in giftCatalog" :key="gift.id" class="wallet-gift-card" type="button" :data-gift-id="gift.id"
                        :aria-label="`Подарок №${gift.id}, ${gift.price_dc} DC`" :disabled="busy || opening" @click="openGiftPreview(gift.id)">
                  <GiftMedia class="wallet-gift-media" :media="gift" />
                  <span>{{ gift.price_dc }} DC</span>
                </button>
              </div>
            </div>
          </template>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore, useSettingsStore, useUserStore } from '@/store'
import { useWalletStore, dcErrorMessage, dcRequestUncertain, type CoinInvoice, type CoinPaymentMethod, type SubscriptionPurchaseResult } from '@/store/modules/wallet'
import { COIN_PACKAGES, DC_CURRENCIES, SUBSCRIPTION_PLANS, dcMoney, dcPurchaseRestriction, type CoinPackageQuantity, type DcCurrency, type SubscriptionPlan, type WalletTab } from '@/services/dc'
import { alertDialog } from '@/services/confirm'
import { loadGiftCatalog, type CatalogGift, type GiftPurchaseResult } from '@/services/gifts'
import GiftMedia from '@/components/GiftMedia.vue'
import UiButton from '@/components/UiButton.vue'
import UiIcon from '@/components/UiIcon.vue'
import UiInput from '@/components/UiInput.vue'
import UiSwitch from '@/components/UiSwitch.vue'

import imageSlide8 from '@/assets/images/carousel-image8.png'
import coins30 from '@/assets/images/coins-30.webp'
import coins100 from '@/assets/images/coins-100.webp'
import coins300 from '@/assets/images/coins-300.webp'
import coins1000 from '@/assets/images/coins-1000.webp'
import paymentsUnavailableImage from '@/assets/images/noPayments.webp'

import iconClose from '@/assets/svg/iconClose.svg'
import iconCheckCircle from '@/assets/svg/iconCheckCircle.svg'
import iconApple from '@/assets/svg/iconApple.svg'
import iconCard from '@/assets/svg/iconCard.svg'
import iconCoin from '@/assets/svg/iconCoin.svg'
import iconDollar from '@/assets/svg/iconDollar.svg'
import iconEuro from '@/assets/svg/iconEuro.svg'
import iconPaypal from '@/assets/svg/iconPaypal.svg'
import iconPresent from '@/assets/svg/iconPresent.svg'
import iconRouble from '@/assets/svg/iconRouble.svg'
import iconSBP from '@/assets/svg/iconSBP.svg'
import iconSubscribe from '@/assets/svg/iconSubscribe.svg'
import defaultAvatar from '@/assets/svg/iconDefaultAvatarBlack.svg'

type GiftRecipient = { user_id: number; username?: string | null; avatar_name?: string | null }

const props = withDefaults(defineProps<{ open: boolean; initialTab?: WalletTab; giftRecipient?: GiftRecipient | null; zIndex?: number }>(), {
  giftRecipient: null,
  zIndex: 1600,
})
const emit = defineEmits<{
  'update:open': [boolean]
  'busy': [boolean]
  'subscription-purchased': [SubscriptionPurchaseResult]
  'gift-purchased': [GiftPurchaseResult]
}>()
const auth = useAuthStore()
const userStore = useUserStore()
const settings = useSettingsStore()
const wallet = useWalletStore()
const route = useRoute()
const router = useRouter()
const dialog = ref<HTMLElement | null>(null)
const giftRecipientSnapshot = ref<GiftRecipient | null>(null)
const lockedTab = ref<'subscription' | 'gifts' | null>(null)
const isGift = computed(() => giftRecipientSnapshot.value !== null)
const giftRecipientName = computed(() => giftRecipientSnapshot.value?.username || `user${giftRecipientSnapshot.value?.user_id}`)
const giftAvatarKey = computed(() => {
  const name = String(giftRecipientSnapshot.value?.avatar_name || '').trim()
  return name && !name.startsWith('avatars/') ? `avatars/${name}` : name
})
const giftRecipientValid = computed(() => !isGift.value || (
  Number.isSafeInteger(giftRecipientSnapshot.value?.user_id)
  && Number(giftRecipientSnapshot.value?.user_id) > 0
  && giftRecipientSnapshot.value?.user_id !== userStore.user?.id
))
const tab = ref<WalletTab>('coins')
const walletTabs: { id: WalletTab; label: string; icon: string }[] = [
  { id: 'coins', label: 'Баланс', icon: iconCoin },
  { id: 'subscription', label: 'Подписка', icon: iconSubscribe },
  { id: 'gifts', label: 'Подарки', icon: iconPresent },
]
const subscriptionBenefits: readonly string[] = [
  'GIF-аватар, выбор цвета и иконки профиля',
  'статистика и история игр пользователей',
  'вход зрителем игры сверх лимита',
  'трансляции в высоком качестве',
  'создание скрытых комнат',
  'черный список пользователей',
  'безлимитное изменение никнейма и его истории',
]
const currencies = DC_CURRENCIES
const currencyIcons: Record<DcCurrency, string> = { RUB: iconRouble, USD: iconDollar, EUR: iconEuro }
const coinPackageImages: Record<CoinPackageQuantity, string> = { 30: coins30, 100: coins100, 300: coins300, 1000: coins1000 }
const currency = ref<DcCurrency>('RUB')
const paymentMethod = ref<CoinPaymentMethod>('card')
const paymentMethods = computed<readonly { id: CoinPaymentMethod; label: string; icon: string; colorIcon?: boolean }[]>(() => currency.value === 'RUB'
  ? [
    { id: 'card', label: 'Карта', icon: iconCard },
    { id: 'sbp', label: 'СБП', icon: iconSBP, colorIcon: true },
  ]
  : [
    { id: 'card', label: 'Карта', icon: iconCard },
    { id: 'apple_pay', label: 'ApplePay', icon: iconApple },
    { id: 'paypal', label: 'PayPal', icon: iconPaypal, colorIcon: true },
  ])
const quantity = ref<CoinPackageQuantity>(30)
const subscriptionPlan = ref<SubscriptionPlan>('week')
const email = ref('')
const error = ref('')
const opening = ref(false)
const giftCatalog = ref<CatalogGift[]>([])
const selectedGiftId = ref<number | null>(null)
const anonymousGift = ref(false)
const catalogLoading = ref(false)
const catalogError = ref(false)
let catalogRequest: AbortController | undefined
const armed = ref(false)
let openSequence = 0
const purchaseUnconfirmedMessage = 'Не удалось подтвердить покупку. Проверьте баланс и историю операций перед новой покупкой.'
const restriction = computed(() => dcPurchaseRestriction(auth.isAuthed, userStore.user, settings.verificationRestrictions))
const busy = computed(() => wallet.invoiceBusy || wallet.subscriptionBusy || wallet.giftBusy)
const balanceText = computed(() => new Intl.NumberFormat('ru-RU').format(wallet.balance))
const packageAmount = computed(() => settings.dcCoinPackages[quantity.value][currency.value])
const totalPrice = computed(() => dcMoney(packageAmount.value, 1, currency.value))
const selectedPlan = computed(() => SUBSCRIPTION_PLANS.find(item => item.id === subscriptionPlan.value)!)
const canAffordSubscription = computed(() => wallet.balance >= selectedPlan.value.cost)
const canPay = computed(() => !isGift.value && settings.paymentsEnabled && !busy.value && !opening.value && !restriction.value && email.value.trim().length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim()))
const selectedGift = computed(() => giftCatalog.value.find(item => item.id === selectedGiftId.value))
const canBuyGift = computed(() => !!selectedGift.value && wallet.balance >= selectedGift.value.price_dc
  && giftRecipientValid.value && !busy.value && !opening.value && !catalogLoading.value && !catalogError.value)
const giftButtonText = computed(() => {
  if (wallet.giftBusy) return 'Покупаем…'
  if (!selectedGift.value) return ''
  const action = isGift.value ? 'Отправить' : 'Купить'
  return `${action} за ${selectedGift.value.price_dc} DC${wallet.balance < selectedGift.value.price_dc ? ' — недостаточно монет' : ''}`
})

function paymentLink(invoice: CoinInvoice): string {
  try { const url = new URL(invoice.payment_url || ''); return url.protocol === 'https:' && !url.username && !url.password ? url.href : '' } catch { return '' }
}
function planLabel(planId: SubscriptionPlan): string { return SUBSCRIPTION_PLANS.find(item => item.id === planId)?.label || 'Подписка' }
function requestClose(): void { if (!busy.value || !settings.paymentsEnabled) emit('update:open', false) }
function handlePaymentsDisabled(err: unknown): boolean {
  const detail = (err as { response?: { data?: { detail?: string | { code?: string } } } })?.response?.data?.detail
  if ((typeof detail === 'object' ? detail?.code : detail) !== 'payments_disabled') return false
  settings.paymentsEnabled = false
  return true
}
function changeTab(next: WalletTab): void {
  if (lockedTab.value || busy.value || opening.value || tab.value === next) return
  error.value = ''
  tab.value = next
}
async function openGiftPreview(id: number): Promise<void> {
  error.value = ''
  selectedGiftId.value = id
  await nextTick()
  if (dialog.value) {
    dialog.value.scrollTop = 0
    dialog.value.querySelector<HTMLButtonElement>('.wallet-gift-back')?.focus({ preventScroll: true })
  }
}
async function closeGiftPreview(): Promise<void> {
  const id = selectedGiftId.value
  selectedGiftId.value = null
  error.value = ''
  await nextTick()
  dialog.value?.querySelector<HTMLButtonElement>(`[data-gift-id="${id}"]`)?.focus()
}
function selectCurrency(next: DcCurrency): void {
  currency.value = next
  if (!paymentMethods.value.some(method => method.id === paymentMethod.value)) paymentMethod.value = 'card'
}
function onDialogKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') { event.stopPropagation(); requestClose() }
  if (event.key !== 'Tab') return
  const focusable = dialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), a[href]')
  const visible = Array.from(focusable || []).filter(item => item.offsetParent !== null)
  const first = visible[0]; const last = visible.at(-1)
  if (!first || !last) { event.preventDefault(); return }
  if (document.activeElement === dialog.value) { event.preventDefault(); (event.shiftKey ? last : first).focus(); return }
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
function saveEmail(): void {
  try { sessionStorage.setItem(`dc:email:${userStore.user?.id}`, email.value.trim().toLowerCase()) } catch {}
}
function cancelGiftCatalog(): void {
  catalogRequest?.abort()
  catalogRequest = undefined
  catalogLoading.value = false
}
async function refreshGiftCatalog(): Promise<void> {
  if (!props.open || tab.value !== 'gifts' || !settings.paymentsEnabled || restriction.value) return
  cancelGiftCatalog()
  const request = new AbortController()
  catalogRequest = request
  catalogLoading.value = true
  catalogError.value = false
  try {
    const catalog = await loadGiftCatalog(request.signal)
    if (request.signal.aborted) return
    giftCatalog.value = catalog.filter(gift => gift.visible).sort((a, b) => a.price_dc - b.price_dc || a.id - b.id)
    if (!selectedGift.value) selectedGiftId.value = null
  } catch {
    if (!request.signal.aborted) catalogError.value = true
  } finally {
    if (catalogRequest === request) {
      catalogRequest = undefined
      catalogLoading.value = false
    }
  }
}
async function payCoins(): Promise<void> {
  if (!canPay.value) return
  error.value = ''
  const paymentTab = window.open('about:blank', '_blank')
  if (!paymentTab) {
    error.value = 'Разрешите открытие новой вкладки для перехода к оплате.'
    return
  }
  let paymentOpened = false
  const closePaymentTab = () => {
    try { if (!paymentTab.closed && paymentTab.location.href === 'about:blank') paymentTab.close() } catch {}
  }
  try {
    paymentTab.opener = null
    paymentTab.document.title = 'Переход к оплате'
    paymentTab.document.body.textContent = 'Подготавливаем страницу оплаты…'
  } catch {
    closePaymentTab()
    error.value = 'Не удалось открыть страницу оплаты. Попробуйте ещё раз.'
    return
  }
  saveEmail()
  const seq = openSequence
  const buyerId = userStore.user?.id
  const buyerSession = auth.sessionId
  const requestedCurrency = currency.value
  const requestedPaymentMethod = paymentMethod.value
  const requestedQuantity = quantity.value
  const requestedAmount = packageAmount.value
  try {
    const invoice = await wallet.createInvoice({
      quantity: requestedQuantity,
      currency: requestedCurrency,
      payment_method: requestedPaymentMethod,
      email: email.value.trim().toLowerCase(),
      expected_amount: requestedAmount,
    })
    if (seq !== openSequence || !props.open || !auth.isAuthed || buyerId !== userStore.user?.id || buyerSession !== auth.sessionId || !settings.paymentsEnabled || restriction.value) return
    const url = invoice.status === 'pending' ? paymentLink(invoice) : ''
    if (url) {
      if (paymentTab.closed) error.value = 'Вкладка оплаты закрыта. Нажмите «Оплатить», чтобы начать заново.'
      else if (paymentTab.location.href === 'about:blank') {
        paymentTab.location.replace(url)
        paymentOpened = true
      }
    } else if (invoice.status !== 'processed') {
      error.value = invoice.status === 'review'
        ? 'Оплата подтверждена. Начисление монет проверяется.'
        : 'Не удалось открыть страницу оплаты. Попробуйте ещё раз.'
    }
  } catch (err: any) {
    if (seq !== openSequence || buyerId !== userStore.user?.id || buyerSession !== auth.sessionId) return
    if (handlePaymentsDisabled(err)) return
    error.value = dcRequestUncertain(err)
      ? 'Не удалось открыть страницу оплаты. Попробуйте ещё раз.'
      : Number(err?.response?.status) === 429 ? 'Слишком много запросов. Попробуйте позже.' : dcErrorMessage(err)
    const detail = err?.response?.data?.detail
    if (detail?.code === 'dc_price_changed') {
      if (settings.dcCoinPackages[requestedQuantity][requestedCurrency] === requestedAmount && detail.amount) settings.setCoinPackagePrice(requestedQuantity, requestedCurrency, detail.amount)
      void settings.fetchPublic().catch(() => {})
    }
  } finally {
    if (!paymentOpened) closePaymentTab()
  }
}
async function purchaseSubscription(): Promise<void> {
  if (!props.open || tab.value !== 'subscription' || busy.value || opening.value || !settings.paymentsEnabled || restriction.value || !canAffordSubscription.value || !giftRecipientValid.value) return
  error.value = ''
  const seq = openSequence
  const buyerId = userStore.user?.id
  const buyerSession = auth.sessionId
  const purchasedPlan = subscriptionPlan.value
  const requestedRecipientId = giftRecipientSnapshot.value?.user_id
  try {
    const result = await wallet.buySubscription(purchasedPlan, requestedRecipientId)
    if (seq === openSequence && props.open && auth.isAuthed && buyerId === userStore.user?.id && buyerSession === auth.sessionId) {
      emit('subscription-purchased', result)
      emit('update:open', false)
      const recipientId = result.recipient_id ?? requestedRecipientId ?? buyerId
      if (recipientId && recipientId !== buyerId) {
        const recipientName = result.recipient_username || (recipientId === giftRecipientSnapshot.value?.user_id ? giftRecipientName.value : `user${recipientId}`)
        await nextTick()
        if (!auth.isAuthed || buyerId !== userStore.user?.id || buyerSession !== auth.sessionId) return
        void alertDialog({
          title: 'Подписка подарена',
          text: `Вы подарили подписку пользователю ${recipientName}. Срок: ${planLabel(purchasedPlan)}.`,
        })
      }
    }
  } catch (err) {
    if (seq !== openSequence || !props.open || !auth.isAuthed || buyerId !== userStore.user?.id || buyerSession !== auth.sessionId) return
    if (handlePaymentsDisabled(err)) return
    const detail = (err as { response?: { data?: { detail?: string | { code?: string } } } })?.response?.data?.detail
    const code = typeof detail === 'object' ? detail?.code : detail
    const status = Number((err as { response?: { status?: number } })?.response?.status)
    if (isGift.value && [403, 404].includes(status) && (code?.startsWith('gift_recipient_') || code === 'gift_self_not_allowed')) {
      await alertDialog(dcErrorMessage(err))
      if (seq === openSequence && props.open) emit('update:open', false)
      return
    }
    const insufficientBalance = code === 'insufficient_dc_balance'
    error.value = insufficientBalance ? '' : dcRequestUncertain(err) ? purchaseUnconfirmedMessage : dcErrorMessage(err)
    await wallet.refreshWallet().catch(() => {
      if (seq === openSequence && insufficientBalance) error.value = dcErrorMessage(err)
    })
  }
}

async function purchaseGift(): Promise<void> {
  if (!props.open || tab.value !== 'gifts' || busy.value || opening.value || !settings.paymentsEnabled || restriction.value) return
  const gift = selectedGift.value
  if (!gift || !canBuyGift.value) return
  error.value = ''
  const seq = openSequence
  const buyerId = userStore.user?.id
  const buyerSession = auth.sessionId
  const recipient = giftRecipientSnapshot.value
  const sameBuyer = () => auth.isAuthed && buyerId === userStore.user?.id && buyerSession === auth.sessionId
  const isCurrent = () => props.open && seq === openSequence && sameBuyer()
  try {
    const result = await wallet.buyGift({
      gift_id: gift.id,
      expected_dc_cost: gift.price_dc,
      ...(recipient ? { recipient_id: recipient.user_id, anonymous: anonymousGift.value } : {}),
    })
    if (!isCurrent()) return
    emit('gift-purchased', result)
    emit('update:open', false)
    if (result.recipient_id !== buyerId) {
      const name = result.recipient_username || (result.recipient_id === recipient?.user_id && recipient.username) || `user${result.recipient_id}`
      await nextTick()
      if (sameBuyer()) void alertDialog({ title: 'Подарок отправлен', text: `Вы отправили подарок пользователю ${name}.` })
    }
  } catch (err: any) {
    if (!isCurrent() || handlePaymentsDisabled(err)) return
    const detail = err?.response?.data?.detail
    const code = typeof detail === 'object' ? detail?.code : detail
    if (code === 'gift_price_changed' || code === 'gift_not_found' || code === 'gift_unavailable') void refreshGiftCatalog()
    const status = Number(err?.response?.status)
    if (recipient && [403, 404].includes(status) && typeof code === 'string' && code.startsWith('gift_recipient_')) {
      const messages: Record<string, string> = {
        gift_recipient_banned: 'Нельзя отправить подарок: пользователь находится в бане.',
        gift_recipient_unverified: 'Нельзя отправить подарок: пользователь не прошёл Telegram-верификацию.',
        gift_recipient_deleted: 'Нельзя отправить подарок: аккаунт получателя удалён.',
        gift_recipient_blacklisted: 'Нельзя отправить подарок из-за ограничений чёрного списка.',
      }
      await alertDialog(messages[code] || dcErrorMessage(err))
      if (isCurrent()) emit('update:open', false)
      return
    }
    if (code === 'insufficient_dc_balance' || code === 'insufficient_balance') {
      error.value = 'Недостаточно DC для покупки подарка.'
      void wallet.refreshWallet().catch(() => {})
      return
    }
    const uncertain = dcRequestUncertain(err)
    error.value = uncertain ? purchaseUnconfirmedMessage : dcErrorMessage(err)
    if (uncertain) void wallet.refreshWallet().catch(() => {})
  }
}

watch([() => props.open, () => settings.paymentsEnabled, () => auth.sessionId], async ([open, , session], previous) => {
  cancelGiftCatalog()
  const seq = ++openSequence
  armed.value = false
  opening.value = false
  if (!open) return
  if (previous?.[0] && session !== previous[2]) { emit('update:open', false); return }
  if (!previous?.[0]) {
    giftRecipientSnapshot.value = props.giftRecipient ? { ...props.giftRecipient } : null
    lockedTab.value = isGift.value ? props.initialTab === 'gifts' ? 'gifts' : 'subscription' : null
    giftCatalog.value = []
    selectedGiftId.value = null
    anonymousGift.value = false
    catalogError.value = false
  }
  opening.value = true
  if (!userStore.user && auth.isAuthed) await userStore.fetchMe().catch(() => {})
  if (seq !== openSequence) return
  if (restriction.value) { opening.value = false; emit('update:open', false); void alertDialog(restriction.value); return }
  if (!previous?.[0]) await settings.fetchPublic().catch(() => {})
  if (seq !== openSequence || restriction.value) return
  if (!settings.paymentsEnabled) {
    opening.value = false
    error.value = ''
    await nextTick()
    if (seq === openSequence && props.open) dialog.value?.querySelector<HTMLButtonElement>('button')?.focus({ preventScroll: true })
    return
  }
  wallet.ensureOwner()
  userStore.ensureClock()
  error.value = ''; opening.value = true
  tab.value = lockedTab.value || props.initialTab || 'coins'
  if (tab.value === 'gifts') void refreshGiftCatalog()
  try { email.value = sessionStorage.getItem(`dc:email:${userStore.user?.id}`) || '' } catch {}
  try {
    await wallet.refreshWallet()
  } catch (err) { if (seq === openSequence) error.value = dcErrorMessage(err) }
  finally {
    if (seq === openSequence) {
      opening.value = false
      await nextTick()
      if (seq === openSequence && props.open) dialog.value?.querySelector<HTMLButtonElement>('button')?.focus({ preventScroll: true })
    }
  }
}, { immediate: true })
watch(tab, (next) => {
  if (next === 'gifts') {
    if (!catalogRequest) void refreshGiftCatalog()
  } else {
    selectedGiftId.value = null
    cancelGiftCatalog()
  }
})
watch([() => props.open, busy], ([open, value]) => emit('busy', open && value), { immediate: true })
watch(restriction, reason => {
  if (props.open && reason && (userStore.user || !auth.isAuthed)) {
    cancelGiftCatalog()
    emit('update:open', false)
    void alertDialog(reason)
  }
})
watch(() => userStore.user?.id, () => { wallet.ensureOwner(); email.value = '' })
watch(() => [route.query.dc_payment, route.query.invoiceId, route.query.invoice_id], values => {
  if (props.giftRecipient || !values.some(Boolean)) return
  const query = { ...route.query }
  for (const key of ['dc_payment', 'order_id', 'invoice_id', 'invoiceId', 'status']) delete query[key]
  void router.replace({ query }).catch(() => {})
  if (auth.isAuthed) void userStore.fetchMe().catch(() => {})
}, { immediate: true })
onMounted(() => window.addEventListener('auth-gift_catalog_update', refreshGiftCatalog))
onBeforeUnmount(() => {
  openSequence++
  cancelGiftCatalog()
  window.removeEventListener('auth-gift_catalog_update', refreshGiftCatalog)
  emit('busy', false)
})
</script>

<style scoped lang="scss">
.wallet-overlay {
  position: fixed;
  inset: 0;
  z-index: 1600;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba($neutral-800, 0.2);
  backdrop-filter: blur(12px);
  box-sizing: border-box;
  .wallet-modal {
    display: flex;
    position: relative;
    flex-direction: column;
    gap: 24px;
    width: 800px;
    height: 611px;
    max-width: 100%;
    max-height: 100%;
    padding: 24px;
    box-sizing: border-box;
    overflow-y: auto;
    overscroll-behavior: contain;
    border-radius: 24px;
    background: $neutral-100;
    box-shadow: 0 2px 16px 0 rgba($neutral-black, 0.2);
    color: $neutral-black;
    font-family: Hauora-Regular;
    line-height: 1.4;
    --ui-input-label-bg: #{$neutral-100};
    .wallet-unavailable {
      display: flex;
      flex-direction: column;
      padding: 32px;
      .wallet-unavailable-art {
        margin-top: -10px;
        height: 300px;
        object-fit: contain;
        image-rendering: pixelated;
      }
      .wallet-unavailable-copy {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
        width: 100%;
        text-align: center;
        h2 {
          margin: 0;
          color: $neutral-black;
          font-family: Involve-Medium;
          font-weight: 500;
          font-size: 26px;
          line-height: 30px;
          letter-spacing: -0.52px;
        }
        p {
          max-width: 380px;
          color: $neutral-700;
          font-size: 18px;
          line-height: 26px;
          letter-spacing: -0.36px;
        }
      }
    }
    .wallet-unavailable-actions {
      display: flex;
      justify-content: center;
      padding: 64px 0 16px;
    }
    :deep(.ui-button--disabled) {
      --ui-button-disabled-bg: #{$neutral-200};
      --ui-button-disabled-color: #{$neutral-600};
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      .wallet-close {
        --ui-button-height: 24px;
        --ui-button-icon-size: 24px;
        --ui-button-bg: transparent;
        --ui-button-hover-bg: transparent;
        --ui-button-disabled-bg: transparent;
        --ui-button-hover-color: #{$green-500};
      }
      .wallet-header-balance {
        display: flex;
        position: absolute;
        top: 0;
        left: 50%;
        align-items: center;
        justify-content: center;
        gap: 6px;
        max-width: calc(100% - 48px);
        height: 38px;
        padding: 2px 14px 6px 18px;
        box-sizing: border-box;
        border-radius: 0 0 18px 18px;
        background: $neutral-white;
        transform: translateX(-50%);
        strong {
          min-width: 0;
          color: $neutral-black;
          font-family: Hauora-Bold;
          font-size: 20px;
          font-variant-numeric: tabular-nums;
          line-height: 24px;
        }
        .wallet-balance-icon {
          --ui-icon-width: 24px;
          --ui-icon-height: 24px;
        }
        &--long strong {
          font-size: 16px;
        }
      }
      .wallet-heading {
        display: flex;
        flex: 1;
        min-width: 0;
        h2 {
          font-weight: normal;
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
          margin: 0;
        }
      }
    }
    p {
      margin: 0;
    }
    .wallet-gift-recipient {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      border-radius: 16px;
      background: $neutral-white;
      > span {
        color: $neutral-600;
        font-size: 14px;
      }
      .wallet-gift-user {
        display: flex;
        align-items: center;
        gap: 4px;
        min-width: 0;
        img {
          display: block;
          flex: 0 0 24px;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          object-fit: cover;
        }
        strong {
          min-width: 0;
          color: $neutral-black;
          font-family: Hauora-Bold;
          font-size: 16px;
          overflow-wrap: anywhere;
        }
      }
    }
    .wallet-tabs {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      width: 100%;
    }
    .wallet-choice,
    .wallet-action {
      height: auto;
      min-height: var(--ui-button-height);
      max-width: 100%;
      padding-block: 4px;
      white-space: normal;
      overflow-wrap: anywhere;
    }
    .wallet-choice {
      --ui-button-padding-x: 8px;
    }
    .wallet-balance-icon,
    .wallet-choice--brand :deep(.ui-button__icon) {
      background: var(--ui-icon-url) center / contain no-repeat;
      -webkit-mask: none;
      mask: none;
    }
    .wallet-action {
      width: fit-content;
    }
    .wallet-state {
      color: $neutral-600;
      font-size: 14px;
    }
    .wallet-error {
      color: $red-700;
      font-size: 14px;
    }
    .wallet-panel {
      display: flex;
      flex-direction: column;
      gap: 20px;
      &--gift-detail {
        flex: 1 1 0;
        min-height: 230px;
      }
      .wallet-gift-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 10px;
        .wallet-gift-card {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 6px;
          padding: 8px;
          border: 2px solid transparent;
          border-radius: 16px;
          background: $neutral-white;
          color: $neutral-800;
          font: inherit;
          cursor: pointer;
          &:hover:not(:disabled),
          &:focus-visible {
            border-color: $green-500;
          }
          &:disabled {
            cursor: default;
          }
          .wallet-gift-media {
            height: auto;
            aspect-ratio: 1;
          }
          > span:not(.wallet-gift-media) {
            padding: 4px 8px;
            border-radius: 999px;
            background: $neutral-100;
            font-size: 14px;
            line-height: 16px;
            white-space: nowrap;
          }
        }
      }
      .wallet-benefits-card {
        display: flex;
        position: relative;
        flex-direction: column;
        padding: 24px;
        border-radius: 24px;
        background: $soft-purple-900;
        .background-image {
          position: absolute;
          left: 0;
          top: 0;
          width: 100%;
          height: 100%;
          border-radius: inherit;
          object-fit: cover;
        }
        .wallet-benefits {
          display: flex;
          flex-direction: column;
          gap: 6px;
          margin: 0;
          padding: 0;
          list-style: none;
          z-index: 1;
          li {
            display: flex;
            align-items: center;
            gap: 4px;
            .wallet-benefit-icon {
              --ui-icon-width: 24px;
              --ui-icon-height: 24px;
              --ui-icon-color: #{$neutral-white};
            }
            span {
              min-width: 0;
              color: $neutral-white;
              font-family: Hauora-Regular;
              font-size: 16px;
              line-height: 16px;
              letter-spacing: -0.32px;
              overflow-wrap: anywhere;
            }
          }
        }
      }
      .wallet-form {
        display: flex;
        flex-direction: column;
        gap: 24px;
        &.wallet-gift-detail {
          flex: 1;
          min-height: 0;
          gap: 12px;
          .wallet-gift-preview {
            flex: 1 1 0;
            min-height: 96px;
          }
          .wallet-gift-actions {
            display: grid;
            grid-template-columns: auto minmax(0, 1fr);
            align-items: center;
            gap: 8px;
          }
        }
        .wallet-payment-fields {
          display: flex;
          flex-direction: column;
          gap: 16px;
          .wallet-payment-field {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
            align-items: center;
            gap: 10px;
            .wallet-payment-label {
              margin-left: 4px;
              font-family: Hauora-Bold;
              font-size: 16px;
              line-height: 18px;
              letter-spacing: -0.32px;
              overflow-wrap: anywhere;
            }
            .wallet-currencies,
            .wallet-payment-methods {
              display: flex;
              justify-content: flex-end;
              gap: 10px;
              .wallet-choice {
                flex: 1 1 auto;
                min-width: 117px;
                max-width: 117px;
              }
            }
          }
        }
        .wallet-package-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
          .wallet-package-card {
            display: flex;
            position: relative;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 8px;
            min-width: 0;
            min-height: 85px;
            padding: 8px 0 12px;
            border: 2px solid transparent;
            border-radius: 20px;
            background: $neutral-white;
            color: $neutral-700;
            font-family: Hauora-Regular;
            cursor: pointer;
            .wallet-discount {
              position: absolute;
              top: -8px;
              right: 10px;
              padding: 4px 7px;
              border-radius: 999px;
              background: $red-500;
              color: $neutral-white;
              font-family: Hauora-Bold;
              font-size: 13px;
              line-height: 16px;
            }
            .wallet-coin-illustration {
              display: block;
              flex: 0 0 auto;
              width: 100%;
              height: 100px;
              object-fit: contain;
            }
            strong {
              max-width: 100%;
              font-family: Hauora-Bold;
              font-size: 22px;
              text-align: center;
              overflow-wrap: anywhere;
            }
            > span:not(.wallet-discount) {
              font-size: 17px;
              overflow-wrap: anywhere;
            }
            &.active {
              background: linear-gradient(261deg, $soft-purple-800 0%, $green-700 100%);
              border-color: $green-500;
              color: $neutral-white;
            }
            &:focus-visible {
              outline: 2px solid $green-400;
              outline-offset: 3px;
            }
            &:disabled {
              cursor: default;
              opacity: 0.65;
            }
          }
        }
      }
    }
  }
}
.wallet-overlay-enter-active,
.wallet-overlay-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.wallet-overlay-enter-from,
.wallet-overlay-leave-to {
  opacity: 0;
}
</style>
