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
const urlMap = new Map<string, string>()
const urlOrder: string[] = []
const URL_MAX = 300

function rememberURL(key: string, url: string) {
  const prev = urlMap.get(key)
  if (prev && prev !== url) { try { URL.revokeObjectURL(prev) } catch {} }
  urlMap.set(key, url)
  const idx = urlOrder.indexOf(key)
  if (idx !== -1) urlOrder.splice(idx, 1)
  urlOrder.push(key)
  while (urlOrder.length > URL_MAX) {
    const oldKey = urlOrder.shift()
    if (!oldKey) continue
    const u = urlMap.get(oldKey)
    if (u) {
      try { URL.revokeObjectURL(u) } catch {}
      urlMap.delete(oldKey)
    }
  }
}

export function clearObjectURL(key: string) {
  const u = urlMap.get(key)
  if (u) {
    try { URL.revokeObjectURL(u) } catch {}
    urlMap.delete(key)
  }
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
    tx.oncomplete = () => resolve(res!)
    tx.onerror = () => reject(tx.error)
    let res: T
    ;(async () => { try { res = await fn(st) } catch (e) { reject(e) } })()
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
  await withStore('readwrite', st => new Promise<void>((resolve, reject) => {
    const req = st.put(val)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  }))
}

export function parseAvatarVersion(name: string): number {
  const m =
    name.match(/^\d+-([0-9]{12,})-[0-9a-f]{6}\.[a-z0-9]+$/i) ||
    name.match(/^\d+-([0-9]{9,})\.[a-z0-9]+$/i)
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

export async function getImageURL(key: string, version: number, loader?: (key: string)=>Promise<Blob>): Promise<string> {
  const u = urlMap.get(key)
  if (u) return u

  try {
    const cur = await get(key)
    if (cur && cur.version === version) {
      const cached = URL.createObjectURL(cur.blob)
      rememberURL(key, cached)
      return cached
    }
  } catch {}

  const load = loader || fetchBlobByPresign
  const blob = await load(key)
  try { await put({ key, version, blob, ctype: blob.type }) } catch {}
  const url = URL.createObjectURL(blob)
  rememberURL(key, url)
  return url
}
