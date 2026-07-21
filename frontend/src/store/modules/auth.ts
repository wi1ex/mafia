import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { startAuthSocket, stopAuthSocket } from '@/services/sio'
import {
  api,
  AUTH_SESSION_SID_HEADER,
  setAuthHeader,
  addAuthExpiredListener,
  refreshAccessTokenFull,
} from '@/services/axios'
import { isPwaMode } from '@/services/pwa'
import { alertDialog } from '@/services/confirm'
import { formatModerationAlert } from '@/services/moderation'
import { hasAuthCookieMutex, withAuthCookieLock } from '@/services/refreshCoordination'
import { useUserStore } from './user'
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
  const loginCooldownUntil = ref(0)
  const registerCooldownUntil = ref(0)
  const sessionStorageKeepKeys = ['auth:tabId', 'auth:sessionSid']

  const isAuthed = computed(() => Boolean(sessionId.value))
  const loginCooldownActive = computed(() => loginCooldownUntil.value > Date.now())
  const registerCooldownActive = computed(() => registerCooldownUntil.value > Date.now())

  let busInited = false
  let unsubFA: (() => void) | null = null
  let unsubINC: (() => void) | null = null
  let loginCooldownTimer: number | null = null
  let registerCooldownTimer: number | null = null

  function readRetryAfterSeconds(error: any, fallbackS: number): number {
    const headers = error?.response?.headers
    let raw: unknown = null
    if (headers && typeof headers.get === 'function') {
      raw = headers.get('retry-after')
    } else if (headers && typeof headers === 'object') {
      raw = headers['retry-after'] ?? headers['Retry-After']
    }
    const parsed = Number(Array.isArray(raw) ? raw[0] : raw)
    return Number.isFinite(parsed) && parsed > 0 ? Math.ceil(parsed) : fallbackS
  }

  function formatRetryAfter(seconds: number): string {
    const total = Math.max(1, Math.ceil(seconds))
    if (total < 60) return `${total} сек.`
    const minutes = Math.floor(total / 60)
    const rest = total % 60
    return rest > 0 ? `${minutes} мин. ${rest} сек.` : `${minutes} мин.`
  }

  function clearCooldown(action: 'login' | 'register'): void {
    if (action === 'login') {
      if (loginCooldownTimer !== null) window.clearTimeout(loginCooldownTimer)
      loginCooldownTimer = null
      loginCooldownUntil.value = 0
      return
    }
    if (registerCooldownTimer !== null) window.clearTimeout(registerCooldownTimer)
    registerCooldownTimer = null
    registerCooldownUntil.value = 0
  }

  function setCooldown(action: 'login' | 'register', seconds: number): void {
    const ttlMs = Math.max(1, Math.ceil(seconds)) * 1000
    const nextUntil = Date.now() + ttlMs
    if (action === 'login') {
      loginCooldownUntil.value = Math.max(loginCooldownUntil.value, nextUntil)
      if (loginCooldownTimer !== null) window.clearTimeout(loginCooldownTimer)
      loginCooldownTimer = window.setTimeout(() => {
        loginCooldownTimer = null
        loginCooldownUntil.value = 0
      }, Math.max(0, loginCooldownUntil.value - Date.now()))
      return
    }
    registerCooldownUntil.value = Math.max(registerCooldownUntil.value, nextUntil)
    if (registerCooldownTimer !== null) window.clearTimeout(registerCooldownTimer)
    registerCooldownTimer = window.setTimeout(() => {
      registerCooldownTimer = null
      registerCooldownUntil.value = 0
    }, Math.max(0, registerCooldownUntil.value - Date.now()))
  }

  function remainingCooldownSeconds(action: 'login' | 'register'): number {
    const until = action === 'login' ? loginCooldownUntil.value : registerCooldownUntil.value
    return until > 0 ? Math.max(0, Math.ceil((until - Date.now()) / 1000)) : 0
  }

  function handleAuthRateLimit(action: 'login' | 'register', error: any): boolean {
    const st = Number(error?.response?.status || 0)
    if (st !== 429) return false

    const detail = String(error?.response?.data?.detail || '').trim()
    const retryAfter = readRetryAfterSeconds(error, detail === 'ip_temporarily_blocked' ? 1800 : 60)
    if (detail === 'ip_temporarily_blocked') {
      setCooldown('login', retryAfter)
      setCooldown('register', retryAfter)
      void alertDialog(`Слишком много попыток. Доступ временно ограничен на ${formatRetryAfter(retryAfter)}.`)
      return true
    }

    setCooldown(action, retryAfter)
    const actionLabel = action === 'login' ? 'входа' : 'регистрации'
    void alertDialog(`Слишком много попыток ${actionLabel}. Повторите через ${formatRetryAfter(retryAfter)}.`)
    return true
  }

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

  function clearSessionStoragePreserving(keys: string[]) {
    try {
      const keep: Record<string, string> = {}
      for (const key of keys) {
        const raw = sessionStorage.getItem(key)
        if (raw !== null) keep[key] = raw
      }
      sessionStorage.clear()
      for (const [key, value] of Object.entries(keep)) {
        try { sessionStorage.setItem(key, value) } catch {}
      }
    } catch {}
  }

  function bindBus() {
    if (busInited) return
    initSessionBus()
    unsubFA = onForeignActive((on) => { foreign.value = on })
    unsubINC = onInconsistency(async () => { await localSignOut() })
    foreign.value = isForeignActive()
    busInited = true
  }
  function unbindBus() {
    unsubFA?.()
    unsubINC?.()
    unsubFA = unsubINC = null
    busInited = false
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

  async function clearSession({ preservePublishedSid = false }: { preservePublishedSid?: boolean } = {}) {
    sessionId.value = ''
    setAuthHeader('')
    stopAuthSocket()
    clearSid({ preservePublished: preservePublishedSid })
    unbindBus()
    stopSessionBus()
    foreign.value = isForeignActive()
    ready.value = true
    try {
      useUserStore().clear()
    } catch {}
  }

  async function localSignOut(expectedSid: string = sessionId.value): Promise<void> {
    try {
      await withAuthCookieLock(async () => {
        if (sessionId.value !== expectedSid) return
        await clearSession()
      })
    } catch {
      if (sessionId.value === expectedSid) {
        await clearSession({ preservePublishedSid: true })
      }
    }
  }

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
        await localSignOut()
        return
      }
      const returnedSid = String(data.sid || '')
      let applied = false
      try {
        await withAuthCookieLock(async () => {
          let publishedSid = returnedSid
          let scopeReadable = false
          try {
            publishedSid = localStorage.getItem('auth:sid') || ''
            scopeReadable = true
          } catch {}
          if (!returnedSid || (scopeReadable && publishedSid !== returnedSid)) return
          await applySession(data)
          applied = true
        })
      } catch {}
      if (!applied) {
        await localSignOut()
        return
      }
      return
    } catch {
      await localSignOut()
    }
  }

  function wipeLocalForNewLogin(opts?: { userChanged?: boolean }) {
    try {
      clearSessionStoragePreserving(sessionStorageKeepKeys)
      scanAndDelContains(['apps_seen'])
      if (!opts?.userChanged) return
      delLS([
        'room:lastRoom',
        'room:lastGame',
      ])
      scanAndDel(['vol:', 'loglevel:', 'room:'])
    } catch {}
  }

  function onAuthorizedUserResolved(userId?: number) {
    try {
      const uid = Number(userId || 0)
      const prevRaw = localStorage.getItem('auth:last_uid')
      const prevUid = Number(prevRaw || 0)
      const prevKnown = Number.isFinite(prevUid) && prevUid > 0
      const userChanged = prevKnown && uid > 0 && prevUid !== uid
      wipeLocalForNewLogin({ userChanged })
      if (uid > 0) localStorage.setItem('auth:last_uid', String(uid))
    } catch {}
  }

  function publishedSessionMatches(expectedSid: string): boolean {
    if (!expectedSid || sessionId.value !== expectedSid || !hasAuthCookieMutex()) return false
    try {
      return (localStorage.getItem('auth:sid') || '') === expectedSid
    } catch {
      return typeof navigator !== 'undefined' && Boolean((navigator as Navigator & { locks?: unknown }).locks)
    }
  }

  async function finalizeAuthorizedUser(expectedSid: string, userId?: number): Promise<boolean> {
    if (!expectedSid) return false
    try {
      return await withAuthCookieLock(async () => {
        if (!publishedSessionMatches(expectedSid)) return false
        onAuthorizedUserResolved(userId)
        return true
      })
    } catch {
      return false
    }
  }

  async function signInWithPassword(payload: { username: string; password: string }): Promise<void> {
    const retryIn = remainingCooldownSeconds('login')
    if (retryIn > 0) {
      void alertDialog(`Попробуйте снова через ${formatRetryAfter(retryIn)}.`)
      return
    }
    let loginSid = ''
    try {
      const headers = isPwaMode() ? { 'X-PWA': '1' } : undefined
      await withAuthCookieLock(async () => {
        const { data } = await api.post('/auth/login', payload, headers ? { headers } : undefined)
        loginSid = String(data?.sid || '')
        await applySession(data)
      })
      clearCooldown('login')
      const userStore = useUserStore()
      await userStore.fetchMe()
      const stillCurrent = await finalizeAuthorizedUser(loginSid, userStore.user?.id)
      if (stillCurrent && userStore.passwordTemp) {
        const { default: router } = await import('@/router')
        router.push({ name: 'profile', query: { tab: 'profile' } }).catch(() => {})
      }
    } catch (e: any) {
      const st = e?.response?.status
      const detail = e?.response?.data?.detail
      if (handleAuthRateLimit('login', e)) return
      if (st === 403 && detail === 'password_not_set') {
        void alertDialog('Пароль не установлен. Восстановите пароль через TG-бота.')
      } else if (st === 403 && detail === 'user_deleted') {
        void alertDialog('Авторизация невозможна: аккаунт удален')
      } else if (st === 401 && detail === 'invalid_credentials') {
        void alertDialog('Неверный никнейм или пароль')
      } else {
        void alertDialog('Не удалось войти')
      }
    }
  }

  async function registerWithPassword(payload: {
    username: string
    password: string
    accept_rules?: boolean
    accept_legal_documents?: boolean
    confirm_adult?: boolean
  }): Promise<void> {
    const retryIn = remainingCooldownSeconds('register')
    if (retryIn > 0) {
      void alertDialog(`Попробуйте снова через ${formatRetryAfter(retryIn)}.`)
      return
    }
    let registrationSid = ''
    try {
      const headers = isPwaMode() ? { 'X-PWA': '1' } : undefined
      await withAuthCookieLock(async () => {
        const res = await api.post('/auth/register', payload, headers ? { headers } : undefined)
        const next = res.data as { access_token?: string; sid?: string }
        registrationSid = String(next.sid || '')
        await applySession(next)
      })
      clearCooldown('register')
    } catch (e: any) {
      const st = e?.response?.status
      const detail = e?.response?.data?.detail
      const moderationText = formatModerationAlert(detail)
      if (handleAuthRateLimit('register', e)) return
      if (st === 428 && detail === 'rules_required') {
        void alertDialog('Необходимо согласиться с правилами')
        return
      }
      if (st === 428 && detail === 'adult_confirmation_required') {
        void alertDialog('Необходимо подтвердить, что вам исполнилось 18 лет')
        return
      }
      if (st === 428 && detail === 'legal_documents_required') {
        void alertDialog('Необходимо принять Пользовательское соглашение и ознакомиться с Политикой обработки персональных данных')
        return
      }
      if (st === 403 && detail === 'registration_disabled') {
        void alertDialog('Регистрация временно недоступна')
      } else if (st === 409 && detail === 'username_taken') {
        void alertDialog('Никнейм уже занят')
      } else if (st === 422 && moderationText) {
        void alertDialog({ title: 'Отказ в регистрации', text: moderationText })
      } else if (st === 422 && detail === 'invalid_username_format') {
        void alertDialog('Никнейм не должен начинаться с deleted_ или user_ и не должен содержать символы кроме ()._-')
      } else if (st === 422 && detail === 'invalid_password') {
        void alertDialog('Пароль должен быть от 8 до 32 символов и без пробелов')
      } else {
        void alertDialog('Не удалось зарегистрироваться')
      }
      return
    }

    const userStore = useUserStore()
    try {
      await userStore.fetchMe()
    } catch {
      try {
        await new Promise<void>((resolve) => window.setTimeout(resolve, 300))
        await userStore.fetchMe()
      } catch {
        void alertDialog('Ошибка загрузки профиля')
        return
      }
    }
    await finalizeAuthorizedUser(registrationSid, userStore.user?.id)
  }

  async function logout(): Promise<void> {
    const expectedSid = sessionId.value
    try {
      await withAuthCookieLock(async () => {
        if (!publishedSessionMatches(expectedSid)) return
        await api.post('/auth/logout', undefined, {
          __skipAuth: true,
          headers: { [AUTH_SESSION_SID_HEADER]: expectedSid },
        })
        await clearSession()
      })
    } catch {}
    finally {
      if (sessionId.value === expectedSid) await localSignOut(expectedSid)
    }
  }

  return {
    sessionId,
    ready,
    isAuthed,
    foreignActive: foreign,
    loginCooldownActive,
    registerCooldownActive,

    init,
    signInWithPassword,
    registerWithPassword,
    logout,
    localSignOut,
    wipeLocalForNewLogin,
  }
})
