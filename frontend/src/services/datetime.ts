const DEFAULT_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
}

export function formatLocalDateTime(value?: string | number | Date | null, options: Intl.DateTimeFormatOptions = DEFAULT_OPTIONS): string {
  if (!value) return '-'
  const dt = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(dt.getTime())) return '-'
  return new Intl.DateTimeFormat(undefined, options).format(dt)
}
