<template>
  <Teleport to="body">
    <Transition name="support-site-overlay">
      <div
        v-if="open"
        class="support-site-overlay"
        @pointerdown.self="armed = true"
        @pointerup.self="armed && requestClose()"
        @pointerleave.self="armed = false"
        @pointercancel.self="armed = false"
      >
        <div class="support-site-modal" role="dialog" aria-modal="true">
          <header>
            <div class="header-div">
              <span class="header-title">{{ lavaFormOpen ? 'Оплата Lava' : 'Выбери удобный способ поддержки' }}</span>
              <span class="header-text">{{ lavaFormOpen ? 'Настрой параметры платежа перед переходом на страницу оплаты.' : 'Помоги развитию проекта и получи дополнительные возможности внутри платформы.' }}</span>
            </div>
            <button type="button" aria-label="Закрыть" @click="requestClose">
              <UiIcon class="close-icon" :icon="iconClose" />
            </button>
          </header>

          <div v-if="!lavaFormOpen" class="site-list">
            <component
              :is="site.enabled ? 'a' : 'button'"
              v-for="site in supportSites"
              :key="site.id"
              class="site-option"
              :href="site.enabled ? site.url : undefined"
              :target="site.enabled ? '_blank' : undefined"
              :rel="site.enabled ? 'noopener noreferrer' : undefined"
              :type="site.enabled ? undefined : 'button'"
              :disabled="!site.enabled"
              @click="onSelect(site)"
            >
              <div class="site-title">
                <img :src="site.icon" :alt="site.iconAlt" class="site-logo" />
                <UiIcon class="arrow-icon" :icon="iconArrowNext" />
              </div>
              <div class="site-copy">
                <span class="site-name">{{ site.name }}</span>
                <span class="site-note">{{ site.note }}</span>
              </div>
            </component>

            <button class="site-option lava-option" type="button" :disabled="lavaBusy" @click="openLavaForm">
              <div class="site-title">
                <span class="lava-logo">Lava</span>
                <UiIcon class="arrow-icon" :icon="iconArrowNext" />
              </div>
              <div class="site-copy">
                <span class="site-name">Lava.top</span>
                <span class="site-note">Подписка и промокод</span>
              </div>
            </button>
          </div>

          <form v-else class="lava-form" @submit.prevent="onLavaPay">
            <label class="lava-field">
              <span>Email</span>
              <input v-model.trim="lavaForm.email" type="email" autocomplete="email" placeholder="mail@example.com" />
            </label>

            <div class="lava-field">
              <span>Срок подписки</span>
              <div class="lava-segmented">
                <button
                  v-for="plan in lavaPlans"
                  :key="plan.id"
                  type="button"
                  :class="{ active: lavaForm.plan === plan.id }"
                  @click="lavaForm.plan = plan.id"
                >
                  {{ plan.label }}
                </button>
              </div>
            </div>

            <div class="lava-field">
              <span>Валюта</span>
              <div class="lava-segmented compact">
                <button
                  v-for="currency in lavaCurrencies"
                  :key="currency"
                  type="button"
                  :class="{ active: lavaForm.currency === currency }"
                  @click="lavaForm.currency = currency"
                >
                  {{ currency }}
                </button>
              </div>
            </div>

            <div v-if="lavaForm.currency === 'RUB'" class="lava-field">
              <span>Способ оплаты</span>
              <div class="lava-method-list">
                <button
                  v-for="method in availableLavaPaymentOptions"
                  :key="method.id"
                  type="button"
                  :class="{ active: lavaForm.payment_option === method.id }"
                  @click="lavaForm.payment_option = method.id"
                >
                  <span>{{ method.label }}</span>
                  <small>{{ method.note }}</small>
                </button>
              </div>
            </div>

            <label class="lava-field">
              <span>Промокод</span>
              <input v-model.trim="lavaForm.promo_code" type="text" inputmode="text" autocomplete="off" placeholder="PROMO2026" />
            </label>

            <div class="lava-actions">
              <button class="lava-back" type="button" :disabled="lavaBusy" @click="closeLavaForm">Назад</button>
              <button class="lava-submit" type="submit" :disabled="lavaBusy">
                {{ lavaBusy ? 'Открываем оплату' : 'Перейти к оплате' }}
              </button>
            </div>
          </form>
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
import iconSupportService1 from '@/assets/images/donateTribute.png'
import iconSupportService2 from '@/assets/images/donateBoosty.png'

