<template>
  <Teleport to="body">
    <Transition name="support-site-overlay">
      <div v-if="open" class="support-site-overlay" @pointerdown.self="armed = true" @pointerup.self="armed && requestClose()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <div class="support-site-modal" role="dialog" aria-modal="true">
          <header>
            <div class="header-div">
              <span class="header-title">{{ lavaFormOpen ? 'Оплатить подписку' : 'Выбери свой план подписки или просто поддержи проект' }}</span>
              <span class="header-text" v-if="lavaFormOpen">Настрой параметры платежа перед переходом на страницу оплаты</span>
            </div>
            <button type="button" aria-label="Закрыть" @click="requestClose">
              <UiIcon class="close-icon" :icon="iconClose" />
            </button>
          </header>

          <div class="support-site-content">
            <Transition name="support-content-switch" mode="out-in">
              <div v-if="!lavaFormOpen" key="site-list" class="site-list">
                <a class="site-option" :href="tributeSite.url" target="_blank" rel="noopener noreferrer" @click="onTributeSelect">
                  <img :src="iconTribute" alt="tribute" class="site-logo" />
                  <span class="site-note">Поддержать проект</span>
                </a>

                <button class="site-option btn-option" type="button" :disabled="lavaBusy" @click="openLavaForm">
                  <img :src="iconLavaTop" alt="lava.top" class="site-logo" />
                  <span class="site-note">Оформить подписку</span>
                </button>
              </div>

              <form v-else key="lava-form" class="lava-form" @submit.prevent="onLavaPay">
                <label class="lava-field">
                  <span>Email</span>
                  <input v-model.trim="lavaForm.email" type="email" autocomplete="email" placeholder="mail@example.com" />
                </label>

                <div class="lava-field">
                  <span>Срок подписки</span>
                  <div class="lava-segmented">
                    <button v-for="plan in lavaPlans" :key="plan.id" type="button" :class="{ active: lavaForm.plan === plan.id }" @click="lavaForm.plan = plan.id">
                      {{ plan.label }}
                    </button>
                  </div>
                </div>

                <div class="lava-field">
                  <span>Валюта</span>
                  <div class="lava-segmented compact">
                    <button v-for="currency in lavaCurrencies" :key="currency" type="button" :class="{ active: lavaForm.currency === currency }" @click="lavaForm.currency = currency">
                      {{ currency }}
                    </button>
                  </div>
                </div>

                <Transition name="lava-payment-expand">
                  <div v-if="lavaForm.currency === 'RUB'" class="lava-field lava-payment-field">
                    <span>Способ оплаты</span>
                    <div class="lava-method-list">
                      <button v-for="method in availableLavaPaymentOptions" :key="method.id" type="button" :class="{ active: lavaForm.payment_option === method.id }" @click="lavaForm.payment_option = method.id">
                        <span>{{ method.label }}</span>
                      </button>
                    </div>
                  </div>
                </Transition>

                <label class="lava-field">
                  <span>Промокод</span>
                  <input v-model.trim="lavaForm.promo_code" type="text" inputmode="text" autocomplete="off" placeholder="PROMOCODE" />
                </label>

                <div class="lava-actions">
                  <button class="lava-back" type="button" :disabled="lavaBusy" @click="closeLavaForm">Назад</button>
                  <button class="lava-submit" type="submit" :disabled="lavaBusy">
                    {{ lavaBusy ? 'Открываем оплату' : 'Перейти к оплате' }}
                  </button>
                </div>
              </form>
            </Transition>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import UiIcon from '@/components/UiIcon.vue'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { useAuthStore } from '@/store'

