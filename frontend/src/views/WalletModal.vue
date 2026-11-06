<template>
  <Teleport to="#desktop-teleport-root">
    <Transition name="wallet-overlay">
      <div v-if="open && !restriction" class="wallet-overlay" @pointerdown.self="armed = true" @pointerup.self="armed && requestClose()" @pointerleave.self="armed = false">
        <section ref="dialog" class="wallet-modal" role="dialog" aria-modal="true" :aria-labelledby="settings.paymentsEnabled ? 'wallet-title' : 'wallet-unavailable-title'" tabindex="-1" @keydown="onDialogKeydown">
          <template v-if="!settings.paymentsEnabled">
            <div class="wallet-unavailable">
              <img class="wallet-unavailable-art" :src="paymentsUnavailableImage" width="800" height="600" alt="" aria-hidden="true" />
              <div class="wallet-unavailable-copy">
                <h2 id="wallet-unavailable-title">Упс! Что-то пошло не так.</h2>
                <p>В данный момент платежи не принимаются</p>
              </div>
            </div>
            <div class="wallet-unavailable-actions">
              <UiButton size="middle" text="Закрыть" width="180px" @click="requestClose" />
            </div>
          </template>
          <template v-else>
            <header>
              <div class="wallet-header-balance" :class="{ 'wallet-header-balance--long': balanceText.length > 12 }" role="status" aria-live="polite" aria-atomic="true" :aria-label="`Баланс: ${balanceText} DC`">
                <strong>{{ balanceText }}</strong>
                <img :src="coins30" width="32" height="28" alt="" aria-hidden="true" />
              </div>
              <div class="wallet-heading">
                <h2 id="wallet-title">Магазин</h2>
              </div>
              <UiButton variant="white" size="low" :icon="iconClose" width="40px" aria-label="Закрыть" :disabled="busy" @click="requestClose" />
            </header>
            <UiSwitch v-model="subscriptionTabActive" class="wallet-tabs" off-label="Пополнение баланса" on-label="Покупка подписки" aria-label="Пополнение баланса / Покупка подписки" theme="light" without-text @change="onTabChange" />
            <p v-if="opening" class="wallet-state" role="status">Загрузка…</p>
            <p v-if="error" class="wallet-error" role="alert">{{ error }}</p>

            <div v-show="tab === 'coins'" id="wallet-coins" role="region" aria-label="Пополнение баланса" class="wallet-panel">
              <template v-if="selectedInvoice">
                <div class="wallet-summary invoice-summary">
                  <strong>{{ invoiceHeading(selectedInvoice) }}</strong>
                  <span>Заказ №{{ selectedInvoice.order_id }}</span>
                  <span>{{ selectedInvoice.quantity }} DC за {{ invoiceMoney(selectedInvoice) }}</span>
                  <p>{{ invoiceStatusText(selectedInvoice) }}</p>
                  <div class="wallet-actions">
                    <UiButton v-if="selectedInvoice.status === 'pending' && paymentLink(selectedInvoice)" :href="paymentLink(selectedInvoice)" text="Продолжить оплату" :disabled="busy || checking" />
                    <UiButton v-if="selectedInvoice.status !== 'processed' && selectedInvoice.status !== 'failed'" variant="white" :text="checking ? 'Проверяем оплату…' : 'Проверить оплату'" :disabled="checking || busy" @click="checkSelectedInvoice(false)" />
                    <UiButton v-if="selectedInvoice.status === 'processed'" text="Купить подписку" @click="tab = 'subscription'" />
                  </div>
                </div>
                <template v-if="selectedInvoice.status === 'unknown' && !paymentLink(selectedInvoice)">
                  <p class="wallet-state">Ссылка на оплату недоступна. Можно оформить другой счёт. Прежний заказ сохранится и будет доступен для проверки в списке выставленных счетов.</p>
                  <UiButton variant="white" text="Оформить другой счёт" :disabled="busy || checking" @click="newInvoice" />
                </template>
                <UiButton v-else-if="!['creating', 'unknown', 'review'].includes(selectedInvoice.status)" variant="white" text="Новый счёт" :disabled="busy || checking" @click="newInvoice" />
              </template>
              <div v-else-if="wallet.pending.invoice" class="wallet-summary">
                <p>Подтверждение создания счёта пока не получено. Проверим тот же заказ.</p>
                <UiButton :text="wallet.invoiceBusy ? 'Проверяем…' : 'Проверить создание счёта'" :disabled="busy" @click="recoverInvoice" />
              </div>
              <form v-else class="wallet-form" @submit.prevent="payCoins">
                <UiInput id="dc-email" v-model.trim="email" type="email" autocomplete="email" label="Email для оформления платежа" placeholder="mail@example.com" mode="light" :disabled="busy || opening" />
                <div class="wallet-currencies" role="group" aria-label="Валюта оплаты">
                  <button v-for="item in currencies" :key="item" type="button" :class="{ active: currency === item }" :aria-pressed="currency === item" :disabled="busy" @click="currency = item">{{ item }}</button>
                </div>
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
                <UiButton type="submit" :text="wallet.invoiceBusy ? 'Создаём счёт…' : `Оплатить ${totalPrice}`" :disabled="!canPay" width="100%" />
              </form>
              <div v-if="otherInvoices.length" class="wallet-orders">
                <span>Выставленные счета</span>
                <button v-for="invoice in otherInvoices" :key="invoice.order_id" type="button" :disabled="busy" @click="selectedOrderId = invoice.order_id">
                  <span>№{{ invoice.order_id }} · {{ invoice.quantity }} DC · {{ invoiceMoney(invoice) }}</span><small>{{ invoiceHeading(invoice) }}</small>
                </button>
              </div>
            </div>

            <div v-show="tab === 'subscription'" id="wallet-subscription" role="region" aria-label="Покупка подписки" class="wallet-panel">
              <div class="wallet-benefits-card">
                <img class="background-image" :src="imageSlide8" alt="" aria-hidden="true" />
                <ul class="wallet-benefits" aria-label="Привилегии подписки">
                  <li v-for="benefit in subscriptionBenefits" :key="benefit">
                    <UiIcon class="wallet-benefit-icon" :icon="iconCheckCircle" />
                    <span>{{ benefit }}</span>
                  </li>
                </ul>
              </div>
              <div v-if="wallet.pending.subscription" class="wallet-summary">
                <p>Проверяем результат покупки…</p>
                <span>Тариф: {{ planLabel(wallet.pending.subscription.plan) }}</span>
                <UiButton :text="wallet.subscriptionBusy ? 'Проверяем…' : 'Проверить результат покупки'" :disabled="busy" @click="purchaseSubscription(true)" />
              </div>
              <form v-else class="wallet-form" @submit.prevent="purchaseSubscription(false)">
                <div class="wallet-package-grid" role="group" aria-label="Тариф подписки">
                  <button v-for="plan in SUBSCRIPTION_PLANS" :key="plan.id" class="wallet-package-card" type="button"
                          :class="{ active: subscriptionPlan === plan.id }" :aria-pressed="subscriptionPlan === plan.id"
                          :disabled="busy || opening" @click="subscriptionPlan = plan.id">
                    <span v-if="plan.discount" class="wallet-discount">−{{ plan.discount }}%</span>
                    <strong>{{ plan.label }}</strong><span>{{ plan.cost }} DC</span>
                  </button>
                </div>
                <UiButton class="wallet-subscription-buy" type="submit" :text="wallet.subscriptionBusy ? 'Покупаем…' : `Купить за ${selectedPlan.cost} DC${canAffordSubscription ? '' : ' — недостаточно монет'}`" :disabled="!canAffordSubscription || busy || opening" width="100%" />
              </form>
            </div>
          </template>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore, useSettingsStore, useUserStore } from '@/store'
