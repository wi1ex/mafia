import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

const PAGE_SIZE = 50

export type Note = {
  id: number
  title: string
  text?: string
  date: string
  read: boolean
}

type NotifsListResponse = {
  items?: Note[]
  unread_count?: number
  has_more?: boolean
  next_before_id?: number | null
}

type WsNotePayload = Note & {
  kind?: string
  action?: unknown
}

function toPositiveIntOrNull(v: unknown): number | null {
  const parsed = typeof v === 'string' ? Number(v) : v
  if (typeof parsed !== 'number' || !Number.isFinite(parsed)) return null
  const n = Math.trunc(parsed)
  return n > 0 ? n : null
}

function dedupeByIdDesc(list: Note[]): Note[] {
  const seen = new Set<number>()
  const out: Note[] = []
  for (const item of list) {
    if (!Number.isFinite(item?.id)) continue
    if (seen.has(item.id)) continue
    seen.add(item.id)
    out.push(item)
  }
  return out
}

function getTailCursor(list: Note[]): number | null {
  if (!list.length) return null
  return toPositiveIntOrNull(list[list.length - 1]?.id)
}

export const useNotifStore = defineStore('notif', () => {
  const items = ref<Note[]>([])
  const unread = ref(0)
  const hasMore = ref(false)
  const loadingInitial = ref(false)
  const loadingMore = ref(false)
  const nextBeforeId = ref<number | null>(null)

  let inited = false
  let onNotifyEv: ((e: any) => void) | null = null
  let onRoomAppEv: ((e: any) => void) | null = null
  let fetchGeneration = 0

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

  function applyPageMeta(data: NotifsListResponse, page: Note[], rawCount: number = page.length) {
    const hasMoreFromServer = typeof data?.has_more === 'boolean' ? data.has_more : null
    const nextCursorFromServer = toPositiveIntOrNull(data?.next_before_id)

    const resolvedHasMore = hasMoreFromServer ?? (rawCount >= PAGE_SIZE)
    hasMore.value = Boolean(resolvedHasMore)
    nextBeforeId.value = hasMore.value ? (nextCursorFromServer ?? getTailCursor(page)) : null
  }

  function applyUnreadFromResponse(data: NotifsListResponse) {
    if (typeof data?.unread_count !== 'number' || !Number.isFinite(data.unread_count)) return
    unread.value = Math.max(0, Math.trunc(data.unread_count))
  }

  async function fetchAll() {
    const gen = ++fetchGeneration
    loadingInitial.value = true
    loadingMore.value = false
    try {
      const { data } = await api.get<NotifsListResponse>('/notifs', { params: { limit: PAGE_SIZE } })
      if (gen !== fetchGeneration) return
      const rawPage = Array.isArray(data?.items) ? data.items : []
      const page = dedupeByIdDesc(rawPage)
      items.value = page
      applyUnreadFromResponse(data)
      applyPageMeta(data, page, rawPage.length)
    } finally {
      if (gen === fetchGeneration) loadingInitial.value = false
    }
  }

  async function loadMore() {
    const cursor = nextBeforeId.value
    if (!cursor || !hasMore.value || loadingInitial.value || loadingMore.value) return
    const gen = fetchGeneration
    loadingMore.value = true
    try {
      const { data } = await api.get<NotifsListResponse>('/notifs', { params: { limit: PAGE_SIZE, before_id: cursor } })
      if (gen !== fetchGeneration) return
      const rawPage = Array.isArray(data?.items) ? data.items : []
      const page = dedupeByIdDesc(rawPage)
      const known = new Set(items.value.map(x => x.id))
      const append: Note[] = []
      for (const it of page) {
        if (known.has(it.id)) continue
        known.add(it.id)
        append.push(it)
      }
      if (append.length) items.value = [...items.value, ...append]
      applyUnreadFromResponse(data)
      applyPageMeta(data, page, rawPage.length)
    } finally {
      if (gen === fetchGeneration) loadingMore.value = false
    }
  }

  function ensureWS() {
    if (inited) return
    if (onNotifyEv) window.removeEventListener('auth-notify', onNotifyEv)
    if (onRoomAppEv) window.removeEventListener('auth-room_invite', onRoomAppEv)
    onNotifyEv = (e: any) => {
      const p = e?.detail as WsNotePayload | undefined
      if (!p) return
      if (p.kind === 'app') return

      const { action, ...clean } = p
      const id = toPositiveIntOrNull(clean?.id)
      if (!id) return
      if (items.value.some(x => x.id === id)) return

      const note: Note = {
        id,
        title: clean.title.trim() ? clean.title : 'Уведомление',
        text: typeof clean.text === 'string' && clean.text.trim() ? clean.text : undefined,
        date: clean.date,
        read: Boolean(clean.read)
      }

      items.value.unshift(note)
      if (!note.read) unread.value++
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
    const uniqueIds = Array.from(new Set(ids))
    for (const rawId of uniqueIds) {
      const id = toPositiveIntOrNull(rawId)
      if (!id) continue
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
    hasMore,
    loadingInitial,
    loadingMore,

    fetchAll,
    loadMore,
    ensureWS,
    markReadVisible,
    markAll
  }
})
