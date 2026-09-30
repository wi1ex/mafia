<template>
  <div class="profile-subscription">
    <div class="subscription-blocks">
        <section class="block-payments">
          <header class="section-header">
            <span class="section-title">История платежей</span>
            <span class="section-count">{{ subscriptionStatusText }}</span>
          </header>
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
        </section>
    </div>
    <div class="subscription-blocks">
        <section class="block-blacklist">
          <div class="blacklist-head">
            <div class="blacklist-title">
              <span class="section-title">Черный список</span>
              <UiTooltip
                :text="blacklistHint"
                placement="bottom-right"
                bubble-width="320px"
              />
            </div>
          </div>
          <div v-if="blacklistLoading" class="blacklist-empty">Загрузка…</div>
          <div v-else-if="blacklistError" class="blacklist-empty danger">{{ blacklistError }}</div>
          <div v-else-if="blacklistItems.length === 0" class="blacklist-empty">В черном списке пока никого нет.</div>
          <div v-else class="blacklist-list">
            <article v-for="item in blacklistItems" :key="item.id" class="blacklist-card">
              <button class="blacklist-user" type="button" :disabled="!canOpenMiniProfile(item)" :aria-label="`Открыть профиль ${item.username || `user${item.id}`}`" @click="openMiniProfile(item)">
                <img class="blacklist-avatar" v-minio-img="{ key: blacklistAvatarKey(item), placeholder: iconDefaultAvatar, lazy: true, animated: true }" alt="avatar" />
                <div class="blacklist-main">
                  <span>{{ item.username || `user${item.id}` }}</span>
                  <small>Добавлен: {{ formatLocalDateTime(item.created_at || '') }}</small>
                </div>
              </button>
              <UiButton
                class="blacklist-remove"
                variant="red"
                size="middle"
                :icon="iconDelete"
                :text="blacklistRemoving[item.id] ? '...' : 'Удалить из ЧС'"
                :disabled="blacklistRemoving[item.id]"
                @click="removeFromBlacklistProfile(item)"
              />
            </article>
          </div>
        </section>
        <MiniProfile
          v-model:open="miniProfileOpen"
          :user-id="miniProfileUserId"
          :initial-profile="miniProfileInitial"
          :show-stats-button="true"
        />
    </div>
  </div>
  <MiniProfile
    v-model:open="miniProfileOpen"
    :user-id="miniProfileUserId"
    :initial-profile="miniProfileInitial"
    :show-stats-button="true"
  />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { formatLocalDateTime } from '@/services/datetime'
import { useSubscriptionStatus } from '@/services/useSubscriptionStatus'
import { storeToRefs } from 'pinia'
import { useFriendsStore, useUserStore, type BlacklistItem } from '@/store'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId } from '@/services/miniProfile'
import UiButton from '@/components/UiButton.vue'
import UiTooltip from '@/components/UiTooltip.vue'
import MiniProfile from '@/views/MiniProfile.vue'
import iconDefaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconDelete from '@/assets/svg/iconDelete.svg'

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

const { subscriptionStatusText } = useSubscriptionStatus()
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

const friendsStore = useFriendsStore()
const userStore = useUserStore()
const { subscriptionHint } = useSubscriptionStatus()
const { subscriptionActive } = storeToRefs(userStore)
const blacklistHint = computed(() => {
  const explanation = 'Вы не сможете получать от пользователей из ЧС заявки в друзья и комнаты, а также уведомления из чата.'
  return `${explanation} ${subscriptionHint('Черный список доступен только при наличии подписки.')}`
})
const blacklistLoading = ref(false)
const blacklistError = ref('')
const blacklistRemoving = reactive<Record<number, boolean>>({})
const miniProfileOpen = ref(false)
const miniProfileUserId = ref<number | null>(null)
const miniProfileInitial = ref<BlacklistItem | null>(null)
const blacklistItems = computed<BlacklistItem[]>(() => (
  Array.isArray(friendsStore.blacklist) ? friendsStore.blacklist : []
))

async function loadBlacklist(): Promise<void> {
  if (blacklistLoading.value) return
  blacklistLoading.value = true
  blacklistError.value = ''
  try {
    await friendsStore.fetchBlacklist()
  } catch (e: any) {
    const detail = String(e?.response?.data?.detail || '').trim()
    if (detail === 'subscription_required') {
      blacklistError.value = ''
      return
    }
    blacklistError.value = 'Не удалось загрузить черный список'
  } finally {
    blacklistLoading.value = false
  }
}

