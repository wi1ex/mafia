import { api } from '@/services/axios'

type Stored = {
  key: string
  version: number
  blob: Blob
  ctype?: string
}

const DB_NAME = 'media-cache'
const DB_VER = 1
const STORE = 'objects'

type UrlRec = {
  url: string
  refs: number
}
const urlMap = new Map<string, UrlRec>()
const urlOrder: string[] = []
const URL_MAX = 300

function _evictLRU(limit = URL_MAX) {
  let guard = urlOrder.length + 1
  while (urlOrder.length > limit && guard-- > 0) {
    const k = urlOrder.shift()
    if (!k) continue
    const rec = urlMap.get(k)
    if (!rec) continue
    if (rec.refs <= 0) {
      try { URL.revokeObjectURL(rec.url) } catch {}
      urlMap.delete(k)
    } else {
      urlOrder.push(k)
    }
  }
}

function rememberURL(key: string, url: string) {
  const prev = urlMap.get(key)
  urlMap.set(key, { url, refs: prev?.refs ?? 0 })
  const idx = urlOrder.indexOf(key)
  if (idx !== -1) urlOrder.splice(idx, 1)
  urlOrder.push(key)
  _evictLRU()
}

export function retainImageURL(key: string) {
  const rec = urlMap.get(key)
  if (rec) rec.refs++
}

export function releaseImageURL(key: string) {
  const rec = urlMap.get(key)
  if (!rec) return
  rec.refs = Math.max(0, rec.refs - 1)
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VER)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        const st = db.createObjectStore(STORE, { keyPath: 'key' })
        st.createIndex('version', 'version', { unique: false })
      }
    }
    req.onerror = () => reject(req.error)
    req.onsuccess = () => resolve(req.result)
  })
}

async function withStore<T>(mode: IDBTransactionMode, fn: (st: IDBObjectStore) => Promise<T>): Promise<T> {
  const db = await openDB()
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(STORE, mode)
    const st = tx.objectStore(STORE)
    let result!: T
    tx.oncomplete = () => resolve(result)
    tx.onabort = () => reject(tx.error || new Error('idb_tx_aborted'))
    tx.onerror = () => reject(tx.error || new Error('idb_tx_error'))
    ;(async () => {
      try { result = await fn(st) } catch (e) {
        try { tx.abort() } catch {}
        reject(e)
      }
    })()
  })
}

async function get(key: string): Promise<Stored | undefined> {
  return withStore('readonly', st => new Promise((resolve, reject) => {
    const req = st.get(key)
    req.onsuccess = () => resolve(req.result as Stored | undefined)
    req.onerror = () => reject(req.error)
  }))
}

async function put(val: Stored): Promise<void> {
  try {
    await withStore('readwrite', st => new Promise<void>((resolve, reject) => {
      const req = st.put(val)
      req.onsuccess = () => resolve()
      req.onerror = () => reject(req.error)
    }))
  } catch (e:any) {
    if (e?.name === 'QuotaExceededError') { return }
    throw e
  }
}

export function parseAvatarVersion(name: string): number {
  const m = name.match(/^\d+-([0-9]{9,})\.[a-z0-9]+$/i)
  return m ? Number(m[1]) : 0
}

export async function presign(key: string): Promise<string> {
  const { data } = await api.get('/media/presign', { params: { key }, __skipAuth: true })
  return String(data?.url || '')
}

export async function fetchBlobByPresign(key: string): Promise<Blob> {
  const url = await presign(key)
  const resp = await fetch(url, { credentials: 'omit', cache: 'no-store' })
  if (!resp.ok) throw new Error('fetch_failed')
  return await resp.blob()
}

export async function getImageURL(key: string, version: number, loader?: (key: string) => Promise<Blob>): Promise<string> {
  const rec = urlMap.get(key)
  if (rec) {
    rec.refs++
    return rec.url
  }
  try {
    const cur = await get(key)
    if (cur && cur.version === version) {
      const cached = URL.createObjectURL(cur.blob)
      rememberURL(key, cached)
      retainImageURL(key)
      return cached
    }
  } catch {}
  const load = loader || fetchBlobByPresign
  const blob = await load(key)
  try { await put({ key, version, blob, ctype: blob.type }) } catch {}
  const url = URL.createObjectURL(blob)
  rememberURL(key, url)
  retainImageURL(key)
  return url
}
