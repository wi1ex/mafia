<template>
  <div class="profile-subscription">
    <div class="subscription-blocks subscription-blocks--payments">
        <section class="block-payments block-scrollable">
          <header class="section-header">
            <span class="section-title">История операций</span>
          </header>
          <div v-if="paymentsLoading" class="payments-state">Загрузка...</div>
          <div v-else-if="paymentsError" class="payments-state danger">{{ paymentsError }}</div>
          <div v-else-if="paymentsItems.length === 0" class="payments-state">Операций пока нет</div>
          <div v-else class="subscription-scroll-wrap">
            <div ref="paymentsScroll" class="payments-table-wrap subscription-scroll">
            <table class="payments-table">
              <thead>
                <tr>
                  <th>Дата и время</th>
                  <th>Тип</th>
                  <th>Получено</th>
                  <th>Потрачено</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in paymentsItems" :key="item.id">
                  <td>{{ formatLocalDateTime(item.date, PAYMENT_DATE_OPTIONS) }}</td>
                  <td>{{ item.type }}</td>
                  <td>{{ item.received }}</td>
                  <td>{{ item.spent }}</td>
                </tr>
              </tbody>
            </table>
            </div>
            <UiScrollbar :target="paymentsScroll" theme="dark" right="-14px" />
          </div>
          <div v-if="paymentsPages > 1" class="payments-pager">
            <UiButton variant="white" size="low" text="Назад" :disabled="paymentsPage <= 1 || paymentsLoading" @click="changePaymentsPage(paymentsPage - 1)" />
            <span>{{ paymentsPage }} / {{ paymentsPages }}</span>
            <UiButton variant="white" size="low" text="Вперёд" :disabled="paymentsPage >= paymentsPages || paymentsLoading" @click="changePaymentsPage(paymentsPage + 1)" />
          </div>
        </section>
    </div>
    <div class="subscription-blocks subscription-blocks--blacklist">
        <section class="block-blacklist block-scrollable">
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
          <div v-else-if="blacklistItems.length === 0" class="blacklist-empty">В ЧС пока никого нет</div>
          <div v-else class="subscription-scroll-wrap">
            <div ref="blacklistScroll" class="blacklist-table-wrap subscription-scroll">
            <table class="blacklist-table">
              <thead>
                <tr>
                  <th>Пользователь</th>
                  <th>Дата добавления</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in blacklistItems" :key="item.id">
                  <td>
                    <button class="blacklist-user" type="button" :disabled="!canOpenMiniProfile(item)" :aria-label="`Открыть профиль ${item.username || `user${item.id}`}`" @click="openMiniProfile(item)">
                      <img class="blacklist-avatar" v-minio-img="{ key: blacklistAvatarKey(item), placeholder: iconDefaultAvatar, lazy: true, animated: true }" alt="avatar" />
                      <span>{{ item.username || `user${item.id}` }}</span>
                    </button>
                  </td>
                  <td>{{ formatLocalDateTime(item.created_at || '') }}</td>
                </tr>
              </tbody>
            </table>
            </div>
            <UiScrollbar :target="blacklistScroll" theme="dark" right="-14px" />
          </div>
        </section>
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { formatLocalDateTime } from '@/services/datetime'
import { useSubscriptionStatus } from '@/services/useSubscriptionStatus'
import { storeToRefs } from 'pinia'
import { useFriendsStore, useUserStore, type BlacklistItem } from '@/store'
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId } from '@/services/miniProfile'
import UiTooltip from '@/components/UiTooltip.vue'
import UiScrollbar from '@/components/UiScrollbar.vue'
import UiButton from '@/components/UiButton.vue'
import MiniProfile from '@/views/MiniProfile.vue'
import iconDefaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'

type SubscriptionPaymentItem = {
  id: string
  date: string
  type: string
  received: string
  spent: string
}

type SubscriptionPaymentsResponse = {
  items?: SubscriptionPaymentItem[] | null
  total: number
  page: number
  per_page: number
  pages: number
}

