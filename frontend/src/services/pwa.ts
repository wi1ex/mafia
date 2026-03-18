export function isPwaMode(): boolean {
  if (typeof window === 'undefined') return false
  const nav = window.navigator as Navigator & { standalone?: boolean }
  if (nav.standalone) return true
  if (typeof window.matchMedia !== 'function') return false
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.matchMedia('(display-mode: fullscreen)').matches ||
    window.matchMedia('(display-mode: minimal-ui)').matches
  )
}

export const BASE_TITLE = 'Deceit'
export const ROOM_FALLBACK_TITLE = 'Комната'

function ensureMeta(name: string, content: string): void {
  let el = document.querySelector(`meta[name="${name}"]`) as HTMLMetaElement | null
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute('name', name)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

function ensureTitleNode(text: string): void {
  let el = document.querySelector('head > title')
  if (!el) {
    el = document.createElement('title')
    document.head.appendChild(el)
  }
  if (el.textContent !== text) el.textContent = text
}

export function setPageTitle(title?: string, options?: { syncAppleTitle?: boolean }): void {
  const next = String(title || '').trim() || BASE_TITLE
  document.title = next
  ensureTitleNode(next)
  if (options?.syncAppleTitle) ensureMeta('apple-mobile-web-app-title', next)
}
