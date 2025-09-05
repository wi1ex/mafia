import { defineStore } from 'pinia'
import { api } from '@/services/axios'
import { setAccessToken, clearAccessToken, getAccessToken } from '@/services/tokens'

export interface TgUser { id:number; username?:string; first_name?:string; last_name?:string; photo_url?:string; auth_date?:number; hash?:string }
export interface Pending { session:string; suggested_username?:string; suggested_name?:string }
export interface UserProfile { id:number; username?:string; nickname?:string; name?:string; photo_url?:string; role:string }

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: getAccessToken() || '',
    tgUser: null as TgUser | null,
    me: null as UserProfile | null,
    pending: null as Pending | null,
  }),
  getters: {
    isAuthed: s => !!s.accessToken,
    role: s => s.me?.role ?? 'user',
  },
  actions: {
    setToken(t:string){ this.accessToken=t; setAccessToken(t) },
    logout(){ this.accessToken=''; this.tgUser=null; this.me=null; this.pending=null; clearAccessToken() },
    async signInWithTelegram(u:TgUser){
      this.tgUser = u
      const res = await api.post('/v1/auth/telegram', u, { validateStatus:()=>true })
      if (res.status === 200){ this.setToken(res.data.access_token); this.me = res.data.user; return }
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
      this.setToken(data.access_token)
      this.me = data.user
      this.pending = null
    },
  }
})
