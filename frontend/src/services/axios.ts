import axios, { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios'

const TOKEN_KEY = 'access_token'
let isRefreshing = false
let pending: Array<(t: string | null) => void> = []

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 15000,
  withCredentials: true,
})

api.interceptors.request.use((cfg: InternalAxiosRequestConfig) => {
  const t = localStorage.getItem(TOKEN_KEY)
  if (t) (cfg.headers ||= {}).Authorization = `Bearer ${t}`
  return cfg
})

function setTokenLocal(t: string | null) {
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY)
}

async function doRefresh(): Promise<string | null> {
  try {
    const { data } = await api.post('/auth/refresh')
    const tok = data?.access_token as string | undefined
    if (!tok) throw new Error('no_access')
    setTokenLocal(tok)
    return tok
  } catch {
    setTokenLocal(null)
    return null
  }
}

api.interceptors.response.use(
  (res: AxiosResponse) => res,
  async (error: AxiosError) => {
    const st = error.response?.status, cfg = (error as any).config ?? {}, url: string = cfg.url || ''
    if (st === 401 && !url.includes('/auth/refresh') && !url.includes('/auth/telegram') && !cfg.__retry401) {
      cfg.__retry401 = true
      if (!isRefreshing) {
        isRefreshing = true
        const tok = await doRefresh()
        isRefreshing = false
        pending.forEach(cb => cb(tok))
        pending = []
        if (!tok) return Promise.reject(error)
        (cfg.headers ||= {}).Authorization = `Bearer ${tok}`
        return api(cfg)
      }
      return new Promise((resolve, reject) => {
        pending.push((tok) => {
          if (!tok) return reject(error)
          (cfg.headers ||= {}).Authorization = `Bearer ${tok}`
          resolve(api(cfg))
        })
      })
    }
    return Promise.reject(error)
  }
)

export function setGlobalToken(t: string) {
  setTokenLocal(t)
}

export function clearGlobalToken() {
  setTokenLocal(null)
}

export function getGlobalToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}
