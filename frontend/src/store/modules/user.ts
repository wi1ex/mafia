import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

export interface UserProfile {
  id: number
  username?: string
  avatar_name?: string | null
  role: string
}

export const useUserStore = defineStore('user', () => {
  const user = ref<UserProfile | null>(null)

  async function fetchMe(): Promise<void> {
    const { data } = await api.get<UserProfile>('/users/profile_info')
    user.value = data
  }

  function updateStoredRoomTitle(id: number, name: string) {
    const trimmed = (name || '').trim()
    const nick = trimmed || (Number.isFinite(id) ? `user${id}` : 'user')
    const title = `Комната ${nick}`
    try {
      const raw = localStorage.getItem('room:lastRoom')
      const payload = raw ? JSON.parse(raw) as Record<string, unknown> : {}
      payload.title = title
      localStorage.setItem('room:lastRoom', JSON.stringify(payload))
    } catch {}
  }
  function setUsername(name: string) {
    if (!user.value) return
    user.value.username = name
    updateStoredRoomTitle(user.value.id, name)
  }

  function setAvatarName(name: string | null) { if (user.value) user.value.avatar_name = name }

  function clear(): void {
    user.value = null
  }

  return {
    user,

    fetchMe,
    setUsername,
    setAvatarName,
    clear,
  }
})
