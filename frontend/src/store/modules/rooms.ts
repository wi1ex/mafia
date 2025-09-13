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
  updated_at: string;
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
    const i = rooms.value.findIndex(r => r.id === item.id)
    i >= 0 ? rooms.value.splice(i, 1, { ...rooms.value[i], ...item } as Room) : rooms.value.push(item as Room)
  }

  function remove(id: number) {
    rooms.value = rooms.value.filter(r => r.id !== id)
  }

  function url(): string {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${location.host}/ws/rooms`
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
        if (m.type === 'rooms_snapshot') setAll(m.payload as Room[])
        else if (m.type === 'room_deleted') remove(m.payload.id)
        else if (m.type === 'room_created' || m.type === 'occupancy') upsert(m.payload as Room)
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
