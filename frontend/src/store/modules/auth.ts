import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, setAuthHeader } from '@/services/axios'

export interface TgUser {
  id: number
  username?: string
  photo_url?: string
  auth_date?: number
  hash?: string
}

export interface UserProfile {
  id: number
  username?: string
  photo_url?: string
  role: string
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string>('')
  const user = ref<UserProfile | null>(null)
  const ready = ref(false)
  let initPromise: Promise<void> | null = null

  const isAuthed = computed(() => !!accessToken.value)

  async function init(): Promise<void> {
    if (ready.value) return
    if (initPromise) return initPromise

    initPromise = (async () => {
      try {
        const { data } = await api.post('/auth/refresh', undefined, { __skipAuth: true })
        accessToken.value = data.access_token
        setAuthHeader(accessToken.value)
        await fetchMe()
      } catch {
        accessToken.value = ''
        setAuthHeader(accessToken.value)
        user.value = null
      } finally {
        ready.value = true
        initPromise = null
      }
    })()

    return initPromise
  }

  async function signInWithTelegram(user: TgUser): Promise<void> {
    const { data } = await api.post('/auth/telegram', user)
    accessToken.value = data.access_token
    setAuthHeader(accessToken.value)
    await fetchMe()
    ready.value = true
  }

  async function fetchMe(): Promise<void> {
    const { data } = await api.get<UserProfile>('/users/profile_info')
    user.value = data
  }

  async function logout(): Promise<void> {
    try {
      await api.post('/auth/logout', undefined, { __skipAuth: true })
    } catch {
      // ignore
    } finally {
      accessToken.value = ''
      setAuthHeader(accessToken.value)
      user.value = null
      ready.value = true
    }
  }

  return {
    accessToken,
    user,
    ready,
    isAuthed,

    init,
    fetchMe,
    signInWithTelegram,
    logout,
  }
})
