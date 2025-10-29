let started = false
let timer: number | null = null

async function poll(buildId: string) {
  try {
    const r = await fetch('/version.txt', { cache: 'no-store' })
    const v = (await r.text()).trim()
    if (v && v !== buildId) location.reload()
  } catch {}
}

function start(buildId: string) {
  if (started) return
  started = true

  const run = () => poll(buildId)

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
  start(buildId || '')
}
