import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

export interface Room {
  id: number;
  title: string;
  user_limit: number;
  is_private: boolean;
  creator: number;
  created_at: string;
  occupancy: number;
}

export const useRoomsStore = defineStore('rooms', () => {
  const rooms = ref<Room[]>([])
  const ws = ref<WebSocket | null>(null)
  let backoffMs = 1000
  let reconnectTimer: number | null = null
  let heartbeatTimer: number | null = null

  function setAll(list: Room[]) {
    rooms.value = list
  }

  function upsert(item: Partial<Room> & { id: number }) {
    const id = Number(item.id)
    const i = rooms.value.findIndex(r => r.id === id)
    const merged = { ...(i >= 0 ? rooms.value[i] : {}), ...item, id } as Room
    i >= 0 ? rooms.value.splice(i, 1, merged) : rooms.value.push(merged)
  }

  function remove(id: number) {
    rooms.value = rooms.value.filter(r => r.id !== id)
  }

  function url(): string {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${location.host}/ws/rooms`
  }

  function toNum(v: any, d = 0) { const n = Number(v); return Number.isFinite(n) ? n : d }

  function normRoom(x: any): Room {
    return {
      id: toNum(x.id),
      title: String(x.title || ''),
      user_limit: toNum(x.user_limit),
      is_private: (x.is_private === true || x.is_private === '1' || x.is_private === 1),
      creator: toNum(x.creator),
      created_at: String(x.created_at || ''),
      occupancy: toNum(x.occupancy),
    }
  }

  function startWS() {
    if (ws.value) return
    const sock = new WebSocket(url())
    ws.value = sock

    sock.onopen = () => {
      backoffMs = 1000
      if (heartbeatTimer) window.clearInterval(heartbeatTimer)
      heartbeatTimer = window.setInterval(() => {
        try {
          ws.value?.send('ping')
        } catch {}
      }, 25000) as unknown as number
    }

    sock.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data)
        if (m.type === 'rooms_snapshot') setAll((m.payload as any[]).map(normRoom))
        else if (m.type === 'room_deleted') remove(toNum(m.payload.id))
        else if (m.type === 'room_created') upsert(normRoom(m.payload))
        else if (m.type === 'occupancy') upsert({ id: toNum(m.payload.id), occupancy: toNum(m.payload.occupancy) } as any)
      } catch {}
    }

    sock.onclose = () => {
      ws.value = null
      if (heartbeatTimer) {
        window.clearInterval(heartbeatTimer)
        heartbeatTimer = null
      }
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer)
      }
      reconnectTimer = window.setTimeout(startWS, Math.min(backoffMs, 30000)) as unknown as number
      backoffMs *= 2
    }

    sock.onerror = () => {
      try {
        sock.close()
      } catch {}
    }
  }

  function stopWS() {
    if (reconnectTimer) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (heartbeatTimer) {
      window.clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
    if (ws.value) {
      try {
        ws.value.close()
      } catch {}
      ws.value = null
    }
  }

  async function createRoom(title: string, user_limit: number, is_private = false) {
    const { data } = await api.post<Room>('/rooms', { title, user_limit, is_private })
    upsert(data)
    return data
  }

  return {
    rooms,
    ws,

    startWS,
    stopWS,
    createRoom
  }
})
