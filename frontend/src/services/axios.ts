import axios,{
  AxiosError, AxiosHeaders, AxiosResponse, InternalAxiosRequestConfig,
} from 'axios'

declare module 'axios' {
  export interface InternalAxiosRequestConfig<D = unknown> {
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

const PENDING_LIMIT = 200
const REFRESH_TIMEOUT_MS = 10_000

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
  const tok = await doRefreshWithTimeout()
  if (!tok && notifyOnFail) {
    notifyAuthExpired()
  }
  return tok
}
export function getAccessToken(): string { return accessToken }

export class AuthExpiredError extends Error { constructor() { super('auth_expired') } }
export function setAuthHeader(tok: string): void { accessToken = tok }

function setReqAuthHeader(cfg: InternalAxiosRequestConfig, tok: string): void {
  cfg.headers = AxiosHeaders.from(cfg.headers || {})
  cfg.headers.set('Authorization', `Bearer ${tok}`)
}

async function doRefreshWithTimeout(): Promise<string | null> {
  const ctrl = new AbortController()
  let tid: ReturnType<typeof setTimeout>
  const refreshPromise = (async () => {
    try {
      const headers = AxiosHeaders.from({ Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' })
      const { data } = await api.post('/auth/refresh', undefined, { signal: ctrl.signal, headers, __skipAuth: true })
      const tok = (data?.access_token as string | undefined) ?? null
      setAuthHeader(tok ?? '')
      if (tok) notifyTokenRefreshed(tok)
      return tok
    } catch {
      setAuthHeader('')
      return null
    } finally { clearTimeout(tid) }
  })()
  const timeoutPromise = new Promise<string | null>((resolve) => {
    tid = setTimeout(() => {
      try { ctrl.abort() } catch {}
      resolve(null)
    }, REFRESH_TIMEOUT_MS)
  })
  return Promise.race([refreshPromise, timeoutPromise])
}

api.interceptors.request.use((cfg: InternalAxiosRequestConfig) => {
  if (accessToken && !cfg.__skipAuth) setReqAuthHeader(cfg, accessToken)
  return cfg
})

const AUTH_PATHS = ['/auth/refresh', '/auth/telegram', '/auth/logout'] as const
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
        const tok = await doRefreshWithTimeout()
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

    if (pendingWaiters.length > PENDING_LIMIT) {
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
