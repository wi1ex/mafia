/**
 * Temporary, client-side only device-fingerprint diagnostic.
 *
 * It does not send or persist anything.  The report is deliberately emitted to
 * DevTools so it can be compared manually while the matching rules are being
 * designed.  Remove it before making any production decision about devices.
 */

type UaData = {
  brands?: Array<{ brand?: string; version?: string }>
  mobile?: boolean
  platform?: string
  getHighEntropyValues?: (hints: string[]) => Promise<Record<string, unknown>>
}

type NavigatorWithExtras = Navigator & {
  userAgentData?: UaData
  deviceMemory?: number
  connection?: {
    effectiveType?: string
    rtt?: number
    downlink?: number
    saveData?: boolean
  }
  globalPrivacyControl?: boolean
  getBattery?: () => Promise<{
    charging?: boolean
    level?: number
    chargingTime?: number
    dischargingTime?: number
  }>
}

type WebGlInfo = {
  version: string | null
  shadingLanguageVersion: string | null
  vendor: string | null
  renderer: string | null
  unmaskedVendor: string | null
  unmaskedRenderer: string | null
}

function safe<T>(read: () => T, fallback: T | null = null): T | null {
  try { return read() } catch { return fallback }
}

function media(query: string): boolean | null {
  return safe(() => window.matchMedia(query).matches)
}

function getWebGlInfo(): WebGlInfo | null {
  try {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
    if (!gl || !('getParameter' in gl)) return null

    const webgl = gl as WebGLRenderingContext
    const debug = webgl.getExtension('WEBGL_debug_renderer_info') as { UNMASKED_VENDOR_WEBGL: number; UNMASKED_RENDERER_WEBGL: number } | null
    return {
      version: String(webgl.getParameter(webgl.VERSION) || ''),
      shadingLanguageVersion: String(webgl.getParameter(webgl.SHADING_LANGUAGE_VERSION) || ''),
      vendor: String(webgl.getParameter(webgl.VENDOR) || ''),
      renderer: String(webgl.getParameter(webgl.RENDERER) || ''),
      unmaskedVendor: debug ? String(webgl.getParameter(debug.UNMASKED_VENDOR_WEBGL) || '') : null,
      unmaskedRenderer: debug ? String(webgl.getParameter(debug.UNMASKED_RENDERER_WEBGL) || '') : null,
    }
  } catch {
    return null
  }
}

async function sha256(value: string): Promise<string | null> {
  try {
    if (!globalThis.crypto?.subtle) return null
    const bytes = new TextEncoder().encode(value)
    const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes)
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
  } catch {
    return null
  }
}

async function getCanvasHash(): Promise<string | null> {
  try {
    const canvas = document.createElement('canvas')
    canvas.width = 320
    canvas.height = 80
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.textBaseline = 'alphabetic'
    ctx.fillStyle = '#f60'
    ctx.fillRect(11, 1, 62, 20)
    ctx.fillStyle = '#069'
    ctx.font = '17px Arial'
    ctx.fillText('deceit.games / 123', 4, 42)
    ctx.globalCompositeOperation = 'multiply'
    ctx.fillStyle = 'rgba(102, 204, 0, 0.7)'
    ctx.beginPath()
    ctx.arc(86, 36, 21, 0, Math.PI * 2)
    ctx.fill()
    return await sha256(canvas.toDataURL())
  } catch {
    return null
  }
}

async function getAudioHash(): Promise<string | null> {
  try {
    const OfflineContext = window.OfflineAudioContext || (window as typeof window & { webkitOfflineAudioContext?: typeof OfflineAudioContext }).webkitOfflineAudioContext
    if (!OfflineContext) return null
    const context = new OfflineContext(1, 4_410, 44_100)
    const oscillator = context.createOscillator()
    const compressor = context.createDynamicsCompressor()
    oscillator.type = 'triangle'
    oscillator.frequency.value = 10_000
    oscillator.connect(compressor)
    compressor.connect(context.destination)
    oscillator.start(0)
    const buffer = await context.startRendering()
    const samples = buffer.getChannelData(0).slice(0, 512)
    return await sha256(Array.from(samples, (sample) => sample.toFixed(9)).join(','))
  } catch {
    return null
  }
}

async function getBattery(): Promise<Record<string, unknown> | null> {
  try {
    const battery = await (navigator as NavigatorWithExtras).getBattery?.()
    if (!battery) return null
    return {
      charging: battery.charging ?? null,
      level: battery.level ?? null,
      chargingTime: battery.chargingTime ?? null,
      dischargingTime: battery.dischargingTime ?? null,
    }
  } catch {
    return null
  }
}

async function getUaHighEntropy(uaData: UaData | undefined): Promise<Record<string, unknown> | null> {
  try {
    if (!uaData?.getHighEntropyValues) return null
    return await uaData.getHighEntropyValues([
      'architecture', 'bitness', 'model', 'platformVersion', 'uaFullVersion', 'fullVersionList', 'wow64',
    ])
  } catch {
    return null
  }
}

function getFontAvailability(): Record<string, boolean | null> {
  const fonts = ['Arial', 'Calibri', 'Cambria', 'Courier New', 'Georgia', 'Helvetica', 'Menlo', 'Roboto', 'Segoe UI', 'Times New Roman', 'Ubuntu', 'Verdana']
  return Object.fromEntries(fonts.map((font) => [font, safe(() => document.fonts.check(`12px "${font}"`))]))
}

