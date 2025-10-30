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

export function startAuthSocket(opts?: {
  onForceLogout?: () => void
  onNotify?: (p: any) => void
  onRoomApp?: (p: any) => void
}): Socket {
  if (authSocket) return authSocket
  authSocket = createAuthedSocket('/auth', {
    path: '/ws/socket.io',
    transports: ['websocket','polling'],
    upgrade: true,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 500,
    reconnectionDelayMax: 5000,
  })
  if (opts?.onForceLogout) authSocket.on('force_logout', opts.onForceLogout)
  if (opts?.onNotify) authSocket.on('notify', opts.onNotify)
  if (opts?.onRoomApp) authSocket.on('room_invite', opts.onRoomApp)

  authSocket.on('room_app_approved', (p:any) => {
    try {
      window.dispatchEvent(new CustomEvent('auth-room_app_approved', { detail: p }))
    } catch {}
  })

  return authSocket
}

export function stopAuthSocket(): void {
  try { authSocket?.off?.() } catch {}
  try { authSocket?.close?.() } catch {}
  authSocket = null
}
