import {
  canAcceptRefreshSid,
  canRefreshPublishedSid,
  getRefreshExpectedSid,
} from './session'

export type CoordinatedRefreshResult = {
  token: string | null
  data?: any
}

type RefreshOutcome = {
  kind: 'refresh-outcome'
  source: string
  finishedAt: number
  ok: boolean
}

type RefreshLease = {
  owner: string
  nonce: string
  expiresAt: number
}

type RefreshCandidate = {
  owner: string
  createdAt: number
  expiresAt: number
}

type WebLockManager = {
  request<T>(
    name: string,
    options: { mode: 'exclusive'; signal?: AbortSignal },
    callback: (lock: unknown) => Promise<T>,
  ): Promise<T>
}

const WEB_LOCK_NAME = 'mafia-auth-refresh-v1'
const CHANNEL_NAME = 'mafia-auth-refresh-v1'
const LEASE_KEY = 'auth:refresh:lease:v1'
const OUTCOME_KEY = 'auth:refresh:outcome:v1'
const CANDIDATE_PREFIX = 'auth:refresh:candidate:v1:'
const SESSION_SCOPE_KEY = 'auth:sid'
const CANDIDATE_TTL_MS = 5_000
const LEASE_TTL_MS = 45_000
const LEASE_HEARTBEAT_MS = 5_000
const FOLLOWER_TIMEOUT_MS = 60_000

function randomId(): string {
  try {
    const bytes = new Uint8Array(16)
    globalThis.crypto.getRandomValues(bytes)
    return [...bytes].map(value => value.toString(16).padStart(2, '0')).join('')
  } catch {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
  }
}

const SOURCE_ID = randomId()
let channel: BroadcastChannel | null = null
let coordinationBound = false
let storageUsable: boolean | null = null
const wakeWaiters = new Set<() => void>()

function emptyResult(): CoordinatedRefreshResult {
  return { token: null }
}

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof navigator !== 'undefined'
}

type SessionScopeSnapshot = { value: string; readable: boolean }

function readSessionScope(): SessionScopeSnapshot {
  if (!isBrowser()) return { value: '', readable: false }
  try {
    return { value: window.localStorage.getItem(SESSION_SCOPE_KEY) || '', readable: true }
  } catch {
    return { value: '', readable: false }
  }
}

function scopeChanged(capturedScope: SessionScopeSnapshot): boolean {
  const current = readSessionScope()
  if (current.readable !== capturedScope.readable) return true
  return current.readable && current.value !== capturedScope.value
}

function canUseStorage(): boolean {
  if (!isBrowser()) return false
  if (storageUsable !== null) return storageUsable
  const probe = `${CANDIDATE_PREFIX}probe-${SOURCE_ID}`
  try {
    window.localStorage.setItem(probe, '1')
    window.localStorage.removeItem(probe)
    storageUsable = true
  } catch {
    storageUsable = false
  }
  return storageUsable
}

function wakeFollowers(): void {
  for (const wake of [...wakeWaiters]) {
    try { wake() } catch {}
  }
}

function parseOutcome(value: unknown): RefreshOutcome | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Partial<RefreshOutcome>
  if (
    raw.kind !== 'refresh-outcome' ||
    typeof raw.source !== 'string' ||
    typeof raw.finishedAt !== 'number' ||
    typeof raw.ok !== 'boolean'
  ) return null
  return raw as RefreshOutcome
}

function recordOutcome(_outcome: RefreshOutcome): void {
  wakeFollowers()
}

function ensureCoordinationBound(): void {
  if (!isBrowser() || coordinationBound) return
  coordinationBound = true

  if ('BroadcastChannel' in window) {
    try {
      channel = new BroadcastChannel(CHANNEL_NAME)
      channel.onmessage = (event: MessageEvent) => {
        const outcome = parseOutcome(event.data)
        if (outcome && outcome.source !== SOURCE_ID) recordOutcome(outcome)
      }
    } catch {
      channel = null
    }
  }

  window.addEventListener('storage', (event: StorageEvent) => {
    if (event.key === OUTCOME_KEY && event.newValue) {
      try {
        const outcome = parseOutcome(JSON.parse(event.newValue))
        if (outcome && outcome.source !== SOURCE_ID) recordOutcome(outcome)
      } catch {}
      return
    }
    if (event.key === LEASE_KEY || event.key?.startsWith(CANDIDATE_PREFIX)) wakeFollowers()
  })
}

