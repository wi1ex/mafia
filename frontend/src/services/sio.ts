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

type WiredSocket = Socket & {
  __authWired?: boolean
  __authDispose?: (() => void) | null
}

function disposeAuthWiring(s: Socket | null | undefined): void {
  if (!s) return
  const ws = s as WiredSocket
  try { ws.__authDispose?.() } catch {}
}

function wireAuthedSocket(s: Socket) {
  const ws = s as WiredSocket
  if (ws.__authWired) return s
  ws.__authWired = true

  let triedRefreshOnThisCycle = false
  let disposed = false

  const applyAuth = () => {
    const tok = getAccessToken()
    ;(s as any).auth = { token: tok }
    ;(s.io.opts as any).auth = { token: tok }
  }

  const onConnectError = async () => {
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
  }

  const onConnect = () => { triedRefreshOnThisCycle = false }

  const onRefreshed = (_: string) => applyAuth()
  const onDisconnect = (reason: string) => {
    if (reason === 'io client disconnect') dispose()
  }

  const onExpired = () => {
    dispose()
    try { (s.io.opts as any).reconnection = false } catch {}
    try { s.close() } catch {}
  }

  const dispose = () => {
    if (disposed) return
    disposed = true
    removeTokenRefreshedListener(onRefreshed)
    removeAuthExpiredListener(onExpired)
    try { s.io.off?.('reconnect_attempt', applyAuth as any) } catch {}
    try { s.off?.('connect_error', onConnectError as any) } catch {}
    try { s.off?.('connect', onConnect as any) } catch {}
    try { s.off?.('disconnect', onDisconnect as any) } catch {}
    ws.__authWired = false
    ws.__authDispose = null
  }

  s.on('connect_error', onConnectError)
  s.on('connect', onConnect)
  s.io.on('reconnect_attempt', applyAuth)
  addTokenRefreshedListener(onRefreshed)
  addAuthExpiredListener(onExpired)
  s.on('disconnect', onDisconnect)
  ws.__authDispose = dispose

  return s
}

export function createAuthedSocket(namespace: string, opts?: IoOpts): Socket {
  const s = io(namespace, { ...opts, auth: { token: getAccessToken() } })
  return wireAuthedSocket(s)
}

export function createPublicSocket(namespace: string, opts?: IoOpts): Socket {
  const tok = getAccessToken()
  return io(namespace, { ...opts, auth: tok ? { token: tok } : undefined })
}

export function disposeAuthedSocket(socket: Socket | null | undefined): void {
  disposeAuthWiring(socket)
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
    if (!p?.no_toast) {
      let toastPayload = p
      if (p && typeof p === 'object') {
        toastPayload = { ...p }
        if (Object.prototype.hasOwnProperty.call(p, 'toast_title')) {
          ;(toastPayload as any).title = (p as any).toast_title
        }
        if (Object.prototype.hasOwnProperty.call(p, 'toast_text')) {
          ;(toastPayload as any).text = (p as any).toast_text
        }
      }
      window.dispatchEvent(new CustomEvent('toast', { detail: toastPayload }))
    }
  })

  authSocket.on('friends_update', (p:any) => {
    window.dispatchEvent(new CustomEvent('auth-friends_update', { detail: p }))
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
  disposeAuthWiring(authSocket)
  try { authSocket?.off?.() } catch {}
  try { authSocket?.close?.() } catch {}
  authSocket = null
}
