type RawRecord = Record<string, unknown>

function isRecord(value: unknown): value is RawRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

type ModerationMatch = {
  word?: string
  start?: number
  end?: number
}

function parseMatch(value: unknown): ModerationMatch | null {
  if (!isRecord(value)) return null
  const wordRaw = value.word
  const startRaw = value.start
  const endRaw = value.end

  const word = typeof wordRaw === 'string' ? wordRaw.trim() : ''
  const start = typeof startRaw === 'number' && Number.isFinite(startRaw) ? startRaw : undefined
  const end = typeof endRaw === 'number' && Number.isFinite(endRaw) ? endRaw : undefined
  if (!word && start === undefined && end === undefined) return null
  return { word: word || undefined, start, end }
}

export function formatModerationAlert(detail: unknown): string | null {
  if (!isRecord(detail)) return null
  if (detail.code !== 'inappropriate_text_detected') return null

  const rawMessage = typeof detail.message === 'string' ? detail.message.trim() : ''
  const message = rawMessage || 'Текст содержит неподобающие слова.'
  const rawMatches = Array.isArray(detail.matches) ? detail.matches : []
  const matches = rawMatches.map(parseMatch).filter((item): item is ModerationMatch => Boolean(item))

  if (!matches.length) {
    return message
  }

  const words = Array.from(new Set(matches.map((item) => item.word).filter((item): item is string => Boolean(item))))
  const ranges = matches.map((item) => (typeof item.start === 'number' && typeof item.end === 'number' ? `${item.start}-${item.end}` : '')).filter(Boolean)
  const lines = [message]
  if (words.length) lines.push(`Найдено: ${words.join(', ')}`)
  if (ranges.length) lines.push(`Позиции: ${ranges.join(', ')}`)
  return lines.join('\n\n')
}
