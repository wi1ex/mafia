import axios,{
  AxiosError, AxiosHeaders, AxiosResponse, InternalAxiosRequestConfig,
} from 'axios'
import { coordinateRefresh } from './refreshCoordination'

declare module 'axios' {
  export interface AxiosRequestConfig<D = any> {
    __retry401?: boolean
    __skipAuth?: boolean
  }

  export interface InternalAxiosRequestConfig<D = any> {
    __retry401?: boolean
    __skipAuth?: boolean
  }
}

export const api = axios.create({
  baseURL: '/api',
  timeout: 15_000,
  withCredentials: true,
  headers: { Accept: 'application/json','X-Requested-With': 'XMLHttpRequest' }
})

let accessToken = ''
let isRefreshing = false
let pendingWaiters: Array<(t: string | null) => void> = []

type RefreshResult = {
  token: string | null
  data?: any
}
let refreshInFlight: Promise<RefreshResult> | null = null

const tokenRefreshedListeners: Array<(t: string) => void> = []
const authExpiredListeners: Array<() => void> = []

function notifyTokenRefreshed(tok: string) { for (const cb of [...tokenRefreshedListeners]) { try { cb(tok) } catch {} } }
function notifyAuthExpired() { for (const cb of [...authExpiredListeners]) { try { cb() } catch {} } }

export function addTokenRefreshedListener(cb: (t: string) => void) { tokenRefreshedListeners.push(cb) }
export function removeTokenRefreshedListener(cb: (t: string) => void) {
  const i = tokenRefreshedListeners.indexOf(cb)
  if (i >= 0) tokenRefreshedListeners.splice(i, 1)
}
export function addAuthExpiredListener(cb: () => void) { authExpiredListeners.push(cb) }
export function removeAuthExpiredListener(cb: () => void) {
  const i = authExpiredListeners.indexOf(cb)
  if (i >= 0) authExpiredListeners.splice(i, 1)
}
export async function refreshAccessToken(notifyOnFail = false): Promise<string | null> {
  const { token } = await startRefresh()
  if (!token && notifyOnFail) notifyAuthExpired()
  return token
}
export async function refreshAccessTokenFull(notifyOnFail = false): Promise<any | null> {
  const { token, data } = await startRefresh()
  if (!token && notifyOnFail) notifyAuthExpired()
  return token ? data : null
}
export function getAccessToken(): string { return accessToken }

export class AuthExpiredError extends Error { constructor() { super('auth_expired') } }
export function setAuthHeader(tok: string): void { accessToken = tok }

function setReqAuthHeader(cfg: InternalAxiosRequestConfig, tok: string): void {
  cfg.headers = AxiosHeaders.from(cfg.headers || {})
  cfg.headers.set('Authorization', `Bearer ${tok}`)
}

export const AUTH_SESSION_SID_HEADER = 'X-Auth-Session-Sid'

async function doRefreshWithTimeout(expectedSid: string): Promise<RefreshResult> {
  const ctrl = new AbortController()
  const tid = setTimeout(() => {
    try { ctrl.abort() } catch {}
  }, 10_000)
  try {
    const headers = AxiosHeaders.from({ Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' })
    headers.set(AUTH_SESSION_SID_HEADER, expectedSid)
    const { data } = await api.post('/auth/refresh', undefined, { signal: ctrl.signal, headers, __skipAuth: true })
    const tok = (data?.access_token as string | undefined) ?? null
    return { token: tok, data }
  } catch {
    return { token: null }
  } finally {
    clearTimeout(tid)
  }
}

function applyCoordinatedRefreshResult(result: RefreshResult): void {
  const tok = result.token || ''
  setAuthHeader(tok)
  if (!tok) return

  const sid = String(result.data?.sid || '')
  if (sid && typeof window !== 'undefined') {
    try { window.localStorage.setItem('auth:sid', sid) } catch {}
  }
  notifyTokenRefreshed(tok)
}

async function startRefresh(): Promise<RefreshResult> {
  if (!refreshInFlight) {
    refreshInFlight = (async (): Promise<RefreshResult> => {
      try {
        return await coordinateRefresh(doRefreshWithTimeout, applyCoordinatedRefreshResult)
      } finally {
        refreshInFlight = null
      }
    })()
  }
  return refreshInFlight
}

api.interceptors.request.use((cfg: InternalAxiosRequestConfig) => {
  if (accessToken && !cfg.__skipAuth) setReqAuthHeader(cfg, accessToken)
  return cfg
})

const AUTH_PATHS = ['/auth/refresh', '/auth/login', '/auth/register', '/auth/logout'] as const
const isAuthEndpoint = (url: string) => AUTH_PATHS.some(p => url.includes(p))
const isRefreshWorthyStatus = (st?: number) => st === 401 || st === 419 || st === 440

api.interceptors.response.use(
  (res: AxiosResponse) => res,
  async (error: AxiosError) => {
    const status = error.response?.status
    const cfg = (error.config || {}) as InternalAxiosRequestConfig
    const url = cfg.url || ''
    if (!isRefreshWorthyStatus(status) || cfg.__retry401 || isAuthEndpoint(url)) return Promise.reject(error)
    cfg.__retry401 = true

    if (!isRefreshing) {
      isRefreshing = true
      try {
        const { token: tok } = await startRefresh()
        pendingWaiters.forEach(cb => cb(tok))
        pendingWaiters = []
        if (!tok) {
          notifyAuthExpired()
          return Promise.reject(new AuthExpiredError())
        }
        setReqAuthHeader(cfg, tok)
        return api(cfg)
      } finally { isRefreshing = false }
    }

    if (pendingWaiters.length > 200) {
      pendingWaiters = []
      return Promise.reject(new Error('refresh_queue_overflow'))
    }
    return new Promise((resolve, reject) => {
      pendingWaiters.push((tok) => {
        if (!tok) {
          notifyAuthExpired()
          return reject(new AuthExpiredError())
        }
        setReqAuthHeader(cfg, tok)
        resolve(api(cfg))
      })
    })
  }
)
