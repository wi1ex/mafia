import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, setAuthHeader, setOnAuthExpired, setOnTokenRefreshed } from '@/services/axios'
import { io, Socket } from 'socket.io-client'

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
  const sessionId = ref<string>('')
  const user = ref<UserProfile | null>(null)
  const ready = ref(false)
  let initPromise: Promise<void> | null = null
  let authSio: Socket | null = null
  let bc: BroadcastChannel | null = null

  const isAuthed = computed(() => !!accessToken.value)

  type SessionPayload = { access_token?: string; sid?: string }
  
  async function applySession(data: SessionPayload, { connect = true } = {}) {
    accessToken.value = data.access_token
    sessionId.value = data.sid || ''
    setAuthHeader(accessToken.value)
    setupCrossTab()
    if (connect) connectAuthWS()
    broadcastSession()
    ready.value = true
  }

  function clearSession() {
    accessToken.value = ''
    sessionId.value = ''
    setAuthHeader('')
    user.value = null
    disconnectAuthWS()
    broadcastSession()
    ready.value = true
  }
  
  function connectAuthWS(): void {
    disconnectAuthWS()
    if (!accessToken.value) return
    authSio = io('/auth', {
      path: '/ws/socket.io',
      transports: ['websocket'],
      auth: { token: accessToken.value },
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
      reconnectionDelayMax: 5000,
    })

    authSio.on('force_logout', async () => { await logout() })
  }
  function disconnectAuthWS(): void {
    try { authSio?.off?.() } catch {}
    try { authSio?.close?.() } catch {}
    authSio = null
  }

  function setupCrossTab(): void {
    try {
      if (bc) return
      bc = new BroadcastChannel('auth')
      bc.onmessage = async (ev) => {
        const sid = ev?.data?.sid as string | undefined
        if (sid === undefined) return
        if (sid && sid !== sessionId.value) { await logout() }
        if (!sid && sessionId.value)       { await logout() }
      }
      setOnAuthExpired(() => { void logout() })
      setOnTokenRefreshed((t) => {
        accessToken.value = t
        try { if (authSio) (authSio.io.opts as any).auth = { token: t } } catch {}
      })
    } catch {}
  }
  function broadcastSession(): void {
    try { bc?.postMessage({ sid: sessionId.value }) } catch {}
  }

  async function init(): Promise<void> {
    if (ready.value) return
    if (initPromise) return initPromise

    initPromise = (async () => {
      try {
        const { data } = await api.post('/auth/refresh', undefined, { __skipAuth: true })
        await applySession(data)
      } catch {
        clearSession()
      } finally {
        initPromise = null
      }
    })()

    return initPromise
  }

  async function signInWithTelegram(user: TgUser): Promise<void> {
    const { data } = await api.post('/auth/telegram', user)
    await applySession(data)
    await fetchMe()
  }

  async function fetchMe(): Promise<void> {
    const { data } = await api.get<UserProfile>('/users/profile_info')
    user.value = data
  }

  async function logout(): Promise<void> {
    try { await api.post('/auth/logout', undefined, { __skipAuth: true }) } catch {} finally { clearSession() }
  }

  return {
    accessToken,
    sessionId,
    user,
    ready,
    isAuthed,

    init,
    fetchMe,
    signInWithTelegram,
    logout,
  }
})
