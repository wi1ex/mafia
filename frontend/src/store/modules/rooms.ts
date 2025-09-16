import { defineStore } from 'pinia'
import { ref } from 'vue'
import { io, Socket } from 'socket.io-client'
import { api } from '@/services/axios'
import { useAuthStore } from '@/store/modules/auth'

export interface Room { id:number; title:string; user_limit:number; is_private:boolean; creator:number; created_at:string; occupancy:number }

export const useRoomsStore = defineStore('rooms', () => {
  const rooms = ref<Room[]>([])
  const sio = ref<Socket|null>(null)
  const { accessToken } = useAuthStore()

  function upsert(r: Room) {
    const i = rooms.value.findIndex(x => x.id === r.id)
    if (i>=0) rooms.value[i] = r
    else rooms.value.push(r)
  }

  async function load() {
    const { data } = await api.get<Room[]>('/rooms')
    rooms.value = data
  }

 function startWS() {
  if (sio.value?.connected) return
  sio.value = io('/ws', {
    path: '/ws/socket.io',
    transports: ['websocket'],
    auth: { token: accessToken },
  })
  sio.value.on('rooms_occupancy', (p: {id:number; occupancy:number}) => {
    const i = rooms.value.findIndex(r => r.id === p.id)
    if (i>=0) rooms.value[i] = { ...rooms.value[i], occupancy: p.occupancy }
  })
}

  function stopWS() { try { sio.value?.close() } catch {} sio.value = null }

  async function createRoom(title:string, user_limit:number, is_private:boolean) {
    const { data } = await api.post<Room>('/rooms', { title, user_limit, is_private })
    upsert(data)
    return data
  }

  return {
    rooms,
    load,

    startWS,
    stopWS,
    createRoom }
})
