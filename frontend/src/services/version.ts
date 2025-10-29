let started = false
let timer: number | null = null

function makeVerUrl(buildId: string) {
  const base = (import.meta as any).env?.BASE_URL || '/'
  const root = base.endsWith('/') ? base : base + '/'
  return `${root}version.txt?b=${encodeURIComponent(buildId)}&t=${Date.now()}`
}

async function poll(buildId: string) {
  try {
    const url = makeVerUrl(buildId)
    const r = await fetch(url, { cache: 'no-store' })
    if (!r.ok) {
      console.warn('version.txt fetch', r.status)
      return
    }
    const v = (await r.text()).trim()
    if (v && v !== buildId) location.reload()
  } catch (e) {
    console.warn('version.txt error', e)
  }
}

function start(buildId: string) {
  if (started) return
  started = true
  const run = () => void poll(buildId)
  const arm = () => {
    if (timer != null) return
    run()
    timer = window.setInterval(run, 60_000)
  }
  const disarm = () => {
    if (timer != null) {
      clearInterval(timer)
      timer = null
    }
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) disarm()
    else arm()
  })
  window.addEventListener('online', run)
  if (!document.hidden) arm()
  else run()
}

export function installVersionWatcher(buildId: string) {
  if (!buildId) {
    console.warn('BUILD_ID is empty')
    return
  }
  start(buildId)
}
