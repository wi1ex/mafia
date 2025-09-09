import axios, { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios'

const TOKEN_KEY = 'access_token'
let isRefreshing = false
let pending: Array<(token: string | null) => void> = []

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? '/api',
  timeout: 15000,
  withCredentials: true, // важен для refresh-cookie
})

// подставляем access
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const t = localStorage.getItem(TOKEN_KEY)
  if (t) config.headers.Authorization = `Bearer ${t}`
  return config
})

function setTokenLocal(t: string | null) {
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}

async function doRefresh(): Promise<string | null> {
  try {
    const { data } = await api.post('/v1/auth/refresh')
    const newAccess = data?.access_token as string | undefined
    if (!newAccess) throw new Error('no_access')
    setTokenLocal(newAccess)
    return newAccess
  } catch {
    setTokenLocal(null)
    return null
  }
}

api.interceptors.response.use(
  (res: AxiosResponse) => res,
  async (error: AxiosError) => {
    const respStatus = error.response?.status
    const cfg = (error as any).config ?? {}
    const url: string = cfg.url || ''
    const isAuthEndpoint = url.includes('/v1/auth/refresh') || url.includes('/v1/auth/telegram')
    const alreadyRetried = cfg.__retry401 === true

    if (respStatus === 401 && !isAuthEndpoint && !alreadyRetried) {
      cfg.__retry401 = true

      if (!isRefreshing) {
        isRefreshing = true
        const newTok = await doRefresh()
        isRefreshing = false
        pending.forEach(cb => cb(newTok))
        pending = []
        if (!newTok) return Promise.reject(error)
        cfg.headers = cfg.headers || {}
        cfg.headers.Authorization = `Bearer ${newTok}`
        return api(cfg)
      } else {
        // ждём завершения текущего refresh
        return new Promise((resolve, reject) => {
          pending.push((newTok) => {
            if (!newTok) return reject(error)
            cfg.headers = cfg.headers || {}
            cfg.headers.Authorization = `Bearer ${newTok}`
            resolve(api(cfg))
          })
        })
      }
    }
    return Promise.reject(error)
  }
)

export function setGlobalToken(token: string) { setTokenLocal(token) }
export function clearGlobalToken() { setTokenLocal(null) }
export function getGlobalToken(): string { return localStorage.getItem(TOKEN_KEY) || '' }
