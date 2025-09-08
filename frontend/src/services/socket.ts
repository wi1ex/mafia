// src/services/socket.ts
import { io, Socket } from 'socket.io-client'

let socket: Socket | null = null

export function connectSocket(token: string, onServerKick?: () => void) {
  if (socket) socket.disconnect()
  socket = io('/', {
    path: '/socket.io',
    transports: ['websocket'],
    query: { token: `Bearer ${token}` },
  })
  socket.on('disconnect', (reason) => {
    if (reason === 'io server disconnect' && onServerKick) onServerKick()
  })
  socket.on('connect_error', () => {           // NEW
    if (onServerKick) onServerKick()
  })
  return socket
}

export function getSocket() { return socket }
export function disconnectSocket() { if (socket) { socket.disconnect(); socket = null } }
