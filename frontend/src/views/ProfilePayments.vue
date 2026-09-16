<template>
  <div class="profile-tab-block block-payments">
    <h3>История платежей</h3>
    <div v-if="paymentsLoading" class="payments-state">Загрузка...</div>
    <div v-else-if="paymentsError" class="payments-state danger">{{ paymentsError }}</div>
    <div v-else-if="paymentsItems.length === 0" class="payments-state">Успешных платежей пока нет</div>
    <div v-else class="payments-table-wrap">
      <table class="payments-table">
        <thead>
          <tr>
            <th>Дата платежа</th>
            <th>Email</th>
            <th>Срок подписки</th>
            <th>Оплаченная стоимость</th>
            <th>Промокод</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in paymentsItems" :key="item.id">
            <td>{{ formatPaymentPaidAt(item.paid_at) }}</td>
            <td>{{ item.email || '-' }}</td>
            <td>{{ formatPaymentSubscriptionTerm(item) }}</td>
            <td>{{ formatPaymentMoney(item.amount, item.currency) }}</td>
            <td>{{ formatPaymentPromoDiscount(item.promo_discount_percent) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '@/services/axios'
import { formatLocalDateTime } from '@/services/datetime'

type SubscriptionPaymentPlan = 'month' | 'year'

type SubscriptionPaymentItem = {
  id: number
  paid_at: string
  email?: string | null
  plan?: SubscriptionPaymentPlan | null
  subscription_months: number
  amount?: string | null
  currency?: string | null
  promo_discount_percent?: number | null
}

type SubscriptionPaymentsResponse = {
  items?: SubscriptionPaymentItem[] | null
}

const paymentsItems = ref<SubscriptionPaymentItem[]>([])
const paymentsLoading = ref(false)
const paymentsLoaded = ref(false)
const paymentsError = ref('')
let paymentsRequestSeq = 0

const PAYMENT_DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
}

function paymentMonths(raw: unknown): number {
  const value = Number(raw)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.trunc(value))
}

function paymentMonthWord(value: number): string {
  const mod100 = value % 100
  const mod10 = value % 10
  if (mod100 >= 11 && mod100 <= 14) return 'месяцев'
  if (mod10 === 1) return 'месяц'
  if (mod10 >= 2 && mod10 <= 4) return 'месяца'
  return 'месяцев'
}

function formatPaymentPaidAt(value: string): string {
  return formatLocalDateTime(value, PAYMENT_DATE_OPTIONS)
}

function formatPaymentSubscriptionTerm(item: SubscriptionPaymentItem): string {
  if (item.plan === 'month') return '1 месяц'
  if (item.plan === 'year') return '1 год'

  const months = paymentMonths(item.subscription_months)
  if (months <= 0) return '-'
  return `${months} ${paymentMonthWord(months)}`
}

function formatPaymentMoney(amountRaw?: string | null, currencyRaw?: string | null): string {
  const amountText = String(amountRaw || '').trim()
  if (!amountText) return '-'

  const currency = String(currencyRaw || '').trim().toUpperCase()
  const value = Number(amountText)
  if (Number.isFinite(value) && /^[A-Z]{3}$/.test(currency)) {
    try {
      return new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      }).format(value)
    } catch {
      return `${amountText} ${currency}`.trim()
    }
  }

  return `${amountText} ${currency}`.trim()
}

function formatPaymentPromoDiscount(valueRaw?: number | null): string {
  const value = Number(valueRaw)
  if (!Number.isFinite(value) || value <= 0) return 'нет'

  const formatted = new Intl.NumberFormat('ru-RU', {
    maximumFractionDigits: 2,
  }).format(value)
  return `${formatted}%`
}

async function loadPayments(force = false): Promise<void> {
  if (paymentsLoading.value) return
  if (paymentsLoaded.value && !force) return
  const seq = ++paymentsRequestSeq
  paymentsLoading.value = true
  paymentsError.value = ''
  try {
    const { data } = await api.get<SubscriptionPaymentsResponse>('/users/payments/subscriptions')
    if (seq !== paymentsRequestSeq) return
    paymentsItems.value = Array.isArray(data?.items) ? data.items : []
    paymentsLoaded.value = true
  } catch {
    if (seq !== paymentsRequestSeq) return
    paymentsItems.value = []
    paymentsError.value = 'Не удалось загрузить платежи'
  } finally {
    if (seq === paymentsRequestSeq) paymentsLoading.value = false
  }
}

onMounted(() => {
  void loadPayments(true)
})

onBeforeUnmount(() => {
  paymentsRequestSeq += 1
})
</script>

<style scoped lang="scss">
.block-payments {
  .payments-state {
    padding: 20px 10px;
    text-align: center;
    color: $neutral-300;
    &.danger {
      color: $orange-500;
    }
  }
  .payments-table-wrap {
    width: 100%;
    overflow-x: auto;
    border: 1px solid rgba($neutral-500, 0.5);
    border-radius: 5px;
    background-color: rgba($neutral-800, 0.45);
    .payments-table {
      width: 100%;
      min-width: 820px;
      border-collapse: collapse;
      color: $neutral-100;
      th,
      td {
        padding: 12px 14px;
        border-bottom: 1px solid rgba($neutral-500, 0.35);
        text-align: left;
        vertical-align: top;
        line-height: 1.25;
      }
      th {
        color: $neutral-300;
        font-family: Hauora-SemiBold;
        font-size: 14px;
        white-space: nowrap;
      }
      td {
        font-size: 15px;
        overflow-wrap: anywhere;
      }
      tbody tr:last-child td {
        border-bottom: none;
      }
    }
  }
}
</style>
