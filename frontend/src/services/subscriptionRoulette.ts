import { api } from '@/services/axios'

export const ROULETTE_DAYS = [7, 22, 3, 18, 11, 26, 1, 16, 29, 8, 21, 4, 25, 12, 19, 6, 27, 14, 9, 30, 17, 2, 23, 10, 15, 28, 5, 20, 13, 24] as const
export const ROULETTE_SPIN_MS = 10000
export const ROULETTE_MAX_STOP_OFFSET = 5

export type RoulettePhase = 'idle' | 'requesting' | 'spinning' | 'result' | 'recovering' | 'error'
export type RouletteNotification = {
  id: number
  title: string
  text?: string
  date: string
  read: boolean
  kind: string
  source: 'subscription_roulette'
  no_toast?: boolean
  [key: string]: unknown
}
export type RouletteStatus = {
  round_id: number
  enabled: boolean
  verified: boolean
  eligible: boolean
  already_spun: boolean
  subscription_roulette_days: number | null
  subscription_until: string | null
  notification?: RouletteNotification | null
}

export function validRouletteDays(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 1 && value <= 30
}

export function rouletteDaysWord(days: number): string {
  const last = days % 10
  const lastTwo = days % 100
  return last === 1 && lastTwo !== 11 ? 'день' : last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14) ? 'дня' : 'дней'
}

export function validRouletteRound(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

export function rouletteAngle(days: number, currentAngle = 0, stopOffset = 0): number {
  const index = ROULETTE_DAYS.findIndex(value => value === days)
  if (index < 0) throw new Error('Invalid subscription roulette result')
  const mod = (value: number) => ((value % 360) + 360) % 360
  return currentAngle + 14 * 360 + mod(-index * 12 + stopOffset - currentAngle)
}

export async function fetchRouletteStatus(roundId?: number): Promise<RouletteStatus> {
  if (roundId !== undefined && !validRouletteRound(roundId)) throw new Error('Invalid subscription roulette round')
  const { data } = await api.get<RouletteStatus>('/users/subscription-roulette/status', roundId === undefined ? undefined : { params: { round_id: roundId } })
  return data
}

export async function spinRoulette(roundId: number): Promise<RouletteStatus> {
  if (!validRouletteRound(roundId)) throw new Error('Invalid subscription roulette round')
  const { data } = await api.post<RouletteStatus>('/users/subscription-roulette/spin', { round_id: roundId })
  return data
}

let notificationAccount: number | null = null
let heldAccount: number | null = null
const queued = new Map<number, Record<string, unknown>>()
const shown = new Set<number>()

export function setRouletteNotificationAccount(id: number | null): void {
  if (notificationAccount === id) return
  notificationAccount = id
  heldAccount = null
  queued.clear()
  shown.clear()
}

export function holdRouletteNotifications(id: number): void {
  if (notificationAccount === id) heldAccount = id
}

function dispatchToast(payload: Record<string, unknown>): void {
  const toast = { ...payload }
  if (Object.hasOwn(payload, 'toast_title')) toast.title = payload.toast_title
  if (Object.hasOwn(payload, 'toast_text')) toast.text = payload.toast_text
  window.dispatchEvent(new CustomEvent('toast', { detail: toast }))
}

function showRouletteToast(payload: Record<string, unknown>): void {
  const id = Number(payload.id)
  if (!Number.isSafeInteger(id) || id <= 0 || shown.has(id)) return
  shown.add(id)
  if (shown.size > 256) shown.delete(shown.values().next().value as number)
  dispatchToast(payload)
}

export function releaseRouletteNotifications(id: number): void {
  if (notificationAccount !== id) return
  heldAccount = null
  for (const payload of queued.values()) showRouletteToast(payload)
  queued.clear()
}

export function publishSiteNotification(payload: unknown): void {
  if (!payload || typeof payload !== 'object') return
  const note = payload as Record<string, unknown>
  window.dispatchEvent(new CustomEvent('auth-notify', { detail: note }))
  if (note.no_toast) return
  if (note.source !== 'subscription_roulette') {
    dispatchToast(note)
    return
  }
  if (notificationAccount === null) return
  if (heldAccount === notificationAccount) {
    const id = Number(note.id)
    if (Number.isSafeInteger(id) && id > 0 && !shown.has(id)) queued.set(id, note)
    return
  }
  showRouletteToast(note)
}
