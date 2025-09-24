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
  let storageListenerBound = false

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

  async function localSignOut(): Promise<void> { clearSession() }
  
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

    authSio.on('force_logout', async () => { await localSignOut() })
  }
  function disconnectAuthWS(): void {
    try { authSio?.off?.() } catch {}
    try { authSio?.close?.() } catch {}
    authSio = null
  }

  function setupCrossTab(): void {
    try {
      if (!bc && 'BroadcastChannel' in window) {
        bc = new BroadcastChannel('auth')
        bc.onmessage = async (ev) => handleSidMessage(ev?.data?.sid as string | undefined)
      }
      if (!storageListenerBound) {
        window.addEventListener('storage', (e) => {
          if (e.key !== 'auth:msg' || !e.newValue) return
          try {
            const { sid } = JSON.parse(e.newValue)
            void handleSidMessage(typeof sid === 'string' ? sid : undefined)
          } catch {}
        })
        storageListenerBound = true
      }
      setOnAuthExpired(() => { void localSignOut() })
      setOnTokenRefreshed((t) => {
        accessToken.value = t
        try { if (authSio) (authSio.io.opts as any).auth = { token: t } } catch {}
      })
    } catch {}
  }
  async function handleSidMessage(incoming?: string) {
    if (incoming === undefined) return
    if ((incoming && incoming !== sessionId.value) || (!incoming && sessionId.value)) {
      await localSignOut()
    }
  }
  function broadcastSession(): void {
    const payload = { sid: sessionId.value }
    try { bc?.postMessage(payload) } catch {}
    try {
      localStorage.setItem('auth:msg', JSON.stringify({ ...payload, ts: Date.now(), rnd: Math.random() }))
    } catch {}
  }

  async function init(): Promise<void> {
    if (ready.value) return
    if (initPromise) return initPromise

    initPromise = (async () => {
      setupCrossTab()
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
    localSignOut,
  }
})
