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

defineProps<{
  paymentsLoading: boolean
  paymentsError: string
  paymentsItems: SubscriptionPaymentItem[]
  formatPaymentPaidAt: (value: string) => string
  formatPaymentSubscriptionTerm: (item: SubscriptionPaymentItem) => string
  formatPaymentMoney: (amountRaw?: string | null, currencyRaw?: string | null) => string
  formatPaymentPromoDiscount: (valueRaw?: number | null) => string
}>()
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
