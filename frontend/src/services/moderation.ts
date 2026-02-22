type RawRecord = Record<string, unknown>

function isRecord(value: unknown): value is RawRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export function formatModerationAlert(detail: unknown): string | null {
  if (!isRecord(detail)) return null
  if (detail.code !== 'inappropriate_text_detected') return null

  const rawMessage = typeof detail.message === 'string' ? detail.message.trim() : ''
  return rawMessage || 'Текст содержит неподобающие слова.'
}
