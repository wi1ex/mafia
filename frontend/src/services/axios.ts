import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios'

export const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
  withCredentials: true,
  headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
})

let accessTok = ''
let isRefreshing = false
let pending: Array<(t: string | null) => void> = []

export function setAuthHeader(tok: string) {
  accessTok = tok
  if (tok) api.defaults.headers.common.Authorization = `Bearer ${tok}`
  else delete api.defaults.headers.common.Authorization
}

api.interceptors.request.use((cfg: InternalAxiosRequestConfig) => {
  if (accessTok) cfg.headers.Authorization = `Bearer ${accessTok}`
  return cfg
})

async function doRefresh(): Promise<string | null> {
  try {
    const { data } = await api.post('/auth/refresh')
    const tok = data?.access_token as string | undefined
    if (!tok) throw new Error('no_access')
    setAuthHeader(tok)
    return tok
  } catch {
    setAuthHeader('')
    return null
  }
}

api.interceptors.response.use(
  (res: AxiosResponse) => res,
  async (error: AxiosError) => {
    const st = error.response?.status
    const cfg: any = error.config || {}
    const url: string = cfg.url || ''
    const isAuthCall = url.includes('/auth/refresh') || url.includes('/auth/telegram')
    if (st === 401 && !cfg.__retry401 && !isAuthCall) {
      cfg.__retry401 = true
      if (!isRefreshing) {
        isRefreshing = true
        try {
          const tok = await doRefresh()
          pending.forEach(cb => cb(tok))
          pending = []
          if (!tok) return Promise.reject(error)
          cfg.headers = cfg.headers || {}
          cfg.headers.Authorization = `Bearer ${tok}`
          return api(cfg)
        } finally {
          isRefreshing = false
        }
      }
      return new Promise((resolve, reject) => {
        pending.push((tok) => {
          if (!tok) return reject(error)
          cfg.headers = cfg.headers || {}
          cfg.headers.Authorization = `Bearer ${tok}`
          resolve(api(cfg))
        })
      })
    }
    return Promise.reject(error)
  }
)
