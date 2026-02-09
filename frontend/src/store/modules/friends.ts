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

export type FriendsCounts = {
  online: number
  offline: number
  incoming: number
  outgoing: number
  total: number
}

export type FriendsTab = 'online' | 'offline' | 'incoming' | 'outgoing'

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
  const counts = ref<FriendsCounts>({
    online: 0,
    offline: 0,
    incoming: 0,
    outgoing: 0,
    total: 0,
  })
  const rooms = ref<RoomBrief[]>([])
  const loading = ref(false)
  let refreshQueued = false
  let inited = false
  let onFriendsUpdate: ((e: any) => void) | null = null
  let refreshTimer: number | undefined
  let tabLoading = false
  let tabQueued: FriendsTab | null = null
  let countsLoading = false
  let countsQueued = false

  async function fetchAll(): Promise<void> {
    if (loading.value) {
      refreshQueued = true
      return
    }
    loading.value = true
    try {
      const { data } = await api.get<FriendsList>('/friends/list', { params: { tab: 'all' } })
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

  async function fetchTab(tab: FriendsTab): Promise<void> {
    if (tabLoading) {
      tabQueued = tab
      return
    }
    tabLoading = true
    try {
      const { data } = await api.get<FriendsList>('/friends/list', { params: { tab } })
      const cur = list.value
      if (tab === 'online') {
        list.value = { ...cur, online: data.online }
      }
      else if (tab === 'offline') {
        list.value = { ...cur, offline: data.offline }
      }
      else if (tab === 'incoming') {
        list.value = { ...cur, incoming: data.incoming }
      }
      else {
        list.value = { ...cur, outgoing: data.outgoing }
      }
    } finally {
      tabLoading = false
      if (tabQueued) {
        const next = tabQueued
        tabQueued = null
        void fetchTab(next)
      }
    }
  }

  async function fetchCounts(): Promise<void> {
    if (countsLoading) {
      countsQueued = true
      return
    }
    countsLoading = true
    try {
      const { data } = await api.get<FriendsCounts>('/friends/counts')
      const next = {
        online: Number.isFinite(data?.online) ? data.online : 0,
        offline: Number.isFinite(data?.offline) ? data.offline : 0,
        incoming: Number.isFinite(data?.incoming) ? data.incoming : 0,
        outgoing: Number.isFinite(data?.outgoing) ? data.outgoing : 0,
        total: Number.isFinite(data?.total) ? data.total : 0,
      }
      counts.value = next
    } finally {
      countsLoading = false
      if (countsQueued) {
        countsQueued = false
        void fetchCounts()
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
      void fetchCounts()
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
    counts,
    rooms,
    loading,
    fetchAll,
    fetchRooms,
    fetchTab,
    fetchCounts,
    fetchStatus,
    sendRequest,
    acceptRequest,
    declineRequest,
    removeFriend,
    inviteToRoom,
    ensureWS,
  }
})
