import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/services/axios'
import { newDcRequestId, type CoinPackageQuantity, type DcCurrency, type SubscriptionPlan } from '@/services/dc'
import type { GiftPurchaseInput, GiftPurchaseResult } from '@/services/gifts'
import { useUserStore } from './user'
import { useAuthStore } from './auth'

export type CoinInvoice = {
  error_code?: string | null
  order_id: number
  status: 'creating' | 'unknown' | 'pending' | 'processed' | 'failed' | 'review'
  payment_url?: string | null
  invoice_id?: string | null
  quantity: number
  unit_price: string | null
  amount: string | null
  currency: DcCurrency | null
  email?: string | null
  request_id?: string | null
  dc_balance: number
}
export type WalletState = { dc_balance: number; subscription_active: boolean; subscription_until: string | null }
export type SubscriptionPurchaseResult = WalletState & { purchase_id: number; recipient_id?: number; recipient_username?: string | null; anonymous?: boolean }
export type CoinPaymentMethod = 'card' | 'sbp' | 'apple_pay' | 'paypal'
type InvoiceRequest = { quantity: CoinPackageQuantity; currency: DcCurrency; payment_method: CoinPaymentMethod; email: string; expected_amount: string; request_id: string }

export function dcErrorMessage(error: any, fallback = 'Не удалось получить результат операции.'): string {
  const detail = typeof error === 'string' ? error : error?.response?.data?.detail
  const code = typeof detail === 'object' ? detail?.code : detail
  const messages: Record<string, string> = {
    payments_disabled: 'В данный момент платежи не принимаются.',
    dc_price_changed: 'Стоимость монет изменилась. Проверьте новую сумму и нажмите «Оплатить» ещё раз.',
    insufficient_dc_balance: 'Недостаточно DC для покупки выбранной подписки.',
    insufficient_balance: 'Недостаточно DC для выполнения операции.',
    user_banned: 'Покупки недоступны: аккаунт забанен.',
    telegram_verification_required: 'Для покупок подтвердите аккаунт через Telegram.',
    rules_required: 'Для покупок примите актуальные правила сайта.',
    user_deleted: 'Аккаунт удалён. Покупки недоступны.',
    idempotency_conflict: 'Этот запрос уже отправлен с другими параметрами. Проверьте результат операции.',
    dc_quantity_invalid: 'Выберите пакет на 30, 100, 300 или 1000 DC.',
    dc_package_invalid: 'Выберите пакет на 30, 100, 300 или 1000 DC.',
    dc_payment_method_invalid: 'Этот способ оплаты недоступен для выбранной валюты.',
    dc_price_invalid: 'Цена пакета настроена некорректно. Попробуйте позже.',
    kassa_coin_offer_missing: 'Выбранный пакет недоступен в Lava. Выберите другой пакет или попробуйте позже.',
    kassa_coin_offer_invalid: 'Цены выбранного пакета временно недоступны. Попробуйте позже.',
    kassa_coin_offer_prices_mismatch: 'Цены выбранного пакета временно недоступны. Попробуйте позже.',
    kassa_amount_rejected: 'Lava отклонила цену пакета. Выберите другой пакет или попробуйте позже.',
    kassa_currency_disabled: 'Выбранная валюта отключена для оплаты в Lava. Выберите другую валюту.',
    kassa_api_key_missing: 'Подключение магазина к Lava временно недоступно. Попробуйте позже.',
    kassa_api_unauthorized: 'У магазина временно нет доступа к Lava. Попробуйте позже.',
    kassa_rate_limited: 'Слишком много запросов на оплату. Попробуйте позже.',
    kassa_invoice_timeout: 'Lava не ответила вовремя. Попробуйте ещё раз.',
    kassa_invoice_request_failed: 'Не удалось связаться с Lava. Попробуйте позже.',
    kassa_invoice_invalid_response: 'Lava вернула неожиданный ответ при создании счёта. Попробуйте позже.',
    kassa_service_unavailable: 'Платёжный сервис Lava временно недоступен. Попробуйте позже.',
    kassa_request_rejected: 'Lava отклонила запрос на создание счёта. Попробуйте позже.',
    dc_email_invalid: 'Введите корректный email.',
    dc_email_required: 'Введите корректный email.',
    kassa_email_invalid: 'Введите корректный email.',
    kassa_email_rejected: 'Lava отклонила этот email для оплаты. Проверьте адрес или укажите другой.',
    subscription_plan_invalid: 'Выберите тариф подписки.',
    gift_self_not_allowed: 'Нельзя подарить подписку самому себе.',
    gift_anonymous_requires_recipient: 'Укажите получателя для анонимного подарка.',
    gift_recipient_not_found: 'Получатель подарка не найден или его аккаунт удалён.',
    gift_recipient_deleted: 'Нельзя подарить подписку: аккаунт получателя удалён.',
    gift_recipient_invalid: 'Выберите другого пользователя для подарка.',
    gift_recipient_banned: 'Нельзя подарить подписку: пользователь находится в бане.',
    gift_recipient_unverified: 'Нельзя подарить подписку: пользователь не прошёл Telegram-верификацию.',
    gift_not_found: 'Подарок больше недоступен.',
    gift_unavailable: 'Подарок больше недоступен.',
    gift_price_changed: 'Стоимость подарка изменилась. Проверьте новую цену.',
    subscription_duration_too_large: 'Выберите меньший срок подписки.',
    dc_balance_too_large: 'Количество монет превышает допустимый предел.',
    coin_order_not_found: 'Счёт не найден в вашем аккаунте.',
  }
  if (typeof code === 'string' && Object.hasOwn(messages, code)) return messages[code]
  if (Number(error?.response?.status) === 401) return 'Для покупок войдите в аккаунт.'
  if (Number(error?.response?.status) === 403) return 'Операция недоступна для этого аккаунта.'
  if (Number(error?.response?.status) === 429) return 'Слишком много запросов. Попробуйте позже.'
  if (Number(error?.response?.status) === 422) return 'Проверьте параметры операции.'
  if (Number(error?.response?.status) === 503) return 'Оплата временно недоступна. Попробуйте позже.'
  return fallback
}

