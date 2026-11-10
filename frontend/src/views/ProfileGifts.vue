<template>
  <section class="profile-gifts" aria-labelledby="profile-gifts-title" :aria-busy="loading">
    <h2 id="profile-gifts-title">Подарки</h2>
    <p v-if="loading && !items.length" class="gifts-state" role="status">Загрузка…</p>
    <p v-else-if="failedPage === null && !items.length" class="gifts-state">У вас пока нет подарков</p>
    <div v-if="failedPage !== null" class="gifts-error" role="alert">
      <span>Не удалось загрузить подарки</span>
      <UiButton variant="white" size="low" text="Повторить" :disabled="removingId !== null" @click="loadPage(failedPage ?? page)" />
    </div>
    <div v-if="items.length" class="gifts-scroll-wrap">
      <div ref="giftsScroll" class="gifts-scroll">
        <table class="gifts-table">
          <thead>
            <tr>
              <th scope="col">Подарок</th>
              <th scope="col">Дата получения</th>
              <th scope="col">Покупатель</th>
              <th scope="col">Цена</th>
              <th scope="col">Действие</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td><GiftMedia class="gift-preview" :media="item" :label="`Подарок №${item.gift_id}`" /></td>
              <td><time :datetime="item.acquired_at">{{ formatLocalDateTime(item.acquired_at, DATE_OPTIONS) }}</time></td>
              <td>{{ payerName(item) }}</td>
              <td class="gift-price">{{ coinFormat.format(item.dc_cost) }} DC</td>
              <td>
                <UiButton variant="red" size="low" :icon="iconDelete" :text="removingId === item.id ? 'Удаляем…' : 'Удалить'"
                          :disabled="removingId !== null || loading" :aria-label="`Удалить подарок №${item.gift_id}`" @click="removeGift(item.id)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <UiScrollbar :target="giftsScroll" theme="dark" right="-14px" />
    </div>

    <div v-if="pages > 1" class="gifts-pager">
      <UiButton variant="white" size="low" text="Назад" :disabled="page <= 1 || loading || removingId !== null" @click="loadPage(page - 1)" />
      <span>{{ page }} / {{ pages }}</span>
      <UiButton variant="white" size="low" text="Вперёд" :disabled="page >= pages || loading || removingId !== null" @click="loadPage(page + 1)" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore, useUserStore } from '@/store'
import { formatLocalDateTime } from '@/services/datetime'
import { loadOwnGiftCollection, useOwnGiftRemoval, type OwnGiftCollectionItem } from '@/services/gifts'
import GiftMedia from '@/components/GiftMedia.vue'
import UiButton from '@/components/UiButton.vue'
import UiScrollbar from '@/components/UiScrollbar.vue'
import iconDelete from '@/assets/svg/iconDelete.svg'

const PAGE_SIZE = 20
const DATE_OPTIONS: Intl.DateTimeFormatOptions = { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }
const coinFormat = new Intl.NumberFormat('ru-RU')
const auth = useAuthStore()
const user = useUserStore()
const items = ref<OwnGiftCollectionItem[]>([])
const giftsScroll = ref<HTMLElement | null>(null)
const page = ref(1)
const total = ref(0)
const pages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const loading = ref(false)
const failedPage = ref<number | null>(null)
let listRequest: AbortController | undefined
let refreshPending = false
const { removingId, removeGift } = useOwnGiftRemoval(acquisitionId => {
  items.value = items.value.filter(item => item.id !== acquisitionId)
  total.value = Math.max(0, total.value - 1)
  refreshPending = true
})

watch(removingId, id => {
  if (id === null && refreshPending) {
    refreshPending = false
    void loadPage(Math.min(page.value, pages.value))
  }
})

