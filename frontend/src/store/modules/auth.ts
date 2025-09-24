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
  const foreignActive = ref(false)
  const SID_KEY = 'auth:sid'
  const OWNER_KEY = 'auth:owner'
  const HB_KEY = 'auth:owner_hb'
  const TAB_ID = Math.random().toString(36).slice(2)
  let initPromise: Promise<void> | null = null
  let authSio: Socket | null = null
  let bc: BroadcastChannel | null = null
  let storageListenerBound = false
  let consistencyTimer: number | null = null
  let hbTimer: number | null = null

  type SessionPayload = { access_token?: string; sid?: string }

  const isAuthed = computed(() => !!accessToken.value)
  
  const writeSidMarker = (sid: string) => { try { localStorage.setItem(SID_KEY, sid || '') } catch {} }
  const readSidMarker  = () => { try { return localStorage.getItem(SID_KEY) || '' } catch { return '' } }
  const readOwner = () => { try { return localStorage.getItem(OWNER_KEY) || '' } catch { return '' } }
  const readHb = () => {
    try {
      const v = localStorage.getItem(HB_KEY)
      return v ? JSON.parse(v) as {id: string; ts: number} : null } catch { return null }
  }
  const beat = () => { try { localStorage.setItem(HB_KEY, JSON.stringify({ id: TAB_ID, ts: Date.now() })) } catch {} }
  const becomeOwner = () => {
    try {
      localStorage.setItem(OWNER_KEY, TAB_ID)
      beat()
      if (hbTimer) clearInterval(hbTimer)
      hbTimer = window.setInterval(beat, 4000)
      window.addEventListener('beforeunload', () => { releaseOwnership(sessionId.value) }, { once: true })
    } catch {}
  }
  const releaseOwnership = (prevSid?: string) => {
    try {
      const owner = readOwner()
      if (owner === TAB_ID) {
        localStorage.removeItem(OWNER_KEY)
        localStorage.removeItem(HB_KEY)
        if (prevSid && readSidMarker() === prevSid) writeSidMarker('')
      }
    } catch {}
  }
  const ownerAlive = () => {
    const owner = readOwner()
    const hb = readHb()
    return !!owner && !!hb && hb.id === owner && (Date.now() - hb.ts) < 15000
  }
  const checkConsistency = async () => {
    const globalSid = readSidMarker()
    const cur = sessionId.value || ''
    if (!cur && globalSid) {
      if (!ownerAlive()) {
        releaseOwnership(globalSid)
        try { writeSidMarker('') } catch {}
        foreignActive.value = false
      } else {
        foreignActive.value = true
      }
      return
    }
    if (cur && !globalSid) {
      foreignActive.value = false
      await localSignOut()
      return
    }
    if (cur && globalSid && cur !== globalSid) {
      foreignActive.value = false
      await localSignOut()
      return
    }
    foreignActive.value = false
  }
  
  async function applySession(data: SessionPayload, { connect = true } = {}) {
    accessToken.value = data.access_token
    sessionId.value = data.sid || ''
    setAuthHeader(accessToken.value)
    setupCrossTab()
    if (connect) connectAuthWS()
    writeSidMarker(sessionId.value)
    if (!readOwner() || !ownerAlive()) becomeOwner()
    broadcastSession()
    ready.value = true
  }

  function clearSession() {
    const prev = sessionId.value
    accessToken.value = ''
    sessionId.value = ''
    setAuthHeader('')
    user.value = null
    disconnectAuthWS()
    writeSidMarker('')
    releaseOwnership(prev)
    foreignActive.value = !!readSidMarker()
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
        window.addEventListener('focus', () => { void checkConsistency() })
        document.addEventListener('visibilitychange', () => { if (!document.hidden) void checkConsistency() })
        consistencyTimer = window.setInterval(() => { void checkConsistency() }, 5000)
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
    await checkConsistency()
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
      await checkConsistency()
      if (foreignActive.value) {
        ready.value = true
      } else {
        try {
          const { data } = await api.post('/auth/refresh', undefined, { __skipAuth: true })
          await applySession(data)
        } catch {
          const hasGlobal = !!readSidMarker()
          if (hasGlobal) { ready.value = true } else { clearSession() }
        } finally {
          initPromise = null
        }
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
    foreignActive,

    init,
    fetchMe,
    signInWithTelegram,
    logout,
    localSignOut,
  }
})