export function dcRequestUncertain(error: any): boolean {
  const status = Number(error?.response?.status || 0)
  const detail = error?.response?.data?.detail
  const definiteErrors = ['payments_disabled', 'kassa_coin_offer_missing', 'kassa_coin_offer_invalid', 'kassa_coin_offer_prices_mismatch', 'kassa_api_key_missing', 'kassa_api_unauthorized', 'dc_price_invalid']
  return status === 0 || (status >= 500 && !definiteErrors.includes(detail)) || (status === 409 && ['request_pending', 'operation_pending'].includes(detail))
}

export const useWalletStore = defineStore('wallet', () => {
  const user = useUserStore()
  const auth = useAuthStore()
  const loading = ref(false)
  const invoiceBusy = ref(false)
  const subscriptionBusy = ref(false)
  const giftBusy = ref(false)
  const ownerId = ref(0)
  let ownerSession = ''
  let refreshSequence = 0
  const balance = computed(() => user.user?.dc_balance ?? 0)

  function ensureOwner(): number {
    const uid = Number(user.user?.id || 0)
    if (ownerId.value !== uid || ownerSession !== auth.sessionId) {
      ownerId.value = uid
      ownerSession = auth.sessionId
      refreshSequence++
      loading.value = false
      invoiceBusy.value = false
      subscriptionBusy.value = false
      giftBusy.value = false
    }
    return uid
  }
  function ownsRequest(uid: number, session: string): boolean {
    return uid === ownerId.value && uid === Number(user.user?.id) && session === ownerSession && session === auth.sessionId
  }
  function applyState(state: Partial<WalletState>, uid: number): void {
    if (Number(user.user?.id) !== uid) return
    user.setWalletState(state)
  }
  async function refreshWallet(): Promise<void> {
    const uid = ensureOwner()
    if (!uid) return
    const session = ownerSession
    const sequence = ++refreshSequence
    const previous = user.user
    const previousBalance = previous?.dc_balance
    const previousEnd = previous?.subscription_until
    loading.value = true
    try {
      const { data } = await api.get<WalletState>('/payments/wallet')
      if (ownsRequest(uid, session) && sequence === refreshSequence && user.user === previous && user.user?.dc_balance === previousBalance && user.user?.subscription_until === previousEnd) applyState(data, uid)
    } finally { if (sequence === refreshSequence) loading.value = false }
  }
  async function createInvoice(input: Omit<InvoiceRequest, 'request_id'>): Promise<CoinInvoice> {
    const uid = ensureOwner()
    if (!uid || invoiceBusy.value) throw new Error('operation_busy')
    const session = ownerSession
    const request = { ...input, request_id: newDcRequestId() }
    invoiceBusy.value = true
    try {
      const { data } = await api.post<CoinInvoice>('/payments/coins/invoices', request)
      if (data.status === 'processed' && ownsRequest(uid, session)) void refreshWallet().catch(() => {})
      return data
    } finally { if (ownsRequest(uid, session)) invoiceBusy.value = false }
  }
  async function buySubscription(plan: SubscriptionPlan, recipientId?: number, anonymous = false): Promise<SubscriptionPurchaseResult> {
    const uid = ensureOwner()
    if (!uid || subscriptionBusy.value) throw new Error('operation_busy')
    const session = ownerSession
    if (recipientId !== undefined && (!Number.isSafeInteger(recipientId) || recipientId <= 0 || recipientId === uid)) throw new Error('gift_recipient_invalid')
    const request = { plan, request_id: newDcRequestId(), recipient_id: recipientId, anonymous: anonymous || undefined }
    subscriptionBusy.value = true
    const previous = user.user
    const previousBalance = previous?.dc_balance
    const previousEnd = previous?.subscription_until
    try {
      const { data } = await api.post<SubscriptionPurchaseResult>('/payments/subscriptions', request)
      if (ownsRequest(uid, session)) {
        if (user.user === previous && user.user?.dc_balance === previousBalance && user.user?.subscription_until === previousEnd) {
          const recipient = data.recipient_id ?? recipientId ?? uid
          applyState(recipient === uid ? data : { dc_balance: data.dc_balance }, uid)
        }
        void refreshWallet().catch(() => {})
        window.dispatchEvent(new CustomEvent('dc-wallet-changed', { detail: { user_id: uid } }))
      }
      return data
    } finally { if (ownsRequest(uid, session)) subscriptionBusy.value = false }
  }

  async function buyGift(input: GiftPurchaseInput): Promise<GiftPurchaseResult> {
    const uid = ensureOwner()
    if (!uid || giftBusy.value || subscriptionBusy.value || invoiceBusy.value) throw new Error('operation_busy')
    const request = { ...input, request_id: newDcRequestId() }
    const session = ownerSession
    const previous = user.user
    const previousBalance = previous?.dc_balance
    giftBusy.value = true
    try {
      const { data } = await api.post<GiftPurchaseResult>('/gifts/purchases', request)
      if (ownsRequest(uid, session)) {
        if (user.user === previous && user.user?.dc_balance === previousBalance) applyState({ dc_balance: data.dc_balance }, uid)
        void refreshWallet().catch(() => {})
        window.dispatchEvent(new CustomEvent('dc-wallet-changed', { detail: { user_id: uid } }))
      }
      return data
    } finally {
      if (ownsRequest(uid, session)) giftBusy.value = false
    }
  }

  return { balance, loading, invoiceBusy, subscriptionBusy, giftBusy, ensureOwner, refreshWallet, createInvoice, buySubscription, buyGift }
})
