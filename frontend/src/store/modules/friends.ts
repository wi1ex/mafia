import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

export type FriendStatus = 'self' | 'friends' | 'outgoing' | 'incoming' | 'none'

export type FriendListKind = 'incoming' | 'outgoing' | 'online' | 'offline'

export type FriendListItem = {
  kind: FriendListKind
  id: number
  username?: string
  avatar_name?: string | null
  online?: boolean
  closeness?: number
  room_id?: number | null
  room_title?: string | null
  room_in_game?: boolean | null
  room_invited?: boolean | null
  telegram_verified?: boolean
  tg_invites_enabled?: boolean
  requested_at?: string | null
}

export type FriendsListResponse = {
  items: FriendListItem[]
}

export type FriendApiAction =
  | 'send'
  | 'accept'
  | 'decline'
  | 'cancel'
  | 'remove'
  | 'unknown'

function actionFallback(action: FriendApiAction): string {
  if (action === 'send') return 'Не удалось отправить заявку в друзья'
  if (action === 'accept') return 'Не удалось принять заявку в друзья'
  if (action === 'decline') return 'Не удалось отклонить заявку в друзья'
  if (action === 'cancel') return 'Не удалось отменить заявку в друзья'
  if (action === 'remove') return 'Не удалось удалить пользователя из друзей'
  return 'Не удалось выполнить действие с друзьями'
}

export function resolveFriendsApiError(error: any, action: FriendApiAction = 'unknown'): string {
  const st = Number(error?.response?.status || 0)
  const detail = String(error?.response?.data?.detail || '').trim()

  if (detail === 'bad_user_id') return 'Некорректный пользователь'
  if (detail === 'user_not_found') return 'Пользователь не найден'
  if (detail === 'self_request') return 'Нельзя выполнить действие для своего аккаунта'
  if (detail === 'self_remove') return 'Нельзя удалить себя из друзей'
  if (detail === 'already_friends') return 'Вы уже в друзьях'
  if (detail === 'request_already_sent') return 'Заявка уже отправлена'

  if (detail === 'incoming_request') {
    if (action === 'send') return 'У вас уже есть входящая заявка от этого пользователя'
    if (action === 'cancel') return 'Отменить нельзя: это входящая, а не исходящая заявка'
    return 'У вас уже есть входящая заявка от этого пользователя'
  }

  if (detail === 'outgoing_request') {
    if (action === 'accept') return 'Принять нельзя: это ваша исходящая заявка'
    if (action === 'decline') return 'Отклонить нельзя: это ваша исходящая заявка'
    return 'Действие невозможно для текущего типа заявки'
  }

  if (detail === 'request_revoked' || detail === 'request_not_found') {
    if (action === 'accept') return 'Принять заявку нельзя: запрос уже отменен или обработан'
    if (action === 'decline') return 'Отклонить заявку нельзя: запрос уже отменен или обработан'
    if (action === 'cancel') return 'Отменить заявку нельзя: запрос уже отменен или обработан'
    return 'Заявка больше недоступна'
  }

  if (detail === 'friend_not_found') return 'Пользователь не найден в списке друзей'
  if (detail === 'friend_remove_too_early') return 'Удалить из друзей можно только через 10 минут после принятия заявки'

  if (st === 429) return 'Слишком много запросов. Попробуйте через несколько секунд'
  if (st >= 500) return 'Сервис временно недоступен. Попробуйте позже'

  return actionFallback(action)
}

export function shouldRefreshFriendsStateAfterError(error: any): boolean {
  const detail = String(error?.response?.data?.detail || '').trim()
  return [
    'request_revoked',
    'request_not_found',
    'request_already_sent',
    'already_friends',
    'incoming_request',
    'outgoing_request',
    'friend_not_found',
  ].includes(detail)
}

