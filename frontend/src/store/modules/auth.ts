import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, setAuthHeader } from '@/services/axios'

export interface TgUser {
  id: number;
  username?: string;
  photo_url?: string;
  auth_date?: number;
  hash?: string ;
}

export interface UserProfile {
  id: number;
  username?: string;
  photo_url?: string;
  role: string ;
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string>('')
  const me = ref<UserProfile | null>(null)

  const isAuthed = computed(() => !!accessToken.value)
  const role = computed(() => me.value?.role ?? 'user')
  const avatarUrl = computed(() => me.value?.photo_url || null)
  const displayName = computed(() => me.value?.username || 'User')

  function setAccess(t: string) {
    accessToken.value = t
    setAuthHeader(t)
  }

  async function init() {
    try {
      const { data } = await api.post('/auth/refresh')
      setAccess(data.access_token)
      me.value = data.user
    } catch {
      setAccess(''); me.value = null
    }
  }

  async function fetchMe() {
    const { data } = await api.get<UserProfile>('/users/me')
    me.value = data
  }

  async function signInWithTelegram(user: TgUser) {
    const { data } = await api.post('/auth/telegram', user)
    setAccess(data.access_token)
    me.value = data.user
  }

  async function logout() {
    try {
      await api.post('/auth/logout')
    } catch {}
    setAccess('')
    me.value = null
  }

  return {
    accessToken,
    me,
    isAuthed,
    role,
    avatarUrl,
    displayName,

    init,
    fetchMe,
    signInWithTelegram,
    logout,
    setToken: setAccess
  }
})
