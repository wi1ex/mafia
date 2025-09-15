import { defineStore } from 'pinia'
import { api } from '@/services/axios'

export interface JoinReply {
  ws_url: string;
  token: string;
  room_id: number;
}

export const useRtcStore = defineStore('rtc', () => {
  async function requestJoin(roomId: number) {
    const { data } = await api.post<JoinReply>(`/rooms/${roomId}/join`, {})
    return data
  }

  async function requestLeave(roomId: number) {
    await api.post<void>(`/rooms/${roomId}/leave`, {})
  }

 function leaveKeepalive(roomId: number) {
  const base = (api.defaults?.baseURL ?? '').replace(/\/$/, '');
  const url = `${base}/rooms/${roomId}/leave`;

  if ('sendBeacon' in navigator) {
    const payload = new Blob([JSON.stringify({})], { type: 'application/json' });
    navigator.sendBeacon(url, payload);
    return;
  }
  fetch(url, {
    method: 'POST',
    body: '{}',
    headers: { 'content-type': 'application/json' },
    keepalive: true,
    credentials: 'same-origin',
  }).catch(() => {});
}

  return {
    requestJoin,
    requestLeave,
    leaveKeepalive,
  }
})
