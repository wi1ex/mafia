import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/services/axios'
import { setAccessToken, clearAccessToken, getAccessToken } from '@/services/tokens'

export interface TgUser { id:number; username?:string; photo_url?:string; auth_date?:number; hash?:string }
export interface UserProfile { id:number; username?:string; photo_url?:string; role:string }

function parseJwtExp(jwtStr: string): number | null {
  try {
    const [, payload] = jwtStr.split('.')
    const json = JSON.parse(
      decodeURIComponent(
        atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
          .split('')
          .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      )
    )
    return typeof json.exp === 'number' ? json.exp : null
  } catch { return null }
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string>(getAccessToken() || '')
  const me = ref<UserProfile | null>(null)
  let refreshTimer: number | null = null

  const isAuthed = computed(() => !!accessToken.value)
  const role = computed(() => me.value?.role ?? 'user')
  const avatarUrl = computed(() => me.value?.photo_url ? `/api/v1/assets/avatars/${me.value.photo_url}` : null)
  const displayName = computed(() => me.value?.username || 'User')

  function scheduleRefresh(){
    if (!accessToken.value) return
    const exp = parseJwtExp(accessToken.value); if (!exp) return
    const msToExp = exp*1000 - Date.now()
    const msToRefresh = Math.max(0, msToExp - 5*60*1000)
    if (refreshTimer) clearTimeout(refreshTimer)
    refreshTimer = window.setTimeout(() => { refresh().catch(() => logout()) }, msToRefresh)
  }

  function setAccess(t: string){
    accessToken.value = t
    setAccessToken(t)
    scheduleRefresh()
  }

  async function refresh(){
    const { data } = await api.post('/v1/auth/refresh')
    if (!data?.access_token) throw new Error('refresh_failed')
    setAccess(data.access_token)
    try { await fetchMe() } catch {}
  }

  async function fetchMe(){
    if (!accessToken.value) return
    const { data } = await api.get<UserProfile>('/v1/users/me')
    me.value = data
  }

  async function init(){
    if (accessToken.value) { scheduleRefresh(); try { await fetchMe() } catch {} }
  }

  async function signInWithTelegram(user: TgUser){
    const { data } = await api.post('/v1/auth/telegram', user)
    setAccess(data.access_token)
    me.value = data.user
  }

  function logout(){
    if (refreshTimer) { clearTimeout(refreshTimer); refreshTimer = null }
    api.post('/v1/auth/logout').catch(()=>{})
    accessToken.value = ''
    me.value = null
    clearAccessToken()
  }

  return {
    // state
    accessToken, me,
    // getters
    isAuthed, role, avatarUrl, displayName,
    // actions
    init, refresh, fetchMe, signInWithTelegram, logout,
    // compat
    setToken: setAccess,
  }
})
