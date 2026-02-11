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
  telegram_verified?: boolean
  tg_invites_enabled?: boolean
  requested_at?: string | null
}

export type FriendsListResponse = {
  items: FriendListItem[]
}

export const useFriendsStore = defineStore('friends', () => {
  const list = ref<FriendListItem[]>([])
  const incomingCount = ref(0)
  let inited = false
  let onFriendsUpdate: ((e: any) => void) | null = null
  let refreshTimer: number | undefined
  let listLoading = false
  let listQueued = false
  let countLoading = false
  let countQueued = false

  async function fetchList(): Promise<void> {
    if (listLoading) {
      listQueued = true
      return
    }
    listLoading = true
    try {
      const { data } = await api.get<FriendsListResponse>('/friends/list')
      list.value = Array.isArray(data?.items) ? data.items : []
    } finally {
      listLoading = false
      if (listQueued) {
        listQueued = false
        void fetchList()
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
    removeFriend,
    inviteToRoom,
    ensureWS,
  }
})
