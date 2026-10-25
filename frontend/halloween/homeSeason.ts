import { computed, onMounted, shallowRef } from 'vue'

type HomeSeasonManifest = {
  version: 1
  revision: string
  images: string[]
  decorations: typeof DECORATION_FILES
  stylesheet: 'theme.css'
}

type LoadedHomeSeason = {
  images: string[]
}

const RESOURCE_TIMEOUT_MS = 12000
const EXPECTED_IMAGES = Array.from({ length: 7 }, (_, index) => `carousel-image${index + 1}.png`)
const DECORATION_FILES = {
  buttonFingers: 'button-fingers.png',
  buttonWeb: 'button-web.svg',
  evilPumpkin: 'evil-pumpkin.png',
  logo: 'logo-halloween.svg',
} as const
const DECORATION_PROPERTIES = {
  buttonFingers: '--home-season-button-fingers',
  buttonWeb: '--home-season-button-web',
  evilPumpkin: '--home-season-evil-pumpkin',
  logo: '--home-season-logo',
} as const
const loadedSeason = shallowRef<LoadedHomeSeason | null>(null)
const seasonActive = computed(() => loadedSeason.value !== null)
let loadStarted = false
let cancelled = false
let stylesheet: HTMLLinkElement | null = null

function parseManifest(value: unknown): HomeSeasonManifest {
  if (!value || typeof value !== 'object') throw new Error('Invalid seasonal manifest')
  const manifest = value as Partial<HomeSeasonManifest>
  if (
    manifest.version !== 1 ||
    typeof manifest.revision !== 'string' ||
    !/^[a-zA-Z0-9._-]{1,80}$/.test(manifest.revision) ||
    manifest.stylesheet !== 'theme.css' ||
    !Array.isArray(manifest.images) ||
    manifest.images.length !== EXPECTED_IMAGES.length ||
    !manifest.images.every((filename, index) => filename === EXPECTED_IMAGES[index]) ||
    !manifest.decorations ||
    typeof manifest.decorations !== 'object' ||
    Array.isArray(manifest.decorations) ||
    Object.keys(manifest.decorations).length !== Object.keys(DECORATION_FILES).length ||
    !Object.entries(DECORATION_FILES).every(([key, filename]) => (
      manifest.decorations?.[key as keyof typeof DECORATION_FILES] === filename
    ))
  ) {
    throw new Error('Invalid seasonal manifest')
  }
  return manifest as HomeSeasonManifest
}

async function fetchManifest(url: URL): Promise<HomeSeasonManifest> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), RESOURCE_TIMEOUT_MS)
  try {
    const response = await fetch(url, { cache: 'no-store', signal: controller.signal, credentials: 'same-origin' })
    if (!response.ok) throw new Error('Seasonal manifest unavailable')
    // Parsing and schema validation also reject a dev-server SPA HTML fallback with status 200.
    return parseManifest(await response.json())
  } finally {
    window.clearTimeout(timeout)
  }
}

function preloadImage(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    const finish = (error?: Error) => {
      window.clearTimeout(timeout)
      image.onload = null
      image.onerror = null
      if (error) reject(error)
      else resolve()
    }
    const timeout = window.setTimeout(() => finish(new Error('Seasonal image timed out')), RESOURCE_TIMEOUT_MS)
    image.onerror = () => finish(new Error('Seasonal image unavailable'))
    image.onload = () => {
      if (!image.naturalWidth || !image.naturalHeight) {
        finish(new Error('Invalid seasonal image'))
        return
      }
      image.decode().then(() => finish(), () => finish(new Error('Seasonal image could not be decoded')))
    }
    image.src = url
  })
}

function preloadStylesheet(url: string): Promise<HTMLLinkElement> {
  return new Promise((resolve, reject) => {
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    // Keep the CSS inactive until every seasonal resource has loaded successfully.
    link.media = 'not all'
    link.href = url
    const finish = (error?: Error) => {
      window.clearTimeout(timeout)
      link.onload = null
      link.onerror = null
      if (error) {
        link.remove()
        reject(error)
      } else resolve(link)
    }
    const timeout = window.setTimeout(() => finish(new Error('Seasonal stylesheet timed out')), RESOURCE_TIMEOUT_MS)
    link.onload = () => finish()
    link.onerror = () => finish(new Error('Seasonal stylesheet unavailable'))
    document.head.append(link)
  })
}

export function resetHomeSeason(): void {
  cancelled = true
  loadedSeason.value = null
  document.documentElement.removeAttribute('data-home-season')
  for (const property of Object.values(DECORATION_PROPERTIES)) {
    document.documentElement.style.removeProperty(property)
  }
  stylesheet?.remove()
  stylesheet = null
}

async function loadHomeSeason(): Promise<void> {
  if (loadStarted) return
  loadStarted = true
  try {
    const base = new URL(import.meta.env.BASE_URL, window.location.origin)
    const folder = new URL('seasonal/halloween/', base)
    const manifest = await fetchManifest(new URL('manifest.json', folder))
    // The uncached manifest is the presence gate. A revision keeps large images cacheable
    // while allowing their replacements to bypass the server's immutable asset cache.
    const resourceUrl = (filename: string): string => {
      const url = new URL(filename, folder)
      url.searchParams.set('v', manifest.revision)
      return url.href
    }
    const images = manifest.images.map(resourceUrl)
    const decorations = Object.entries(DECORATION_FILES).map(([key, filename]) => ({
      property: DECORATION_PROPERTIES[key as keyof typeof DECORATION_PROPERTIES],
      url: resourceUrl(filename),
    }))
    await Promise.all([...images, ...decorations.map(({ url }) => url)].map(preloadImage))
    if (cancelled) return
    const link = await preloadStylesheet(resourceUrl(manifest.stylesheet))
    if (cancelled) {
      link.remove()
      return
    }
    stylesheet = link
    for (const { property, url } of decorations) {
      document.documentElement.style.setProperty(property, `url(${JSON.stringify(url)})`)
    }
    link.media = 'all'
    document.documentElement.setAttribute('data-home-season', 'halloween')
    loadedSeason.value = { images }
  } catch {
    // The optional folder may intentionally be absent. Keep the original page in that case.
    resetHomeSeason()
  }
}

export function useHomeSeason() {
  onMounted(() => { void loadHomeSeason() })
  const seasonImage = (index: number, fallback: string): string => loadedSeason.value?.images[index] ?? fallback
  return { seasonActive, seasonImage, resetHomeSeason }
}
