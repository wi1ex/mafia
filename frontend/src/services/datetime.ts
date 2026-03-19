const DEFAULT_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
}

const CHAT_TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  hour: '2-digit',
  minute: '2-digit',
}

const CHAT_DATE_TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
}

export function formatLocalDateTime(value?: string | number | Date | null, options: Intl.DateTimeFormatOptions = DEFAULT_OPTIONS): string {
  if (!value) return '-'
  const dt = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(dt.getTime())) return '-'
  return new Intl.DateTimeFormat(undefined, options).format(dt)
}

export function formatChatTimestamp(value?: string | number | Date | null): string {
  if (!value) return '-'
  const dt = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(dt.getTime())) return '-'

  const now = new Date()
  const sameDay = (
    dt.getFullYear() === now.getFullYear()
    && dt.getMonth() === now.getMonth()
    && dt.getDate() === now.getDate()
  )

  return new Intl.DateTimeFormat(undefined, sameDay ? CHAT_TIME_OPTIONS : CHAT_DATE_TIME_OPTIONS).format(dt)
}
