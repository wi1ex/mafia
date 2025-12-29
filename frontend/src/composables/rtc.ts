import { ref, type Ref } from 'vue'
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
const LS = {
  mic: 'audioDeviceId',
  cam: 'videoDeviceId',
  vq: 'room:videoQuality',
  perm: 'mediaPermProbed',
  mirror: 'room:mirror',
}

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
  resumeAudio: () => Promise<void>
  autoplayUnlocked: Ref<boolean>
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

  const screenKey = (id: string) => `${id}#s`
  const isScreenKey = (key: string) => key.endsWith('#s')
  const isSub = (pub: RemoteTrackPublication) => pub.isSubscribed
  const lowVideoQuality = new VideoPreset(320, 180, 150_000, 30)
  const highVideoQuality = new VideoPreset(640, 360, 450_000, 30)
  const highScreenQuality = ScreenSharePresets.h720fps30
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
    if (waState === -1) return false
    try {
      getCtx()
      waState = 1
      return true
    } catch {
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
    a.volume = Math.min(1, Math.max(0, (want || 100) / 100))
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
  const autoplayUnlocked = ref(false)
  async function resumeAudio() {
    if (resumeBusy) return
    resumeBusy = true
    try {
      if (audioCtx && audioCtx.state !== 'running') { await audioCtx.resume() }
      const plays: Promise<unknown>[] = []
      for (const a of audioEls.values()) plays.push(a.play().catch(() => {}))
      await Promise.allSettled(plays)
      autoplayUnlocked.value = true
    } finally {
      queueMicrotask(() => { resumeBusy = false })
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
    const setEnabled = (on: boolean) =>
      kind === 'audioinput'
        ? lk.value?.localParticipant.setMicrophoneEnabled(on)
        : lk.value?.localParticipant.setCameraEnabled(on)
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

  async function enable(kind: DeviceKind): Promise<boolean> {
    const room = lk.value
    if (!room) {
      error('enable: no room', { kind })
      return false
    }
    if (!isIOS && await shouldProbeKind(kind)) {
      const ok = await probePermissions({ audio: kind === 'audioinput', video: kind === 'videoinput' })
      if (!ok) return false
    }
    if ((kind === 'audioinput' ? mics.value.length : cams.value.length) === 0) {
      try {
        const perms = kind === 'audioinput' ? { audio: true, video: false } : { audio: false, video: true }
        await navigator.mediaDevices.getUserMedia(perms)
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
        await room.localParticipant.setCameraEnabled(true, { deviceId: { exact: id }, resolution: highVideoQuality.resolution } as any)
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
          await room.localParticipant.setCameraEnabled(true, { deviceId: { exact: nextId }, resolution: highVideoQuality.resolution } as any)
        }
        setPermState(kind === 'audioinput' ? { audio: true } : { video: true })
        return true
      } catch (e2:any) {
        error('enable retry exact failed', { kind, name: e2?.name })
        try {
          if (kind === 'audioinput') await room.localParticipant.setMicrophoneEnabled(true, audioOptionsFor(undefined))
          else await room.localParticipant.setCameraEnabled(true, { resolution: highVideoQuality.resolution } as any)
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

  const remoteQuality = ref<VQ>((loadLS(LS.vq) as VQ) === 'sd' ? 'sd' : 'hd')
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
        simulcast: true,
        videoSimulcastLayers: [lowVideoQuality, highVideoQuality],
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
    setRemoteQualityForAll,
    isSpeaking,
    setUserVolume,
    getUserVolume,
    resumeAudio,
    autoplayUnlocked,
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