const paymentsItems = ref<SubscriptionPaymentItem[]>([])
const paymentsScroll = ref<HTMLElement | null>(null)
const blacklistScroll = ref<HTMLElement | null>(null)
const paymentsLoading = ref(false)
const paymentsLoaded = ref(false)
const paymentsError = ref('')
const paymentsPage = ref(1)
const paymentsPages = ref(1)
let paymentsRequestSeq = 0

const PAYMENT_DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
}

async function loadPayments(force = false): Promise<void> {
  if (paymentsLoaded.value && !force) return
  const seq = ++paymentsRequestSeq
  paymentsLoading.value = true
  paymentsError.value = ''
  try {
    const { data } = await api.get<SubscriptionPaymentsResponse>('/users/payments/history', { params: { page: paymentsPage.value, per_page: 20 } })
    if (seq !== paymentsRequestSeq) return
    paymentsItems.value = Array.isArray(data?.items) ? data.items : []
    paymentsPages.value = Math.max(1, Number(data.pages) || 1)
    if (paymentsPage.value > paymentsPages.value) {
      paymentsPage.value = paymentsPages.value
      void loadPayments(true)
      return
    }
    paymentsLoaded.value = true
  } catch {
    if (seq !== paymentsRequestSeq) return
    paymentsItems.value = []
    paymentsError.value = 'Не удалось загрузить историю операций'
  } finally {
    if (seq === paymentsRequestSeq) paymentsLoading.value = false
  }
}

function changePaymentsPage(page: number): void {
  paymentsPage.value = Math.max(1, Math.min(paymentsPages.value, page))
  void loadPayments(true)
}

function onWalletChanged(event: Event): void {
  const uid = Number((event as CustomEvent)?.detail?.user_id || 0)
  if (uid && uid !== userStore.user?.id) return
  paymentsPage.value = 1
  void loadPayments(true)
}

onMounted(() => {
  void loadPayments(true)
  window.addEventListener('dc-wallet-changed', onWalletChanged)
})

onBeforeUnmount(() => {
  paymentsRequestSeq += 1
  window.removeEventListener('dc-wallet-changed', onWalletChanged)
})

const friendsStore = useFriendsStore()
const userStore = useUserStore()
const { subscriptionHint } = useSubscriptionStatus()
const { subscriptionActive } = storeToRefs(userStore)
const blacklistHint = computed(() => {
  const explanation = 'Вы не сможете отправлять друг другу заявки в друзья. Пользователь не сможет подать заявку в вашу закрытую комнату. В вашем профиле ему не будут доступны сведения профиля. В общем чате не будут видны его сообщения, прекратятся уведомления о его упоминаниях и реакциях.'
  return subscriptionHint(explanation, 'Черный список доступен только при активной подписке.')
})
const blacklistLoading = ref(false)
const blacklistError = ref('')
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

watch(subscriptionActive, () => {
  void loadBlacklist()
})