function publishOutcome(ok: boolean): void {
  const outcome: RefreshOutcome = {
    kind: 'refresh-outcome',
    source: SOURCE_ID,
    finishedAt: Date.now(),
    ok,
  }
  recordOutcome(outcome)
  try { channel?.postMessage(outcome) } catch {}
  if (canUseStorage()) {
    try { window.localStorage.setItem(OUTCOME_KEY, JSON.stringify(outcome)) } catch {}
  }
}

function waitForWake(timeoutMs: number): Promise<void> {
  return new Promise(resolve => {
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      wakeWaiters.delete(finish)
      resolve()
    }
    const timer = window.setTimeout(finish, Math.max(0, timeoutMs))
    wakeWaiters.add(finish)
  })
}

function readJson(key: string): unknown | null {
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? JSON.parse(raw) as unknown : null
  } catch {
    return null
  }
}

function parseRefreshLease(value: unknown): RefreshLease | null {
  if (!value || typeof value !== 'object') return null
  const lease = value as Partial<RefreshLease>
  if (
    typeof lease.owner !== 'string' ||
    typeof lease.nonce !== 'string' ||
    typeof lease.expiresAt !== 'number' ||
    !Number.isFinite(lease.expiresAt)
  ) return null
  return { owner: lease.owner, nonce: lease.nonce, expiresAt: lease.expiresAt }
}

function parseRefreshCandidate(value: unknown): RefreshCandidate | null {
  if (!value || typeof value !== 'object') return null
  const candidate = value as Partial<RefreshCandidate>
  if (
    typeof candidate.owner !== 'string' ||
    typeof candidate.createdAt !== 'number' ||
    !Number.isFinite(candidate.createdAt) ||
    typeof candidate.expiresAt !== 'number' ||
    !Number.isFinite(candidate.expiresAt)
  ) return null
  return {
    owner: candidate.owner,
    createdAt: candidate.createdAt,
    expiresAt: candidate.expiresAt,
  }
}

function readStoredLease(): RefreshLease | null {
  return parseRefreshLease(readJson(LEASE_KEY))
}

function readActiveLease(): RefreshLease | null {
  const lease = readStoredLease()
  if (!lease) return null
  return lease.expiresAt > Date.now() ? lease : null
}

function ownsStorageLease(lease: RefreshLease): boolean {
  const current = readActiveLease()
  return current?.owner === lease.owner && current.nonce === lease.nonce
}

function removeOwnCandidate(key: string): void {
  try { window.localStorage.removeItem(key) } catch {}
}

function liveCandidates(now: number): Array<{ key: string; value: RefreshCandidate }> {
  const candidates: Array<{ key: string; value: RefreshCandidate }> = []
  try {
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index)
      if (!key?.startsWith(CANDIDATE_PREFIX)) continue
      const candidate = parseRefreshCandidate(readJson(key))
      if (
        !candidate ||
        candidate.expiresAt <= now
      ) {
        try { window.localStorage.removeItem(key) } catch {}
        continue
      }
      candidates.push({ key, value: candidate })
    }
  } catch {}
  candidates.sort((left, right) => (
    left.value.createdAt - right.value.createdAt || left.value.owner.localeCompare(right.value.owner)
  ))
  return candidates
}

async function tryAcquireStorageLease(): Promise<RefreshLease | null> {
  if (readActiveLease()) return null

  const createdAt = Date.now()
  const owner = `${SOURCE_ID}:${randomId()}`
  const candidateKey = `${CANDIDATE_PREFIX}${owner}`
  const candidate: RefreshCandidate = { owner, createdAt, expiresAt: createdAt + CANDIDATE_TTL_MS }
  try { window.localStorage.setItem(candidateKey, JSON.stringify(candidate)) } catch { return null }

  await new Promise<void>(resolve => window.setTimeout(resolve, 80))

  if (readActiveLease()) {
    removeOwnCandidate(candidateKey)
    return null
  }
  const winner = liveCandidates(Date.now())[0]
  if (!winner || winner.value.owner !== owner) {
    removeOwnCandidate(candidateKey)
    return null
  }

  const lease: RefreshLease = { owner, nonce: randomId(), expiresAt: Date.now() + LEASE_TTL_MS }
  try { window.localStorage.setItem(LEASE_KEY, JSON.stringify(lease)) } catch {
    removeOwnCandidate(candidateKey)
    return null
  }
  await new Promise<void>(resolve => window.setTimeout(resolve, 25))
  removeOwnCandidate(candidateKey)

  const confirmed = readStoredLease()
  if (confirmed?.owner === lease.owner && confirmed.nonce === lease.nonce) return lease
  return null
}

