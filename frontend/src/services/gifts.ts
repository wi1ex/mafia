import { isAxiosError } from 'axios'
import { onBeforeUnmount, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog, confirmDialogWithCheckbox } from '@/services/confirm'
import type { ToastUser } from '@/services/toast'
import { useAuthStore, useUserStore } from '@/store'

export type GiftMediaAsset = {
  preview_key: string
  avif_key: string
}

export type CatalogGift = GiftMediaAsset & {
  id: number
  price_dc: number
  visible: boolean
}

export type GiftCollectionItem = GiftMediaAsset & {
  id: number
  gift_id: number
  quantity: number
  acquired_at: string
  anonymous: boolean
  sender: ToastUser | null
}

export type GiftCollection = { items: GiftCollectionItem[]; total: number; has_more: boolean; profile_gift_id?: number | null }

export type GiftPurchaseInput = {
  gift_id: number
  expected_dc_cost: number
  recipient_id?: number
  anonymous?: boolean
}

export type GiftPurchaseResult = {
  purchase_id: number
  gift_id: number
  recipient_id: number
  recipient_username: string | null
  dc_balance: number
}

export async function loadGiftCatalog(signal?: AbortSignal): Promise<CatalogGift[]> {
  const { data } = await api.get<CatalogGift[]>('/gifts/catalog', { signal })
  return data
}

export async function loadGiftCollection(userId: number, grouped: boolean, limit: number, offset: number, signal?: AbortSignal): Promise<GiftCollection> {
  const { data } = await api.get<GiftCollection>(`/gifts/users/${userId}`, { params: { grouped, limit, offset }, signal })
  return data
}

export async function moveOwnGift(acquisitionId: number, targetId: number, place: 'before' | 'after', signal?: AbortSignal): Promise<void> {
  await api.patch('/gifts/me/order', { acquisition_id: acquisitionId, target_id: targetId, place }, { signal })
}

export async function setOwnProfileGift(acquisitionId: number | null, signal?: AbortSignal) {
  const { data } = await api.patch<{ profile_gift_id: number | null; profile_gift_preview_key: string | null }>(
    '/gifts/me/profile-icon', { acquisition_id: acquisitionId }, { signal },
  )
  return data
}

const GIFT_REMOVAL_INSUFFICIENT_BALANCE = 'Подарок получен меньше 7 дней назад - удаление будет платным (50% от стоимости подарка). На балансе недостаточно DC.'

export function useOwnGiftRemoval(onRemoved: (acquisitionId: number) => void) {
  const auth = useAuthStore()
  const user = useUserStore()
  const removingId = ref<number | null>(null)
  let activeRequest: AbortController | undefined

  function resetGiftRemoval(): void {
    activeRequest?.abort()
    activeRequest = undefined
    removingId.value = null
  }

  async function removeGift(acquisitionId: number): Promise<void> {
    const session = auth.sessionId
    const ownerId = user.user?.id
    if (!session || !ownerId || activeRequest) return

    const request = new AbortController()
    activeRequest = request
    removingId.value = acquisitionId
    const current = () => !request.signal.aborted && auth.sessionId === session && user.user?.id === ownerId
    const url = `/gifts/purchases/${acquisitionId}`

    try {
      const { data: quote } = await api.get<{ cost_dc: number; dc_balance: number }>(`${url}/removal`, { signal: request.signal })
      if (!current()) return
      if (quote.cost_dc > quote.dc_balance) {
        await alertDialog(GIFT_REMOVAL_INSUFFICIENT_BALANCE)
        return
      }

      const { ok, checkboxChecked } = await confirmDialogWithCheckbox({
        title: 'Удалить подарок?',
        text: quote.cost_dc > 0
          ? `Подарок получен меньше 7 дней назад. Будет списано ${quote.cost_dc} DC (50% от стоимости подарка).`
          : 'Подарок исчезнет из вашей коллекции.',
        checkboxLabel: 'Я понимаю, что подарок будет удалён',
        checkboxRequired: true,
        confirmText: 'Удалить',
      })
      if (!current() || !ok || !checkboxChecked) return

      const previousUser = user.user
      const previousBalance = previousUser?.dc_balance
      const { data } = await api.delete<{ dc_balance: number; profile_icon_cleared?: boolean }>(url, {
        params: { max_cost_dc: quote.cost_dc }, signal: request.signal,
      })
      if (!current()) return
      if (quote.cost_dc > 0 && user.user === previousUser && user.user?.dc_balance === previousBalance) {
        user.setWalletState({ dc_balance: data.dc_balance })
      }
      if (data.profile_icon_cleared && previousUser && user.user === previousUser) {
        previousUser.profile_gift_preview_key = null
      }
      onRemoved(acquisitionId)
    } catch (error) {
      if (!current()) return
      const detail = isAxiosError<{ detail?: string }>(error) ? error.response?.data?.detail : undefined
      if (detail === 'gift_removal_insufficient_balance') {
        await alertDialog(GIFT_REMOVAL_INSUFFICIENT_BALANCE)
      } else if (detail === 'gift_removal_cost_changed') {
        await alertDialog('Стоимость удаления изменилась. Откройте подтверждение ещё раз.')
      } else {
        await alertDialog('Не удалось удалить подарок. Попробуйте ещё раз.')
      }
    } finally {
      if (activeRequest === request) resetGiftRemoval()
    }
  }

  watch([() => auth.sessionId, () => user.user?.id], resetGiftRemoval)
  onBeforeUnmount(resetGiftRemoval)
  return { removingId, removeGift, resetGiftRemoval }
}