/** Emits a single JSON block which is easy to copy from the browser console. */
export async function logDeviceDiagnostics(source: 'login_completed' | 'home_opened'): Promise<void> {
  try {
    const nav = navigator as NavigatorWithExtras
    const uaData = nav.userAgentData
    const orientation = safe(() => screen.orientation)
    const plugins = safe(() => Array.from(navigator.plugins || [], (plugin) => ({
      name: plugin.name,
      filename: plugin.filename,
      description: plugin.description,
      mimeTypes: Array.from(plugin, (type) => type.type),
    })), [])
    const [uaHighEntropy, canvasHash, audioHash, battery] = await Promise.all([
      getUaHighEntropy(uaData),
      getCanvasHash(),
      getAudioHash(),
      getBattery(),
    ])
    const storage = await safe(async () => await navigator.storage?.estimate(), null)
    const locale = Intl.DateTimeFormat().resolvedOptions()

    const report = {
      diagnostic_version: 1,
      source,
      captured_at: new Date().toISOString(),
      browser: {
        userAgent: navigator.userAgent,
        appVersion: navigator.appVersion,
        platform: navigator.platform,
        vendor: navigator.vendor,
        product: navigator.product,
        productSub: navigator.productSub,
        language: navigator.language,
        languages: Array.from(navigator.languages || []),
        cookieEnabled: navigator.cookieEnabled,
        onLine: navigator.onLine,
        doNotTrack: navigator.doNotTrack,
        globalPrivacyControl: nav.globalPrivacyControl ?? null,
        webdriver: navigator.webdriver,
        pdfViewerEnabled: safe(() => navigator.pdfViewerEnabled),
        userAgentData: uaData ? {
          brands: uaData.brands ?? [],
          mobile: uaData.mobile ?? null,
          platform: uaData.platform ?? null,
          highEntropy: uaHighEntropy,
        } : null,
        plugins,
      },
      device: {
        hardwareConcurrency: navigator.hardwareConcurrency ?? null,
        deviceMemoryGiB: nav.deviceMemory ?? null,
        maxTouchPoints: navigator.maxTouchPoints ?? null,
        screen: {
          width: screen.width,
          height: screen.height,
          availableWidth: screen.availWidth,
          availableHeight: screen.availHeight,
          colorDepth: screen.colorDepth,
          pixelDepth: screen.pixelDepth,
          orientationType: orientation?.type ?? null,
          orientationAngle: orientation?.angle ?? null,
        },
        viewport: {
          innerWidth: window.innerWidth,
          innerHeight: window.innerHeight,
          outerWidth: window.outerWidth,
          outerHeight: window.outerHeight,
          devicePixelRatio: window.devicePixelRatio,
        },
        webgl: getWebGlInfo(),
        canvasSha256: canvasHash,
        audioSha256: audioHash,
        fonts: getFontAvailability(),
      },
      locale: {
        timeZone: locale.timeZone ?? null,
        timeZoneOffsetMinutes: new Date().getTimezoneOffset(),
        locale: locale.locale ?? null,
        calendar: locale.calendar ?? null,
        numberingSystem: locale.numberingSystem ?? null,
        hourCycle: locale.hourCycle ?? null,
      },
      capabilities: {
        localStorage: safe(() => Boolean(window.localStorage)),
        sessionStorage: safe(() => Boolean(window.sessionStorage)),
        indexedDb: Boolean(window.indexedDB),
        serviceWorker: 'serviceWorker' in navigator,
        webRtc: Boolean(window.RTCPeerConnection),
        mediaDevices: Boolean(navigator.mediaDevices),
        bluetooth: 'bluetooth' in navigator,
        usb: 'usb' in navigator,
        hid: 'hid' in navigator,
        serial: 'serial' in navigator,
        xr: 'xr' in navigator,
        storageEstimate: storage ?? null,
        battery,
        connection: nav.connection ? {
          effectiveType: nav.connection.effectiveType ?? null,
          rtt: nav.connection.rtt ?? null,
          downlink: nav.connection.downlink ?? null,
          saveData: nav.connection.saveData ?? null,
        } : null,
      },
      mediaQueries: {
        darkMode: media('(prefers-color-scheme: dark)'),
        reducedMotion: media('(prefers-reduced-motion: reduce)'),
        forcedColors: media('(forced-colors: active)'),
        contrastMore: media('(prefers-contrast: more)'),
        pointerFine: media('(pointer: fine)'),
        pointerCoarse: media('(pointer: coarse)'),
        anyPointerFine: media('(any-pointer: fine)'),
        anyPointerCoarse: media('(any-pointer: coarse)'),
        hover: media('(hover: hover)'),
        anyHover: media('(any-hover: hover)'),
        colorGamutP3: media('(color-gamut: p3)'),
        standalone: media('(display-mode: standalone)'),
      },
    }

    console.groupCollapsed(`[device-diagnostics] ${source}`)
    console.log(report)
    console.log(JSON.stringify(report, null, 2))
    console.groupEnd()
  } catch (error) {
    console.warn('[device-diagnostics] collection failed', error)
  }
}
