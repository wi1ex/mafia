import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, setAuthHeader, addAuthExpiredListener } from '@/services/axios'
import {
  initSessionBus, setSid, clearSid, isForeignActive,
  onForeignActive, onInconsistency, checkConsistencyNow
} from '@/services/session'
import { startAuthSocket, stopAuthSocket } from '@/services/sio'

export interface TgUser {
  id: number; username?: string; photo_url?: string; auth_date?: number; hash?: string
}
export interface UserProfile {
  id: number; username?: string; photo_url?: string; role: string
}

export const useAuthStore = defineStore('auth', () => {
  const sessionId = ref<string>('')
  const user = ref<UserProfile | null>(null)
  const ready = ref(false)
  const foreign = ref(false)

  const isAuthed = computed(() => !!sessionId.value)

  let busInited = false
  let unsubFA: (() => void) | null = null
  let unsubINC: (() => void) | null = null

  function bindBus() {
    if (busInited) return
    initSessionBus()
    unsubFA = onForeignActive((on) => { foreign.value = on })
    unsubINC = onInconsistency(async () => { await localSignOut() })
    busInited = true
  }
  function unbindBus() {
    unsubFA?.()
    unsubINC?.()
    unsubFA = unsubINC = null
  }

  async function applySession(data: { access_token?: string; sid?: string }, { connect = true } = {}) {
    sessionId.value = data.sid || ''
    setAuthHeader(data.access_token || '')
    bindBus()
    setSid(sessionId.value)
    if (connect) startAuthSocket({ onForceLogout: () => { void localSignOut() } })
    ready.value = true
  }

  function clearSession() {
    const prev = sessionId.value
    sessionId.value = ''
    user.value = null
    setAuthHeader('')
    stopAuthSocket()
    clearSid(prev)
    foreign.value = isForeignActive()
    ready.value = true
  }

  async function localSignOut(): Promise<void> { clearSession() }

  async function init(): Promise<void> {
    if (ready.value) return
    bindBus()
    addAuthExpiredListener(() => { void localSignOut() })

    await checkConsistencyNow()
    if (isForeignActive()) {
      foreign.value = true
      ready.value = true
      return
    }
    try {
      const { data } = await api.post('/auth/refresh', undefined, { __skipAuth: true })
      await applySession(data)
    } catch {
      clearSession()
    }
  }

  async function signInWithTelegram(tg: TgUser): Promise<void> {
    const { data } = await api.post('/auth/telegram', tg)
    await applySession(data)
    await fetchMe()
  }

  async function fetchMe(): Promise<void> {
    const { data } = await api.get<UserProfile>('/users/profile_info')
    user.value = data
  }

  async function logout(): Promise<void> {
    try { await api.post('/auth/logout', undefined, { __skipAuth: true }) } catch {}
    finally { clearSession() }
  }

  return {
    sessionId,
    user,
    ready,
    isAuthed,
    foreignActive: foreign,

    init,
    fetchMe,
    signInWithTelegram,
    logout,
    localSignOut,
  }
})
