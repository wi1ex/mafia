import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { startAuthSocket, stopAuthSocket } from '@/services/sio'
import {
  api,
  setAuthHeader,
  addAuthExpiredListener,
  refreshAccessTokenFull,
} from '@/services/axios'
import {
  initSessionBus,
  setSid,
  clearSid,
  isForeignActive,
  onForeignActive,
  onInconsistency,
  checkConsistencyNow,
  stopSessionBus,
} from '@/services/session'

export interface TgUser {
  id: number
  username?: string
  photo_url?: string
  auth_date?: number
  hash?: string
}

export const useAuthStore = defineStore('auth', () => {
  const sessionId = ref<string>('')
  const ready = ref(false)
  const foreign = ref(false)

  const isAuthed = computed(() => Boolean(sessionId.value))

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
    if (connect) {
      startAuthSocket({
        onForceLogout: () => { void localSignOut() },
        onNotify: (p) => {
          try {
            window.dispatchEvent(new CustomEvent('auth-notify', { detail: p }))
            window.dispatchEvent(new CustomEvent('toast', { detail: { id: p.id, kind: 'approve', text: p.text } }))
          } catch {}
        },
        onRoomApp: (p) => {
          try {
            window.dispatchEvent(new CustomEvent('auth-room_app', { detail: p }))
            const text = `Заявка в комнату #${p.room_id}: ${p.user?.username || ('user' + p.user?.id)}`
            window.dispatchEvent(new CustomEvent('toast', {
              detail: {
                kind: 'app',
                text,
                action: {
                  label: 'Разрешить вход',
                  run: async () => { try { await api.post(`/rooms/${p.room_id}/applications/${p.user.id}/approve`) } catch {} }
                }
              }
            }))
          } catch {}
        }
      })
    }
    ready.value = true
  }

  async function clearSession() {
    const prev = sessionId.value
    sessionId.value = ''
    setAuthHeader('')
    stopAuthSocket()
    clearSid(prev)
    unbindBus()
    stopSessionBus()
    foreign.value = isForeignActive()
    ready.value = true
    try {
      const { useUserStore } = await import('@/store/modules/user')
      useUserStore().clear()
    } catch {}
  }

  async function localSignOut(): Promise<void> { await clearSession() }

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
      const data = await refreshAccessTokenFull(false)
      if (!data) {
        await clearSession()
        return
      }
      await applySession(data)
    } catch {
      await clearSession()
    }
  }

  function wipeLocalForNewLogin() {
    try {
      const toDel = new Set([ 'audioDeviceId', 'videoDeviceId', 'videoQuality', 'mediaPermProbed' ])
      const extra: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i)!
        if (k.startsWith('vol:') || k.startsWith('auth:') || k.startsWith('loglevel:')) extra.push(k)
      }
      ;[...toDel, ...extra].forEach((k:any) => { try { localStorage.removeItem(k) } catch {} })
      try { sessionStorage.clear() } catch {}
    } catch {}
  }

  async function signInWithTelegram(tg: TgUser): Promise<void> {
    const { data } = await api.post('/auth/telegram', tg)
    await applySession(data)
    const { useUserStore } = await import('@/store/modules/user')
    await useUserStore().fetchMe()
  }

  async function logout(): Promise<void> {
    try { await api.post('/auth/logout', undefined, { __skipAuth: true }) } catch {}
    finally { await clearSession() }
  }

  return {
    sessionId,
    ready,
    isAuthed,
    foreignActive: foreign,

    init,
    signInWithTelegram,
    logout,
    localSignOut,
    wipeLocalForNewLogin,
  }
})
