import { defineStore } from 'pinia'
import { api } from '@/services/axios'

export interface Room { id:number; title:string; user_limit:number; is_private:boolean; created_by_user_id:number; created_at:string; updated_at:string; occupancy:number }

export const useRoomsStore = defineStore('rooms', {
  state: () => ({
    rooms: [] as Room[],
    sse: null as EventSource | null,
  }),
  actions: {
    async fetchRooms(){
      const { data } = await api.get<Room[]>('/v1/rooms')
      this.rooms = data
    },
    startSSE(){
      this.stopSSE()
      const es = new EventSource('/sse/rooms')
      es.addEventListener('snapshot', (e:any) => { this.rooms = JSON.parse(e.data) })
      es.addEventListener('update', (e:any) => {
        const msg = JSON.parse(e.data) as {type:string; payload:any}
        if (msg.type === 'room_created') this.upsert({ ...msg.payload })
        if (msg.type === 'room_deleted') this.remove(msg.payload.id)
        if (msg.type === 'occupancy')   this.upsert({ id: msg.payload.id, occupancy: msg.payload.occupancy } as Partial<Room> as Room)
      })
      this.sse = es
    },
    stopSSE(){
      this.sse?.close(); this.sse = null
    },
    upsert(item: Partial<Room> & { id:number }){
      const i = this.rooms.findIndex(r => r.id === item.id)
      if (i >= 0) this.rooms[i] = { ...this.rooms[i], ...item } as Room
      else this.rooms.push(item as Room)
    },
    remove(id:number){ this.rooms = this.rooms.filter(r => r.id !== id) },
    async createRoom(title:string, user_limit:number, is_private=false){
      const { data } = await api.post<Room>('/v1/rooms', { title, user_limit, is_private })
      this.upsert(data)
      return data
    },
  }
})
