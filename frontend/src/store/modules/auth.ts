import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { startAuthSocket, stopAuthSocket } from '@/services/sio'
import {
  api,
  setAuthHeader,
  addAuthExpiredListener,
  refreshAccessTokenFull,
} from '@/services/axios'
import { isPwaMode } from '@/services/pwa'
import { alertDialog } from '@/services/confirm'
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

export const useAuthStore = defineStore('auth', () => {
  const sessionId = ref<string>('')
  const ready = ref(false)
  const foreign = ref(false)

  const isAuthed = computed(() => Boolean(sessionId.value))

  let busInited = false
  let unsubFA: (() => void) | null = null
  let unsubINC: (() => void) | null = null

  function delLS(keys: string[]) {
    for (const k of keys) { try { localStorage.removeItem(k) } catch {} }
  }

  function scanAndDel(prefixes: string[]) {
    const extra: string[] = []
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i)!
        if (prefixes.some(p => k.startsWith(p))) extra.push(k)
      }
    } catch {}
    delLS(extra)
  }

  function scanAndDelContains(parts: string[]) {
    const extra: string[] = []
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i)!
        if (parts.some(p => k.includes(p))) extra.push(k)
      }
    } catch {}
    delLS(extra)
  }

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
      startAuthSocket({ onForceLogout: () => { void localSignOut() } })
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
      const { useUserStore } = await import('@/store')
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
      await new Promise(r => setTimeout(r, 0))
      await checkConsistencyNow()
      if (isForeignActive()) {
        foreign.value = true
        ready.value = true
        return
      }
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

  function wipeLocalForNewLogin(opts?: { userChanged?: boolean }) {
    try {
      try { sessionStorage.clear() } catch {}
      scanAndDelContains(['apps_seen'])
      if (!opts?.userChanged) return
      delLS([
        'auth:sid',
        'auth:lock',
        'room:lastRoom',
        'room:lastGame'
      ])
      scanAndDel(['vol:', 'loglevel:', 'room:'])
    } catch {}
  }

  async function signInWithPassword(payload: { username: string; password: string }): Promise<void> {
    try {
      const headers = isPwaMode() ? { 'X-PWA': '1' } : undefined
      const { data } = await api.post('/auth/login', payload, headers ? { headers } : undefined)
      await applySession(data)
      const { useUserStore } = await import('@/store')
      const userStore = useUserStore()
      await userStore.fetchMe()
      if (userStore.passwordTemp) {
        const { default: router } = await import('@/router')
        router.push({ name: 'profile', query: { tab: 'account' } }).catch(() => {})
      }
    } catch (e: any) {
      const st = e?.response?.status
      const detail = e?.response?.data?.detail
      if (st === 403 && detail === 'password_not_set') {
        void alertDialog('Пароль не установлен. Восстановите пароль через Telegram-бота.')
      } else if (st === 403 && detail === 'user_deleted') {
        void alertDialog('Авторизация невозможна: аккаунт удален')
      } else if (st === 401 && detail === 'invalid_credentials') {
        void alertDialog('Неверный логин или пароль')
      } else {
        void alertDialog('Не удалось войти')
      }
    }
  }

  async function registerWithPassword(payload: { username: string; password: string; accept_rules?: boolean }): Promise<void> {
    try {
      const headers = isPwaMode() ? { 'X-PWA': '1' } : undefined
      const { data } = await api.post('/auth/register', payload, headers ? { headers } : undefined)
      await applySession(data)
      const { useUserStore } = await import('@/store')
      await useUserStore().fetchMe()
    } catch (e: any) {
      const st = e?.response?.status
      const detail = e?.response?.data?.detail
      if (st === 428 && detail === 'rules_required') {
        void alertDialog('Необходимо согласиться с правилами')
        return
      }
      if (st === 403 && detail === 'registration_disabled') {
        void alertDialog('Регистрация временно недоступна')
      } else if (st === 409 && detail === 'username_taken') {
        void alertDialog('Никнейм уже занят')
      } else if (st === 422 && detail === 'invalid_username_format') {
        void alertDialog('Недопустимый формат никнейма')
      } else if (st === 422 && detail === 'invalid_password') {
        void alertDialog('Пароль не должен быть пустым')
      } else {
        void alertDialog('Не удалось зарегистрироваться')
      }
    }
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
    signInWithPassword,
    registerWithPassword,
    logout,
    localSignOut,
    wipeLocalForNewLogin,
  }
})