async function loadPage(target = page.value): Promise<void> {
  if (!auth.sessionId || !user.user?.id) return
  const session = auth.sessionId
  const owner = user.user.id
  const request = new AbortController()
  listRequest?.abort()
  listRequest = request
  loading.value = true
  failedPage.value = null
  try {
    const collection = await loadOwnGiftCollection(PAGE_SIZE, (target - 1) * PAGE_SIZE, request.signal)
    if (request.signal.aborted || auth.sessionId !== session || user.user?.id !== owner) return
    const lastPage = Math.max(1, Math.ceil(collection.total / PAGE_SIZE))
    if (target > lastPage) {
      void loadPage(lastPage)
      return
    }
    items.value = collection.items
    total.value = collection.total
    if (target !== page.value && giftsScroll.value) giftsScroll.value.scrollTop = 0
    page.value = target
  } catch {
    if (!request.signal.aborted && auth.sessionId === session && user.user?.id === owner) failedPage.value = target
  } finally {
    if (listRequest === request) {
      listRequest = undefined
      loading.value = false
    }
  }
}

function payerName(item: OwnGiftCollectionItem): string {
  if (item.payer_kind === 'self') return 'Вы'
  if (item.payer_kind === 'anonymous') return 'Аноним'
  return item.sender?.username || (item.sender ? `user${item.sender.id}` : 'Аккаунт удалён')
}

function refresh(): void {
  if (removingId.value !== null) refreshPending = true
  else void loadPage()
}

function onGiftsUpdate(event: Event): void {
  if (Number((event as CustomEvent)?.detail?.user_id) === user.user?.id) refresh()
}

function onCatalogUpdate(event: Event): void {
  const detail = (event as CustomEvent)?.detail
  if (detail?.media_changed && items.value.some(item => item.gift_id === Number(detail.gift_id))) refresh()
}

function reset(): void {
  listRequest?.abort()
  listRequest = undefined
  refreshPending = false
  items.value = []
  total.value = 0
  page.value = 1
  loading.value = false
  failedPage.value = null
}

watch([() => auth.sessionId, () => user.user?.id], () => {
  reset()
  void loadPage()
}, { immediate: true })

onMounted(() => {
  window.addEventListener('auth-gifts_update', onGiftsUpdate)
  window.addEventListener('auth-gift_catalog_update', onCatalogUpdate)
})

onBeforeUnmount(() => {
  reset()
  window.removeEventListener('auth-gifts_update', onGiftsUpdate)
  window.removeEventListener('auth-gift_catalog_update', onCatalogUpdate)
})
</script>

<style scoped lang="scss">
.profile-gifts {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
  height: fit-content;
  max-height: 100%;
  min-height: 0;
  box-sizing: border-box;
  padding: 24px;
  border-radius: 24px;
  background-color: $soft-purple-900;
  h2 {
    flex-shrink: 0;
    margin: 0;
    color: $neutral-white;
    font-family: Involve-Medium;
    font-size: 24px;
    font-weight: 500;
    line-height: 30px;
  }
  .gifts-state,
  .gifts-error {
    margin: 0;
    padding: 12px 0;
    text-align: center;
    color: $neutral-300;
  }
  .gifts-error {
    display: flex;
    justify-content: center;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    color: $red-500;
  }
  .gifts-scroll-wrap {
    display: flex;
    position: relative;
    min-height: 0;
    .gifts-scroll {
      width: 100%;
      min-width: 0;
      min-height: 0;
      overflow: auto;
      scrollbar-width: none;
      border-radius: 20px;
      background-color: $soft-purple-800;
      .gifts-table {
        width: 100%;
        border-collapse: collapse;
        color: $neutral-100;
        th,
        td {
          padding: 12px 16px;
          border-bottom: 1px solid rgba($neutral-500, 0.2);
          text-align: left;
          vertical-align: middle;
        }
        th {
          color: $neutral-white;
          font-family: Hauora-SemiBold;
          font-size: 16px;
        }
        td {
          font-size: 15px;
          overflow-wrap: anywhere;
          .gift-preview {
            width: 56px;
            height: 56px;
          }
          &.gift-price {
            white-space: nowrap;
          }
        }
        tr:last-child td {
          border-bottom: 0;
        }
      }
    }
  }
  .gifts-pager {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    color: $neutral-300;
  }
}
</style>
