import { api } from '@/services/axios'
import type { ToastUser } from '@/services/toast'

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
  sender: ToastUser | null
}

export type GiftCollection = { items: GiftCollectionItem[]; total: number; has_more: boolean }

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
