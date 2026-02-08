import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

export type FriendStatus = 'self' | 'friends' | 'outgoing' | 'incoming' | 'none'

export type FriendItem = {
  id: number
  username?: string
  avatar_name?: string | null
  online: boolean
  closeness: number
  room_id?: number | null
  room_title?: string | null
  room_in_game?: boolean | null
}

export type FriendRequestItem = {
  id: number
  username?: string
  avatar_name?: string | null
  requested_at?: string | null
}

export type FriendsList = {
  online: FriendItem[]
  offline: FriendItem[]
  incoming: FriendRequestItem[]
  outgoing: FriendRequestItem[]
}

export type RoomBrief = {
  id: number
  title: string
  user_limit: number
  privacy: 'open' | 'private'
  creator: number
  creator_name: string
  creator_avatar_name?: string | null
  created_at: string
  occupancy: number
  in_game: boolean
  game_phase: string
  entry_closed: boolean
}

export const useFriendsStore = defineStore('friends', () => {
  const list = ref<FriendsList>({
    online: [],
    offline: [],
    incoming: [],
    outgoing: [],
  })
  const rooms = ref<RoomBrief[]>([])
  const loading = ref(false)
  let refreshQueued = false
  let inited = false
  let onFriendsUpdate: ((e: any) => void) | null = null
  let refreshTimer: number | undefined

  async function fetchAll(): Promise<void> {
    if (loading.value) {
      refreshQueued = true
      return
    }
    loading.value = true
    try {
      const { data } = await api.get<FriendsList>('/friends/list')
      list.value = data
    } finally {
      loading.value = false
      if (refreshQueued) {
        refreshQueued = false
        void fetchAll()
      }
    }
  }

  async function fetchRooms(): Promise<void> {
    const { data } = await api.get<RoomBrief[]>('/rooms/active')
    rooms.value = data
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
      void fetchAll()
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
    rooms,
    loading,
    fetchAll,
    fetchRooms,
    fetchStatus,
    sendRequest,
    acceptRequest,
    declineRequest,
    removeFriend,
    inviteToRoom,
    ensureWS,
  }
})
