import { defineStore } from 'pinia'
import { api } from '@/services/axios'
import { setAccessToken, clearAccessToken, getAccessToken } from '@/services/tokens'

export interface TgUser { id:number; username?:string; photo_url?:string; auth_date?:number; hash?:string }
export interface UserProfile { id:number; username?:string; photo_url?:string; role:string }

function parseJwtExp(jwtStr: string): number | null {
  try {
    const [, payload] = jwtStr.split('.')
    const json = JSON.parse(decodeURIComponent(atob(payload.replace(/-/g, '+').replace(/_/g, '/')).split('').map(c=>'%'+('00'+c.charCodeAt(0).toString(16)).slice(-2)).join('')))
    return typeof json.exp === 'number' ? json.exp : null
  } catch { return null }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: getAccessToken() || '',
    me: null as UserProfile | null,
    refreshTimer: 0 as any,
  }),
  getters: {
    isAuthed: s => !!s.accessToken,
    role: s => s.me?.role ?? 'user',
    avatarUrl: s => s.me?.photo_url ? `/api/v1/assets/avatars/${s.me.photo_url}` : null,
    displayName: s => s.me?.username || 'User',
  },
  actions: {
    _scheduleRefresh(){
      if (!this.accessToken) return
      const exp = parseJwtExp(this.accessToken); if (!exp) return
      const msToExp = exp*1000 - Date.now()
      const msToRefresh = Math.max(0, msToExp - 5*60*1000)
      clearTimeout(this.refreshTimer)
      this.refreshTimer = setTimeout(() => { this.refresh().catch(()=>this.logout()) }, msToRefresh)
    },
    _setAccess(t:string){ this.accessToken=t; setAccessToken(t); this._scheduleRefresh() },
    async refresh(){
      const { data } = await api.post('/v1/auth/refresh')
      if (!data?.access_token) throw new Error('refresh_failed')
      this._setAccess(data.access_token)
      // опционально подтянем профиль
      try { await this.fetchMe() } catch {}
    },
    async fetchMe(){
      if (!this.accessToken) return
      const { data } = await api.get<UserProfile>('/v1/users/me')
      this.me = data
    },
    async init(){
      if (this.accessToken) { this._scheduleRefresh(); try { await this.fetchMe() } catch {} }
    },
    async signInWithTelegram(user: TgUser){
      const { data } = await api.post('/v1/auth/telegram', user)
      this._setAccess(data.access_token)
      this.me = data.user
    },
    logout(){
      clearTimeout(this.refreshTimer); this.refreshTimer = 0
      this.accessToken = ''; this.me = null; clearAccessToken()
      api.post('/v1/auth/logout').catch(()=>{})
    },
  }
})
