import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { api } from '@/services/axios'
import { useAuthStore } from './auth'

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
  const auth = useAuthStore()
  const items = ref<Note[]>([])
  const unread = ref(0)
  const hasMore = ref(false)
  const loadingInitial = ref(false)
  const loadingMore = ref(false)
  const nextBeforeId = ref<number | null>(null)

  let inited = false
  let onNotifyEv: ((e: any) => void) | null = null
  let onConnectedEv: (() => void) | null = null
  let fetchGeneration = 0
  let headPageLoaded = false
  let mutationVersion = 0
  let ownerSession = auth.sessionId
  let ownerAbort = new AbortController()
  let refreshTimer: number | undefined
  const locallyRead = new Set<number>()
  let locallyReadThrough = 0

  const pending = new Set<number>()
  let pendingAllBeforeId = 0
  let flushing = false
  let tFlush: number | undefined
  let backoffMs = 0

  function resetOwner(session: string): void {
    ownerAbort.abort()
    ownerAbort = new AbortController()
    ownerSession = session
    fetchGeneration++
    headPageLoaded = false
    mutationVersion++
    if (tFlush) window.clearTimeout(tFlush)
    if (refreshTimer) window.clearTimeout(refreshTimer)
    tFlush = undefined
    refreshTimer = undefined
    pending.clear()
    pendingAllBeforeId = 0
    locallyRead.clear()
    locallyReadThrough = 0
    flushing = false
    backoffMs = 0
    items.value = []
    unread.value = 0
    hasMore.value = false
    nextBeforeId.value = null
    loadingInitial.value = false
    loadingMore.value = false
  }

  function scheduleRefresh(): void {
    if (refreshTimer || !ownerSession) return
    refreshTimer = window.setTimeout(() => {
      refreshTimer = undefined
      void fetchAll().catch(() => {})
    }, 300)
  }

  function mergePage(page: Note[]): void {
    const known = new Map(items.value.map(item => [item.id, item]))
    for (const item of page) {
      known.set(item.id, {
        ...item,
        read: Boolean(item.read || known.get(item.id)?.read || locallyRead.has(item.id) || item.id <= locallyReadThrough),
      })
    }
    items.value = [...known.values()].sort((left, right) => right.id - left.id)
  }

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

  function applyUnreadFromResponse(data: NotifsListResponse, version: number) {
    if (pending.size || pendingAllBeforeId || flushing) return
    if (version !== mutationVersion) {
      scheduleRefresh()
      return
    }
    if (typeof data?.unread_count !== 'number' || !Number.isFinite(data.unread_count)) return
    unread.value = Math.max(0, Math.trunc(data.unread_count))
  }

  async function fetchAll() {
    if (!ownerSession) return
    const gen = ++fetchGeneration
    const version = mutationVersion
    const signal = ownerAbort.signal
    loadingInitial.value = true
    loadingMore.value = false
    try {
      const { data } = await api.get<NotifsListResponse>('/notifs', { params: { limit: PAGE_SIZE }, signal })
      if (signal.aborted || gen !== fetchGeneration) return
      const rawPage = Array.isArray(data?.items) ? data.items : []
      const page = dedupeByIdDesc(rawPage)
      const existingIds = new Set(items.value.map(item => item.id))
      const preservePagination = headPageLoaded && page.some(item => existingIds.has(item.id))
      mergePage(page)
      applyUnreadFromResponse(data, version)
      if (!preservePagination) applyPageMeta(data, page, rawPage.length)
      headPageLoaded = true
    } finally {
      if (gen === fetchGeneration) loadingInitial.value = false
    }
  }

  async function loadMore() {
    let cursor = nextBeforeId.value
    if (!ownerSession || !cursor || !hasMore.value || loadingInitial.value || loadingMore.value) return
    const gen = fetchGeneration
    const version = mutationVersion
    const signal = ownerAbort.signal
    loadingMore.value = true
    try {
      while (cursor) {
        const { data } = await api.get<NotifsListResponse>('/notifs', { params: { limit: PAGE_SIZE, before_id: cursor }, signal })
        if (signal.aborted || gen !== fetchGeneration) return
        const rawPage = Array.isArray(data?.items) ? data.items : []
        const page = dedupeByIdDesc(rawPage)
        const existingIds = new Set(items.value.map(item => item.id))
        const hasNewItems = page.some(item => !existingIds.has(item.id))
        mergePage(page)
        applyUnreadFromResponse(data, version)
        applyPageMeta(data, page, rawPage.length)
        if (hasNewItems || !hasMore.value || nextBeforeId.value === cursor) break
        cursor = nextBeforeId.value
      }
    } finally {
      if (gen === fetchGeneration) loadingMore.value = false
    }
  }

  function ensureWS() {
    if (inited) return
    if (onNotifyEv) window.removeEventListener('auth-notify', onNotifyEv)
    if (onConnectedEv) window.removeEventListener('auth-connected', onConnectedEv)
    onNotifyEv = (e: any) => {
      const p = e?.detail as Note | undefined
      if (!p || !ownerSession) return

      const id = toPositiveIntOrNull(p.id)
      if (!id) return
      if (items.value.some(x => x.id === id)) return

      const note: Note = {
        id,
        title: typeof p.title === 'string' && p.title.trim() ? p.title : 'Уведомление',
        text: typeof p.text === 'string' && p.text.trim() ? p.text : undefined,
        date: p.date,
        read: Boolean(p.read || locallyRead.has(id) || id <= locallyReadThrough)
      }

      items.value.unshift(note)
      if (!note.read) unread.value++
      mutationVersion++
    }
    onConnectedEv = () => { void fetchAll().catch(() => {}) }
    window.addEventListener('auth-notify', onNotifyEv)
    window.addEventListener('auth-connected', onConnectedEv)
    inited = true
  }

  async function flush() {
    if (!ownerSession || flushing || (!pending.size && !pendingAllBeforeId)) return
    flushing = true
    const session = ownerSession
    const signal = ownerAbort.signal
    let allBeforeId = pendingAllBeforeId
    let ids = Array.from(pending).filter(id => id > allBeforeId)
    pendingAllBeforeId = 0
    pending.clear()
    try {
      if (allBeforeId) {
        await api.post('/notifs/mark_read', { all_before_id: allBeforeId }, { signal })
        allBeforeId = 0
      }
      if (ids.length) await api.post('/notifs/mark_read', { ids }, { signal })
      ids = []
      if (session !== ownerSession || signal.aborted) return
      backoffMs = 0
      mutationVersion++
      scheduleRefresh()
    } catch (e: any) {
      if (session !== ownerSession || signal.aborted) return
      const status = Number(e?.response?.status || 0)
      if (!status || status === 429 || status >= 500) {
        backoffMs = Math.min(10000, backoffMs ? backoffMs * 2 : 300)
        pendingAllBeforeId = Math.max(pendingAllBeforeId, allBeforeId)
        ids.forEach(id => pending.add(id))
      }
    } finally {
      if (session === ownerSession && !signal.aborted) {
        flushing = false
        if (pending.size || pendingAllBeforeId) scheduleFlush()
      }
    }
  }

  async function markReadVisible(ids: number[]) {
    if (!ownerSession || !ids.length) return
    const uniqueIds = Array.from(new Set(ids))
    for (const rawId of uniqueIds) {
      const id = toPositiveIntOrNull(rawId)
      if (!id) continue
      const it = items.value.find(x => x.id === id)
      if (it && !it.read) {
        it.read = true
        unread.value = Math.max(0, unread.value - 1)
      }
      locallyRead.add(id)
      pending.add(id)
    }
    mutationVersion++
    scheduleFlush()
  }

  async function markAll() {
    if (!ownerSession) return
    const maxId = items.value.reduce((m, x) => Math.max(m, x.id), 0)
    if (!maxId) return
    locallyReadThrough = Math.max(locallyReadThrough, maxId)
    pendingAllBeforeId = Math.max(pendingAllBeforeId, maxId)
    items.value.forEach(item => { if (item.id <= maxId) item.read = true })
    unread.value = 0
    mutationVersion++
    scheduleFlush()
  }

  watch(() => auth.sessionId, resetOwner, { flush: 'sync' })

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