import iconClose from '@/assets/svg/iconClose.svg'
import iconArrowNext from '@/assets/svg/iconArrowNext.svg'
import iconTribute from '@/assets/images/donateTribute.png'
import iconLavaTop from '@/assets/images/donateLavaTop.png'

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
    flex-direction: column;
    padding: 24px;
    gap: 32px;
    width: 558px;
    max-height: calc(100dvh - 32px);
    border-radius: 24px;
    background-color: $neutral-100;
    box-shadow: 0 2px 16px 0 rgba($neutral-black, 0.20);
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      .header-div {
        display: flex;
        flex-direction: column;
        gap: 8px;
        .header-title {
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
      button {
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
    }
    .support-site-content {
      display: flex;
      width: 100%;
      .site-list {
        display: flex;
        gap: 10px;
        .site-option {
          display: flex;
          flex-direction: column;
          padding: 16px;
          gap: 40px;
          width: 242px;
          height: 122px;
          border-radius: 20px;
          border: 1px solid $neutral-white;
          background-color: $neutral-white;
          color: $fg;
          text-align: left;
          text-decoration: none;
          outline: none;
          cursor: pointer;
          transition: border-color 0.25s ease-in-out;
          &.btn-option {
            width: 274px;
            height: 154px;
          }
          &:not(:disabled):hover,
          &:not(:disabled):focus-visible,
          &:not(:disabled):active {
            border-color: $green-600;
          }
          .site-logo {
            height: 40px;
          }
          .site-note {
            color: $neutral-500;
            font-family: Hauora-Regular;
            font-size: 16px;
            line-height: 16px;
            letter-spacing: -0.32px;
          }
        }
      }
    }
    .lava-form {
      display: flex;
      flex-direction: column;
      width: 100%;
      > .lava-field + .lava-field,
      > .lava-actions {
        margin-top: 16px;
      }
      .lava-field {
        display: flex;
        flex-direction: column;
        gap: 8px;
        color: $neutral-black;
        font-family: Hauora-Regular;
        font-size: 14px;
        line-height: 18px;
        letter-spacing: 0;
        input {
          width: 100%;
          height: 42px;
          padding: 0 12px;
          border: 1px solid $neutral-white;
          border-radius: 10px;
          background-color: $neutral-white;
          color: $neutral-black;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 20px;
          letter-spacing: 0;
          outline: none;
          transition: border-color 0.25s ease-in-out;
          &:focus {
            border-color: $green-600;
          }
        }
      }
      .lava-segmented {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
        &.compact {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        button {
          height: 40px;
          border: 1px solid $neutral-white;
          border-radius: 10px;
          background-color: $neutral-white;
          color: $neutral-black;
          font-family: Hauora-Bold;
          font-size: 15px;
          line-height: 18px;
          letter-spacing: 0;
          cursor: pointer;
          transition: border-color 0.25s ease-in-out, background-color 0.25s ease-in-out;
          &.active {
            border-color: $green-600;
            background-color: rgba($green-500, 0.12);
          }
          &:hover,
          &:focus-visible {
            border-color: $green-600;
          }
        }
      }
      .lava-method-list {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
        button {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          justify-content: center;
          min-height: 58px;
          padding: 10px 12px;
          border: 1px solid $neutral-white;
          border-radius: 10px;
          background-color: $neutral-white;
          color: $neutral-black;
          text-align: left;
          cursor: pointer;
          transition: border-color 0.25s ease-in-out, background-color 0.25s ease-in-out;
          span {
            font-family: Hauora-Bold;
            font-size: 15px;
            line-height: 18px;
            letter-spacing: 0;
          }
          &.active {
            border-color: $green-600;
            background-color: rgba($green-500, 0.12);
          }
          &:hover,
          &:focus-visible {
            border-color: $green-600;
          }
        }
      }
      .lava-actions {
        display: grid;
        grid-template-columns: 1fr 1.4fr;
        gap: 10px;
        margin-top: 4px;
        button {
          height: 42px;
          border: none;
          border-radius: 10px;
          font-family: Hauora-Bold;
          font-size: 15px;
          line-height: 18px;
          letter-spacing: 0;
          cursor: pointer;
          transition: opacity 0.25s ease-in-out, background-color 0.25s ease-in-out;
          &:disabled {
            opacity: 0.55;
            cursor: not-allowed;
          }
        }
        .lava-back {
          background-color: $neutral-white;
          color: $neutral-black;
          &:not(:disabled):hover,
          &:not(:disabled):focus-visible {
            background-color: rgba($neutral-black, 0.06);
          }
        }
        .lava-submit {
          background-color: $green-600;
          color: $neutral-white;
          &:not(:disabled):hover,
          &:not(:disabled):focus-visible {
            background-color: $green-700;
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

.support-content-switch-enter-active,
.support-content-switch-leave-active {
  max-height: 760px;
  overflow: hidden;
  transition: max-height 0.25s ease-in-out, opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}

.support-content-switch-enter-from,
.support-content-switch-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-10px);
}

.support-content-switch-enter-to,
.support-content-switch-leave-from {
  max-height: 760px;
  opacity: 1;
  transform: translateY(0);
}

.lava-payment-expand-enter-active,
.lava-payment-expand-leave-active {
  overflow: hidden;
  transition: max-height 0.25s ease-in-out, margin-top 0.25s ease-in-out, opacity 0.2s ease-in-out, transform 0.25s ease-in-out;
}

.lava-payment-expand-enter-from,
.lava-payment-expand-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-10px);
}

.lava-form > .lava-payment-field.lava-payment-expand-enter-from,
.lava-form > .lava-payment-field.lava-payment-expand-leave-to {
  margin-top: 0;
}

.lava-payment-expand-enter-to,
.lava-payment-expand-leave-from {
  max-height: 120px;
  opacity: 1;
  transform: translateY(0);
}

.lava-form > .lava-payment-field.lava-payment-expand-enter-to,
.lava-form > .lava-payment-field.lava-payment-expand-leave-from {
  margin-top: 16px;
}

</style>
