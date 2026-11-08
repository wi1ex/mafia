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
}

type SocketNotification = Pick<ToastPayload, 'id' | 'user' | 'room_id'> & { toast?: ToastContent }

export function dispatchSocketToast(payload: unknown): void {
  if (!payload || typeof payload !== 'object') return

  const { toast, id, user, room_id } = payload as SocketNotification
  if (!toast || typeof toast.kind !== 'string' || typeof toast.title !== 'string') return

  const { kind, title, text, actions, details, silent } = toast
  window.dispatchEvent(new CustomEvent<ToastPayload>('toast', {
    detail: { kind, title, text, actions, details, silent, id, user, room_id },
  }))
}
