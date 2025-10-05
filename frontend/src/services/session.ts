type ForeignActiveCb = (on: boolean) => void
type InconsistencyCb = () => void

const TAB_ID = Math.random().toString(36).slice(2)

let bc: BroadcastChannel | null = null
let hbTimer: number | null = null
let consistencyTimer: number | null = null
let storageListenerBound = false
let inited = false

let currentSid = ''
let foreignActive = false

const foreignActiveSubs = new Set<ForeignActiveCb>()
const inconsistencySubs = new Set<InconsistencyCb>()

const read = {
  sid(): string { try { return localStorage.getItem('auth:sid') || '' } catch { return '' } },
  owner(): string { try { return localStorage.getItem('auth:owner') || '' } catch { return '' } },
  hb(): { id: string; ts: number } | null {
    try {
      const v = localStorage.getItem('auth:owner_hb')
      return v ? JSON.parse(v) : null
    } catch { return null }
  },
}

function writeSidMarker(sid: string) { try { localStorage.setItem('auth:sid', sid || '') } catch {} }
function beat() { try { localStorage.setItem('auth:owner_hb', JSON.stringify({ id: TAB_ID, ts: Date.now() })) } catch {} }
function ownerAlive(): boolean {
  const owner = read.owner()
  const hb = read.hb()
  if (!owner || !hb) return false
  return hb.id === owner && (Date.now() - hb.ts) < 15_000
}
function becomeOwner() {
  try {
    localStorage.setItem('auth:owner', TAB_ID)
    beat()
    if (hbTimer) clearInterval(hbTimer)
    hbTimer = window.setInterval(beat, 4000)
    window.addEventListener('beforeunload', () => { releaseOwnership(currentSid) }, { once: true })
  } catch {}
}
function releaseOwnership(prevSid?: string) {
  try {
    const owner = read.owner()
    if (owner === TAB_ID) {
      localStorage.removeItem('auth:owner')
      localStorage.removeItem('auth:owner_hb')
      if (prevSid && read.sid() === prevSid) writeSidMarker('')
    }
  } catch {}
}
function broadcastSession(sid: string) {
  const payload = { sid }
  try { bc?.postMessage(payload) } catch {}
  try { localStorage.setItem('auth:msg', JSON.stringify({ ...payload, ts: Date.now(), rnd: Math.random() })) } catch {}
}
function setForeignActive(on: boolean) {
  if (foreignActive !== on) {
    foreignActive = on
    foreignActiveSubs.forEach(cb => { try { cb(on) } catch {} })
  }
}

async function checkConsistency(): Promise<void> {
  const globalSid = read.sid()
  const cur = currentSid || ''

  if (!cur && globalSid) {
    if (!ownerAlive()) {
      releaseOwnership(globalSid)
      try { writeSidMarker('') } catch {}
      setForeignActive(false)
    } else {
      setForeignActive(true)
    }
    return
  }
  if (cur && !globalSid) {
    setForeignActive(false)
    inconsistencySubs.forEach(cb => { try { cb() } catch {} })
    return
  }
  if (cur && globalSid && cur !== globalSid) {
    setForeignActive(false)
    inconsistencySubs.forEach(cb => { try { cb() } catch {} })
    return
  }
  setForeignActive(false)
}

let storageHandler: ((e: StorageEvent)=>void) | null = null
let focusHandler: (()=>void) | null = null
let visHandler: (()=>void) | null = null

function bindListenersOnce() {
  if (storageListenerBound) return
  storageListenerBound = true

  if ('BroadcastChannel' in window) {
    try {
      bc = new BroadcastChannel('auth')
      bc.onmessage = () => { void checkConsistency() }
    } catch {}
  }

  storageHandler = (e) => {
    if (e.key === 'auth:msg' && e.newValue) { void checkConsistency() }
  }
  focusHandler = () => { void checkConsistency() }
  visHandler = () => { if (!document.hidden) void checkConsistency() }

  window.addEventListener('storage', storageHandler)
  window.addEventListener('focus', focusHandler)
  document.addEventListener('visibilitychange', visHandler)

  consistencyTimer = window.setInterval(() => { void checkConsistency() }, 5000)
}

export function initSessionBus(): void {
  if (inited) return
  inited = true
  bindListenersOnce()
  void checkConsistency()
}

export function stopSessionBus(): void {
  try { bc?.close() } catch {}
  bc = null
  if (hbTimer) {
    clearInterval(hbTimer)
    hbTimer = null
  }
  if (consistencyTimer) {
    clearInterval(consistencyTimer)
    consistencyTimer = null
  }
  if (storageHandler) {
    window.removeEventListener('storage', storageHandler)
    storageHandler = null
  }
  if (focusHandler) {
    window.removeEventListener('focus', focusHandler)
    focusHandler = null
  }
  if (visHandler) {
    document.removeEventListener('visibilitychange', visHandler)
    visHandler = null
  }
  storageListenerBound = false
  inited = false
  foreignActiveSubs.clear()
  inconsistencySubs.clear()
}

export function setSid(sid: string): void {
  currentSid = sid || ''
  writeSidMarker(currentSid)
  if (!read.owner() || !ownerAlive()) becomeOwner()
  broadcastSession(currentSid)
}

export function clearSid(prevSid?: string): void {
  const prev = prevSid ?? currentSid
  currentSid = ''
  writeSidMarker('')
  releaseOwnership(prev)
  broadcastSession('')
}

export function isForeignActive(): boolean { return foreignActive }

export async function checkConsistencyNow(): Promise<boolean> {
  await checkConsistency()
  return foreignActive
}

export function onForeignActive(cb: ForeignActiveCb): () => void {
  foreignActiveSubs.add(cb)
  return () => { foreignActiveSubs.delete(cb) }
}
export function onInconsistency(cb: InconsistencyCb): () => void {
  inconsistencySubs.add(cb)
  return () => { inconsistencySubs.delete(cb) }
}
