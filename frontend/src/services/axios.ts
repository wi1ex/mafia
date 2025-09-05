import axios from 'axios'
import { getAccessToken, clearAccessToken } from './tokens'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? '/api',
  timeout: 15000,
  withCredentials: false,
})

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401) {
      clearAccessToken()
    }
    return Promise.reject(err)
  }
)
