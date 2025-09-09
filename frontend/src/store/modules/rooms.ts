import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

export interface Room {
  id: number;
  title: string;
  user_limit: number;
  is_private: boolean;
  created_by_user_id: number;
  created_at: string;
  updated_at: string;
  occupancy: number ;
}

export const useRoomsStore = defineStore('rooms', () => {
  const rooms = ref<Room[]>([])
  const sse = ref<EventSource | null>(null)
  let backoffMs = 1000

  async function fetchRooms() {
    const { data } = await api.get<Room[]>('/rooms')
    rooms.value = data
  }

  function upsert(item: Partial<Room> & {id: number}) {
    const i = rooms.value.findIndex(r=>r.id===item.id)
    i >= 0 ? rooms.value.splice(i,1,{...rooms.value[i],...item} as Room) : rooms.value.push(item as Room)
  }

  function remove(id: number) {
    rooms.value = rooms.value.filter(r => r.id !== id)
  }

  function startSSE(){
    stopSSE()
    const es = new EventSource('/sse/rooms')
    sse.value = es

    es.onopen = () => {
      backoffMs = 1000
    }

    es.onerror = () => {
      es.close()
      sse.value=null
      setTimeout(()=>startSSE(), Math.min(backoffMs, 30000))
      backoffMs *= 2
    }

    es.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data)
        if (m.type === 'room_created' || m.type === 'occupancy' || m.type === 'room_snapshot') {
          upsert(m.payload)
        }
        else if (m.type==='room_deleted') {
          remove(m.payload.id)
        }
      } catch {}
    }
  }

  function stopSSE() {
    if (sse.value) {
      sse.value.close()
      sse.value=null
    }
  }

  async function createRoom(title: string, user_limit: number, is_private=false) {
    const { data } = await api.post<Room>('/rooms', { title, user_limit, is_private })
    upsert(data)
    return data
  }

  return {
    rooms,
    sse,

    fetchRooms,
    startSSE,
    stopSSE,
    createRoom
  }
})
