import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

type Note = {
  id: number
  text: string
  created_at: string
  read: boolean
}

export const useNotifStore = defineStore('notif', () => {
  const items = ref<Note[]>([])
  const unread = ref(0)
  let inited = false
  let onNotifyEv: ((e: any) => void) | null = null
  let onRoomAppEv: ((e: any) => void) | null = null

  async function fetchAll() {
    const { data } = await api.get('/notifs')
    items.value = data.items
    unread.value = data.unread_count
  }

  function ensureWS() {
    if (inited) return
    onNotifyEv = (e: any) => {
      const p = e?.detail as Note
      if (!p) return
      items.value.unshift({ ...p, read: false })
      unread.value++
      const m = /#(\d+)/.exec(p.text || '')
      if (m) {
        const roomId = Number(m[1])
        if (Number.isFinite(roomId)) window.dispatchEvent(new CustomEvent('room-approved', { detail: { roomId } }))
      }
    }
    onRoomAppEv = (_e: any) => {}
    window.addEventListener('auth-notify', onNotifyEv)
    window.addEventListener('auth-room_invite', onRoomAppEv)
    inited = true
  }

  async function markReadVisible(ids: number[]) {
    if (!ids.length) return
    try { await api.post('/notifs/mark_read', { ids }) } catch {}
    for (const id of ids) {
      const it = items.value.find(x => x.id === id)
      if (it && !it.read) {
        it.read = true
        unread.value = Math.max(0, unread.value - 1)
      }
    }
  }
  async function markAll() {
    const maxId = items.value.reduce((m, x) => Math.max(m, x.id), 0)
    try { await api.post('/notifs/mark_read', { all_before_id: maxId }) } catch {}
    items.value.forEach(x => x.read = true)
    unread.value = 0
  }

  return {
    items,
    unread,

    fetchAll,
    ensureWS,
    markReadVisible,
    markAll
  }
})
