import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

export type SiteUpdate = {
  id: number
  version: string
  description: string
  date: string
  read: boolean
}

export const useUpdatesStore = defineStore('updates', () => {
  const items = ref<SiteUpdate[]>([])
  const unread = ref(0)
  let inited = false
  let onUpdateEv: ((e: any) => void) | null = null

  async function fetchAll() {
    const { data } = await api.get('/updates')
    items.value = Array.isArray(data?.items) ? data.items : []
    unread.value = Number.isFinite(data?.unread_count) ? data.unread_count : 0
  }

  async function markAll() {
    try { await api.post('/updates/mark_read', { all: true }) } catch {}
    items.value.forEach(x => { x.read = true })
    unread.value = 0
  }

  function ensureWS() {
    if (inited) return
    if (onUpdateEv) window.removeEventListener('auth-site_update', onUpdateEv)
    onUpdateEv = () => { void fetchAll() }
    window.addEventListener('auth-site_update', onUpdateEv)
    inited = true
  }

  return {
    items,
    unread,

    fetchAll,
    markAll,
    ensureWS,
  }
})