watch(() => [userStore.user?.subscription_until, userStore.user?.dc_balance], () => {
  paymentsPage.value = 1
  void loadPayments(true)
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
  height: 100%;
  min-height: 0;
  .subscription-blocks {
    display: flex;
    flex-direction: column;
    gap: 10px;
    box-sizing: border-box;
    min-width: 0;
    height: 100%;
    min-height: 0;
    &--payments {
      width: calc(60% - 5px);
    }
    &--blacklist {
      width: calc(40% - 5px);
    }
    > .block-scrollable {
      flex-shrink: 0;
      max-height: 100%;
      box-sizing: border-box;
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 20px;
      padding: 24px;
      border-radius: 24px;
      background-color: $soft-purple-900;
      .section-header,
      .blacklist-head {
        flex-shrink: 0;
      }
      .subscription-scroll-wrap {
        position: relative;
        display: flex;
        min-height: 0;
        .subscription-scroll {
          min-height: 0;
          overflow: auto;
          scrollbar-width: none;
          &::-webkit-scrollbar {
            display: none;
          }
        }
      }
      &.block-payments {
        .section-header {
          display: flex;
          flex-wrap: wrap;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
          .section-title {
            display: block;
            color: $neutral-white;
            font-family: Involve-Medium;
            font-size: 24px;
            line-height: 30px;
          }
        }
        .payments-state {
          padding: 20px 10px;
          text-align: center;
          color: $neutral-300;
          &.danger {
            color: $orange-500;
          }
        }
        .subscription-scroll-wrap {
          .payments-table-wrap {
            width: 100%;
            overflow-x: auto;
            border-radius: 20px;
            background-color: $soft-purple-800;
            .payments-table {
              width: 100%;
              border-collapse: collapse;
              color: $neutral-100;
              thead {
                tr {
                  th {
                    padding: 16px;
                    border-bottom: 1px solid rgba($neutral-500, 0.2);
                    text-align: left;
                    vertical-align: top;
                    line-height: 1.25;
                    color: $neutral-white;
                    font-family: Hauora-SemiBold;
                    font-size: 16px;
                    white-space: nowrap;
                    &:not(:first-child) {
                      text-align: center;
                    }
                  }
                }
              }
              tbody {
                tr {
                  td {
                    padding: 12px 16px;
                    border-bottom: 1px solid rgba($neutral-500, 0.2);
                    text-align: left;
                    vertical-align: top;
                    font-size: 14px;
                    overflow-wrap: anywhere;
                    &:not(:first-child) {
                      text-align: center;
                    }
                  }
                  &:last-child {
                    td {
                      border-bottom: none;
                    }
                  }
                }
              }
            }
          }
        }
        .payments-pager {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 8px;
          justify-content: space-between;
          color: $neutral-300;
        }
      }
      &.block-blacklist {
        .blacklist-head {
          display: flex;
          flex-wrap: wrap;
          align-items: flex-start;
          justify-content: space-between;
          gap: 10px;
          .blacklist-title {
            display: flex;
            align-items: center;
            gap: 8px;
            .section-title {
              display: block;
              color: $neutral-white;
              font-family: Involve-Medium;
              font-size: 24px;
              line-height: 30px;
            }
          }
        }
        .blacklist-empty {
          text-align: center;
          padding: 20px 0;
          color: $neutral-300;
          &.danger {
            color: $red-500;
          }
        }
        .subscription-scroll-wrap {
          .blacklist-table-wrap {
            width: 100%;
            overflow-x: auto;
            border: 1px solid $soft-purple-800;
            border-radius: 20px;
            background-color: $soft-purple-800;
            .blacklist-table {
              width: 100%;
              border-collapse: collapse;
              color: $neutral-100;
              thead {
                tr {
                  th {
                    padding: 14px 16px;
                    border-bottom: 1px solid rgba($neutral-500, 0.2);
                    text-align: center;
                    vertical-align: middle;
                    line-height: 1.25;
                    color: $neutral-white;
                    font-family: Hauora-SemiBold;
                    font-size: 16px;
                    white-space: nowrap;
                    &:first-child {
                      text-align: left;
                    }
                  }
                }
              }
              tbody {
                tr {
                  td {
                    padding: 14px 16px;
                    border-bottom: 1px solid rgba($neutral-500, 0.2);
                    text-align: center;
                    vertical-align: middle;
                    line-height: 1.25;
                    font-size: 15px;
                    &:first-child {
                      text-align: left;
                    }
                    .blacklist-user {
                      display: inline-flex;
                      align-items: center;
                      gap: 4px;
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
                        width: 24px;
                        height: 24px;
                        border-radius: 50%;
                        object-fit: cover;
                        background-color: black;
                      }
                      span {
                        color: $neutral-100;
                        font-family: Hauora-SemiBold;
                        font-size: 16px;
                        line-height: 1.2;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        white-space: nowrap;
                      }
                    }
                  }
                  &:last-child {
                    td {
                      border-bottom: none;
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
</style>