import { useWalletStore, dcErrorMessage, type CoinInvoice } from '@/store/modules/wallet'
import { COIN_PACKAGES, DC_CURRENCIES, SUBSCRIPTION_PLANS, dcMoney, dcPurchaseRestriction, type CoinPackageQuantity, type DcCurrency, type SubscriptionPlan, type WalletTab } from '@/services/dc'
import { alertDialog } from '@/services/confirm'
import UiButton from '@/components/UiButton.vue'
import UiIcon from '@/components/UiIcon.vue'
import UiInput from '@/components/UiInput.vue'
import UiSwitch from '@/components/UiSwitch.vue'
import imageSlide8 from '@/assets/images/carousel-image8.png'
import coins30 from '@/assets/images/coins-30.webp'
import coins100 from '@/assets/images/coins-100.webp'
import coins300 from '@/assets/images/coins-300.webp'
import coins1000 from '@/assets/images/coins-1000.webp'
import paymentsUnavailableImage from '@/assets/images/payments-unavailable.webp'
import iconClose from '@/assets/svg/iconClose.svg'
import iconCheckCircle from '@/assets/svg/iconCheckCircle.svg'

const props = defineProps<{ open: boolean; initialTab?: WalletTab }>()
const emit = defineEmits<{ 'update:open': [boolean] }>()
const auth = useAuthStore()
const userStore = useUserStore()
const settings = useSettingsStore()
const wallet = useWalletStore()
const route = useRoute()
const router = useRouter()
const dialog = ref<HTMLElement | null>(null)
const tab = ref<WalletTab>('coins')
const subscriptionTabActive = computed({
  get: () => tab.value === 'subscription',
  set: (value: boolean) => { tab.value = value ? 'subscription' : 'coins' },
})
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
const coinPackageImages: Record<CoinPackageQuantity, string> = { 30: coins30, 100: coins100, 300: coins300, 1000: coins1000 }
const currency = ref<DcCurrency>('RUB')
const quantity = ref<CoinPackageQuantity>(30)
const subscriptionPlan = ref<SubscriptionPlan>('week')
const email = ref('')
const error = ref('')
const opening = ref(false)
const checking = ref(false)
const selectedOrderId = ref<number | null>(null)
const armed = ref(false)
let openSequence = 0
let pollTimer: ReturnType<typeof setTimeout> | undefined
let invoiceRetryTimer: ReturnType<typeof setTimeout> | undefined
let subscriptionRetryTimer: ReturnType<typeof setTimeout> | undefined
let retriedInvoice = false
let retriedSubscription = false
const restriction = computed(() => dcPurchaseRestriction(auth.isAuthed, userStore.user, settings.verificationRestrictions))
const busy = computed(() => wallet.invoiceBusy || wallet.subscriptionBusy)
const balanceText = computed(() => new Intl.NumberFormat('ru-RU').format(wallet.balance))
const packageAmount = computed(() => settings.dcCoinPackages[quantity.value][currency.value])
const totalPrice = computed(() => dcMoney(packageAmount.value, 1, currency.value))
const selectedPlan = computed(() => SUBSCRIPTION_PLANS.find(item => item.id === subscriptionPlan.value)!)
const canAffordSubscription = computed(() => wallet.balance >= selectedPlan.value.cost)
const canPay = computed(() => settings.paymentsEnabled && !busy.value && !opening.value && !restriction.value && email.value.trim().length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim()))
const selectedInvoice = computed(() => wallet.invoices.find(item => item.order_id === selectedOrderId.value))
const otherInvoices = computed(() => wallet.invoices.filter(item => !['processed', 'failed'].includes(item.status) && item.order_id !== selectedOrderId.value))

