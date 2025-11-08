import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

export type Note = {
  id: number
  title: string
  text?: string
  date: string
  read: boolean
}

export const useNotifStore = defineStore('notif', () => {
  const items = ref<Note[]>([])
  const unread = ref(0)

  let inited = false
  let onNotifyEv: ((e: any) => void) | null = null
  let onRoomAppEv: ((e: any) => void) | null = null

  const pending = new Set<number>()
  let flushing = false
  let tFlush: number | undefined
  let backoffMs = 0

  function scheduleFlush() {
    if (tFlush) return
    tFlush = window.setTimeout(() => {
      tFlush = undefined
      void flush()
    }, Math.max(300, backoffMs))
  }

  async function fetchAll() {
    const { data } = await api.get('/notifs')
    items.value = data.items
    unread.value = data.unread_count
  }

  function ensureWS() {
    if (inited) return
    if (onNotifyEv) window.removeEventListener('auth-notify', onNotifyEv)
    if (onRoomAppEv) window.removeEventListener('auth-room_invite', onRoomAppEv)
    onNotifyEv = (e: any) => {
      const p = e?.detail as Note
      if (!p) return
      if (p.kind !== 'app') {
        const { action, ...clean } = p as any
        items.value.unshift(clean)
        if (!p.read) unread.value++
      }
    }
    onRoomAppEv = (_e: any) => {}
    window.addEventListener('auth-notify', onNotifyEv)
    window.addEventListener('auth-room_invite', onRoomAppEv)
    inited = true
  }

  async function flush() {
    if (flushing || pending.size === 0) return
    flushing = true
    const ids = Array.from(pending)
    pending.clear()
    try {
      await api.post('/notifs/mark_read', { ids })
      backoffMs = 0
    } catch (e: any) {
      if (e?.response?.status === 429) {
        backoffMs = Math.min(2000, backoffMs ? backoffMs * 2 : 300)
        ids.forEach(id => pending.add(id))
        scheduleFlush()
      }
    } finally { flushing = false }
  }

  async function markReadVisible(ids: number[]) {
    if (!ids.length) return
    for (const id of ids) {
      const it = items.value.find(x => x.id === id)
      if (it && !it.read) {
        it.read = true
        unread.value = Math.max(0, unread.value - 1)
      }
      pending.add(id)
    }
    scheduleFlush()
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
