type ToastRouteAction = {
  kind: 'route'
  label: string
  to: string
  style?: 'primary' | 'neutral'
}

type ToastApiAction = {
  kind: 'api'
  label: string
  url: string
  method?: 'get' | 'post' | 'delete' | 'put'
  body?: unknown
  style?: 'primary' | 'neutral'
}

type ToastGiftOpenAction = {
  kind: 'gift_open'
  label: string
  acquisition_id: number
  style?: 'primary' | 'neutral'
}

export type ToastAction = ToastRouteAction | ToastApiAction | ToastGiftOpenAction

export type ToastUser = {
  id: number
  username?: string
  avatar_name?: string | null
  role?: string | null
  theme_color?: string | null
  theme_icon?: string | null
}

type ToastContent = {
  kind: string
  title: string
  text: string
  actions: ToastAction[]
  details?: string
  silent?: boolean
}

export type ToastPayload = ToastContent & {
  id?: number
  user?: ToastUser
  room_id?: number
  subscriptionGiftDuration?: string
}

type SocketNotification = Pick<ToastPayload, 'id' | 'user' | 'room_id'> & {
  toast?: ToastContent
  subscription_gift?: { duration?: unknown }
}

export function parseSocketToast(payload: unknown): ToastPayload | null {
  if (!payload || typeof payload !== 'object') return null

  const { toast, id, user, room_id, subscription_gift } = payload as SocketNotification
  if (!toast || typeof toast.kind !== 'string' || typeof toast.title !== 'string') return null

  const { kind, title, text, actions, details, silent } = toast
  const subscriptionGiftDuration = kind === 'subscription_gift' && typeof subscription_gift?.duration === 'string'
    ? subscription_gift.duration
    : undefined
  return { kind, title, text, actions, details, silent, id, user, room_id, subscriptionGiftDuration }
}

export function dispatchSocketToast(payload: unknown): void {
  const detail = parseSocketToast(payload)
  if (detail) window.dispatchEvent(new CustomEvent<ToastPayload>('toast', { detail }))
}
