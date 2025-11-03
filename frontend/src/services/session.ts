type ForeignActiveCb = (on: boolean) => void
type InconsistencyCb = () => void

const TTL_VISIBLE_MS = 3000
const TTL_HIDDEN_MS  = 6000
const BEAT_VISIBLE   = 1200
const BEAT_HIDDEN    = 2500

const LS_SID_KEY    = 'auth:sid'
const LS_LOCK_KEY   = 'auth:lock'
const LS_DEVICE_KEY = 'auth:deviceId'
const SS_TAB_KEY    = 'auth:tabId'
const BC_NAME       = 'auth_lock'

type Lock = {
  owner: {
    deviceId: string
    tabId: string
  }
  hb: number
  sid?: string
}

let inited = false
let bc: BroadcastChannel | null = null
let beatTimer: number | null = null
let consistencyTimer: number | null = null
let storageHandler: ((e: StorageEvent)=>void) | null = null
let visHandler: (()=>void) | null = null
let pageHideHandler: (()=>void) | null = null
let pageShowHandler: (()=>void) | null = null

let currentSid = ''
let foreignActive = false

const foreignSubs = new Set<ForeignActiveCb>()
const incSubs = new Set<InconsistencyCb>()

const now = () => Date.now()
const navType = () => (performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming|undefined)?.type
const isReload = () => navType() === 'reload'

function rid(): string {
  const a = new Uint8Array(16)
  crypto.getRandomValues(a)
  return [...a].map(x => x.toString(16).padStart(2, '0')).join('')
}

function getDeviceId(): string {
  try {
    let id = localStorage.getItem(LS_DEVICE_KEY)
    if (!id) {
      id = rid()
      localStorage.setItem(LS_DEVICE_KEY, id)
    }
    return id
  } catch { return 'dev-'+rid() }
}

function getTabId(): string {
  try {
    let id = sessionStorage.getItem(SS_TAB_KEY)
    if (!id) {
      id = rid()
      sessionStorage.setItem(SS_TAB_KEY, id)
    }
    return id
  } catch { return 'tab-'+rid() }
}

const DEVICE_ID = getDeviceId()
const TAB_ID    = getTabId()

function readSid(): string {
  try { return localStorage.getItem(LS_SID_KEY) || '' } catch { return '' }
}

function writeSid(v: string) {
  try { localStorage.setItem(LS_SID_KEY, v || '') } catch {}
}

function readLock(): Lock | null {
  try {
    const s = localStorage.getItem(LS_LOCK_KEY)
    return s ? JSON.parse(s) as Lock : null
  } catch { return null }
}

function writeLock(lock: Lock) {
  try { localStorage.setItem(LS_LOCK_KEY, JSON.stringify(lock)) } catch {}
  try { bc?.postMessage({ t: 'lock', lock }) } catch {}
}

function deleteLock() {
  try { localStorage.removeItem(LS_LOCK_KEY) } catch {}
  try { bc?.postMessage({ t: 'lock', lock: null }) } catch {}
}

function ttlMs(): number {
  return document.visibilityState === 'visible' ? TTL_VISIBLE_MS : TTL_HIDDEN_MS
}

function beatMs(): number {
  return document.visibilityState === 'visible' ? BEAT_VISIBLE : BEAT_HIDDEN
}

function isOwner(lock: Lock | null): boolean {
  return !!lock && lock.owner.deviceId === DEVICE_ID && lock.owner.tabId === TAB_ID
}

function isStale(lock: Lock | null): boolean {
  if (!lock) return true
  return (now() - lock.hb) > ttlMs()
}

function setForeign(on: boolean) {
  if (foreignActive !== on) {
    foreignActive = on
    foreignSubs.forEach(cb => { try { cb(on) } catch {} })
  }
}

function acquireOrTakeover(): boolean {
  const lock = readLock()
  if (!lock || isStale(lock)) {
    writeLock({ owner: { deviceId: DEVICE_ID, tabId: TAB_ID }, hb: now(), sid: currentSid || readSid() })
    setForeign(false)
    return true
  }
  if (isOwner(lock)) {
    writeLock({ ...lock, hb: now(), sid: currentSid || lock.sid })
    setForeign(false)
    return true
  }
  if (isReload() && lock.owner.deviceId === DEVICE_ID) {
    writeLock({ owner: { deviceId: DEVICE_ID, tabId: TAB_ID }, hb: now(), sid: currentSid || lock.sid })
    setForeign(false)
    return true
  }
  setForeign(true)
  return false
}

