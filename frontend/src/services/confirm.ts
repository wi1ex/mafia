import { reactive } from 'vue'

export type ConfirmMode = 'confirm' | 'alert'
export type ConfirmAction = 'confirm' | 'cancel' | 'close'

export type ConfirmRadioOption = {
  value: string
  label: string
  disabled?: boolean
  tooltip?: string
}

export type ConfirmPayload = {
  title?: string
  text: string
  confirmText?: string
  cancelText?: string
  checkboxLabel?: string
  checkboxLabelSuffix?: string
  checkboxLinkText?: string
  checkboxLinkTo?: string
  checkboxRequired?: boolean
  checkboxDefault?: boolean
  radioOptions?: ConfirmRadioOption[]
  radioDefault?: string
  hideText?: boolean
}

type ConfirmResult = {
  ok: boolean
  action: ConfirmAction
  checkboxChecked: boolean
  radioValue: string
}

type ConfirmState = {
  open: boolean
  mode: ConfirmMode
  title: string
  text: string
  confirmText: string
  cancelText: string
  checkboxLabel: string
  checkboxLabelSuffix: string
  checkboxLinkText: string
  checkboxLinkTo: string
  checkboxRequired: boolean
  checkboxChecked: boolean
  radioOptions: ConfirmRadioOption[]
  radioValue: string
  hideText: boolean
}

const state = reactive<ConfirmState>({
  open: false,
  mode: 'alert',
  title: '',
  text: '',
  confirmText: 'ОК',
  cancelText: 'Отмена',
  checkboxLabel: '',
  checkboxLabelSuffix: '',
  checkboxLinkText: '',
  checkboxLinkTo: '',
  checkboxRequired: false,
  checkboxChecked: false,
  radioOptions: [],
  radioValue: '',
  hideText: false,
})

let resolver: ((value: ConfirmResult) => void) | null = null

function currentResult(ok: boolean, action: ConfirmAction = ok ? 'confirm' : 'close'): ConfirmResult {
  return {
    ok,
    action,
    checkboxChecked: Boolean(state.checkboxChecked),
    radioValue: state.radioValue,
  }
}

function open(mode: ConfirmMode, payload: ConfirmPayload): Promise<ConfirmResult> {
  if (state.open && resolver) {
    resolver(currentResult(false))
    resolver = null
  }
  state.mode = mode
  state.title = payload.title || (mode === 'confirm' ? 'Подтверждение' : 'Сообщение')
  state.text = payload.text
  state.confirmText = payload.confirmText || 'ОК'
  state.cancelText = payload.cancelText || 'Отмена'
  state.checkboxLabel = payload.checkboxLabel || ''
  state.checkboxLabelSuffix = payload.checkboxLabelSuffix || ''
  state.checkboxLinkText = payload.checkboxLinkText || ''
  state.checkboxLinkTo = payload.checkboxLinkTo || ''
  state.checkboxRequired = Boolean(payload.checkboxRequired)
    && Boolean(payload.checkboxLabel || payload.checkboxLinkText || payload.checkboxLabelSuffix)
  state.checkboxChecked = Boolean(payload.checkboxDefault)
  state.radioOptions = (payload.radioOptions || [])
    .filter(option => Boolean(option?.value) && Boolean(option?.label))
    .map(option => ({
      value: String(option.value),
      label: String(option.label),
      disabled: Boolean(option.disabled),
      tooltip: option.tooltip ? String(option.tooltip) : '',
    }))
  state.radioValue = state.radioOptions.some(option => option.value === payload.radioDefault)
    ? String(payload.radioDefault)
    : (state.radioOptions[0]?.value || '')
  state.hideText = Boolean(payload.hideText)
  state.open = true
  return new Promise((resolve) => {
    resolver = resolve
  })
}

export function confirmDialog(payload: string | ConfirmPayload): Promise<boolean> {
  const data = typeof payload === 'string' ? { text: payload } : payload
  return open('confirm', data).then(result => result.ok)
}

export async function confirmDialogWithAction(payload: string | ConfirmPayload): Promise<{ ok: boolean; action: ConfirmAction }> {
  const data = typeof payload === 'string' ? { text: payload } : payload
  const result = await open('confirm', data)
  return {
    ok: result.ok,
    action: result.action,
  }
}

export async function confirmDialogWithCheckbox(payload: string | ConfirmPayload): Promise<{ ok: boolean; checkboxChecked: boolean }> {
  const data = typeof payload === 'string' ? { text: payload } : payload
  const result = await open('confirm', data)
  return {
    ok: result.ok,
    checkboxChecked: result.checkboxChecked,
  }
}

export async function confirmDialogWithRadio(payload: string | ConfirmPayload): Promise<{ ok: boolean; radioValue: string }> {
  const data = typeof payload === 'string' ? { text: payload } : payload
  const result = await open('confirm', data)
  return {
    ok: result.ok,
    radioValue: result.radioValue,
  }
}

export function alertDialog(payload: string | ConfirmPayload): Promise<void> {
  const data = typeof payload === 'string' ? { text: payload } : payload
  return open('alert', data).then(() => {})
}

export function useConfirmState() {
  return state
}

export function resolveConfirm(result: boolean, action: ConfirmAction = result ? 'confirm' : 'close') {
  if (!state.open) return
  state.open = false
  const resolve = resolver
  resolver = null
  if (resolve) resolve(currentResult(result, action))
}
