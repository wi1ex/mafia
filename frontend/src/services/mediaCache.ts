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
const verMap = new Map<string, number>()
const inFlight = new Map<string, Promise<string>>()
const urlOrder: string[] = []
const URL_MAX = 300

function rememberURL(key: string, url: string, ver: number) {
  urlMap.set(key, url)
  verMap.set(key, ver)
  const i = urlOrder.indexOf(key); if (i !== -1) urlOrder.splice(i, 1)
  urlOrder.push(key)
  while (urlOrder.length > URL_MAX) {
    const oldKey = urlOrder.shift()!
    const u = urlMap.get(oldKey)
    if (u) { try { URL.revokeObjectURL(u) } catch {} }
    urlMap.delete(oldKey)
    verMap.delete(oldKey)
  }
}

export function clearObjectURL(key: string) {
  urlMap.delete(key)
  verMap.delete(key)
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
  const { data } = await api.get('/media/presign', { params: { key } })
  return String(data?.url || '')
}

export async function fetchBlobByPresign(key: string): Promise<Blob> {
  const url = await presign(key)
  const resp = await fetch(url, { credentials: 'omit', cache: 'no-store' })
  if (!resp.ok) throw new Error('fetch_failed')
  return await resp.blob()
}

export async function getImageURL(key: string, version: number, loader?: (k:string)=>Promise<Blob>): Promise<string> {
  const cached = urlMap.get(key)
  const cachedVer = verMap.get(key)
  if (cached && cachedVer === version) return cached
  const infl = inFlight.get(key)
  if (infl) return infl
  const p = (async () => {
    try {
      const cur = await get(key)
      if (cur && cur.version === version) {
        const u = URL.createObjectURL(cur.blob)
        rememberURL(key, u, version)
        return u
      }
    } catch {}
    const load = loader || fetchBlobByPresign
    const blob = await load(key)
    try { await put({ key, version, blob, ctype: blob.type }) } catch {}
    const u = URL.createObjectURL(blob)
    rememberURL(key, u, version)
    return u
  })()
  inFlight.set(key, p)
  try { return await p } finally { inFlight.delete(key) }
}