export function inferFriendApiAction(url: string, method?: string): FriendApiAction {
  const path = String(url || '')
  const m = String(method || 'post').toLowerCase()

  if (/^\/friends\/requests\/\d+\/accept$/.test(path) && m === 'post') return 'accept'
  if (/^\/friends\/requests\/\d+\/decline$/.test(path) && m === 'post') return 'decline'
  if (/^\/friends\/requests\/\d+$/.test(path) && m === 'post') return 'send'
  if (/^\/friends\/requests\/\d+$/.test(path) && m === 'delete') return 'cancel'
  if (/^\/friends\/\d+$/.test(path) && m === 'delete') return 'remove'

  return 'unknown'
}

export const useFriendsStore = defineStore('friends', () => {
  const list = ref<FriendListItem[]>([])
  const incomingCount = ref(0)
  let inited = false
  let onFriendsUpdate: ((e: any) => void) | null = null
  let refreshTimer: number | undefined
  let listLoading = false
  let listQueued = false
  let listQueuedRoomId: number | null = null
  let countLoading = false
  let countQueued = false

  function normalizeRoomId(roomId?: number | null): number | null {
    const rid = Number(roomId || 0)
    if (!Number.isFinite(rid) || rid <= 0) return null
    return Math.trunc(rid)
  }

  async function fetchList(roomId?: number | null): Promise<void> {
    const normalizedRoomId = normalizeRoomId(roomId)
    if (listLoading) {
      listQueued = true
      listQueuedRoomId = normalizedRoomId
      return
    }
    listLoading = true
    try {
      const reqCfg = normalizedRoomId ? { params: { room_id: normalizedRoomId } } : undefined
      const { data } = await api.get<FriendsListResponse>('/friends/list', reqCfg)
      list.value = Array.isArray(data?.items) ? data.items : []
    } finally {
      listLoading = false
      if (listQueued) {
        listQueued = false
        const queuedRoomId = listQueuedRoomId
        listQueuedRoomId = null
        void fetchList(queuedRoomId)
      }
    }
  }

  async function fetchIncomingCount(): Promise<void> {
    if (countLoading) {
      countQueued = true
      return
    }
    countLoading = true
    try {
      const { data } = await api.get<{ count: number }>('/friends/incoming_count')
      incomingCount.value = Number.isFinite(data?.count) ? data.count : 0
    } finally {
      countLoading = false
      if (countQueued) {
        countQueued = false
        void fetchIncomingCount()
      }
    }
  }

  async function fetchStatus(userId: number): Promise<FriendStatus> {
    const { data } = await api.get<{ status: FriendStatus }>(`/friends/status/${userId}`)
    return data.status
  }

  async function sendRequest(userId: number): Promise<void> {
    await api.post(`/friends/requests/${userId}`)
  }

  async function acceptRequest(userId: number): Promise<void> {
    await api.post(`/friends/requests/${userId}/accept`)
  }

  async function declineRequest(userId: number): Promise<void> {
    await api.post(`/friends/requests/${userId}/decline`)
  }

  async function cancelOutgoingRequest(userId: number): Promise<void> {
    await api.delete(`/friends/requests/${userId}`)
  }

  async function removeFriend(userId: number): Promise<void> {
    await api.delete(`/friends/${userId}`)
  }

  async function inviteToRoom(userId: number, roomId: number): Promise<void> {
    await api.post('/friends/invite', { user_id: userId, room_id: roomId })
  }

  function scheduleRefresh() {
    if (refreshTimer) return
    refreshTimer = window.setTimeout(() => {
      refreshTimer = undefined
      void fetchIncomingCount()
    }, 200)
  }

  function ensureWS(): void {
    if (inited) return
    if (onFriendsUpdate) window.removeEventListener('auth-friends_update', onFriendsUpdate)
    onFriendsUpdate = (e: any) => {
      const p = e?.detail
      if (!p) return
      scheduleRefresh()
    }
    window.addEventListener('auth-friends_update', onFriendsUpdate)
    inited = true
  }

  return {
    list,
    incomingCount,
    fetchList,
    fetchIncomingCount,
    fetchStatus,
    sendRequest,
    acceptRequest,
    declineRequest,
    cancelOutgoingRequest,
    removeFriend,
    inviteToRoom,
    ensureWS,
  }
})
