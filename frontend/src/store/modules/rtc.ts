import { defineStore } from 'pinia'
import { api } from '@/services/axios'

export interface JoinReply {
  ws_url: string;
  token: string;
  room_id: number;
}

export const useRtcStore = defineStore('rtc', () => {
  async function requestJoin(roomId:number){
    const { data } = await api.post<JoinReply>(`/v1/rooms/${roomId}/join`, {})
    return data
  }
  async function requestLeave(roomId:number){
    await api.post(`/v1/rooms/${roomId}/leave`, {})
  }
  return { requestJoin, requestLeave }
})
