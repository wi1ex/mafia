export type NotificationTextBlock =
  | { type: 'paragraph'; lines: string[] }
  | { type: 'list'; items: string[] }

const LIST_ITEM_RE = /^\s*--\s*(.*)$/

export function normalizeNotificationText(value: string): string {
  return value.replace(/\r\n?/g, '\n')
}

export function parseNotificationText(value?: string | null): NotificationTextBlock[] {
  const lines = normalizeNotificationText(value ?? '').split('\n')
  const blocks: NotificationTextBlock[] = []
  let paragraphLines: string[] = []
  let listItems: string[] = []

  function flushParagraph() {
    if (!paragraphLines.length) return
    blocks.push({ type: 'paragraph', lines: paragraphLines })
    paragraphLines = []
  }

  function flushList() {
    if (!listItems.length) return
    blocks.push({ type: 'list', items: listItems })
    listItems = []
  }

  for (const rawLine of lines) {
    const bulletMatch = rawLine.match(LIST_ITEM_RE)
    if (bulletMatch) {
      flushParagraph()
      const item = bulletMatch[1].trim()
      if (item) listItems.push(item)
      continue
    }

    flushList()
    const line = rawLine.trimEnd()
    if (!line.trim()) {
      flushParagraph()
      continue
    }
    paragraphLines.push(line)
  }

  flushParagraph()
  flushList()

  return blocks
}
