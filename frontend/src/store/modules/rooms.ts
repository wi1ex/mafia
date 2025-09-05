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

  async function fetchRooms(){
    const { data } = await api.get<Room[]>('/v1/rooms')
    rooms.value = data
  }

  function startSSE(){
    stopSSE()
    const es = new EventSource('/sse/rooms')
    es.addEventListener('snapshot', (e: any) => { rooms.value = JSON.parse(e.data) })
    es.addEventListener('update', (e: any) => {
      const msg = JSON.parse(e.data) as {type:string; payload:any}
      if (msg.type === 'room_created') upsert({ ...msg.payload })
      if (msg.type === 'room_deleted') remove(msg.payload.id)
      if (msg.type === 'occupancy')     upsert({ id: msg.payload.id, occupancy: msg.payload.occupancy } as Partial<Room> as Room)
    })
    sse.value = es
  }

  function stopSSE(){ sse.value?.close(); sse.value = null }

  function upsert(item: Partial<Room> & { id:number }){
    const i = rooms.value.findIndex(r => r.id === item.id)
    if (i >= 0) rooms.value[i] = { ...rooms.value[i], ...item } as Room
    else rooms.value.push(item as Room)
  }

  function remove(id:number){ rooms.value = rooms.value.filter(r => r.id !== id) }

  async function createRoom(title:string, user_limit:number, is_private=false){
    const { data } = await api.post<Room>('/v1/rooms', { title, user_limit, is_private })
    upsert(data)
    return data
  }

  return { rooms, sse, fetchRooms, startSSE, stopSSE, upsert, remove, createRoom }
})
