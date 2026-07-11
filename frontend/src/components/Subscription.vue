<template>
  <Teleport to="#desktop-teleport-root">
    <Transition name="subscription-purchase-overlay">
      <div v-if="open" class="subscription-purchase-overlay" @pointerdown.self="armed = true" @pointerup.self="armed && requestClose()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <div class="subscription-purchase-modal" role="dialog" aria-modal="true">
          <button class="close-btn" type="button" aria-label="Закрыть" @click="requestClose">
            <UiIcon class="close-icon" :icon="iconClose" />
          </button>
          <header>
            <div class="header-track" :class="{ 'is-kassa': kassaFormOpen }">
              <div class="header-div" :aria-hidden="kassaFormOpen ? 'true' : 'false'">
                <span class="header-title">Выбери свой план подписки или просто поддержи проект</span>
              </div>
              <div class="header-div" :aria-hidden="kassaFormOpen ? 'false' : 'true'">
                <span class="header-title">Оформление подписки</span>
                <span class="header-text">Настрой параметры платежа перед переходом на страницу оплаты</span>
              </div>
            </div>
          </header>

          <div class="subscription-purchase-content">
            <div class="subscription-purchase-track" :class="{ 'is-kassa': kassaFormOpen }">
              <div class="subscription-purchase-slide" :inert="kassaFormOpen ? true : undefined" :aria-hidden="kassaFormOpen ? 'true' : 'false'">
                <UiSwitch
                  v-model="subscribeYearSelected"
                  class="subscribe-switch"
                  label="Подписка"
                  off-label="Месяц"
                  on-label="Год"
                  on-badge="-15%"
                  theme="light"
                  without-text
                  aria-label="Выбор срока подписки"
                />
                <div class="subscribe">
                  <img class="background-image" :src="imageSlide8" alt="" aria-hidden="true" />
                  <span class="subscribe-price-value">Оформи подписку всего за <span class="subscribe-price-amount">{{ selectedSubscribePrice.amount }}</span><span class="subscribe-price-period">{{ selectedSubscribePrice.period }}</span></span>
                  <ul class="subscribe-benefits">
                    <li v-for="benefit in subscriptionBenefits" :key="benefit">
                      <UiIcon class="subscribe-benefit-icon" :icon="iconCheckCircle" />
                      <span>{{ benefit }}</span>
                    </li>
                  </ul>
                </div>
                <div class="subscription-actions">
                  <UiButton
                    variant="white"
                    text="Поддержать проект"
                    :icon="iconDonation"
                    :href="donateSite.url"
                    :disabled="!donateSite.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    @click="onDonateSelect"
                  />
                  <UiButton
                    text="Оформить подписку"
                    :icon="iconCard"
                    :disabled="kassaBusy"
                    @click="openKassaForm"
                  />
                </div>
              </div>

              <div class="subscription-purchase-slide" :inert="kassaFormOpen ? undefined : true" :aria-hidden="kassaFormOpen ? 'false' : 'true'">
                <form class="kassa-form" @submit.prevent="onKassaPay">
                  <UiInput
                    id="kassa-email"
                    v-model.trim="kassaForm.email"
                    type="email"
                    autocomplete="email"
                    label="Введите email"
                    placeholder="mail@example.com"
                    mode="light"
                  />

                  <div class="kassa-field">
                    <span class="kassa-text">Срок подписки</span>
                    <div class="kassa-segmented">
                      <button v-for="plan in kassaPlans" :key="plan.id" type="button" :class="{ active: kassaForm.plan === plan.id }" @click="kassaForm.plan = plan.id">
                        <span>{{ plan.label }}</span>
                        <span v-if="plan.id === 'year'" class="kassa-segmented-badge">-15%</span>
                      </button>
                    </div>
                  </div>

                  <div class="kassa-field">
                    <span class="kassa-text">Валюта</span>
                    <div class="kassa-segmented">
                      <button v-for="currency in kassaCurrencies" :key="currency" type="button" :class="{ active: kassaForm.currency === currency }" @click="kassaForm.currency = currency">
                        <UiIcon class="kassa-segmented-icon" :icon="kassaCurrencyIcons[currency]" />
                        <span>{{ currency }}</span>
                      </button>
                    </div>
                  </div>

                  <Transition name="kassa-payment-expand">
                    <div v-if="kassaForm.currency === 'RUB'" class="kassa-field">
                      <span class="kassa-text">Способ оплаты</span>
                      <div class="kassa-segmented">
                        <button v-for="method in availableKassaPaymentOptions" :key="method.id" type="button" :class="{ active: kassaForm.payment_option === method.id }" @click="kassaForm.payment_option = method.id">
                          <UiIcon class="kassa-segmented-icon" :icon="kassaPaymentOptionIcons[method.id]" />
                          <span>{{ method.label }}</span>
                        </button>
                      </div>
                    </div>
                  </Transition>

                  <UiInput
                    id="kassa-promo-code"
                    v-model.trim="kassaForm.promo_code"
                    type="text"
                    inputmode="text"
                    autocomplete="off"
                    label="Введите промокод"
                    placeholder="PROMOCODE"
                    mode="light"
                  />

                  <div class="kassa-actions">
                    <UiButton
                      class="kassa-back"
                      variant="white"
                      :icon="iconArrowDown"
                      icon-position="left"
                      text="Назад"
                      :disabled="kassaBusy"
                      @click="closeKassaForm"
                    />
                    <UiButton
                      class="kassa-submit"
                      type="submit"
                      :text="kassaSubmitText"
                      :disabled="kassaBusy"
                    />
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import UiIcon from '@/components/UiIcon.vue'
import UiInput from '@/components/UiInput.vue'
import UiSwitch from '@/components/UiSwitch.vue'
import UiButton from '@/components/UiButton.vue'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { useAuthStore, useSettingsStore } from '@/store'