function startHeartbeat() {
  stopHeartbeat()
  beatTimer = window.setInterval(() => {
    const lock = readLock()
    if (!lock || isStale(lock)) {
      acquireOrTakeover()
      return
    }
    if (isOwner(lock)) {
      writeLock({ ...lock, hb: now(), sid: currentSid || lock.sid })
    } else {
      setForeign(true)
    }
  }, beatMs())
}

function stopHeartbeat() {
  if (beatTimer) {
    clearInterval(beatTimer)
    beatTimer = null
  }
}

async function checkConsistency(): Promise<void> {
  const globalSid = readSid()
  const lock = readLock()
  if (!currentSid && globalSid) {
    if (!lock || isStale(lock)) {
      deleteLock()
      setForeign(false)
    } else {
      setForeign(!isOwner(lock))
    }
    return
  }
  if (currentSid && !globalSid) {
    setForeign(false)
    incSubs.forEach(cb => { try { cb() } catch {} })
    return
  }
  if (currentSid && globalSid && currentSid !== globalSid) {
    setForeign(false)
    incSubs.forEach(cb => { try { cb() } catch {} })
    return
  }
  if (!lock || isStale(lock)) {
    acquireOrTakeover()
    startHeartbeat()
    return
  }
  setForeign(!isOwner(lock))
}

function bindOnce() {
  if (storageHandler) return
  if ('BroadcastChannel' in window) {
    try {
      bc = new BroadcastChannel(BC_NAME)
      bc.onmessage = (e: MessageEvent) => {
        if (e.data?.t === 'lock') { void checkConsistency() }
      }
    } catch { bc = null }
  }
  storageHandler = (e: StorageEvent) => {
    if (e.key === LS_LOCK_KEY || e.key === LS_SID_KEY) { void checkConsistency() }
  }
  visHandler = () => { startHeartbeat() }
  pageHideHandler = () => { stopHeartbeat() }
  pageShowHandler = () => {
    acquireOrTakeover()
    startHeartbeat()
  }
  window.addEventListener('storage', storageHandler)
  document.addEventListener('visibilitychange', visHandler!)
  window.addEventListener('pagehide', pageHideHandler!)
  window.addEventListener('pageshow', pageShowHandler!)
  consistencyTimer = window.setInterval(() => { void checkConsistency() }, 5000)
}

export function initSessionBus(): void {
  if (inited) return
  inited = true
  bindOnce()
  acquireOrTakeover()
  startHeartbeat()
  void checkConsistency()
}

export function stopSessionBus(): void {
  try { bc?.close() } catch {}
  bc = null
  stopHeartbeat()
  if (consistencyTimer) {
    clearInterval(consistencyTimer)
    consistencyTimer = null
  }
  if (storageHandler) {
    window.removeEventListener('storage', storageHandler)
    storageHandler = null
  }
  if (visHandler) {
    document.removeEventListener('visibilitychange', visHandler)
    visHandler = null
  }
  if (pageHideHandler) {
    window.removeEventListener('pagehide', pageHideHandler)
    pageHideHandler = null
  }
  if (pageShowHandler) {
    window.removeEventListener('pageshow', pageShowHandler)
    pageShowHandler = null
  }
  inited = false
  foreignSubs.clear()
  incSubs.clear()
}

export function setSid(sid: string): void {
  currentSid = sid || ''
  writeSid(currentSid)
  acquireOrTakeover()
  startHeartbeat()
}

export function clearSid(prevSid?: string): void {
  currentSid = ''
  writeSid('')
  const lock = readLock()
  if (isOwner(lock)) deleteLock()
  setForeign(false)
}

export function isForeignActive(): boolean { return foreignActive }

export async function checkConsistencyNow(): Promise<boolean> {
  await checkConsistency()
  return foreignActive
}

export function onForeignActive(cb: ForeignActiveCb): () => void {
  foreignSubs.add(cb)
  return () => { foreignSubs.delete(cb) }
}

export function onInconsistency(cb: InconsistencyCb): () => void {
  incSubs.add(cb)
  return () => { incSubs.delete(cb) }
}
