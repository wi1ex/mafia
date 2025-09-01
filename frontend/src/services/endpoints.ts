export function apiBase(): string {
  return '/api'
}
export function sioPath(): string {
  return '/ws-sio'
}
export function livekitWs(): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/rtc`
}