import imageSlide8 from '@/assets/images/carousel-image8.png'
import iconClose from '@/assets/svg/iconClose.svg'
import iconCheckCircle from '@/assets/svg/iconCheckCircle.svg'
import iconDonation from '@/assets/svg/iconPresent.svg'
import iconArrowDown from '@/assets/svg/iconArrowDown.svg'
import iconRouble from '@/assets/svg/iconRouble.svg'
import iconDollar from '@/assets/svg/iconDollar.svg'
import iconEuro from '@/assets/svg/iconEuro.svg'
import iconCard from '@/assets/svg/iconCard.svg'
import iconSBP from '@/assets/svg/iconSBP.svg'

const props = defineProps<{
  open: boolean
}>()

type PaymentSite = {
  id: string
  name: string
  url: string
}

const emit = defineEmits<{
  'update:open': [boolean]
  'select': [PaymentSite]
}>()

const auth = useAuthStore()
const settings = useSettingsStore()
const kassaBusy = ref(false)
const kassaFormOpen = ref(false)
const kassaEmailStorageKey = 'kassa:buyerEmail'
const emailRe = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/i
const promoCodeRe = /^[A-Z0-9_-]{3,36}$/

type KassaPlan = 'month' | 'year'
type KassaCurrency = 'RUB' | 'USD' | 'EUR'
type KassaPaymentOptionId = 'card' | 'sbp'

type KassaPaymentOption = {
  id: KassaPaymentOptionId
  label: string
  currencies: readonly KassaCurrency[]
  payment_provider: string
  payment_method: string
}

const kassaCurrencyIcons: Record<KassaCurrency, string> = {
  RUB: iconRouble,
  USD: iconDollar,
  EUR: iconEuro,
}

const kassaPaymentOptionIcons: Record<KassaPaymentOptionId, string> = {
  card: iconCard,
  sbp: iconSBP,
}

const kassaPlans: readonly { id: KassaPlan; label: string }[] = [
  { id: 'month', label: 'Месяц' },
  { id: 'year', label: 'Год' },
]

const kassaPlanPrices: Record<KassaPlan, { amount: string; period: string }> = {
  month: { amount: '490 ₽', period: '/мес' },
  year: { amount: '4990 ₽', period: '/год' },
}

const kassaPaymentPrices: Record<KassaCurrency, Record<KassaPlan, string>> = {
  RUB: { month: '490 ₽', year: '4990 ₽' },
  EUR: { month: '6.9 €', year: '69 €' },
  USD: { month: '7.9 $', year: '79 $' },
}

const subscriptionBenefits: readonly string[] = [
  'GIF-аватары',
  'выбор цвета профиля',
  'выбор иконки профиля',
  'создание скрытых комнат',
  'отключение зрителей в игре',
  'трансляции в высоком качестве',
  'черный список пользователей',
  'увеличенный лимит на изменение никнейма',
  'обнуление истории своих никнеймов',
]

