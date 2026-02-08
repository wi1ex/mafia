import { io, Socket } from 'socket.io-client'
import {
  getAccessToken,
  refreshAccessToken,
  addTokenRefreshedListener,
  removeTokenRefreshedListener,
  addAuthExpiredListener,
  removeAuthExpiredListener,
} from '@/services/axios'

type IoOpts = Parameters<typeof io>[1]

function wireAuthedSocket(s: Socket) {
  let triedRefreshOnThisCycle = false

  const applyAuth = () => {
    const tok = getAccessToken()
    ;(s as any).auth = { token: tok }
    ;(s.io.opts as any).auth = { token: tok }
  }

  s.on('connect_error', async () => {
    if (triedRefreshOnThisCycle) return
    triedRefreshOnThisCycle = true
    const tok = await refreshAccessToken(false)
    if (tok) {
      applyAuth()
      try { s.io.reconnect() } catch {}
    } else {
      try { (s.io.opts as any).reconnection = false } catch {}
      try { s.close() } catch {}
    }
  })

  s.on('connect', () => { triedRefreshOnThisCycle = false })

  s.io.on('reconnect_attempt', applyAuth)

  const onRefreshed = (_: string) => applyAuth()
  const onExpired = () => {
    try { (s.io.opts as any).reconnection = false } catch {}
    try { s.close() } catch {}
  }
  addTokenRefreshedListener(onRefreshed)
  addAuthExpiredListener(onExpired)

  const off = () => {
    removeTokenRefreshedListener(onRefreshed)
    removeAuthExpiredListener(onExpired)
    try { s.io.off?.('reconnect_attempt', applyAuth as any) } catch {}
  }

  s.on('disconnect', off)

  s.on('close', off)

  return s
}

export function createAuthedSocket(namespace: string, opts?: IoOpts): Socket {
  const s = io(namespace, { ...opts, auth: { token: getAccessToken() } })
  return wireAuthedSocket(s)
}

export function createPublicSocket(namespace: string, opts?: IoOpts): Socket {
  return io(namespace, { ...opts, auth: undefined })
}

let authSocket: Socket | null = null
const AUTH_HEARTBEAT_MS = 30000
let authHeartbeatTimer: number | null = null

function startAuthHeartbeat(s: Socket): void {
  if (authHeartbeatTimer !== null) return
  const send = () => {
    if (!s.connected) return
    try { s.emit('online_ping') } catch {}
  }
  authHeartbeatTimer = window.setInterval(send, AUTH_HEARTBEAT_MS)
  send()
}

function stopAuthHeartbeat(): void {
  if (authHeartbeatTimer === null) return
  window.clearInterval(authHeartbeatTimer)
  authHeartbeatTimer = null
}

export function startAuthSocket(opts?: { onForceLogout?: () => void }): Socket {
  if (authSocket) return authSocket
  authSocket = createAuthedSocket('/auth', {
    path: '/ws/socket.io',
    transports: ['websocket','polling'],
    upgrade: true,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 200,
    reconnectionDelayMax: 2000,
  })
  if (opts?.onForceLogout) authSocket.on('force_logout', opts.onForceLogout)
  authSocket.on('connect', () => { startAuthHeartbeat(authSocket as Socket) })
  authSocket.on('disconnect', stopAuthHeartbeat)
  authSocket.on('close', stopAuthHeartbeat)

  authSocket.on('notify', (p:any) => {
    window.dispatchEvent(new CustomEvent('auth-notify', { detail: p }))
    if (!p?.no_toast) window.dispatchEvent(new CustomEvent('toast', { detail: p }))
  })

  authSocket.on('site_update', (p:any) => {
    window.dispatchEvent(new CustomEvent('auth-site_update', { detail: p }))
  })

  authSocket.on('settings_update', (p:any) => {
    window.dispatchEvent(new CustomEvent('auth-settings_update', { detail: p }))
  })

  authSocket.on('sanctions_update', (p:any) => {
    window.dispatchEvent(new CustomEvent('auth-sanctions_update', { detail: p }))
  })

  authSocket.on('telegram_verified', (p:any) => {
    window.dispatchEvent(new CustomEvent('auth-telegram_verified', { detail: p }))
  })

  authSocket.on('room_invite', (p:any) => {
    window.dispatchEvent(new CustomEvent('auth-room_invite', { detail: p }))
    const dto = {
      title: 'Заявка в комнату от',
      date: new Date().toISOString(),
      kind: 'app',
      room_id: p.room_id,
      user: p.user,
      action: { kind: 'api', label: 'Одобрить', url: `/rooms/${p.room_id}/requests/${p.user.id}/approve`, method: 'post' },
      read: true,
      ttl_ms: 10000,
    }
    window.dispatchEvent(new CustomEvent('toast', { detail: dto }))
  })

  authSocket.on('room_app_approved', (p:any) => {
    window.dispatchEvent(new CustomEvent('auth-room_app_approved', { detail: p }))
  })

  authSocket.on('room_app_revoked', (p:any) => {
    window.dispatchEvent(new CustomEvent('auth-room_app_revoked', { detail: p }))
  })

  return authSocket
}

export function stopAuthSocket(): void {
  stopAuthHeartbeat()
  try { authSocket?.off?.() } catch {}
  try { authSocket?.close?.() } catch {}
  authSocket = null
}