function blacklistAvatarKey(item: BlacklistItem): string {
  const name = String(item.avatar_name || '').trim()
  if (!name) return ''
  return name.startsWith('avatars/') ? name : `avatars/${name}`
}

function canOpenMiniProfile(item: BlacklistItem): boolean {
  return canOpenMiniProfileTarget({
    targetId: item.id,
    viewerId: userStore.user?.id,
    viewerRole: userStore.user?.role,
    targetRole: item.role,
  })
}

function openMiniProfile(item: BlacklistItem): void {
  if (!canOpenMiniProfile(item)) return
  miniProfileUserId.value = normalizeMiniProfileUserId(item.id)
  miniProfileInitial.value = item
  miniProfileOpen.value = true
}

async function removeFromBlacklistProfile(item: BlacklistItem): Promise<void> {
  const uid = Number(item?.id || 0)
  if (!Number.isFinite(uid) || uid <= 0 || blacklistRemoving[Math.trunc(uid)]) return
  const userLabel = item.username || `user${Math.trunc(uid)}`
  const ok = await confirmDialog({
    title: 'Удалить из Черного списка',
    text: `Вы уверены, что хотите удалить пользователя ${userLabel} из ЧС?`,
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  const id = Math.trunc(uid)
  blacklistRemoving[id] = true
  try {
    await friendsStore.removeFromBlacklist(id)
  } catch (e: any) {
    const detail = String(e?.response?.data?.detail || '').trim()
    if (detail === 'subscription_required') {
      void userStore.fetchMe().catch(() => {})
      void alertDialog('Черный список доступен только при активной подписке')
    } else {
      void alertDialog('Не удалось удалить пользователя из ЧС')
    }
  } finally {
    delete blacklistRemoving[id]
  }
}

watch(subscriptionActive, () => {
  void loadBlacklist()
})

onMounted(() => {
  friendsStore.ensureWS()
  void loadBlacklist()
})
</script>

<style scoped lang="scss">
.profile-subscription {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
}
.subscription-blocks {
  box-sizing: border-box;
  width: calc(50% - 5px);
  min-width: 0;
}
.block-payments {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
  padding: 24px;
  border-radius: 24px;
  background-color: $soft-purple-900;
  .section-header {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }
  .section-title {
    display: block;
    color: $neutral-white;
    font-family: Involve-Medium;
    font-size: 24px;
    line-height: 26px;
  }
  .section-count {
    padding: 8px 10px;
    border-radius: 12px;
    background-color: $blue-100;
    color: $blue-500;
    text-align: center;
    font-size: 14px;
  }
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
    border: 1px solid $soft-purple-800;
    border-radius: 20px;
    background-color: $soft-purple-800;
    .payments-table {
      width: 100%;
      min-width: 820px;
      border-collapse: collapse;
      color: $neutral-100;
      th,
      td {
        padding: 14px 16px;
        border-bottom: 1px solid rgba($neutral-500, 0.2);
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
.block-blacklist {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  padding: 24px;
  border-radius: 24px;
  background-color: $soft-purple-900;
  .section-title {
    display: block;
  }
  .blacklist-title {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .section-title {
    color: $neutral-white;
    font-family: Involve-Medium;
    font-size: 24px;
    line-height: 26px;
  }
  .blacklist-head {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
  }
  .blacklist-empty {
    padding: 20px 0;
    color: $neutral-300;
    &.danger {
      color: $red-500;
    }
  }
  .blacklist-list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 10px;
    margin-top: 10px;
    .blacklist-card {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px;
      border: 1px solid $soft-purple-800;
      border-radius: 20px;
      background-color: $soft-purple-800;
      .blacklist-user {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
        padding: 0;
        border: none;
        border-radius: 12px;
        background: transparent;
        text-align: left;
        cursor: pointer;
        &:disabled {
          cursor: default;
        }
        &:focus-visible {
          outline: 2px solid $green-500;
          outline-offset: 4px;
        }
        .blacklist-avatar {
          flex: 0 0 auto;
          width: 48px;
          height: 48px;
          border-radius: 50%;
          object-fit: cover;
          background-color: black;
        }
        .blacklist-main {
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 0;
          span {
            color: $neutral-100;
            font-family: Hauora-SemiBold;
            font-size: 16px;
            line-height: 1.2;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          small {
            color: $neutral-300;
            font-size: 12px;
            line-height: 1.2;
          }
        }
      }
      .blacklist-remove {
        flex: 0 0 auto;
        max-width: none;
        min-width: 130px;
      }
    }
  }
}
</style>
