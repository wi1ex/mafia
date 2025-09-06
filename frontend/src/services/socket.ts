// src/services/socket.ts
import { io, Socket } from 'socket.io-client'

let socket: Socket | null = null

export function connectSocket(accessToken: string, onKicked: () => void) {
  if (socket) {
    try { socket.disconnect() } catch {}
    socket = null
  }

  // сервер ждёт токен в query (?token=...)
  socket = io('/', {
    path: '/socket.io',
    transports: ['websocket'],
    query: { token: `Bearer ${accessToken}` },
    autoConnect: true,
    reconnection: true,
  })

  // мягкое уведомление из бекенда (см. sio.py)
  socket.on('force_logout', () => { onKicked() })

  // если сервер разорвал коннект — тоже выходим
  socket.on('disconnect', (reason) => {
    if (reason === 'io server disconnect' || reason === 'transport close') {
      onKicked()
    }
  })
}

export function disconnectSocket() {
  if (!socket) return
  try {
    socket.off('force_logout')
    socket.off('disconnect')
    socket.disconnect()
  } finally {
    socket = null
  }
}