function releaseStorageLease(lease: RefreshLease): void {
  try {
    const current = readStoredLease()
    if (current?.owner === lease.owner && current.nonce === lease.nonce) {
      window.localStorage.removeItem(LEASE_KEY)
    }
  } catch {}
  wakeFollowers()
}

async function runAndPublish<T>(run: () => Promise<T>): Promise<T> {
  try {
    const result = await run()
    publishOutcome(true)
    return result
  } catch (error) {
    publishOutcome(false)
    throw error
  }
}

async function coordinateWithWebLock<T>(
  manager: WebLockManager,
  run: () => Promise<T>,
): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), FOLLOWER_TIMEOUT_MS)
  try {
    return await manager.request(
      WEB_LOCK_NAME,
      { mode: 'exclusive', signal: controller.signal },
      async () => runAndPublish(run),
    )
  } finally {
    window.clearTimeout(timeout)
  }
}

async function coordinateWithStorageLease<T>(
  startedAt: number,
  run: () => Promise<T>,
): Promise<T> {
  const deadline = startedAt + FOLLOWER_TIMEOUT_MS
  while (Date.now() < deadline) {
    const lease = await tryAcquireStorageLease()
    if (lease) {
      const heartbeat = window.setInterval(() => {
        try {
          const current = readStoredLease()
          if (current?.owner !== lease.owner || current.nonce !== lease.nonce) return
          lease.expiresAt = Date.now() + LEASE_TTL_MS
          window.localStorage.setItem(LEASE_KEY, JSON.stringify(lease))
        } catch {}
      }, LEASE_HEARTBEAT_MS)
      try {
        if (!ownsStorageLease(lease)) throw new Error('auth_cookie_lock_lost')
        try {
          const result = await run()
          if (!ownsStorageLease(lease)) throw new Error('auth_cookie_lock_lost')
          publishOutcome(true)
          return result
        } catch (error) {
          publishOutcome(false)
          throw error
        }
      } finally {
        window.clearInterval(heartbeat)
        releaseStorageLease(lease)
      }
    }

    const active = readActiveLease()
    const untilLeaseExpiry = active ? Math.max(50, active.expiresAt - Date.now()) : 150
    await waitForWake(Math.min(500, untilLeaseExpiry, Math.max(0, deadline - Date.now())))
  }
  throw new Error('auth_cookie_lock_timeout')
}

/** Run a mutation of the shared auth cookie under the same cross-tab lock. */
export async function withAuthCookieLock<T>(run: () => Promise<T>): Promise<T> {
  if (!isBrowser()) return run()
  ensureCoordinationBound()
  const startedAt = Date.now()

  const manager = (navigator as Navigator & { locks?: WebLockManager }).locks
  if (manager) return coordinateWithWebLock(manager, run)
  if (canUseStorage()) return coordinateWithStorageLease(startedAt, run)

  return runAndPublish(run)
}

export function hasAuthCookieMutex(): boolean {
  if (!isBrowser()) return false
  return Boolean((navigator as Navigator & { locks?: WebLockManager }).locks) || canUseStorage()
}

export async function coordinateRefresh(
  run: (expectedSid: string) => Promise<CoordinatedRefreshResult>,
  applyResult: (result: CoordinatedRefreshResult) => void,
): Promise<CoordinatedRefreshResult> {
  if (!isBrowser()) {
    const result = await run('')
    applyResult(result)
    return result
  }
  const capturedScope = readSessionScope()
  const expectedSid = getRefreshExpectedSid()
  if (
    !expectedSid
    || !hasAuthCookieMutex()
    || (capturedScope.readable && !canRefreshPublishedSid(capturedScope.value))
  ) {
    const rejected = emptyResult()
    applyResult(rejected)
    return rejected
  }
  try {
    return await withAuthCookieLock(async () => {
      if (
        scopeChanged(capturedScope)
        || getRefreshExpectedSid() !== expectedSid
        || (capturedScope.readable && !canRefreshPublishedSid(capturedScope.value))
      ) {
        const rejected = emptyResult()
        applyResult(rejected)
        return rejected
      }
      const result = await run(expectedSid)
      const returnedScope = String(result.data?.sid || '')
      if (
        (
          scopeChanged(capturedScope)
          || getRefreshExpectedSid() !== expectedSid
          || (capturedScope.readable && !canRefreshPublishedSid(capturedScope.value))
          || !canAcceptRefreshSid(returnedScope)
          || returnedScope !== expectedSid
        )
      ) {
        const rejected = emptyResult()
        applyResult(rejected)
        return rejected
      }
      applyResult(result)
      return result
    })
  } catch {
    const rejected = emptyResult()
    applyResult(rejected)
    return rejected
  }
}
