<template>
  <Teleport to="body">
    <Transition name="support-site-overlay">
      <div v-if="open" class="support-site-overlay" @pointerdown.self="armed = true" @pointerup.self="armed && requestClose()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <div class="support-site-modal" role="dialog" aria-modal="true">
          <button class="btn-close" type="button" aria-label="Закрыть" @click="requestClose">
            <UiIcon class="close-icon" :icon="iconClose" />
          </button>
          <header>
            <div class="header-track" :class="{ 'is-lava': lavaFormOpen }">
              <div class="header-div" :aria-hidden="lavaFormOpen ? 'true' : 'false'">
                <span class="header-title">Выбери свой план подписки или просто поддержи проект</span>
              </div>
              <div class="header-div" :aria-hidden="lavaFormOpen ? 'false' : 'true'">
                <span class="header-title">Оформление подписки</span>
                <span class="header-text">Настрой параметры платежа перед переходом на страницу оплаты</span>
              </div>
            </div>
          </header>

          <div class="support-site-content">
            <div class="support-site-track" :class="{ 'is-lava': lavaFormOpen }">
              <div class="support-site-slide" :inert="lavaFormOpen ? true : undefined" :aria-hidden="lavaFormOpen ? 'true' : 'false'">
                <UiSwitch
                  v-model="subscribeYearSelected"
                  class="subscribe-switch"
                  label="Подписка"
                  off-label="Месяц"
                  on-label="Год"
                  on-badge="-15%"
                  :width="472"
                  theme="light"
                  without-text
                  aria-label="Выбор срока подписки"
                />
                <div class="subscribe">
                  <img class="background-image" :src="imageSlide6" alt="" aria-hidden="true" />
                  <span class="subscribe-price-value">Оформи подписку всего за <span class="subscribe-price-amount">{{ selectedSubscribePrice.amount }}</span><span class="subscribe-price-period">{{ selectedSubscribePrice.period }}</span></span>
                  <ul class="subscribe-benefits">
                    <li v-for="benefit in subscriptionBenefits" :key="benefit">
                      <UiIcon class="subscribe-benefit-icon" :icon="iconCheckCircle" />
                      <span>{{ benefit }}</span>
                    </li>
                  </ul>
                </div>
                <div class="site-list">
                  <UiButton
                    variant="white"
                    text="Поддержать проект"
                    :icon="iconTribute"
                    :href="tributeSite.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    @click="onTributeSelect"
                  />
                  <UiButton
                    text="Оформить подписку"
                    :icon="iconLavaTop"
                    :disabled="lavaBusy"
                    @click="openLavaForm"
                  />
                </div>
              </div>

              <div class="support-site-slide" :inert="lavaFormOpen ? undefined : true" :aria-hidden="lavaFormOpen ? 'false' : 'true'">
                <form class="lava-form" @submit.prevent="onLavaPay">
                  <UiInput
                    id="lava-email"
                    v-model.trim="lavaForm.email"
                    class="lava-input"
                    type="email"
                    autocomplete="email"
                    label="Введите email"
                    placeholder="mail@example.com"
                    mode="light"
                  />

                  <div class="lava-field">
                    <span class="lava-text">Срок подписки</span>
                    <div class="lava-segmented">
                      <button v-for="plan in lavaPlans" :key="plan.id" type="button" :class="{ active: lavaForm.plan === plan.id }" @click="lavaForm.plan = plan.id">
                        {{ plan.label }}
                      </button>
                    </div>
                  </div>

                  <div class="lava-field">
                    <span class="lava-text">Валюта</span>
                    <div class="lava-segmented">
                      <button v-for="currency in lavaCurrencies" :key="currency" type="button" :class="{ active: lavaForm.currency === currency }" @click="lavaForm.currency = currency">
                        {{ currency }}
                      </button>
                    </div>
                  </div>

                  <Transition name="lava-payment-expand">
                    <div v-if="lavaForm.currency === 'RUB'" class="lava-field">
                      <span class="lava-text">Способ оплаты</span>
                      <div class="lava-segmented">
                        <button v-for="method in availableLavaPaymentOptions" :key="method.id" type="button" :class="{ active: lavaForm.payment_option === method.id }" @click="lavaForm.payment_option = method.id">
                          <span>{{ method.label }}</span>
                        </button>
                      </div>
                    </div>
                  </Transition>

                  <UiInput
                    id="lava-promo-code"
                    v-model.trim="lavaForm.promo_code"
                    class="lava-input"
                    type="text"
                    inputmode="text"
                    autocomplete="off"
                    label="Введите промокод"
                    placeholder="PROMOCODE"
                    mode="light"
                  />

                  <div class="lava-actions">
                    <UiButton
                      class="lava-back"
                      variant="white"
                      :icon="iconArrowDown"
                      icon-position="left"
                      text="Назад"
                      :disabled="lavaBusy"
                      @click="closeLavaForm"
                    />
                    <UiButton
                      class="lava-submit"
                      type="submit"
                      text="К оплате"
                      :disabled="lavaBusy"
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
import { useAuthStore } from '@/store'