const kassaCurrencies: readonly KassaCurrency[] = ['RUB', 'USD', 'EUR']

const kassaPaymentOptions: readonly KassaPaymentOption[] = [
  {
    id: 'card',
    label: 'Карта',
    currencies: ['RUB'],
    payment_provider: 'SMART_GLOCAL',
    payment_method: 'CARD',
  },
  {
    id: 'sbp',
    label: 'СБП',
    currencies: ['RUB'],
    payment_provider: 'PAY2ME',
    payment_method: 'SBP',
  },
]

const kassaForm = ref<{
  email: string
  plan: KassaPlan
  currency: KassaCurrency
  payment_option: KassaPaymentOptionId
  promo_code: string
}>({
  email: '',
  plan: 'month',
  currency: 'RUB',
  payment_option: 'card',
  promo_code: '',
})

const availableKassaPaymentOptions = computed(() => (
  kassaPaymentOptions.filter((option) => option.currencies.includes(kassaForm.value.currency))
))
const subscribeYearSelected = computed({
  get: () => kassaForm.value.plan === 'year',
  set: (yearSelected: boolean) => {
    kassaForm.value.plan = yearSelected ? 'year' : 'month'
  },
})
const selectedSubscribePrice = computed(() => kassaPlanPrices[kassaForm.value.plan])
const kassaSubmitText = computed(() => (
  `Оплатить ${kassaPaymentPrices[kassaForm.value.currency][kassaForm.value.plan]}`
))

const donateSite = computed<PaymentSite>(() => ({
  id: 'donate',
  name: 'Donate',
  url: String(settings.donationUrl || '').trim(),
}))

const armed = ref(false)

function requestClose(): void {
  if (!kassaBusy.value) kassaFormOpen.value = false
  emit('update:open', false)
}

function onDonateSelect(): void {
  if (!donateSite.value.url) return
  emit('select', donateSite.value)
  requestClose()
}

function openKassaForm(): void {
  if (kassaBusy.value) return
  if (!auth.isAuthed) {
    void alertDialog('Войдите в аккаунт перед оплатой')
    return
  }

  const saved = localStorage.getItem(kassaEmailStorageKey) || ''
  kassaForm.value.email = kassaForm.value.email || saved
  kassaFormOpen.value = true
}

function closeKassaForm(): void {
  if (kassaBusy.value) return
  kassaFormOpen.value = false
}

function selectedKassaPaymentOption(): KassaPaymentOption {
  const selected = availableKassaPaymentOptions.value.find((option) => option.id === kassaForm.value.payment_option)
  return selected || kassaPaymentOptions[0]
}

function paymentProviderForOption(option: KassaPaymentOption): string {
  return option.payment_provider
}

function normalizedKassaEmail(): string | null {
  const email = kassaForm.value.email.trim().toLowerCase()
  if (!emailRe.test(email)) {
    void alertDialog('Введите корректный email')
    return null
  }

  kassaForm.value.email = email
  localStorage.setItem(kassaEmailStorageKey, email)
  return email
}

function normalizedPromoCode(): string | null {
  const promoCode = kassaForm.value.promo_code.trim()
  if (promoCode && !promoCodeRe.test(promoCode)) {
    void alertDialog('Промокод должен быть от 3 до 36 символов: заглавные латинские буквы A-Z, цифры 0-9, "-" или "_"')
    return null
  }

  kassaForm.value.promo_code = promoCode
  return promoCode
}

