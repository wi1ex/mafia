import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { connectSocket, disconnectSocket } from '@/services/socket'
import {
  api,
  initAuthClient,
  applyNewAccessToken,
  getAccessToken,
  forceLogoutClientSide,
} from '@/services/axios'

export interface TgUser {
  id: number;
  username?: string;
  photo_url?: string;
  auth_date?: number;
  hash?: string;
}
export interface UserProfile {
  id: number;
  username?: string;
  photo_url?: string;
  role: string;
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string>(getAccessToken() || '')
  const me = ref<UserProfile | null>(null)

  const isAuthed = computed(() => !!accessToken.value)
  const role = computed(() => me.value?.role ?? 'user')
  const avatarUrl = computed(() => me.value?.photo_url || null)
  const displayName = computed(() => me.value?.username || 'User')

  async function fetchMe(){
    if (!accessToken.value) return
    const { data } = await api.get<UserProfile>('/v1/users/me')
    me.value = data
  }

  async function init(){
    const tok = initAuthClient({
      onTokenChange: (t) => {
        accessToken.value = t || ''
        if (t) {
          connectSocket(t, () => logout())
          fetchMe().catch(() => {})
        } else {
          disconnectSocket()
          me.value = null
        }
      },
      onUnauthorized: () => {
        // сервер отклонил refresh — чистим состояние
        accessToken.value = ''
        me.value = null
        disconnectSocket()
      },
    })

    if (tok) {
      connectSocket(tok, () => logout())
      try { await fetchMe() } catch {}
    }
  }

  async function signInWithTelegram(user: TgUser){
    const { data } = await api.post('/v1/auth/telegram', user)
    applyNewAccessToken(data.access_token)
    me.value = data.user
  }

  async function logout(){
    try { await api.post('/v1/auth/logout') } catch {}
    forceLogoutClientSide()
    disconnectSocket()
    accessToken.value = ''
    me.value = null
  }

  return {
    accessToken, me,
    isAuthed, role, avatarUrl, displayName,
    init, fetchMe, signInWithTelegram, logout,
    setToken: applyNewAccessToken, // совместимость
  }
})