import imageSlide6 from '@/assets/images/carousel-image6.png'
import iconClose from '@/assets/svg/iconClose.svg'
import iconCheckCircle from '@/assets/svg/iconCheckCircle.svg'
import iconTribute from '@/assets/svg/donateTribute.svg'
import iconLavaTop from '@/assets/svg/donateLavaTop.svg'
import iconArrowDown from '@/assets/svg/iconArrowDown.svg'

const props = defineProps<{
  open: boolean
}>()

type SupportSite = {
  id: string
  name: string
  url: string
}

const emit = defineEmits<{
  'update:open': [boolean]
  'select': [SupportSite]
}>()

const auth = useAuthStore()
const lavaBusy = ref(false)
const lavaFormOpen = ref(false)
const lavaEmailStorageKey = 'lava:buyerEmail'
const emailRe = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/i
const promoCodeRe = /^[A-Z0-9_-]{3,36}$/

type LavaPlan = 'month' | 'year'
type LavaCurrency = 'RUB' | 'USD' | 'EUR'
type LavaPaymentOptionId = 'card' | 'sbp'

type LavaPaymentOption = {
  id: LavaPaymentOptionId
  label: string
  currencies: readonly LavaCurrency[]
  payment_provider: string
  payment_method: string
}

const lavaPlans: readonly { id: LavaPlan; label: string }[] = [
  { id: 'month', label: '1 месяц' },
  { id: 'year', label: '12 месяцев' },
]

const lavaPlanPrices: Record<LavaPlan, { amount: string; period: string }> = {
  month: { amount: '490 ₽', period: '/мес' },
  year: { amount: '4990 ₽', period: '/год' },
}

const subscriptionBenefits: readonly string[] = [
  'GIF-аватары',
  'выбор цвета профиля',
  'выбор иконки профиля',
  'создание скрытых комнат',
  'отключение зрителей в игре',
  'трансляции в высоком качестве',
  'увеличенный лимит на изменение никнейма',
  'обнуление истории своих никнеймов',
]

const lavaCurrencies: readonly LavaCurrency[] = ['RUB', 'USD', 'EUR']

