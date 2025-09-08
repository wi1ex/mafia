import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const TOKEN_KEY = 'access_token'

// === внешние колбэки (подписчики) ===
let onTokenChange: ((t: string | null) => void) | null = null
let onUnauthorized: (() => void) | null = null

export function initAuthClient(handlers?: {
  onTokenChange?: (t: string | null) => void
  onUnauthorized?: () => void
}) {
  if (handlers?.onTokenChange) onTokenChange = handlers.onTokenChange
  if (handlers?.onUnauthorized) onUnauthorized = handlers.onUnauthorized

  // при старте восстановим заголовки и авто-рефреш
  const t = getAccessToken()
  if (t) {
    api.defaults.headers.common.Authorization = `Bearer ${t}`
    scheduleRefreshFromToken(t)
  }
  return t
}

// === хранение токена ===
export function getAccessToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}
export function setAccessToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
  api.defaults.headers.common.Authorization = `Bearer ${token}`
  scheduleRefreshFromToken(token)
  onTokenChange?.(token)
}
export function clearAccessToken() {
  localStorage.removeItem(TOKEN_KEY)
  delete api.defaults.headers.common.Authorization
  cancelScheduledRefresh()
  onTokenChange?.(null)
}

// === axios клиент ===
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? '/api',
  timeout: 15000,
  withCredentials: true,
})

// request: подставляем токен из localStorage, если заголовок ещё не стоит
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (!config.headers?.Authorization) {
    const t = getAccessToken()
    if (t) config.headers.Authorization = `Bearer ${t}`
  }
  return config
})

// === авто-рефреш по 401 с single-flight ===
let isRefreshing = false
let waiters: Array<(t: string | null) => void> = []

function notifyWaiters(t: string | null) {
  waiters.forEach((w) => w(t))
  waiters = []
}

api.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    const status = err.response?.status
    const cfg: any = err.config || {}
    const url = (cfg.url || '') as string
    const isRefresh = url.includes('/v1/auth/refresh')
    const alreadyRetried = cfg.__retry401 === true

    if (status === 401 && !isRefresh && !alreadyRetried) {
      cfg.__retry401 = true

      if (!isRefreshing) {
        isRefreshing = true
        try {
          const { data } = await api.post('/v1/auth/refresh')
          const newToken = (data as any)?.access_token as string | undefined
          if (!newToken) throw new Error('no access token')
          setAccessToken(newToken)
          notifyWaiters(newToken)
        } catch {
          clearAccessToken()
          notifyWaiters(null)
          onUnauthorized?.()
          // пробросим исходную ошибку
          throw err
        } finally {
          isRefreshing = false
        }
      }

      // ждём общего рефреша
      const token = await new Promise<string | null>((resolve) => waiters.push(resolve))
      if (!token) throw err
      cfg.headers = cfg.headers || {}
      cfg.headers.Authorization = `Bearer ${token}`
      return api(cfg)
    }

    return Promise.reject(err)
  }
)

// === проактивный рефреш перед истечением ===
let refreshTimer: number | null = null

function cancelScheduledRefresh() {
  if (refreshTimer) {
    window.clearTimeout(refreshTimer)
    refreshTimer = null
  }
}

function parseJwtExp(jwtStr: string): number | null {
  try {
    const [, payload] = jwtStr.split('.')
    const json = JSON.parse(
      decodeURIComponent(
        atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      )
    )
    return typeof json.exp === 'number' ? json.exp : null
  } catch {
    return null
  }
}

function scheduleRefreshFromToken(token: string) {
  cancelScheduledRefresh()
  const exp = parseJwtExp(token)
  if (!exp) return
  const msToExp = exp * 1000 - Date.now()
  const msToRefresh = Math.max(0, msToExp - 5 * 60 * 1000) // за 5 минут
  refreshTimer = window.setTimeout(triggerRefresh, msToRefresh)
}

async function triggerRefresh() {
  try {
    const { data } = await api.post('/v1/auth/refresh')
    const t = (data as any)?.access_token as string | undefined
    if (!t) throw new Error('no access token')
    setAccessToken(t)
  } catch {
    clearAccessToken()
    onUnauthorized?.()
  }
}

// вспомогательное API для логина/логаута из стора
export function applyNewAccessToken(token: string) {
  setAccessToken(token)
}
export function forceLogoutClientSide() {
  clearAccessToken()
}
