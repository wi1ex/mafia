import { ref, type Ref, watch } from 'vue'
import {
  LocalTrackPublication,
  RemoteParticipant,
  RemoteTrack,
  RemoteTrackPublication,
  Room as LkRoom,
  RoomEvent,
  Track,
  VideoPreset,
  VideoPresets,
  ScreenSharePresets,
  VideoQuality,
  createLocalScreenTracks,
  type LocalTrack,
  setLogLevel,
  LogLevel,
} from 'livekit-client'

setLogLevel(LogLevel.error)

export type DeviceKind = 'audioinput' | 'videoinput'
export type VQ = 'sd' | 'hd'
export type CameraQuality = 'low' | 'high' | 'super'
const LS = {
  mic: 'audioDeviceId',
  cam: 'videoDeviceId',
  vq: 'room:videoQuality',
  perm: 'mediaPermProbed',
  mirror: 'room:mirror',
}

const BGM_VOLUME_LS = 'bgm:volume'
const BGM_DEFAULT_VOLUME = 50
const BGM_MAX_VOLUME = 1
const BGM_FILES = Object.entries(
  import.meta.glob('@/assets/music/*.mp3', { eager: true, as: 'url' })
)
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([, v]) => v as string)

const error = (...a: unknown[]) => console.error('[RTC]', ...a)

const UA = navigator.userAgent || ''
const isIOS = /iPad|iPhone|iPod/.test(UA) || (UA.includes('Macintosh') && navigator.maxTouchPoints > 1)

const saveLS = (k: string, v: string) => { try { localStorage.setItem(k, v) } catch {} }
const loadLS = (k: string) => { try { return localStorage.getItem(k) } catch { return null } }

type PermState = { audio: boolean; video: boolean }
function readPermState(): PermState {
  const raw = loadLS(LS.perm)
  if (!raw) return { audio: false, video: false }
  if (raw === '1') return { audio: true, video: true }
  try {
    const parsed = JSON.parse(raw)
    return { audio: parsed?.audio === true, video: parsed?.video === true }
  } catch {
    return { audio: false, video: false }
  }
}

export type UseRTC = {
  lk: Ref<LkRoom | null>
  localId: Ref<string>
  peerIds: Ref<string[]>
  mics: Ref<MediaDeviceInfo[]>
  cams: Ref<MediaDeviceInfo[]>
  LS: typeof LS
  saveLS: (k: string, v: string) => void
  loadLS: (k: string) => string | null
  selectedMicId: Ref<string>
  selectedCamId: Ref<string>
  remoteQuality: Ref<VQ>
  setCameraQuality: (quality: CameraQuality) => Promise<void>
  videoRef: (id: string) => (el: HTMLVideoElement | null) => void
  reconnecting: Ref<boolean>
  screenVideoRef: (id: string) => (el: HTMLVideoElement | null) => void
  prepareScreenShare: (opts?: { audio?: boolean }) => Promise<boolean>
  publishPreparedScreen: () => Promise<boolean>
  cancelPreparedScreen: () => Promise<void>
  stopScreenShare: () => Promise<void>
  screenKey: (id: string) => string
  isScreenKey: (key: string) => boolean
  startScreenShare: (opts?: { audio?: boolean }) => Promise<boolean>
  getLastScreenShareError: () => 'canceled' | 'failed' | null
  initRoom: (opts?: {
    onScreenShareEnded?: () => void | Promise<void>
    onRemoteScreenShareEnded?: (id: string) => void | Promise<void>
    publishDefaults?: ConstructorParameters<typeof LkRoom>[0]['publishDefaults']
    audioCaptureDefaults?: ConstructorParameters<typeof LkRoom>[0]['audioCaptureDefaults']
    videoCaptureDefaults?: ConstructorParameters<typeof LkRoom>[0]['videoCaptureDefaults']
    onDisconnected?: () => void | Promise<void>
  }) => LkRoom
  connect: (wsUrl: string, token: string, opts?: {
    autoSubscribe?: boolean
    maxRetries?: number
    peerConnectionTimeout?: number
    websocketTimeout?: number
  }) => Promise<void>
  disconnect: () => Promise<void>
  setAudioSubscriptionsForAll: (on: boolean) => void
  setVideoSubscriptionsForAll: (on: boolean) => void
  setRemoteQualityForAll: (q: VQ, opts?: { persist?: boolean }) => void
  refreshDevices: () => Promise<void>
  fallback: (kind: DeviceKind) => Promise<void>
  onDeviceChange: (kind: DeviceKind) => Promise<void>
  enable: (kind: DeviceKind) => Promise<boolean>
  permAudio: Ref<boolean>
  permVideo: Ref<boolean>
  permProbed: Ref<boolean>
  probePermissions: (opts?: { audio?: boolean; video?: boolean | MediaTrackConstraints }) => Promise<boolean>
  clearProbeFlag: () => void
  hasAudioInput: Ref<boolean>
  hasVideoInput: Ref<boolean>
  disable: (kind: DeviceKind) => Promise<void>
  isSpeaking: (id: string) => boolean
  setUserVolume: (id: string, v: number) => void
  getUserVolume: (id: string) => number
  resumeAudio: (opts?: { force?: boolean }) => Promise<void>
  primeAudioOnGesture: () => void
  startAudio: () => Promise<boolean>
  autoplayUnlocked: Ref<boolean>
  bgmVolume: Ref<number>
  setBgmSeed: (seed: unknown, fallback?: number) => void
  setBgmPlaying: (on: boolean) => void
  ensureBgmPlayback: () => void
  unlockBgmOnGesture: () => Promise<void>
  destroyBgm: () => void
  cleanupPeer: (id: string) => void
}

