import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

export interface Room {
  id:number; title:string; user_limit:number; is_private:boolean;
  created_by_user_id:number; created_at:string; updated_at:string; occupancy:number
}

export const useRoomsStore = defineStore('rooms', () => {
  const rooms = ref<Room[]>([])
  const sse = ref<EventSource | null>(null)
  let backoffMs = 1000

  async function fetchRooms(){
    const { data } = await api.get<Room[]>('/v1/rooms')
    rooms.value = data
  }

  function upsert(item: Partial<Room> & {id:number}){
    const i = rooms.value.findIndex(r => r.id === item.id)
    if (i >= 0) rooms.value[i] = { ...rooms.value[i], ...item } as Room
    else rooms.value.push(item as Room)
  }
  function remove(id:number){ rooms.value = rooms.value.filter(r => r.id !== id) }

  function startSSE(){
    stopSSE()
    const es = new EventSource('/sse/rooms')
    sse.value = es
    es.onopen = () => { backoffMs = 1000 }
    es.onerror = () => {
      es.close()
      sse.value = null
      setTimeout(() => startSSE(), Math.min(backoffMs, 30000))
      backoffMs *= 2
    }
    es.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'room_created' || msg.type === 'occupancy' || msg.type === 'room_snapshot') upsert(msg.payload)
        else if (msg.type === 'room_deleted') remove(msg.payload.id)
      } catch {}
    }
  }
  function stopSSE(){ if (sse.value) { sse.value.close(); sse.value = null } }

  async function createRoom(title:string, user_limit:number, is_private=false){
    const { data } = await api.post<Room>('/v1/rooms', { title, user_limit, is_private })
    upsert(data); return data
  }

  return { rooms, sse, fetchRooms, startSSE, stopSSE, createRoom }
})
