import { defineStore } from 'pinia'
import { api } from '@/services/axios'
import { setAccessToken, clearAccessToken, getAccessToken } from '@/services/tokens'

export interface TgUser { id:number; username?:string; first_name?:string; last_name?:string; photo_url?:string; auth_date?:number; hash?:string }
export interface Pending { session:string; suggested_username?:string; suggested_name?:string }
export interface UserProfile { id:number; username?:string; nickname?:string; name?:string; photo_url?:string; role:string }

function parseJwtExp(jwtStr: string): number | null {
  try {
    const [, payload] = jwtStr.split('.')
    const json = JSON.parse(decodeURIComponent(atob(payload.replace(/-/g, '+').replace(/_/g, '/')).split('').map(function(c){return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)}).join('')))
    return typeof json.exp === 'number' ? json.exp : null
  } catch { return null }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: getAccessToken() || '',
    me: null as UserProfile | null,
    tgUser: null as TgUser | null,
    pending: null as Pending | null,
    refreshTimer: 0 as number | any,
  }),
  getters: {
    isAuthed: s => !!s.accessToken,
    role: s => s.me?.role ?? 'user',
  },
  actions: {
    _scheduleRefresh(){
      if (!this.accessToken) return
      const exp = parseJwtExp(this.accessToken)
      if (!exp) return
      const msToExp = exp*1000 - Date.now()
      const msToRefresh = Math.max(0, msToExp - 5*60*1000) // за 5 минут
      clearTimeout(this.refreshTimer)
      this.refreshTimer = setTimeout(() => { this.refresh().catch(()=>this.logout()) }, msToRefresh)
    },
    _setAccess(t:string){
      this.accessToken = t
      setAccessToken(t)
      this._scheduleRefresh()
    },
    setToken(t:string){ this._setAccess(t) },
    async refresh(){
      const { data } = await api.post('/v1/auth/refresh')
      if (!data?.access_token) throw new Error('refresh_failed')
      this._setAccess(data.access_token)
    },
    logout(){
      clearTimeout(this.refreshTimer)
      this.refreshTimer = 0
      this.accessToken = ''
      this.tgUser = null
      this.me = null
      this.pending = null
      clearAccessToken()
      // best-effort серверный logout (почистит cookie)
      api.post('/v1/auth/logout').catch(()=>{})
    },
    async signInWithTelegram(u:TgUser){
      this.tgUser = u
      const res = await api.post('/v1/auth/telegram', u, { validateStatus:()=>true })
      if (res.status === 200){ this._setAccess(res.data.access_token); this.me = res.data.user; return }
      if (res.status === 202){ this.pending = res.data; return }
      throw new Error('auth_failed')
    },
    async checkNickname(nick:string){
      const { data } = await api.get('/v1/auth/check-nickname', { params: { nick } })
      return !!data?.available
    },
    async completeProfile(nickname:string, name:string){
      if (!this.pending) throw new Error('no_session')
      const { data } = await api.post('/v1/auth/complete', { session: this.pending.session, nickname, name })
      this._setAccess(data.access_token)
      this.me = data.user
      this.pending = null
    },
  }
})