export function useRTC(): UseRTC {
  let connectInFlight: Promise<void> | null = null
  const lk = ref<LkRoom | null>(null)
  const localId = ref('')
  const peerIds = ref<string[]>([])
  const videoEls = new Map<string, HTMLVideoElement>()
  const audioEls = new Map<string, HTMLAudioElement>()
  const screenVideoEls = new Map<string, HTMLVideoElement>()
  const mics = ref<MediaDeviceInfo[]>([])
  const cams = ref<MediaDeviceInfo[]>([])
  const selectedMicId = ref<string>('')
  const selectedCamId = ref<string>('')
  const wantAudio = ref(true)
  const wantVideo = ref(true)
  const permInit = readPermState()
  const permAudio = ref<boolean>(permInit.audio)
  const permVideo = ref<boolean>(permInit.video)
  const permProbed = ref<boolean>(permInit.audio || permInit.video)
  const hasAudioInput = ref(false)
  const hasVideoInput = ref(false)
  const activeSpeakers = ref<Set<string>>(new Set())
  const audibleIds = ref<Set<string>>(new Set())
  const reconnecting = ref<boolean>(false)
  const bgmVolume = ref<number>(loadBgmVolume())
  const bgmAudio = ref<HTMLAudioElement | null>(null)
  const bgmCurrentSrc = ref<string>('')
  const bgmSeed = ref<number>(0)
  const bgmShouldPlay = ref<boolean>(false)
  let bgmCtx: AudioContext | null = null
  let bgmGain: GainNode | null = null
  let bgmSource: MediaElementAudioSourceNode | null = null
  let bgmUnlocked = false
  const keepBgmAlive = isIOS

  const screenKey = (id: string) => `${id}#s`
  const isScreenKey = (key: string) => key.endsWith('#s')
  const isSub = (pub: RemoteTrackPublication) => pub.isSubscribed
  const lowVideoQuality = new VideoPreset(320, 180, 150_000, 30)
  const highVideoQuality = new VideoPreset(640, 360, 450_000, 30)
  const superVideoQuality = VideoPresets.h720
  const highScreenQuality = ScreenSharePresets.h720fps30
  const cameraQuality = ref<CameraQuality>('high')
  const cameraPresetFor = (quality: CameraQuality) => {
    if (quality === 'low') return lowVideoQuality
    if (quality === 'super') return superVideoQuality
    return highVideoQuality
  }
  const cameraPreset = () => cameraPresetFor(cameraQuality.value)
  const cameraOptions = (deviceId?: string) => ({
    deviceId: deviceId ? ({ exact: deviceId } as any) : undefined,
    resolution: cameraPreset().resolution,
  } as any)
  const cameraPublishOptions = () => ({
    simulcast: false,
    videoSimulcastLayers: undefined,
    videoEncoding: cameraPreset().encoding,
  })
  let lastScreenShareError: 'canceled' | 'failed' | null = null
  const isUserCancel = (e: any) => {
    const n = e?.name
    if (n === 'NotAllowedError' || n === 'AbortError' || n === 'NotFoundError') return true
    const msg = String(e?.message || '').toLowerCase()
    return msg.includes('permission dismissed') || msg.includes('user cancelled') || msg.includes('user canceled')
  }

  type RefDeps = {
    elMap: Map<string, HTMLVideoElement>
    source: Track.Source
  }
  type SrcWrap = {
    node: MediaStreamAudioSourceNode
    stream: MediaStream
  }
  const gainNodes = new Map<string, GainNode>()
  const msrcNodes = new Map<string, SrcWrap>()
  const volumePrefs = new Map<string, number>()
  const VOL_LS = (id: string) => `vol:${id}`
  const lsWriteTimers = new Map<string, number>()
  let audioCtx: AudioContext | null = null
  let waState: 0 | 1 | -1 = 0
  const getCtx = () => (audioCtx ??= new (window.AudioContext || (window as any).webkitAudioContext)())
  function webAudioAvailable(): boolean {
    if (isIOS) return false
    if (waState === -1) return false
    try {
      getCtx()
      waState = 1
      return true
    } catch (err) {
      const name = (err as any)?.name
      if (name === 'NotAllowedError' || name === 'SecurityError') {
        waState = 0
        return false
      }
      waState = -1
      return false
    }
  }

  function getSavedVol(id: string): number {
    try {
      const v = localStorage.getItem(VOL_LS(id))
      if (!v) return 100
      const n = +v
      return Number.isFinite(n) ? Math.min(200, Math.max(0, n)) : 100
    } catch { return 100 }
  }

  function setSavedVol(id: string, v: number) {
    const vv = Math.min(200, Math.max(0, Math.round(v)))
    volumePrefs.set(id, vv)
    const prev = lsWriteTimers.get(id)
    if (prev) window.clearTimeout(prev)
    const t = window.setTimeout(() => {
      try { localStorage.setItem(VOL_LS(id), String(vv)) } catch {}
      lsWriteTimers.delete(id)
    }, 500)
    lsWriteTimers.set(id, t)
  }

  function clampBgmVolume(v: number) {
    if (!Number.isFinite(v)) return BGM_DEFAULT_VOLUME
    return Math.min(100, Math.max(0, Math.round(v)))
  }
  function loadBgmVolume(): number {
    if (typeof window === 'undefined') return BGM_DEFAULT_VOLUME
    try {
      const raw = window.localStorage.getItem(BGM_VOLUME_LS)
      if (raw == null) return BGM_DEFAULT_VOLUME
      const parsed = Number(raw)
      return clampBgmVolume(parsed)
    } catch {
      return BGM_DEFAULT_VOLUME
    }
  }
  function saveBgmVolume(v: number) {
    if (typeof window === 'undefined') return
    try { window.localStorage.setItem(BGM_VOLUME_LS, String(v)) } catch {}
  }
  function resolveBgmUrl(src: string) {
    if (typeof window === 'undefined') return src
    try { return new URL(src, window.location.origin).toString() } catch { return src }
  }
  function ensureBgmContext(): AudioContext | null {
    if (bgmCtx) return bgmCtx
    try {
      bgmCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
      return bgmCtx
    } catch {
      bgmCtx = null
      return null
    }
  }
  function ensureBgmGraph(el: HTMLAudioElement) {
    const ctx = ensureBgmContext()
    if (!ctx) return
    if (!bgmGain) {
      bgmGain = ctx.createGain()
      bgmGain.connect(ctx.destination)
    }
    if (bgmSource && (bgmSource as any).mediaElement === el) return
    if (bgmSource) {
      try { bgmSource.disconnect() } catch {}
    }
    try {
      bgmSource = ctx.createMediaElementSource(el)
      bgmSource.connect(bgmGain)
    } catch {}
  }
  async function resumeBgmAudio() {
    const ctx = ensureBgmContext()
    if (!ctx) return
    if (ctx.state === 'suspended') {
      try { await ctx.resume() } catch {}
    }
  }
  function pickSeededBgmSource(seedBase: number): string {
    if (!BGM_FILES.length) return ''
    const idx = Math.abs(seedBase) % BGM_FILES.length
    return BGM_FILES[idx]
  }
  function setBgmSeed(seed: unknown, fallback = 0) {
    const n = Number(seed)
    const base = Number.isFinite(n) ? Math.floor(n) : Number(fallback || 0)
    bgmSeed.value = Number.isFinite(base) ? Math.floor(base) : 0
    bgmCurrentSrc.value = ''
    if (bgmShouldPlay.value) ensureBgmPlayback()
  }
  function ensureBgmAudio(): HTMLAudioElement {
    if (bgmAudio.value) return bgmAudio.value
    const el = new Audio()
    el.loop = true
    el.preload = 'auto'
    ;(el as any).playsInline = true
    bgmAudio.value = el
    ensureBgmGraph(el)
    applyBgmVolume()
    return el
  }
  function applyBgmVolume() {
    const el = bgmAudio.value
    if (!el) return
    const scaled = (clampBgmVolume(bgmVolume.value) / 100) * BGM_MAX_VOLUME
    const vol = Math.min(1, Math.max(0, scaled))
    const muted = vol <= 0
    if (bgmGain) {
      bgmGain.gain.value = muted ? 0 : vol
      el.volume = 1
    } else {
      el.volume = vol
    }
    el.muted = muted
  }
  function stopBgm() {
    const el = bgmAudio.value
    if (!el) return
    if (keepBgmAlive && bgmUnlocked) {
      el.muted = true
      if (bgmGain) bgmGain.gain.value = 0
      else el.volume = 0
      return
    }
    try { el.pause() } catch {}
    try { el.currentTime = 0 } catch {}
    bgmCurrentSrc.value = ''
  }
  function destroyBgm() {
    const el = bgmAudio.value
    if (!el) return
    stopBgm()
    try { el.src = '' } catch {}
    bgmAudio.value = null
    if (bgmSource) {
      try { bgmSource.disconnect() } catch {}
      bgmSource = null
    }
    if (bgmGain) {
      try { bgmGain.disconnect() } catch {}
      bgmGain = null
    }
    if (bgmCtx) {
      try { void bgmCtx.close() } catch {}
      bgmCtx = null
    }
    bgmUnlocked = false
  }
  function ensureBgmPlayback() {
    if (!bgmShouldPlay.value) {
      stopBgm()
      return
    }
    if (!BGM_FILES.length) {
      stopBgm()
      return
    }
    const el = ensureBgmAudio()
    if (!bgmCurrentSrc.value) {
      const base = bgmSeed.value || 0
      bgmCurrentSrc.value = pickSeededBgmSource(base)
    }
    const src = bgmCurrentSrc.value
    if (!src) return
    const resolved = resolveBgmUrl(src)
    if (resolved && el.src !== resolved) {
      el.src = src
      try { el.currentTime = 0 } catch {}
    }
    applyBgmVolume()
    void resumeBgmAudio()
    void el.play().then(() => { bgmUnlocked = true }).catch(() => {})
  }
  async function unlockBgmOnGesture() {
    if (!keepBgmAlive) return
    if (bgmUnlocked) return
    if (!BGM_FILES.length) return
    const el = ensureBgmAudio()
    ensureBgmGraph(el)
    await resumeBgmAudio()
    if (!bgmCurrentSrc.value) {
      const base = bgmSeed.value || 0
      bgmCurrentSrc.value = pickSeededBgmSource(base)
    }
    const src = bgmCurrentSrc.value
    if (!src) return
    const resolved = resolveBgmUrl(src)
    if (resolved && el.src !== resolved) {
      el.src = src
      try { el.currentTime = 0 } catch {}
    }
    el.muted = true
    if (bgmGain) bgmGain.gain.value = 0
    else el.volume = 0
    try {
      await el.play()
      bgmUnlocked = true
    } catch {}
  }
  function setBgmPlaying(on: boolean) {
    const prev = bgmShouldPlay.value
    if (on === prev) return
    bgmShouldPlay.value = on
    if (!on) {
      stopBgm()
      return
    }
    if (!prev) {
      if (keepBgmAlive && bgmUnlocked) {
        if (bgmAudio.value) try { bgmAudio.value.currentTime = 0 } catch {}
      } else {
        bgmCurrentSrc.value = ''
      }
    }
    ensureBgmPlayback()
  }

  watch(bgmVolume, (v) => {
    const next = clampBgmVolume(v)
    if (next !== v) {
      bgmVolume.value = next
      return
    }
    saveBgmVolume(next)
    applyBgmVolume()
  }, { immediate: true })

  function ensureGainFor(id: string, el: HTMLAudioElement): GainNode {
    const ctx = getCtx()
    let g = gainNodes.get(id)
    if (!g) {
      g = ctx.createGain()
      gainNodes.set(id, g)
      g.connect(ctx.destination)
    }
    const stream = el.srcObject as MediaStream | null
    if (stream) {
      const wrap = msrcNodes.get(id)
      if (!wrap || wrap.stream !== stream) {
        try { wrap?.node.disconnect() } catch {}
        const src = new MediaStreamAudioSourceNode(ctx, { mediaStream: stream })
        src.connect(g)
        msrcNodes.set(id, { node: src, stream })
      }
    } else {
      try { msrcNodes.get(id)?.node.disconnect() } catch {}
      msrcNodes.delete(id)
      el.muted = true
      el.volume = 0
    }
    el.muted = true
    el.volume = 0
    return g
  }

  function applyVolume(id: string, v?: number) {
    const a = audioEls.get(id)
    if (!a) return
    const want = v ?? volumePrefs.get(id) ?? getSavedVol(id)

    if (webAudioAvailable()) {
      try {
        const ctx = getCtx()
        const g = ensureGainFor(id, a)
        const gain = Math.max(0, want / 100)
        const now = ctx.currentTime || 0
        try { g.gain.cancelScheduledValues(now) } catch {}
        g.gain.setTargetAtTime(gain, now, 0.01)
        a.muted = true
        a.volume = 0
        return
      } catch {
        waState = -1
      }
    }
    destroyAudioGraph(id)
    a.muted = false
    a.volume = Math.min(1, Math.max(0, ((want ?? 100) / 100)))
  }

  function setUserVolume(id: string, v: number) {
    const vv = Math.min(200, Math.max(0, Math.round(v)))
    const cur = volumePrefs.get(id) ?? getSavedVol(id)
    if (cur === vv) return
    setSavedVol(id, vv)
    applyVolume(id, vv)
  }
  function getUserVolume(id: string): number {
    let v = volumePrefs.get(id)
    if (v == null) {
      v = getSavedVol(id)
      volumePrefs.set(id, v)
    }
    return v
  }

  let resumeBusy = false
  let resumeForceQueued = false
  const autoplayUnlocked = ref(false)
  function primeAudioOnGesture() {
    if (isIOS) {
      audioEls.forEach((_el, id) => {
        try { applyVolume(id) } catch {}
      })
      return
    }
    if (waState === -1) waState = 0
    if (!webAudioAvailable()) return
    try {
      const ctx = getCtx()
      if (ctx.state === 'suspended') {
        void ctx.resume().catch(() => {})
      }
      const gain = ctx.createGain()
      gain.gain.value = 0
      gain.connect(ctx.destination)
      const src = ctx.createBufferSource()
      src.buffer = ctx.createBuffer(1, 1, ctx.sampleRate)
      src.connect(gain)
      src.start(0)
      src.onended = () => {
        try { src.disconnect() } catch {}
        try { gain.disconnect() } catch {}
      }
      audioEls.forEach((_el, id) => {
        try { applyVolume(id) } catch {}
      })
    } catch {}
  }
  async function resumeAudio(opts?: { force?: boolean }) {
    const force = opts?.force === true || autoplayUnlocked.value
    if (resumeBusy) {
      if (force) resumeForceQueued = true
      return
    }
    resumeBusy = true
    try {
      const wasUnlocked = autoplayUnlocked.value
      const ua = (navigator as any).userActivation
      const canPrime = !isIOS && (force || !ua || !!(ua?.isActive || ua?.hasBeenActive))
      if (!audioCtx && canPrime) { try { getCtx() } catch {} }
      const ctxResume = (!isIOS && audioCtx && audioCtx.state !== 'running') ? audioCtx.resume().catch(() => {}) : null
      const plays: Promise<unknown>[] = []
      for (const a of audioEls.values()) {
        try { plays.push(a.play()) } catch (err) { plays.push(Promise.reject(err)) }
      }
      if (force) autoplayUnlocked.value = true
      const withTimeout = (p: Promise<unknown>) => Promise.race([
        p,
        new Promise(resolve => { setTimeout(resolve, 500) }),
      ])
      const results = await Promise.allSettled(plays.map(withTimeout))
      if (ctxResume) {
        try {
          await Promise.race([
            ctxResume,
            new Promise(resolve => { setTimeout(resolve, 500) }),
          ])
        } catch {}
      }
      const played = results.some(r => r.status === 'fulfilled')
      const ctxRunning = !!audioCtx && audioCtx.state === 'running'
      const usesWebAudio = waState === 1
      if (!force) {
        const next = usesWebAudio ? ctxRunning : (ctxRunning || played)
        if (next) autoplayUnlocked.value = true
        else if (!wasUnlocked) autoplayUnlocked.value = false
      }
    } finally {
      queueMicrotask(() => {
        resumeBusy = false
        if (resumeForceQueued) {
          resumeForceQueued = false
          void resumeAudio({ force: true })
        }
      })
    }
  }

  async function startAudio(): Promise<boolean> {
    const room = lk.value as any
    if (!room || typeof room.startAudio !== 'function') return false
    try {
      await room.startAudio()
      return true
    } catch {
      return false
    }
  }

  const isSpeaking = (id: string) => {
    if (id === localId.value) return activeSpeakers.value.has(id)
    return activeSpeakers.value.has(id) && audibleIds.value.has(id)
  }

  function refreshAudibleIds() {
    const room = lk.value
    const s = new Set<string>()
    if (!room || !wantAudio.value) {
      audibleIds.value = s
      return
    }
    room.remoteParticipants.forEach(p => {
      const has = p.getTrackPublications().some(pub => pub.kind === Track.Kind.Audio && isSub(pub))
      if (has) s.add(String(p.identity))
    })
    audibleIds.value = s
  }

  const getByIdentity = (room: LkRoom, id: string) => {
    if (typeof room.getParticipantByIdentity === 'function') {
      return room.getParticipantByIdentity(id) ?? undefined
    }
    for (const p of room.remoteParticipants.values()) {
      if (String(p.identity) === id) return p
    }
    return undefined
  }

  function persistPermState() {
    try {
      saveLS(LS.perm, JSON.stringify({ audio: permAudio.value, video: permVideo.value }))
    } catch {}
  }
  function setPermState(next: Partial<PermState>) {
    let changed = false
    if (typeof next.audio === 'boolean' && next.audio !== permAudio.value) {
      permAudio.value = next.audio
      changed = true
    }
    if (typeof next.video === 'boolean' && next.video !== permVideo.value) {
      permVideo.value = next.video
      changed = true
    }
    if (changed) {
      permProbed.value = permAudio.value || permVideo.value
      persistPermState()
    }
  }

  let probeInFlight: Promise<boolean> | null = null
  async function probePermissions(opts?: { audio?: boolean; video?: boolean | MediaTrackConstraints }): Promise<boolean> {
    const audio = opts?.audio ?? true
    const video = opts?.video ?? true
    if (!audio && !video) return true
    if (probeInFlight) return probeInFlight
    probeInFlight = (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio, video })
        stream.getTracks().forEach(t => { try { t.stop() } catch {} })
        await refreshDevices()
        setPermState({
          audio: audio ? true : permAudio.value,
          video: video ? true : permVideo.value,
        })
        return true
      } catch (e:any) {
        error('probePermissions fail', { name: e?.name, message: e?.message })
        setPermState({
          audio: audio ? false : permAudio.value,
          video: video ? false : permVideo.value,
        })
        return false
      } finally {
        probeInFlight = null
      }
    })()
    return probeInFlight
  }

  function clearProbeFlag() { setPermState({ audio: false, video: false }) }

  async function shouldProbeKind(kind: DeviceKind): Promise<boolean> {
    if (kind === 'audioinput' && permAudio.value) return false
    if (kind === 'videoinput' && permVideo.value) return false
    const perms = navigator.permissions
    if (perms?.query) {
      try {
        const name = kind === 'audioinput' ? 'microphone' : 'camera'
        const res = await perms.query({ name: name as PermissionName })
        return res.state !== 'granted'
      } catch {
        return true
      }
    }
    return true
  }

  function buildProbeTargets(kind: DeviceKind): { audio: boolean; video: boolean } {
    const hasAudio = hasAudioInput.value
    const hasVideo = hasVideoInput.value
    if (hasAudio && hasVideo) return { audio: true, video: true }
    if (kind === 'audioinput') return { audio: true, video: false }
    return { audio: false, video: true }
  }

  async function shouldProbeTargets(targets: { audio: boolean; video: boolean }): Promise<boolean> {
    const needAudio = targets.audio && await shouldProbeKind('audioinput')
    const needVideo = targets.video && await shouldProbeKind('videoinput')
    return needAudio || needVideo
  }

  async function disable(kind: DeviceKind) {
    try {
      if (kind === 'audioinput') await lk.value?.localParticipant.setMicrophoneEnabled(false)
      else await lk.value?.localParticipant.setCameraEnabled(false)
    } catch {}
  }

  async function startScreenShare(opts?: { audio?: boolean }): Promise<boolean> {
    const got = await prepareScreenShare(opts)
    if (!got) return false
    const ok = await publishPreparedScreen()
    if (!ok) {
      try { await cancelPreparedScreen() } catch {}
      return false
    }
    lastScreenShareError = null
    return true
  }

  let preparedScreen: LocalTrack[] | null = null
  const screenVideoRef = makeVideoRef({ elMap: screenVideoEls, source: Track.Source.ScreenShare })
  function attachScreenTrackEndedHandlers(tracks: LocalTrack[]) {
    tracks.forEach(t => {
      const onEnded = async () => { try { await lk.value?.localParticipant.unpublishTrack(t) } catch {} }
      t.mediaStreamTrack.addEventListener('ended', onEnded, { once: true })
    })
  }
  async function createScreenTracks(audio: boolean): Promise<LocalTrack[]> {
    const tracks = await createLocalScreenTracks({ audio, resolution: highScreenQuality.resolution })
    attachScreenTrackEndedHandlers(tracks)
    return tracks
  }
  async function prepareScreenShare(opts?: { audio?: boolean }): Promise<boolean> {
    try {
      lastScreenShareError = null
      preparedScreen = await createScreenTracks(opts?.audio ?? true)
      return true
    } catch (e: any) {
      if (isUserCancel(e)) {
        lastScreenShareError = 'canceled'
        preparedScreen = null
        return false
      }
      try {
        preparedScreen = await createScreenTracks(false)
        return true
      } catch (e2: any) {
        lastScreenShareError = isUserCancel(e2) ? 'canceled' : 'failed'
        preparedScreen = null
        return false
      }
    }
  }
  async function publishPreparedScreen(): Promise<boolean> {
    if (!lk.value || !preparedScreen?.length) return false
    const video = preparedScreen.find(t => t.kind === Track.Kind.Video)
    const audio = preparedScreen.find(t => t.kind === Track.Kind.Audio)
    try {
      if (video) {
        await lk.value.localParticipant.publishTrack(video, {
          source: Track.Source.ScreenShare,
          simulcast: false,
          videoEncoding: highScreenQuality.encoding,
        })
      }
    } catch {
      try { preparedScreen.forEach(t => t.stop()) } catch {}
      preparedScreen = null
      lastScreenShareError = 'failed'
      return false
    }
    if (audio) {
      try {
        await lk.value.localParticipant.publishTrack(audio, {
          source: Track.Source.ScreenShareAudio,
        })
      } catch {
        try { audio.stop() } catch {}
      }
    }
    preparedScreen = null
    return true
  }
  async function cancelPreparedScreen() {
    try { preparedScreen?.forEach(t => t.stop()) } catch {}
    preparedScreen = null
  }

  async function stopScreenShare() {
    try { await lk.value?.localParticipant.setScreenShareEnabled(false) } catch {}
  }

  function setBaseVideoAttrs(el: HTMLVideoElement, self: boolean) {
    el.autoplay = true
    el.playsInline = true
    el.muted = self
  }
  function attachBySource(room: LkRoom, id: string, src: Track.Source, el: HTMLVideoElement) {
    const p =
      getByIdentity(room, id) ??
      (String(room.localParticipant.identity) === id ? room.localParticipant : undefined)
    p?.getTrackPublications()?.forEach(pub => {
      const rp = pub as RemoteTrackPublication
      if (pub.kind === Track.Kind.Video && rp.source === src && pub.track) {
        try { pub.track.attach(el) } catch {}
      }
    })
  }
  function makeVideoRef(deps: RefDeps) {
    return (id: string) => (el: HTMLVideoElement|null) => {
      const prev = deps.elMap.get(id)
      if (!el) {
        if (prev) { try { prev.srcObject = null } catch {} }
        deps.elMap.delete(id)
        return
      }
      if (prev && prev !== el) { try { prev.srcObject = null } catch {} }
      setBaseVideoAttrs(el, id===localId.value)
      deps.elMap.set(id, el)
      const room = lk.value
      if (!room) return
      attachBySource(room, id, deps.source, el)
    }
  }

  const videoRef = makeVideoRef({ elMap: videoEls, source: Track.Source.Camera })

  function destroyAudioGraph(id: string) {
    const w = msrcNodes.get(id)
    try { w?.node.disconnect() } catch {}
    msrcNodes.delete(id)
    try { gainNodes.get(id)?.disconnect() } catch {}
    gainNodes.delete(id)
  }

  function ensureAudioEl(id: string): HTMLAudioElement {
    let a = audioEls.get(id)
    if (!a) {
      a = new Audio()
      a.autoplay = true
      a.playsInline = true
      a.muted = true
      a.style.display = 'none'
      audioEls.set(id, a)
      document.body.appendChild(a)
      applyVolume(id)
    }
    return a
  }

  async function onDeviceChange(kind: DeviceKind) {
    const id = kind === 'audioinput' ? selectedMicId.value : selectedCamId.value
    if (!id) return
    saveLS(kind === 'audioinput' ? LS.mic : LS.cam, id)
    const room = lk.value
    if (!room) return
    const pubs = room.localParticipant.getTrackPublications()
    const enabled = pubs.some(pub => kind === 'audioinput'
      ? pub.kind === Track.Kind.Audio && (pub as any).source === Track.Source.Microphone && !!pub.track
      : pub.kind === Track.Kind.Video && (pub as any).source === Track.Source.Camera && !!pub.track
    )
    if (!enabled) return
    try { await room.switchActiveDevice(kind, id) } catch {}
  }

  async function fallback(kind: DeviceKind): Promise<void> {
    await refreshDevices()
    const list = kind === 'audioinput' ? mics.value : cams.value
    const setEnabled = (on: boolean) => {
      if (kind === 'audioinput') return lk.value?.localParticipant.setMicrophoneEnabled(on)
      if (!on) return lk.value?.localParticipant.setCameraEnabled(false)
      return lk.value?.localParticipant.setCameraEnabled(true, cameraOptions(), cameraPublishOptions())
    }
    if (list.length === 0) {
      try { await setEnabled(false) } catch {}
      if (kind === 'audioinput') {
        selectedMicId.value = ''
        saveLS(LS.mic, '')
      } else {
        selectedCamId.value = ''
        saveLS(LS.cam, '')
      }
      return
    }
    const id = list[0].deviceId
    try { await lk.value?.switchActiveDevice(kind, id) } catch {}
    if (kind === 'audioinput') {
      selectedMicId.value = id
      saveLS(LS.mic, id)
    } else {
      selectedCamId.value = id
      saveLS(LS.cam, id)
    }
  }

  async function refreshDevices() {
    try {
      const list = await navigator.mediaDevices.enumerateDevices()
      mics.value = list.filter(d => d.kind === 'audioinput')
      cams.value = list.filter(d => d.kind === 'videoinput')
      const micLabelsKnown = mics.value.some(d => (d.label ?? '').trim().length > 0)
      const camLabelsKnown = cams.value.some(d => (d.label ?? '').trim().length > 0)
      if (!isIOS) {
        if (micLabelsKnown) setPermState({ audio: true })
        if (camLabelsKnown) setPermState({ video: true })
      }
      const perms = navigator.permissions
      if (perms?.query) {
        try {
          const [camPerm, micPerm] = await Promise.all([
            perms.query({ name: 'camera' as PermissionName }),
            perms.query({ name: 'microphone' as PermissionName }),
          ])
          if (micPerm.state === 'granted') setPermState({ audio: true })
          if (micPerm.state === 'denied') setPermState({ audio: false })
          if (camPerm.state === 'granted') setPermState({ video: true })
          if (camPerm.state === 'denied') setPermState({ video: false })
        } catch {}
      }
      hasAudioInput.value = mics.value.length > 0
      hasVideoInput.value = cams.value.length > 0
      if (!mics.value.find(d => d.deviceId === selectedMicId.value)) {
        const fromLS = loadLS(LS.mic)
        selectedMicId.value = (fromLS && mics.value.find(d => d.deviceId === fromLS)) ? fromLS : (mics.value[0]?.deviceId || '')
      }
      if (!cams.value.find(d => d.deviceId === selectedCamId.value)) {
        const fromLS = loadLS(LS.cam)
        selectedCamId.value = (fromLS && cams.value.find(d => d.deviceId === fromLS)) ? fromLS : (cams.value[0]?.deviceId || '')
      }
    } catch (e) {
      error('refreshDevices', e)
      setPermState({ audio: false, video: false })
    }
  }

  async function enableWithFallback(room: LkRoom, kind: DeviceKind): Promise<boolean> {
    if ((kind === 'audioinput' ? mics.value.length : cams.value.length) === 0) {
      try {
        const perms = kind === 'audioinput' ? { audio: true, video: false } : { audio: false, video: true }

        // await navigator.mediaDevices.getUserMedia(perms)
        const stream = await navigator.mediaDevices.getUserMedia(perms)
        try { stream.getTracks().forEach(t => { try { t.stop() } catch {} }) } catch {}

        await refreshDevices()
        if ((kind === 'audioinput' ? mics.value.length : cams.value.length) === 0) {
          setPermState(kind === 'audioinput' ? { audio: false } : { video: false })
          return false
        }
        setPermState(kind === 'audioinput' ? { audio: true } : { video: true })
      } catch (e:any) {
        error('enable: gUM to populate devices failed', { kind, name: e?.name })
        setPermState(kind === 'audioinput' ? { audio: false } : { video: false })
        return false
      }
    }
    let id = kind === 'audioinput' ? selectedMicId.value : selectedCamId.value
    if (!id) {
      await fallback(kind)
      id = kind === 'audioinput' ? selectedMicId.value : selectedCamId.value
      if (!id) {
        error('enable: no device id', { kind })
        return false
      }
    }
    try {
      if (kind === 'audioinput') {
        await room.localParticipant.setMicrophoneEnabled(true, audioOptionsFor(id))
      } else {
        await room.localParticipant.setCameraEnabled(true, cameraOptions(id), cameraPublishOptions())
      }
      setPermState(kind === 'audioinput' ? { audio: true } : { video: true })
      return true
    } catch (e:any) {
      error('enable exact failed', { kind, id, name: e?.name })
      if (e?.name === 'NotAllowedError' || e?.name === 'SecurityError' || e?.name === 'AbortError' || e?.name === 'NotReadableError') {
        setPermState(kind === 'audioinput' ? { audio: false } : { video: false })
      }
      await fallback(kind)
      const nextId = kind === 'audioinput' ? selectedMicId.value : selectedCamId.value
      if (!nextId) return false
      try {
        if (kind === 'audioinput') {
          await room.localParticipant.setMicrophoneEnabled(true, audioOptionsFor(nextId))
        } else {
          await room.localParticipant.setCameraEnabled(true, cameraOptions(nextId), cameraPublishOptions())
        }
        setPermState(kind === 'audioinput' ? { audio: true } : { video: true })
        return true
      } catch (e2:any) {
        error('enable retry exact failed', { kind, name: e2?.name })
        try {
          if (kind === 'audioinput') await room.localParticipant.setMicrophoneEnabled(true, audioOptionsFor(undefined))
          else await room.localParticipant.setCameraEnabled(true, cameraOptions(), cameraPublishOptions())
          setPermState(kind === 'audioinput' ? { audio: true } : { video: true })
          return true
        } catch (e3:any) {
          error('enable final failed', { kind, name: e3?.name, message: e3?.message })
          if (e3?.name === 'NotAllowedError' || e3?.name === 'SecurityError' || e3?.name === 'AbortError' || e3?.name === 'NotReadableError') {
            setPermState(kind === 'audioinput' ? { audio: false } : { video: false })
          }
          return false
        }
      }
    }
  }

  async function setCameraQuality(quality: CameraQuality): Promise<void> {
    const next = quality === 'low' || quality === 'super' ? quality : 'high'
    const changed = cameraQuality.value !== next
    cameraQuality.value = next
    if (!changed) return

    const room = lk.value
    if (!room) return
    const pub = room.localParticipant.getTrackPublications()
      .find(p => p.kind === Track.Kind.Video && (p as any).source === Track.Source.Camera)
    if (!pub || !pub.track || (pub as any).isMuted) return
    try { await room.localParticipant.unpublishTrack(pub.track) } catch {}
    try { pub.track.stop() } catch {}
    try {
      await room.localParticipant.setCameraEnabled(true, cameraOptions(selectedCamId.value), cameraPublishOptions())
    } catch {
      try {
        await room.localParticipant.setCameraEnabled(true, cameraOptions(), cameraPublishOptions())
      } catch {}
    }
  }

  async function enable(kind: DeviceKind): Promise<boolean> {
    const room = lk.value
    if (!room) {
      error('enable: no room', { kind })
      return false
    }
    const probeTargets = buildProbeTargets(kind)
    if (await shouldProbeTargets(probeTargets)) {
      const ok = await probePermissions(probeTargets)
      if (!ok) return false
    }
    const ok = await enableWithFallback(room, kind)
    if (ok) return true
    const reprobeOk = await probePermissions(probeTargets)
    if (!reprobeOk) return false
    return await enableWithFallback(room, kind)
  }

  const setAudioSubscriptionsForAll = (on: boolean) => {
    wantAudio.value = on
    const room = lk.value
    if (room) {
      room.remoteParticipants.forEach(p => {
        p.getTrackPublications().forEach(pub => {
          if (pub.kind === Track.Kind.Audio) {
            try { pub.setSubscribed(on) } catch {}
          }
        })
      })
    }
    if (!on) {
      audibleIds.value = new Set()
    } else {
      refreshAudibleIds()
      void resumeAudio()
    }
  }
  const setVideoSubscriptionsForAll = (on: boolean) => {
    wantVideo.value = on
    const room = lk.value
    if (!room) return

    room.remoteParticipants.forEach(p => {
      p.getTrackPublications().forEach(pub => {
        if (pub.kind !== Track.Kind.Video) return
        const rpub = pub as RemoteTrackPublication
        const isScreen = rpub.source === Track.Source.ScreenShare
        try {
          rpub.setSubscribed(isScreen || on)
          if (rpub.isSubscribed) applyVideoQuality(rpub)
        } catch {}
      })
    })
  }

  function applyVideoQuality(pub: RemoteTrackPublication) {
    if (pub.kind !== Track.Kind.Video || !pub.isSubscribed) return
    try {
      pub.setVideoQuality(remoteQuality.value === 'hd' ? VideoQuality.HIGH : VideoQuality.LOW)
    } catch {}
  }
  const applySubsFor = (p: RemoteParticipant) => {
    p.getTrackPublications().forEach(pub => {
      if (pub.kind === Track.Kind.Audio) {
        try { pub.setSubscribed(wantAudio.value) } catch {}
        return
      }
      if (pub.kind === Track.Kind.Video) {
        const rpub = pub as RemoteTrackPublication
        const isScreen = rpub.source === Track.Source.ScreenShare
        try {
          rpub.setSubscribed(isScreen || wantVideo.value)
          if (rpub.isSubscribed) applyVideoQuality(rpub)
        } catch {}
      }
    })
  }

  const remoteQuality = ref<VQ>('hd')
  function setRemoteQualityForAll(q: VQ, opts?: { persist?: boolean }) {
    const persist = opts?.persist !== false
    const changed = remoteQuality.value !== q
    if (changed) {
      remoteQuality.value = q
    }
    if (persist) saveLS(LS.vq, q)
    const room = lk.value
    if (!room) return
    room.remoteParticipants.forEach(p => {
      p.getTrackPublications().forEach(pub => {
        if (pub.kind === Track.Kind.Video && pub.isSubscribed) applyVideoQuality(pub as RemoteTrackPublication)
      })
    })
  }

  function audioOptionsFor(deviceId?: string) {
    return {
      deviceId: deviceId ? ({ exact: deviceId } as any) : undefined,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    } as any
  }

  function cleanupPeer(id: string) {
    const aIds = [id, screenKey(id)]
    for (const aid of aIds) {
      const a = audioEls.get(aid)
      if (a) {
        try { a.srcObject = null } catch {}
        try { a.remove() } catch {}
        audioEls.delete(aid)
      }
      const tm = lsWriteTimers.get(aid)
      if (tm) { try { clearTimeout(tm) } catch {} lsWriteTimers.delete(aid) }
      destroyAudioGraph(aid)
      volumePrefs.delete(aid)
    }

    const v = videoEls.get(id)
    if (v) {
      try { v.srcObject = null } catch {}
      videoEls.delete(id)
    }
    const sv = screenVideoEls.get(id)
    if (sv) {
      try { sv.srcObject = null } catch {}
      screenVideoEls.delete(id)
    }

    const sAud = new Set(audibleIds.value)
    sAud.delete(id)
    audibleIds.value = sAud
    const sSpk = new Set(activeSpeakers.value)
    sSpk.delete(id)
    activeSpeakers.value = sSpk

    peerIds.value = peerIds.value.filter(x => x !== id)
  }

  function cleanupMedia() {
    activeSpeakers.value = new Set()
    audibleIds.value = new Set()
    videoEls.forEach(el => { try { el.srcObject = null } catch {} })
    videoEls.clear()
    audioEls.forEach(a => {
      try { a.srcObject = null } catch {}
      try { a.remove() } catch {}
    })
    audioEls.clear()
    screenVideoEls.forEach(el => { try { el.srcObject = null } catch {} })
    screenVideoEls.clear()
    try {
      gainNodes.forEach(g => g.disconnect())
      gainNodes.clear()
    } catch {}
    try {
      msrcNodes.forEach(w => { try { w.node.disconnect() } catch {} })
      msrcNodes.clear()
    } catch {}
    try { audioCtx?.close() } catch {}
    audioCtx = null
    volumePrefs.clear()
    lsWriteTimers.forEach(t => { try { window.clearTimeout(t) } catch {} })
    lsWriteTimers.clear()
    waState = 0
    peerIds.value = []
    localId.value = ''
    try { preparedScreen?.forEach(t => t.stop()) } catch {}
    preparedScreen = null
  }

  function initRoom(opts?: {
    onScreenShareEnded?: () => void | Promise<void>
    onRemoteScreenShareEnded?: (id: string) => void | Promise<void>
    publishDefaults?: ConstructorParameters<typeof LkRoom>[0]['publishDefaults']
    audioCaptureDefaults?: ConstructorParameters<typeof LkRoom>[0]['audioCaptureDefaults']
    videoCaptureDefaults?: ConstructorParameters<typeof LkRoom>[0]['videoCaptureDefaults']
    onDisconnected?: () => void | Promise<void>
  }): LkRoom {
    if (lk.value) {
      const st: string | undefined = (lk.value as any)?.state ?? (lk.value as any)?.connectionState
      if (st === 'disconnected') {
        try { lk.value.removeAllListeners?.() } catch {}
        lk.value = null
      } else {
        return lk.value
      }
    }
    const room = new LkRoom({
      dynacast: true,
      publishDefaults: {
        // videoCodec: 'vp8',
        videoCodec: 'h264',
        red: true,
        dtx: true,
        simulcast: false,
        videoSimulcastLayers: undefined,
        screenShareEncoding: highScreenQuality.encoding,
        screenShareSimulcastLayers: undefined,
        ...(opts?.publishDefaults || {})
      },
      audioCaptureDefaults: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        ...(opts?.audioCaptureDefaults || {})
      },
      videoCaptureDefaults: {
        resolution: highVideoQuality.resolution,
        ...(opts?.videoCaptureDefaults || {})
      },
    })
    lk.value = room

    room.on(RoomEvent.Reconnecting, () => { reconnecting.value = true })

    room.on(RoomEvent.Reconnected, () => {
      reconnecting.value = false
      refreshAudibleIds()
      void resumeAudio()
    })

    room.on(RoomEvent.Disconnected, () => {
      reconnecting.value = false
      cleanupMedia()
      try { room.removeAllListeners?.() } catch {}
      lk.value = null
      try { opts?.onDisconnected?.() } catch {}
    })

    room.on(RoomEvent.LocalTrackPublished, (pub: LocalTrackPublication) => {
      if (pub.kind === Track.Kind.Video && pub.source === Track.Source.ScreenShare) {
        const el = screenVideoEls.get(localId.value)
        if (el && pub.track) { try { pub.track.attach(el) } catch {} }
      }
      if (pub.kind === Track.Kind.Video && pub.source === Track.Source.Camera) {
        const el = videoEls.get(localId.value)
        if (el && pub.track) { try { pub.track.attach(el) } catch {} }
      }
    })

    room.on(RoomEvent.LocalTrackUnpublished, (pub: LocalTrackPublication) => {
      if (pub.kind === Track.Kind.Video && pub.source === Track.Source.ScreenShare) {
        const el = screenVideoEls.get(localId.value)
        if (el && pub.track) { try { pub.track.detach(el) } catch {} }
        try { opts?.onScreenShareEnded?.() } catch {}
      }
      if (pub.kind === Track.Kind.Video && pub.source === Track.Source.Camera) {
        const el = videoEls.get(localId.value)
        if (el && pub.track) { try { pub.track.detach(el) } catch {} }
      }
    })

    room.on(RoomEvent.TrackSubscribed, (t: RemoteTrack, pub, part) => {
      const id = String(part.identity)
      if (t.kind === Track.Kind.Video) {
        if ((pub as RemoteTrackPublication).source === Track.Source.ScreenShare) {
          const el = screenVideoEls.get(id)
          if (el) { try { t.attach(el) } catch {} }
          return
        }
        const el = videoEls.get(id)
        if (el) { try { t.attach(el) } catch {} }
        applyVideoQuality(pub as RemoteTrackPublication)
      } else if (t.kind === Track.Kind.Audio) {
        const isScreenA = (pub as RemoteTrackPublication).source === Track.Source.ScreenShareAudio
        const aid = isScreenA ? screenKey(id) : id
        const a = ensureAudioEl(aid)
        try { t.attach(a) } catch { destroyAudioGraph(aid) }
        try { applyVolume(aid) } catch {}
        try { void resumeAudio() } catch {}
        a.play().catch(() => {})
      }
    })

    room.on(RoomEvent.TrackUnsubscribed, (t: RemoteTrack, pub, part) => {
      const id = String(part.identity)
      if (t.kind === Track.Kind.Video) {
        const isScreenV = (pub as RemoteTrackPublication).source === Track.Source.ScreenShare
        const el = isScreenV ? screenVideoEls.get(id) : videoEls.get(id)
        if (el) { try { t.detach(el) } catch {} }
        if (isScreenV) { try { opts?.onRemoteScreenShareEnded?.(id) } catch {} }
      } else if (t.kind === Track.Kind.Audio) {
        const isScreenA = (pub as RemoteTrackPublication).source === Track.Source.ScreenShareAudio
        const aid = isScreenA ? screenKey(id) : id
        const a = audioEls.get(aid)
        if (a) {
          try { t.detach(a) } catch {}
          a.muted = true
          a.volume = 0
        }
        destroyAudioGraph(aid)
        const tm = lsWriteTimers.get(aid)
        if (tm) {
          try { clearTimeout(tm) } catch {}
          lsWriteTimers.delete(aid)
        }
      }
    })

    room.on(RoomEvent.TrackPublished, (_pub, part) => applySubsFor(part as RemoteParticipant))

    room.on(RoomEvent.ParticipantConnected, (p: RemoteParticipant) => {
      const id = String(p.identity)
      if (!peerIds.value.includes(id)) { peerIds.value = [...peerIds.value, id] }
      applySubsFor(p)
      refreshAudibleIds()
      void resumeAudio()
    })

    room.on(RoomEvent.ParticipantDisconnected, (p) => {
      const id = String(p.identity)
      cleanupPeer(id)
    })

    room.on(RoomEvent.TrackSubscriptionStatusChanged, (pub, _status, _part) => {
      if (pub.kind === Track.Kind.Video && isSub(pub)) {
        applyVideoQuality(pub as RemoteTrackPublication)
      }
      if (pub.kind === Track.Kind.Audio && _part) {
        const id = String(_part.identity)
        const s = new Set(audibleIds.value)
        if (isSub(pub)) s.add(id)
        else s.delete(id)
        audibleIds.value = s
      }
    })

    room.on(RoomEvent.MediaDevicesChanged, refreshDevices)

    room.on(RoomEvent.ActiveSpeakersChanged, (parts) => {
      activeSpeakers.value = new Set(parts.map(p => String(p.identity)))
    })

    return room
  }

  async function connect(wsUrl: string, token: string, opts?: {
    autoSubscribe?: boolean
    maxRetries?: number
    peerConnectionTimeout?: number
    websocketTimeout?: number
  }) {
    const room = lk.value ?? initRoom()
    if (connectInFlight) {
      await connectInFlight
      return
    }
    connectInFlight = (async () => {
      await room.connect(wsUrl, token, {
        autoSubscribe: opts?.autoSubscribe ?? false,
        maxRetries: opts?.maxRetries ?? 5,
        peerConnectionTimeout: opts?.peerConnectionTimeout ?? 8_000,
        websocketTimeout: opts?.websocketTimeout ?? 5_000,
      })

      localId.value = String(room.localParticipant.identity)
      const ids: string[] = [localId.value]
      room.remoteParticipants.forEach(p => ids.push(String(p.identity)))
      peerIds.value = [...new Set([...peerIds.value, ...ids])]

      room.remoteParticipants.forEach(p => applySubsFor(p))
      if (wantAudio.value) { void resumeAudio() }

      await refreshDevices()
      refreshAudibleIds()
    })()
    try { await connectInFlight } finally { connectInFlight = null }
  }

  async function disconnect() {
    reconnecting.value = false
    try {
      const pubs = lk.value?.localParticipant.getTrackPublications() ?? []
      for (const p of pubs) { try { p.track?.stop() } catch {} }
    } catch {}

    try { lk.value?.localParticipant.setMicrophoneEnabled(false) } catch {}
    try { lk.value?.localParticipant.setCameraEnabled(false) } catch {}

    try { await lk.value?.disconnect() } catch {}
    try { lk.value?.removeAllListeners?.() } catch {}
    cleanupMedia()
    lk.value = null
  }

  return {
    lk,
    localId,
    peerIds,
    mics,
    cams,
    LS,
    remoteQuality,
    selectedMicId,
    selectedCamId,
    permAudio,
    permVideo,
    permProbed,
    hasAudioInput,
    hasVideoInput,
    screenVideoRef,
    videoRef,
    reconnecting,
    autoplayUnlocked,
    bgmVolume,

    initRoom,
    connect,
    disconnect,
    setAudioSubscriptionsForAll,
    setVideoSubscriptionsForAll,
    saveLS,
    loadLS,
    refreshDevices,
    fallback,
    onDeviceChange,
    enable,
    probePermissions,
    clearProbeFlag,
    disable,
    setCameraQuality,
    setRemoteQualityForAll,
    isSpeaking,
    setUserVolume,
    getUserVolume,
    resumeAudio,
    primeAudioOnGesture,
    startAudio,
    setBgmSeed,
    setBgmPlaying,
    ensureBgmPlayback,
    unlockBgmOnGesture,
    destroyBgm,
    prepareScreenShare,
    publishPreparedScreen,
    cancelPreparedScreen,
    stopScreenShare,
    screenKey,
    isScreenKey,
    startScreenShare,
    getLastScreenShareError: () => lastScreenShareError,
    cleanupPeer,
  }
}