const lavaPaymentOptions: readonly LavaPaymentOption[] = [
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

const lavaForm = ref<{
  email: string
  plan: LavaPlan
  currency: LavaCurrency
  payment_option: LavaPaymentOptionId
  promo_code: string
}>({
  email: '',
  plan: 'month',
  currency: 'RUB',
  payment_option: 'card',
  promo_code: '',
})

const availableLavaPaymentOptions = computed(() => (
  lavaPaymentOptions.filter((option) => option.currencies.includes(lavaForm.value.currency))
))
const subscribeYearSelected = computed({
  get: () => lavaForm.value.plan === 'year',
  set: (yearSelected: boolean) => {
    lavaForm.value.plan = yearSelected ? 'year' : 'month'
  },
})
const selectedSubscribePrice = computed(() => lavaPlanPrices[lavaForm.value.plan])

const tributeSite: SupportSite = {
  id: 'tribute',
  name: 'Tribute',
  url: 'https://web.tribute.tg/d/Cvc',
}

const armed = ref(false)

function requestClose(): void {
  if (!lavaBusy.value) lavaFormOpen.value = false
  emit('update:open', false)
}

function onTributeSelect(): void {
  emit('select', tributeSite)
  requestClose()
}

function openLavaForm(): void {
  if (lavaBusy.value) return
  if (!auth.isAuthed) {
    void alertDialog('Войдите в аккаунт перед оплатой')
    return
  }

  const saved = localStorage.getItem(lavaEmailStorageKey) || ''
  lavaForm.value.email = lavaForm.value.email || saved
  lavaFormOpen.value = true
}

function closeLavaForm(): void {
  if (lavaBusy.value) return
  lavaFormOpen.value = false
}

function selectedLavaPaymentOption(): LavaPaymentOption {
  const selected = availableLavaPaymentOptions.value.find((option) => option.id === lavaForm.value.payment_option)
  return selected || lavaPaymentOptions[0]
}

function paymentProviderForOption(option: LavaPaymentOption): string {
  return option.payment_provider
}

function normalizedLavaEmail(): string | null {
  const email = lavaForm.value.email.trim().toLowerCase()
  if (!emailRe.test(email)) {
    void alertDialog('Введите корректный email')
    return null
  }

  lavaForm.value.email = email
  localStorage.setItem(lavaEmailStorageKey, email)
  return email
}

function normalizedPromoCode(): string | null {
  const promoCode = lavaForm.value.promo_code.trim()
  if (promoCode && !promoCodeRe.test(promoCode)) {
    void alertDialog('Промокод должен быть от 3 до 36 символов: заглавные латинские буквы A-Z, цифры 0-9, "-" или "_"')
    return null
  }

  lavaForm.value.promo_code = promoCode
  return promoCode
}

async function onLavaPay(): Promise<void> {
  if (lavaBusy.value) return
  if (!auth.isAuthed) {
    void alertDialog('Войдите в аккаунт перед оплатой')
    return
  }

  const email = normalizedLavaEmail()
  if (!email) return

  const promoCode = normalizedPromoCode()
  if (promoCode === null) return

  const paymentOption = lavaForm.value.currency === 'RUB' ? selectedLavaPaymentOption() : null
  const paymentProvider = paymentOption ? paymentProviderForOption(paymentOption) : ''

  lavaBusy.value = true
  const paymentWindow = window.open('', '_blank')
  if (paymentWindow) paymentWindow.opener = null
  try {
    const { data } = await api.post<{ payment_url: string; processed?: boolean }>('/payments/lava/link', {
      email,
      plan: lavaForm.value.plan,
      currency: lavaForm.value.currency,
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
    emit('select', { id: 'lava', name: 'Lava.top', url: paymentUrl })
    requestClose()
    if (paymentWindow) paymentWindow.location.href = paymentUrl
    else window.location.assign(paymentUrl)
  } catch (e: any) {
    if (paymentWindow) paymentWindow.close()
    const st = Number(e?.response?.status || 0)
    const detail = String(e?.response?.data?.detail || '')
    if (st === 401) void alertDialog('Войдите в аккаунт перед оплатой')
    else if (st === 422 && detail === 'lava_email_required') void alertDialog('Введите email для отправки чека и оформления платежа')
    else if (st === 422 && detail === 'lava_email_invalid') void alertDialog('Введите корректный email')
    else if (st === 422 && detail === 'lava_email_rejected') void alertDialog('Сервис не принял этот email. Проверьте адрес или попробуйте другой')
    else if (st === 422 && detail === 'lava_promo_code_invalid') void alertDialog('Промокод должен содержать только заглавные латинские буквы, цифры, "-" или "_"')
    else if (st === 422 && detail === 'lava_promo_code_usage_limit_exceeded') void alertDialog('Лимит использования промокода исчерпан')
    else if (st === 422 && detail === 'lava_promo_code_rejected') void alertDialog('Сервис не принял промокод для выбранного тарифа или валюты')
    else if (st === 422 && detail === 'lava_currency_rejected') void alertDialog('Сервис не принял выбранную валюту. Выберите другую валюту')
    else if (st === 422 && detail === 'lava_currency_invalid') void alertDialog('Выбрана неподдерживаемая валюта')
    else if (st === 422 && detail === 'lava_plan_invalid') void alertDialog('Выбран неподдерживаемый тариф подписки')
    else if (st === 422 && detail === 'lava_payment_method_rejected') void alertDialog('Сервис не принял выбранный способ оплаты. Выберите другой способ')
    else if (st === 422 && detail === 'lava_payment_provider_invalid') void alertDialog('Выбран неподдерживаемый платежный провайдер')
    else if (st === 422 && detail === 'lava_payment_method_invalid') void alertDialog('Выбран неподдерживаемый способ оплаты')
    else if (st === 422 && detail === 'lava_payment_method_required') void alertDialog('Выберите способ оплаты')
    else if (st === 422 && detail === 'lava_payment_method_unsupported') void alertDialog('Выбранный способ оплаты недоступен для этой валюты')
    else if (st === 422 && detail === 'lava_request_rejected') void alertDialog('Сервис отклонил параметры платежа. Проверьте тариф, валюту и промокод')
    else if (st === 429 && detail === 'lava_rate_limited') void alertDialog('Сервис временно ограничил частоту запросов. Повторите попытку позже')
    else if (st === 503 && detail === 'lava_offer_not_found') void alertDialog('Тариф сервиса не найден. Сообщите администратору')
    else if (st === 503 && detail === 'lava_api_unauthorized') void alertDialog('Оплата сервиса настроена неверно: API-ключ не принят')
    else if (st === 503 && detail === 'lava_service_unavailable') void alertDialog('Сервис временно недоступен. Повторите попытку позже')
    else if (st === 503 && detail === 'lava_product_missing') void alertDialog('Оплата сервиса не настроена: не указан продукт')
    else if (st === 503 && detail === 'lava_api_key_missing') void alertDialog('Оплата сервиса не настроена: не указан API-ключ')
    else if (st === 503 && detail === 'lava_monthly_offer_missing') void alertDialog('Оплата сервиса не настроена: не указан месячный тариф')
    else if (st === 503 && detail === 'lava_yearly_offer_missing') void alertDialog('Оплата сервиса не настроена: не указан годовой тариф')
    else if (st === 502 && detail === 'lava_contract_id_missing') void alertDialog('Сервис создал платеж без номера договора. Повторите попытку позже')
    else if (st === 502 && detail === 'lava_payment_url_missing') void alertDialog('Сервис не вернул ссылку на оплату. Повторите попытку позже')
    else if (st === 502 && detail === 'lava_invoice_invalid_response') void alertDialog('Сервис вернул некорректный ответ. Повторите попытку позже')
    else if (st === 502 && detail === 'lava_invoice_request_failed') void alertDialog('Не удалось подключиться к сервису. Повторите попытку позже')
    else if (st === 502 && detail === 'lava_invoice_failed') void alertDialog('Сервис отклонил создание платежа. Проверьте параметры или повторите попытку позже')
    else if (st === 502 && detail === 'lava_free_invoice_not_processed') void alertDialog('Платеж без оплаты создан, но подписка не активировалась. Сообщите администратору')
    else if (st === 504 && detail === 'lava_invoice_timeout') void alertDialog('Сервис не ответил вовремя. Повторите попытку позже')
    else if (st === 503 && detail.startsWith('lava_')) void alertDialog('Оплата сервиса пока не настроена')
    else if (st === 422 && detail.startsWith('lava_')) void alertDialog('Проверьте параметры оплаты')
    else void alertDialog('Не удалось открыть оплату сервиса')
  } finally {
    lavaBusy.value = false
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (!props.open) return
  if (event.key === 'Escape') requestClose()
}

watch(() => lavaForm.value.currency, () => {
  if (lavaForm.value.currency !== 'RUB') return

  const available = availableLavaPaymentOptions.value.some((option) => option.id === lavaForm.value.payment_option)
  if (!available) {
    lavaForm.value.payment_option = availableLavaPaymentOptions.value[0]?.id || 'card'
  }
})

watch(() => props.open, (open) => {
  armed.value = false
  if (open) {
    lavaForm.value.email = lavaForm.value.email || localStorage.getItem(lavaEmailStorageKey) || ''
    document.addEventListener('keydown', onKeydown)
  } else {
    lavaFormOpen.value = false
    document.removeEventListener('keydown', onKeydown)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped lang="scss">
.support-site-overlay {
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($neutral-black, 0.20);
  backdrop-filter: blur(12px);
  z-index: 1000;
  .support-site-modal {
    display: flex;
    position: relative;
    flex-direction: column;
    padding: 24px;
    width: 570px;
    height: 596px;
    border-radius: 24px;
    background-color: $neutral-100;
    box-shadow: 0 2px 16px 0 rgba($neutral-black, 0.20);
    overflow: hidden;
    .btn-close {
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
      &:hover,
      &:focus-visible,
      &:active {
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
        &.is-lava {
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
    .support-site-content {
      display: flex;
      overflow: hidden;
      .support-site-track {
        display: flex;
        flex: 0 0 200%;
        transition: transform 0.35s cubic-bezier(0.25, 1, 0.5, 1);
        &.is-lava {
          transform: translateX(-50%);
        }
        .support-site-slide {
          flex: 0 0 50%;
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
          .site-list {
            display: flex;
            justify-self: center;
            gap: 10px;
          }
          .lava-form {
            display: flex;
            flex-direction: column;
            margin-top: 62px;
            gap: 24px;
            .lava-input {
              --ui-input-label-bg: #{$neutral-100};
            }
            .lava-field {
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 40px;
              .lava-text {
                color: $neutral-black;
                font-family: Hauora-Bold;
                font-size: 16px;
                line-height: 18px;
                letter-spacing: -0.32px;
              }
              .lava-segmented {
                display: flex;
                align-items: center;
                gap: 10px;
                button {
                  display: flex;
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
                  cursor: pointer;
                  transition: color 0.25s ease-in-out, background-color 0.25s ease-in-out;
                  &.active {
                    color: $neutral-white;
                    background: linear-gradient(261deg, $soft-purple-800 0%, $green-700 100%);
                  }
                  &:hover,
                  &:focus-visible,
                  &:active {
                    background-color: $neutral-white;
                    color: $neutral-black;
                  }
                }
              }
            }
            .lava-actions {
              display: flex;
              justify-content: center;
              margin-top: 62px;
              gap: 10px;
              :deep(.lava-back .ui-button__icon) {
                transform: rotate(-90deg);
              }
            }
          }
        }
      }
    }
  }
}

.support-site-overlay-enter-active,
.support-site-overlay-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.support-site-overlay-enter-from,
.support-site-overlay-leave-to {
  opacity: 0;
}
.lava-payment-expand-enter-active,
.lava-payment-expand-leave-active {
  overflow: hidden;
  transition: max-height 0.25s ease-in-out, opacity 0.2s ease-in-out, transform 0.25s ease-in-out;
}
.lava-payment-expand-enter-from,
.lava-payment-expand-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-10px);
}
.lava-payment-expand-enter-to,
.lava-payment-expand-leave-from {
  max-height: 120px;
  opacity: 1;
  transform: translateY(0);
}

</style>
