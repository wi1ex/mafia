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

  function clear(): void {
    user.value = null
  }

  return {
    user,
    fetchMe,
    clear,
  }
})