function paymentLink(invoice: CoinInvoice): string {
  try { const url = new URL(invoice.payment_url || ''); return url.protocol === 'https:' && !url.username && !url.password ? url.href : '' } catch { return '' }
}
function invoiceMoney(invoice: CoinInvoice): string {
  return invoice.amount && invoice.currency ? dcMoney(invoice.amount, 1, invoice.currency) : '—'
}
function planLabel(planId: SubscriptionPlan): string { return SUBSCRIPTION_PLANS.find(item => item.id === planId)?.label || 'Подписка' }
function invoiceHeading(invoice: CoinInvoice): string {
  return { pending: 'Неоплаченный счёт', processed: 'Баланс пополнен', failed: 'Оплата не прошла', review: 'Оплата подтверждена', creating: 'Проверяем счёт…', unknown: 'Проверяем счёт…' }[invoice.status] || 'Счёт'
}
function invoiceStatusText(invoice: CoinInvoice): string {
  if (invoice.status === 'processed') return 'Монеты зачислены на баланс. Подписку можно купить отдельно.'
  if (invoice.status === 'review') return 'Оплата подтверждена. Монеты пока не зачислены. Повторно оплачивать счёт не нужно.'
  if (invoice.status === 'failed') return 'Оплата не прошла. Проверьте статус счёта перед повторной попыткой.'
  return 'Подтверждение оплаты пока не получено. Если вы уже оплатили счёт, повторно оплачивать не нужно.'
}
function requestClose(): void { if (!busy.value || !settings.paymentsEnabled) emit('update:open', false) }
function handlePaymentsDisabled(err: unknown): boolean {
  const detail = (err as { response?: { data?: { detail?: string | { code?: string } } } })?.response?.data?.detail
  if ((typeof detail === 'object' ? detail?.code : detail) !== 'payments_disabled') return false
  settings.paymentsEnabled = false
  return true
}
async function onTabChange(): Promise<void> {
  const seq = openSequence
  await nextTick()
  if (props.open && seq === openSequence) dialog.value?.focus({ preventScroll: true })
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
function newInvoice(): void { selectedOrderId.value = null; quantity.value = 30; error.value = '' }
function stopTimers(): void {
  clearTimeout(pollTimer)
  clearTimeout(invoiceRetryTimer)
  clearTimeout(subscriptionRetryTimer)
}
function scheduleCheck(): void {
  clearTimeout(pollTimer)
  if (!props.open || !settings.paymentsEnabled || restriction.value || !selectedInvoice.value || !['creating', 'unknown', 'pending'].includes(selectedInvoice.value.status)) return
  pollTimer = setTimeout(() => { void checkSelectedInvoice(true) }, 15_000)
}
async function checkSelectedInvoice(quiet = false): Promise<void> {
  const orderId = selectedOrderId.value
  if (!orderId || checking.value || restriction.value) return
  checking.value = true
  if (!quiet) error.value = ''
  try { await wallet.checkInvoice(orderId) }
  catch (err) { if (!quiet) error.value = dcErrorMessage(err) }
  finally { checking.value = false; scheduleCheck() }
}
async function payCoins(): Promise<void> {
  if (!canPay.value) return
  error.value = ''
  saveEmail()
  const seq = openSequence
  const requestedCurrency = currency.value
  const requestedQuantity = quantity.value
  const requestedAmount = packageAmount.value
  try {
    const invoice = await wallet.createInvoice({ quantity: requestedQuantity, currency: requestedCurrency, email: email.value.trim().toLowerCase(), expected_amount: requestedAmount })
    if (seq !== openSequence || !settings.paymentsEnabled || restriction.value) return
    selectedOrderId.value = invoice.order_id
    const url = invoice.status === 'pending' ? paymentLink(invoice) : ''
    if (url) window.location.assign(url)
    scheduleCheck()
  } catch (err: any) {
    if (seq !== openSequence) return
    if (handlePaymentsDisabled(err)) return
    error.value = dcErrorMessage(err)
    const detail = err?.response?.data?.detail
    if (detail?.code === 'dc_price_changed') {
      if (settings.dcCoinPackages[requestedQuantity][requestedCurrency] === requestedAmount && detail.amount) settings.setCoinPackagePrice(requestedQuantity, requestedCurrency, detail.amount)
      void settings.fetchPublic().catch(() => {})
    }
    if (wallet.pending.invoice && !retriedInvoice) {
      retriedInvoice = true
      invoiceRetryTimer = setTimeout(() => { if (props.open && !restriction.value) void recoverInvoice() }, 1500)
    }
  }
}
async function recoverInvoice(): Promise<void> {
  if (busy.value || !settings.paymentsEnabled || restriction.value) return
  error.value = ''
  const requestId = wallet.pending.invoice?.request_id
  try {
    await wallet.loadInvoices()
    if (!props.open || !settings.paymentsEnabled || restriction.value) return
    if (wallet.pending.invoice) selectedOrderId.value = (await wallet.createInvoice()).order_id
    else selectedOrderId.value = wallet.invoices.find(item => item.request_id === requestId)?.order_id ?? selectedOrderId.value
    scheduleCheck()
  } catch (err) { if (!handlePaymentsDisabled(err)) error.value = dcErrorMessage(err) }
}
async function purchaseSubscription(recover: boolean): Promise<void> {
  if (busy.value || !settings.paymentsEnabled || restriction.value || (!recover && !canAffordSubscription.value)) return
  error.value = ''
  const seq = openSequence
  try {
    await wallet.buySubscription(recover ? undefined : subscriptionPlan.value)
    if (seq === openSequence) emit('update:open', false)
  } catch (err) {
    if (seq !== openSequence) return
    if (handlePaymentsDisabled(err)) return
    const detail = (err as { response?: { data?: { detail?: string | { code?: string } } } })?.response?.data?.detail
    const insufficientBalance = (typeof detail === 'object' ? detail?.code : detail) === 'insufficient_dc_balance'
    error.value = insufficientBalance ? '' : dcErrorMessage(err)
    if (!wallet.pending.subscription) await wallet.refreshWallet().catch(() => {
      if (seq === openSequence && insufficientBalance) error.value = dcErrorMessage(err)
    })
    else if (!retriedSubscription) {
      retriedSubscription = true
      subscriptionRetryTimer = setTimeout(() => { if (props.open && !restriction.value) void purchaseSubscription(true) }, 1500)
    }
  }
}

watch([() => props.open, () => settings.paymentsEnabled], async ([open], previous) => {
  stopTimers()
  const seq = ++openSequence
  armed.value = false
  opening.value = false
  if (!open) return
  opening.value = true
  if (!userStore.user && auth.isAuthed) await userStore.fetchMe().catch(() => {})
  if (seq !== openSequence) return
  if (restriction.value) { opening.value = false; emit('update:open', false); void alertDialog(restriction.value); return }
  if (!previous[0]) await settings.fetchPublic().catch(() => {})
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
  selectedOrderId.value = null
  retriedInvoice = false; retriedSubscription = false
  tab.value = props.initialTab || (wallet.balance > 0 ? 'subscription' : 'coins')
  try { email.value = sessionStorage.getItem(`dc:email:${userStore.user?.id}`) || '' } catch {}
  try {
    await Promise.all([wallet.refreshWallet(), wallet.loadInvoices()])
    if (seq !== openSequence) return
    const rawOrder = Number(route.query.order_id || 0)
    const invoiceId = String(route.query.invoice_id || route.query.invoiceId || '')
    const returnInvoice = wallet.invoices.find(item => item.order_id === rawOrder || (!!invoiceId && item.invoice_id === invoiceId))
    if (route.query.dc_payment || invoiceId) {
      tab.value = 'coins'
      selectedOrderId.value = returnInvoice?.order_id ?? (Number.isSafeInteger(rawOrder) && rawOrder > 0 ? rawOrder : null)
      if (selectedOrderId.value) await checkSelectedInvoice()
      else error.value = 'Счёт не найден в вашем аккаунте.'
      if (seq !== openSequence) return
      const query = { ...route.query }
      for (const key of ['dc_payment', 'order_id', 'invoice_id', 'invoiceId', 'status']) delete query[key]
      await router.replace({ query })
    } else {
      selectedOrderId.value = wallet.invoices.find(item => !['processed', 'failed'].includes(item.status))?.order_id ?? null
      scheduleCheck()
    }
    if (wallet.pending.subscription) { tab.value = 'subscription'; void purchaseSubscription(true) }
  } catch (err) { if (seq === openSequence) error.value = dcErrorMessage(err) }
  finally {
    if (seq === openSequence) {
      opening.value = false
      await nextTick()
      if (seq === openSequence && props.open) dialog.value?.querySelector<HTMLButtonElement>('button')?.focus({ preventScroll: true })
    }
  }
})
watch(restriction, reason => {
  if (props.open && reason && (userStore.user || !auth.isAuthed)) {
    stopTimers()
    emit('update:open', false)
    void alertDialog(reason)
  }
})
watch(() => userStore.user?.id, () => { wallet.ensureOwner(); email.value = ''; selectedOrderId.value = null })
watch(() => [route.query.dc_payment, route.query.invoiceId, route.query.invoice_id], values => {
  if (values.some(Boolean) && !props.open) emit('update:open', true)
}, { immediate: true })
watch(selectedOrderId, scheduleCheck)
onBeforeUnmount(() => { openSequence++; stopTimers() })
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
    gap: 20px;
    width: 800px;
    height: 616px;
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
      display: grid;
      position: relative;
      min-height: min(420px, 55vh);
      padding: 16px;
      box-sizing: border-box;
      isolation: isolate;
      .wallet-unavailable-art {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        object-fit: contain;
        object-position: center bottom;
        image-rendering: pixelated;
        opacity: 0.32;
        z-index: -1;
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
      padding: 16px;
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
        img {
          display: block;
          flex: 0 0 32px;
          width: 32px;
          height: 28px;
          object-fit: contain;
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
    .wallet-tabs {
      width: 100%;
      --switch-height: 48px;
      --switch-knob: 50%;
      --switch-translate: 100%;
      :deep(label) {
        width: 100%;
      }
      :deep(.slider-option) {
        box-sizing: border-box;
        padding: 0 8px;
        font-size: 16px;
        line-height: 20px;
      }
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
      .wallet-benefits-card {
        display: flex;
        position: relative;
        flex-direction: column;
        padding: 16px 24px;
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
          gap: 4px;
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
      .wallet-summary {
        display: flex;
        flex-direction: column;
        gap: 8px;
        background: $neutral-white;
        padding: 20px;
        border-radius: 20px;
        strong {
          font-family: Hauora-Bold;
          font-size: 18px;
        }
        span {
          color: $neutral-600;
        }
        p {
          color: $neutral-700;
        }
        .wallet-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 8px;
        }
      }
      .wallet-form {
        display: flex;
        flex-direction: column;
        gap: 20px;
        .wallet-subscription-buy {
          height: auto;
          min-height: var(--ui-button-height);
          padding: 12px 16px;
          :deep(.ui-button__text) {
            white-space: normal;
            overflow: visible;
          }
        }
        .wallet-currencies {
          display: flex;
          gap: 10px;
          button {
            flex: 1;
            min-width: 0;
            border: 0;
            border-radius: 999px;
            padding: 12px 8px;
            background: $neutral-white;
            color: $neutral-700;
            font: inherit;
            cursor: pointer;
            &.active {
              background: linear-gradient(261deg, $soft-purple-800 0%, $green-700 100%);
              color: $neutral-white;
            }
            &:not(.active):not(:disabled):hover {
              color: $neutral-black;
            }
            &:focus-visible {
              outline: 2px solid $green-400;
            }
            &:disabled {
              cursor: default;
              opacity: 0.65;
            }
          }
        }
        .wallet-package-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
          @media (max-width: 600px) {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
          .wallet-package-card {
            display: flex;
            position: relative;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 8px;
            min-width: 0;
            min-height: 108px;
            padding: 22px 12px;
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
      .wallet-orders {
        display: flex;
        flex-direction: column;
        gap: 8px;
        color: $neutral-600;
        button {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          text-align: left;
          padding: 12px;
          background: $neutral-white;
          color: $neutral-black;
          border: 0;
          border-radius: 12px;
          font: inherit;
          cursor: pointer;
          small {
            color: $neutral-600;
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
