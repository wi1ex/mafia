import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/services/axios'
import { isSubscriptionPlan, newDcRequestId, type CoinPackageQuantity, type DcCurrency, type SubscriptionPlan } from '@/services/dc'
import type { GiftPurchaseInput, GiftPurchaseResult } from '@/services/gifts'
import { useUserStore } from './user'
import { useAuthStore } from './auth'

export type CoinInvoice = {
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
export type SubscriptionPurchaseResult = WalletState & { purchase_id: number; recipient_id?: number; recipient_username?: string | null }
export type CoinPaymentMethod = 'card' | 'sbp' | 'apple_pay' | 'paypal'
type InvoiceRequest = { quantity: CoinPackageQuantity; currency: DcCurrency; payment_method: CoinPaymentMethod; email: string; expected_amount: string; request_id: string }
type SubscriptionRequest = { plan: SubscriptionPlan; request_id: string; recipient_id?: number }
type GiftPurchaseRequest = GiftPurchaseInput & { request_id: string }
type PendingRequests = { subscription?: SubscriptionRequest; gift?: GiftPurchaseRequest }

function storageKey(userId: number): string { return `dc:requests:v2:${userId}` }
function readPending(userId: number): PendingRequests {
  try {
    const raw = JSON.parse(sessionStorage.getItem(storageKey(userId)) || '{}') as PendingRequests
    const validId = (id: unknown) => typeof id === 'string' && /^[a-f0-9-]{36}$/i.test(id)
    const validPositiveInt = (value: number | undefined) => Number.isSafeInteger(value) && Number(value) > 0
    const gift = raw.gift
    return {
      subscription: validId(raw.subscription?.request_id) && isSubscriptionPlan(raw.subscription?.plan) && (raw.subscription?.recipient_id === undefined || (Number.isSafeInteger(raw.subscription.recipient_id) && raw.subscription.recipient_id > 0)) ? raw.subscription : undefined,
      gift: gift && validId(gift.request_id) && validPositiveInt(gift.gift_id) && validPositiveInt(gift.expected_dc_cost)
        && (gift.recipient_id === undefined || validPositiveInt(gift.recipient_id))
        && (gift.anonymous === undefined || typeof gift.anonymous === 'boolean') ? gift : undefined,
    }
  } catch { return {} }
}

export function dcErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail
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
    kassa_coin_offer_invalid: 'Цены выбранного пакета временно недоступны. Попробуйте позже.',
    kassa_coin_offer_prices_mismatch: 'Цены выбранного пакета временно недоступны. Попробуйте позже.',
    dc_email_invalid: 'Введите корректный email.',
    dc_email_required: 'Введите корректный email.',
    kassa_email_invalid: 'Введите корректный email.',
    subscription_plan_invalid: 'Выберите тариф подписки.',
    gift_self_not_allowed: 'Нельзя подарить подписку самому себе.',
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
  if (messages[code]) return messages[code]
  if (Number(error?.response?.status) === 401) return 'Для покупок войдите в аккаунт.'
  if (Number(error?.response?.status) === 403) return 'Операция недоступна для этого аккаунта.'
  if (Number(error?.response?.status) === 429) return 'Слишком много запросов. Повторите проверку позже.'
  if (Number(error?.response?.status) === 422) return 'Проверьте параметры операции.'
  if (Number(error?.response?.status) === 503) return 'Оплата временно недоступна. Попробуйте позже.'
  return 'Не удалось получить результат. Проверьте состояние той же операции.'
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
  const pending = ref<PendingRequests>({})
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
      pending.value = uid > 0 ? readPending(uid) : {}
    }
    return uid
  }
  function ownsRequest(uid: number, session: string): boolean {
    return uid === ownerId.value && uid === Number(user.user?.id) && session === ownerSession && session === auth.sessionId
  }
  function savePending(uid: number): void {
    if (uid !== ownerId.value) return
    try {
      if (pending.value.subscription || pending.value.gift) sessionStorage.setItem(storageKey(uid), JSON.stringify(pending.value))
      else sessionStorage.removeItem(storageKey(uid))
    } catch {}
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
  async function buySubscription(plan?: SubscriptionPlan, recipientId?: number): Promise<SubscriptionPurchaseResult> {
    const uid = ensureOwner()
    if (!uid || subscriptionBusy.value) throw new Error('operation_busy')
    const session = ownerSession
    const replay = !!pending.value.subscription
    if (recipientId !== undefined && (!Number.isSafeInteger(recipientId) || recipientId <= 0 || recipientId === uid)) throw new Error('gift_recipient_invalid')
    if (plan && pending.value.subscription && (pending.value.subscription.recipient_id ?? uid) !== (recipientId ?? uid)) throw new Error('pending_recipient_mismatch')
    const request = pending.value.subscription || (plan ? { plan, request_id: newDcRequestId(), ...(recipientId === undefined ? {} : { recipient_id: recipientId }) } : null)
    if (!request) throw new Error('request_missing')
    pending.value.subscription = request
    savePending(uid)
    subscriptionBusy.value = true
    const previous = user.user
    const previousBalance = previous?.dc_balance
    const previousEnd = previous?.subscription_until
    try {
      const { data } = await api.post<SubscriptionPurchaseResult>('/payments/subscriptions', request)
      if (!replay && ownsRequest(uid, session) && user.user === previous && user.user?.dc_balance === previousBalance && user.user?.subscription_until === previousEnd) {
        const recipient = data.recipient_id ?? request.recipient_id ?? uid
        applyState(recipient === uid ? data : { dc_balance: data.dc_balance }, uid)
      }
      if (ownsRequest(uid, session)) void refreshWallet().catch(() => {})
      if (ownsRequest(uid, session)) {
        delete pending.value.subscription
        savePending(uid)
        window.dispatchEvent(new CustomEvent('dc-wallet-changed', { detail: { user_id: uid } }))
      }
      return data
    } catch (error) {
      if (!dcRequestUncertain(error) && ownsRequest(uid, session)) {
        delete pending.value.subscription
        savePending(uid)
      }
      throw error
    } finally { if (ownsRequest(uid, session)) subscriptionBusy.value = false }
  }

  async function buyGift(input?: GiftPurchaseInput): Promise<GiftPurchaseResult> {
    const uid = ensureOwner()
    if (!uid || giftBusy.value || subscriptionBusy.value || invoiceBusy.value) throw new Error('operation_busy')
    if (input && pending.value.gift) throw new Error('operation_pending')
    const request = pending.value.gift || (input ? { ...input, request_id: newDcRequestId() } : null)
    if (!request) throw new Error('request_missing')
    const session = ownerSession
    const previous = user.user
    const previousBalance = previous?.dc_balance
    pending.value.gift = request
    savePending(uid)
    giftBusy.value = true
    try {
      const { data } = await api.post<GiftPurchaseResult>('/gifts/purchases', request)
      if (ownsRequest(uid, session)) {
        if (user.user === previous && user.user?.dc_balance === previousBalance) applyState({ dc_balance: data.dc_balance }, uid)
        delete pending.value.gift
        savePending(uid)
        void refreshWallet().catch(() => {})
        window.dispatchEvent(new CustomEvent('dc-wallet-changed', { detail: { user_id: uid } }))
      }
      return data
    } catch (error) {
      if (!dcRequestUncertain(error) && ownsRequest(uid, session)) {
        delete pending.value.gift
        savePending(uid)
      }
      throw error
    } finally {
      if (ownsRequest(uid, session)) giftBusy.value = false
    }
  }

  return { balance, loading, invoiceBusy, subscriptionBusy, giftBusy, pending, ensureOwner, refreshWallet, createInvoice, buySubscription, buyGift }
})
