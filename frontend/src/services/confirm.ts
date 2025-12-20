import { reactive } from 'vue'

export type ConfirmMode = 'confirm' | 'alert'

export type ConfirmPayload = {
  title?: string
  text: string
  confirmText?: string
  cancelText?: string
}

type ConfirmState = {
  open: boolean
  mode: ConfirmMode
  title: string
  text: string
  confirmText: string
  cancelText: string
}

const state = reactive<ConfirmState>({
  open: false,
  mode: 'alert',
  title: '',
  text: '',
  confirmText: 'ОК',
  cancelText: 'Отмена',
})

let resolver: ((value: boolean) => void) | null = null

function open(mode: ConfirmMode, payload: ConfirmPayload): Promise<boolean> {
  if (state.open && resolver) {
    resolver(false)
    resolver = null
  }
  state.mode = mode
  state.title = payload.title || (mode === 'confirm' ? 'Подтверждение' : 'Сообщение')
  state.text = payload.text
  state.confirmText = payload.confirmText || 'ОК'
  state.cancelText = payload.cancelText || 'Отмена'
  state.open = true
  return new Promise((resolve) => {
    resolver = resolve
  })
}

export function confirmDialog(payload: string | ConfirmPayload): Promise<boolean> {
  const data = typeof payload === 'string' ? { text: payload } : payload
  return open('confirm', data)
}

export function alertDialog(payload: string | ConfirmPayload): Promise<void> {
  const data = typeof payload === 'string' ? { text: payload } : payload
  return open('alert', data).then(() => {})
}

export function useConfirmState() {
  return state
}

export function resolveConfirm(result: boolean) {
  if (!state.open) return
  state.open = false
  const resolve = resolver
  resolver = null
  if (resolve) resolve(result)
}