async function onKassaPay(): Promise<void> {
  if (kassaBusy.value) return
  if (!auth.isAuthed) {
    void alertDialog('Войдите в аккаунт перед оплатой')
    return
  }

  const email = normalizedKassaEmail()
  if (!email) return

  const promoCode = normalizedPromoCode()
  if (promoCode === null) return

  const paymentOption = kassaForm.value.currency === 'RUB' ? selectedKassaPaymentOption() : null
  const paymentProvider = paymentOption ? paymentProviderForOption(paymentOption) : ''

  kassaBusy.value = true
  const paymentWindow = window.open('', '_blank')
  if (paymentWindow) paymentWindow.opener = null
  try {
    const { data } = await api.post<{ payment_url: string; processed?: boolean }>('/payments/kassa/link', {
      email,
      plan: kassaForm.value.plan,
      currency: kassaForm.value.currency,
      payment_provider: paymentProvider,
      payment_method: paymentOption?.payment_method || '',
      promo_code: promoCode,
    })
    const paymentUrl = String(data?.payment_url || '')
    if (!paymentUrl && data?.processed) {
      if (paymentWindow) paymentWindow.close()
      requestClose()
      void alertDialog('Подписка активирована')
      return
    }

    if (!paymentUrl) throw new Error('payment_url_missing')
    emit('select', { id: 'kassa', name: 'kassa', url: paymentUrl })
    requestClose()
    if (paymentWindow) paymentWindow.location.href = paymentUrl
    else window.location.assign(paymentUrl)
  } catch (e: any) {
    if (paymentWindow) paymentWindow.close()
    const st = Number(e?.response?.status || 0)
    const detail = String(e?.response?.data?.detail || '')
    if (st === 401) void alertDialog('Войдите в аккаунт перед оплатой')
    else if (st === 422 && detail === 'kassa_email_required') void alertDialog('Введите email для отправки чека и оформления платежа')
    else if (st === 422 && detail === 'kassa_email_invalid') void alertDialog('Введите корректный email')
    else if (st === 422 && detail === 'kassa_email_rejected') void alertDialog('Сервис не принял этот email. Проверьте адрес или попробуйте другой')
    else if (st === 422 && detail === 'kassa_promo_code_invalid') void alertDialog('Промокод должен содержать только заглавные латинские буквы, цифры, "-" или "_"')
    else if (st === 422 && detail === 'kassa_promo_code_usage_limit_exceeded') void alertDialog('Лимит использования промокода исчерпан')
    else if (st === 422 && detail === 'kassa_promo_code_rejected') void alertDialog('Сервис не принял промокод для выбранного тарифа или валюты')
    else if (st === 422 && detail === 'kassa_currency_rejected') void alertDialog('Сервис не принял выбранную валюту. Выберите другую валюту')
    else if (st === 422 && detail === 'kassa_currency_invalid') void alertDialog('Выбрана неподдерживаемая валюта')
    else if (st === 422 && detail === 'kassa_plan_invalid') void alertDialog('Выбран неподдерживаемый тариф подписки')
    else if (st === 422 && detail === 'kassa_payment_method_rejected') void alertDialog('Сервис не принял выбранный способ оплаты. Выберите другой способ')
    else if (st === 422 && detail === 'kassa_payment_provider_invalid') void alertDialog('Выбран неподдерживаемый платежный провайдер')
    else if (st === 422 && detail === 'kassa_payment_method_invalid') void alertDialog('Выбран неподдерживаемый способ оплаты')
    else if (st === 422 && detail === 'kassa_payment_method_required') void alertDialog('Выберите способ оплаты')
    else if (st === 422 && detail === 'kassa_payment_method_unsupported') void alertDialog('Выбранный способ оплаты недоступен для этой валюты')
    else if (st === 422 && detail === 'kassa_request_rejected') void alertDialog('Сервис отклонил параметры платежа. Проверьте тариф, валюту и промокод')
    else if (st === 429 && detail === 'kassa_rate_limited') void alertDialog('Сервис временно ограничил частоту запросов. Повторите попытку позже')
    else if (st === 503 && detail === 'kassa_offer_not_found') void alertDialog('Тариф сервиса не найден. Сообщите администратору')
    else if (st === 503 && detail === 'kassa_api_unauthorized') void alertDialog('Оплата сервиса настроена неверно: API-ключ не принят')
    else if (st === 503 && detail === 'kassa_service_unavailable') void alertDialog('Сервис временно недоступен. Повторите попытку позже')
    else if (st === 503 && detail === 'kassa_product_missing') void alertDialog('Оплата сервиса не настроена: не указан продукт')
    else if (st === 503 && detail === 'kassa_api_key_missing') void alertDialog('Оплата сервиса не настроена: не указан API-ключ')
    else if (st === 503 && detail === 'kassa_monthly_offer_missing') void alertDialog('Оплата сервиса не настроена: не указан месячный тариф')
    else if (st === 503 && detail === 'kassa_yearly_offer_missing') void alertDialog('Оплата сервиса не настроена: не указан годовой тариф')
    else if (st === 502 && detail === 'kassa_contract_id_missing') void alertDialog('Сервис создал платеж без номера договора. Повторите попытку позже')
    else if (st === 502 && detail === 'kassa_payment_url_missing') void alertDialog('Сервис не вернул ссылку на оплату. Повторите попытку позже')
    else if (st === 502 && detail === 'kassa_invoice_invalid_response') void alertDialog('Сервис вернул некорректный ответ. Повторите попытку позже')
    else if (st === 502 && detail === 'kassa_invoice_request_failed') void alertDialog('Не удалось подключиться к сервису. Повторите попытку позже')
    else if (st === 502 && detail === 'kassa_invoice_failed') void alertDialog('Сервис отклонил создание платежа. Проверьте параметры или повторите попытку позже')
    else if (st === 502 && detail === 'kassa_free_invoice_not_processed') void alertDialog('Платеж без оплаты создан, но подписка не активировалась. Сообщите администратору')
    else if (st === 504 && detail === 'kassa_invoice_timeout') void alertDialog('Сервис не ответил вовремя. Повторите попытку позже')
    else if (st === 503 && detail.startsWith('kassa_')) void alertDialog('Оплата сервиса пока не настроена')
    else if (st === 422 && detail.startsWith('kassa_')) void alertDialog('Проверьте параметры оплаты')
    else void alertDialog('Не удалось открыть оплату сервиса')
  } finally {
    kassaBusy.value = false
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (!props.open) return
  if (event.key === 'Escape') requestClose()
}

watch(() => kassaForm.value.currency, () => {
  if (kassaForm.value.currency !== 'RUB') return

  const available = availableKassaPaymentOptions.value.some((option) => option.id === kassaForm.value.payment_option)
  if (!available) {
    kassaForm.value.payment_option = availableKassaPaymentOptions.value[0]?.id || 'card'
  }
})

watch(() => props.open, (open) => {
  armed.value = false
  if (open) {
    kassaForm.value.email = kassaForm.value.email || localStorage.getItem(kassaEmailStorageKey) || ''
    document.addEventListener('keydown', onKeydown)
  } else {
    kassaFormOpen.value = false
    document.removeEventListener('keydown', onKeydown)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped lang="scss">
.subscription-purchase-overlay {
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($neutral-800, 0.2);
  backdrop-filter: blur(12px);
  z-index: 1000;
  .subscription-purchase-modal {
    display: flex;
    position: relative;
    flex-direction: column;
    padding: 24px;
    width: 570px;
    height: 624px;
    border-radius: 24px;
    background-color: $neutral-100;
    box-shadow: 0 2px 16px 0 rgba($neutral-black, 0.20);
    overflow: hidden;
    .close-btn {
      position: absolute;
      top: 24px;
      right: 24px;
      z-index: 1;
      padding: 0;
      width: 24px;
      height: 24px;
      border: none;
      background: none;
      cursor: pointer;
      .close-icon {
        --ui-icon-width: 24px;
        --ui-icon-height: 24px;
        --ui-icon-color: #{$neutral-black};
      }
      &:not(:disabled):hover,
      &:not(:disabled):focus-visible,
      &:not(:disabled):active {
        .close-icon {
          --ui-icon-color: #{$green-500};
        }
      }
    }
    header {
      display: flex;
      overflow: hidden;
      .header-track {
        display: flex;
        flex: 0 0 200%;
        transition: transform 0.35s cubic-bezier(0.25, 1, 0.5, 1);
        &.is-kassa {
          transform: translateX(-50%);
        }
      }
      .header-div {
        display: flex;
        flex: 0 0 50%;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        .header-title {
          max-width: 350px;
          text-align: center;
          color: $neutral-black;
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        .header-text {
          color: $neutral-500;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 22px;
          letter-spacing: -0.32px;
        }
      }
    }
    .subscription-purchase-content {
      display: flex;
      overflow: hidden;
      .subscription-purchase-track {
        display: flex;
        flex: 0 0 200%;
        transition: transform 0.35s cubic-bezier(0.25, 1, 0.5, 1);
        &.is-kassa {
          transform: translateX(-50%);
        }
        .subscription-purchase-slide {
          flex: 0 0 50%;
          position: relative;
          overflow-y: auto;
          scrollbar-width: none;
          &[inert] {
            pointer-events: none;
          }
          &::-webkit-scrollbar {
            display: none;
          }
          .subscribe-switch {
            margin: 40px 0 16px;
          }
          .subscribe {
            display: flex;
            position: relative;
            flex-direction: column;
            margin-bottom: 40px;
            padding: 24px;
            gap: 40px;
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
            .subscribe-price-value {
              max-width: 250px;
              color: $neutral-white;
              font-family: Involve-Medium;
              font-size: 24px;
              line-height: 26px;
              letter-spacing: -0.48px;
              z-index: 1;
              .subscribe-price-amount {
                color: $green-500;
              }
              .subscribe-price-period {
                color: $neutral-500;
              }
            }
            .subscribe-benefits {
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
                .subscribe-benefit-icon {
                  --ui-icon-width: 20px;
                  --ui-icon-height: 20px;
                  --ui-icon-color: #{$neutral-white};
                }
                span {
                  color: $neutral-white;
                  font-family: Hauora-Regular;
                  font-size: 16px;
                  line-height: 16px;
                  letter-spacing: -0.32px;
                }
              }
            }
          }
          .subscription-actions {
            display: flex;
            justify-self: center;
            gap: 10px;
          }
          .kassa-form {
            display: flex;
            flex-direction: column;
            margin-top: 76px;
            gap: 24px;
            .kassa-field {
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 40px;
              .kassa-text {
                color: $neutral-black;
                font-family: Hauora-Bold;
                font-size: 16px;
                line-height: 18px;
                letter-spacing: -0.32px;
              }
              .kassa-segmented {
                display: flex;
                align-items: center;
                gap: 10px;
                button {
                  display: flex;
                  position: relative;
                  align-items: center;
                  justify-content: center;
                  padding: 0 16px;
                  gap: 4px;
                  width: 129px;
                  height: 48px;
                  border: none;
                  border-radius: 999px;
                  background-color: $neutral-white;
                  color: $neutral-400;
                  font-family: Hauora-Regular;
                  font-size: 18px;
                  line-height: 20px;
                  letter-spacing: -0.36px;
                  overflow: hidden;
                  cursor: pointer;
                  transition: color 0.25s ease-in-out;
                  &::before {
                    content: "";
                    position: absolute;
                    inset: 0;
                    border-radius: inherit;
                    background: linear-gradient(261deg, $soft-purple-800 0%, $green-700 100%);
                    opacity: 0;
                    pointer-events: none;
                    transition: opacity 0.25s ease-in-out;
                  }
                  span {
                    position: relative;
                    z-index: 1;
                  }
                  .kassa-segmented-icon {
                    position: relative;
                    z-index: 1;
                    --ui-icon-width: 24px;
                    --ui-icon-height: 24px;
                    --ui-icon-color: currentColor;
                  }
                  .kassa-segmented-badge {
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    padding: 3px 5px;
                    border-radius: 999px;
                    background-color: $red-500;
                    color: $neutral-white;
                    font-family: Hauora-Regular;
                    font-size: 14px;
                    line-height: 14px;
                    letter-spacing: -0.28px;
                    pointer-events: none;
                  }
                  &.active {
                    color: $neutral-white;
                    &::before {
                      opacity: 1;
                    }
                  }
                  &:not(.active):hover,
                  &:not(.active):focus-visible,
                  &:not(.active):active {
                    color: $neutral-black;
                  }
                }
              }
            }
            .kassa-actions {
              display: flex;
              position: absolute;
              left: 135px;
              bottom: 0;
              gap: 10px;
              .kassa-submit {
                min-width: 175px;
              }
              :deep(.kassa-back .ui-button__icon) {
                transform: rotate(90deg);
              }
            }
          }
        }
      }
    }
  }
}

.subscription-purchase-overlay-enter-active,
.subscription-purchase-overlay-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.subscription-purchase-overlay-enter-from,
.subscription-purchase-overlay-leave-to {
  opacity: 0;
}
.kassa-payment-expand-enter-active,
.kassa-payment-expand-leave-active {
  overflow: hidden;
  transition: max-height 0.25s ease-in-out, opacity 0.2s ease-in-out, transform 0.25s ease-in-out;
}
.kassa-payment-expand-enter-from,
.kassa-payment-expand-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-10px);
}
.kassa-payment-expand-enter-to,
.kassa-payment-expand-leave-from {
  max-height: 120px;
  opacity: 1;
  transform: translateY(0);
}

</style>
