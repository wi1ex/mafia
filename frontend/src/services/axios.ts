import axios from 'axios'

const TOKEN_KEY = 'access_token'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? '/api',
  timeout: 15000,
  withCredentials: true,
})

api.interceptors.request.use((config) => {
  const t = localStorage.getItem(TOKEN_KEY)
  if (t) config.headers.Authorization = `Bearer ${t}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
    }
    return Promise.reject(err)
  }
)

export function setGlobalToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}
export function clearGlobalToken() {
  localStorage.removeItem(TOKEN_KEY)
}
export function getGlobalToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}