const props = defineProps<{
  open: boolean
}>()

type SupportSite = {
  id: string
  name: string
  url: string
}

type SupportSiteOption = SupportSite & {
  icon: string
  iconAlt: string
  note: string
  enabled: boolean
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
const promoCodeRe = /^[A-Za-z0-9_-]{3,36}$/

type LavaPlan = 'month' | 'year'
type LavaCurrency = 'RUB' | 'USD' | 'EUR'
type LavaPaymentOptionId = 'card' | 'sbp'

type LavaPaymentOption = {
  id: LavaPaymentOptionId
  label: string
  note: string
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
    note: 'Банковская карта',
    currencies: ['RUB'],
    payment_provider: 'SMART_GLOCAL',
    payment_method: 'CARD',
  },
  {
    id: 'sbp',
    label: 'СБП',
    note: 'Быстрый платеж в RUB',
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

const supportSites = computed<readonly SupportSiteOption[]>(() => [
  {
    id: 'service_1',
    name: 'Tribute',
    url: 'https://web.tribute.tg/d/Cvc',
    icon: iconSupportService1,
    iconAlt: 'tribute',
    note: 'Сервис поддержки в Telegram',
    enabled: true,
  },
  {
    id: 'service_2',
    name: 'Boosty',
    url: 'https://boosty.to/deceit_games',
    icon: iconSupportService2,
    iconAlt: 'boosty',
    note: 'Внешний сервис поддержки',
    enabled: true,
  },
])

const armed = ref(false)

function requestClose(): void {
  if (!lavaBusy.value) lavaFormOpen.value = false
  emit('update:open', false)
}

function onSelect(site: SupportSiteOption): void {
  if (!site.enabled) return
  emit('select', { id: site.id, name: site.name, url: site.url })
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
    void alertDialog('Промокод должен быть от 3 до 36 символов: латиница, цифры, "-" или "_"')
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
    else if (st === 422 && detail === 'lava_email_invalid') void alertDialog('Введите корректный email')
    else if (st === 422 && detail === 'lava_promo_code_invalid') void alertDialog('Проверьте промокод')
    else if (st === 422 && detail === 'lava_promo_code_rejected') void alertDialog('Lava не приняла промокод для выбранных параметров')
    else if (st === 422 && detail.startsWith('lava_payment_')) void alertDialog('Выберите другой способ оплаты')
    else if (st === 422 && detail.startsWith('lava_')) void alertDialog('Проверьте параметры оплаты')
    else if (st === 503 && detail.startsWith('lava_')) void alertDialog('Оплата Lava пока не настроена')
    else void alertDialog('Не удалось открыть оплату Lava')
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
    max-width: calc(100vw - 32px);
    max-height: calc(100dvh - 32px);
    overflow-y: auto;
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
    .site-list {
      display: flex;
      flex-wrap: wrap;
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
        transition: border-color 0.25s ease-in-out, opacity 0.25s ease-in-out;
        &:not(:disabled):hover,
        &:not(:disabled):focus-visible,
        &:not(:disabled):active {
          border-color: $green-600;
          .site-title {
            .arrow-icon {
              --ui-icon-color: #{$green-600};
            }
          }
        }
        &:disabled {
          width: 274px;
          height: 154px;
          filter: grayscale(100%) brightness(60%);
          opacity: 0.5;
          cursor: not-allowed;
        }
        .site-title {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          .site-logo {
            height: 40px;
          }
          .arrow-icon {
            --ui-icon-width: 20px;
            --ui-icon-height: 20px;
            --ui-icon-color: #{$neutral-white};
          }
        }
        .site-copy {
          display: flex;
          flex-direction: column;
          gap: 8px;
          .site-name {
            color: $neutral-black;
            font-family: Hauora-Bold;
            font-size: 16px;
            line-height: 18px;
            letter-spacing: -0.32px;
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
      gap: 16px;
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
          small {
            color: $neutral-500;
            font-family: Hauora-Regular;
            font-size: 12px;
            line-height: 16px;
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

@media (max-width: 640px) {
  .support-site-overlay {
    align-items: flex-start;
    padding: 16px;
    .support-site-modal {
      width: 100%;
      .lava-form {
        .lava-method-list,
        .lava-actions {
          grid-template-columns: 1fr;
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

</style>
