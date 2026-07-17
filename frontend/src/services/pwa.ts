import { reactive, readonly } from 'vue'

export type InstallPromptChoice = {
  outcome: 'accepted' | 'dismissed'
  platform: string
}

export type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<InstallPromptChoice>
}

type PwaInstallState = {
  installed: boolean
  deferredPrompt: BeforeInstallPromptEvent | null
}

const installState = reactive<PwaInstallState>({
  installed: false,
  deferredPrompt: null,
})

let trackingInstalled = false

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

function syncInstalledState(): void {
  installState.installed = isPwaMode()
  if (installState.installed) installState.deferredPrompt = null
}

export function installPwaTracking(): void {
  if (trackingInstalled || typeof window === 'undefined') return
  trackingInstalled = true
  syncInstalledState()

  window.addEventListener('beforeinstallprompt', (event: Event) => {
    event.preventDefault()
    installState.deferredPrompt = event as BeforeInstallPromptEvent
    installState.installed = false
  })

  window.addEventListener('appinstalled', () => {
    installState.installed = true
    installState.deferredPrompt = null
  })

  window.addEventListener('pageshow', syncInstalledState)
  document.addEventListener('visibilitychange', syncInstalledState)
}

export function usePwaInstallState() {
  installPwaTracking()
  return readonly(installState)
}

export async function requestPwaInstall(): Promise<'accepted' | 'dismissed' | 'installed' | 'unavailable'> {
  installPwaTracking()
  if (installState.installed) return 'installed'

  const promptEvent = installState.deferredPrompt
  if (!promptEvent) return 'unavailable'

  installState.deferredPrompt = null

  try {
    await promptEvent.prompt()
    const choice = await promptEvent.userChoice
    return choice?.outcome === 'accepted' ? 'accepted' : 'dismissed'
  } catch {
    return 'unavailable'
  } finally {
    syncInstalledState()
  }
}

export const BASE_TITLE = 'deceit.games — играйте в мафию онлайн и общайтесь в комнатах с трансляциями'
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
