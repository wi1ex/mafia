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

let defaultFormatter: Intl.DateTimeFormat | undefined
let chatTimeFormatter: Intl.DateTimeFormat | undefined
let chatDateTimeFormatter: Intl.DateTimeFormat | undefined

function localTimeAsUtc(dt: Date): number {
  const utc = new Date(0)
  utc.setUTCFullYear(dt.getFullYear(), dt.getMonth(), dt.getDate())
  return utc.setUTCHours(dt.getHours(), dt.getMinutes(), dt.getSeconds(), dt.getMilliseconds())
}

export function formatLocalDateTime(value?: string | number | Date | null, options: Intl.DateTimeFormatOptions = DEFAULT_OPTIONS, locale?: Intl.LocalesArgument): string {
  if (!value) return '—'
  const dt = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(dt.getTime())) return '—'
  if (options === DEFAULT_OPTIONS && locale === undefined && !(value instanceof Date)) {
    const localTime = localTimeAsUtc(dt)
    if (Number.isFinite(localTime)) {
      defaultFormatter ??= new Intl.DateTimeFormat(undefined, { ...DEFAULT_OPTIONS, timeZone: 'UTC' })
      return defaultFormatter.format(localTime)
    }
  }
  return new Intl.DateTimeFormat(locale, options).format(dt)
}

export function formatChatTimestamp(value?: string | number | Date | null): string {
  if (!value) return '—'
  const dt = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(dt.getTime())) return '—'

  const now = new Date()
  const sameDay = (
    dt.getFullYear() === now.getFullYear()
    && dt.getMonth() === now.getMonth()
    && dt.getDate() === now.getDate()
  )

  const localTime = value instanceof Date ? NaN : localTimeAsUtc(dt)
  if (!Number.isFinite(localTime)) {
    return new Intl.DateTimeFormat(undefined, sameDay ? CHAT_TIME_OPTIONS : CHAT_DATE_TIME_OPTIONS).format(dt)
  }
  const formatter = sameDay
    ? (chatTimeFormatter ??= new Intl.DateTimeFormat(undefined, { ...CHAT_TIME_OPTIONS, timeZone: 'UTC' }))
    : (chatDateTimeFormatter ??= new Intl.DateTimeFormat(undefined, { ...CHAT_DATE_TIME_OPTIONS, timeZone: 'UTC' }))
  return formatter.format(localTime)
}
