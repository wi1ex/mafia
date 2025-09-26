import { ref, type Ref } from 'vue'
import {
  LocalTrackPublication,
  RemoteParticipant,
  RemoteTrack,
  RemoteTrackPublication,
  Room as LkRoom,
  RoomEvent,
  Track,
  VideoPresets,
  VideoQuality,
} from 'livekit-client'
import { setLogLevel, LogLevel } from 'livekit-client'

setLogLevel(LogLevel.warn)

type DeviceKind = 'audioinput' | 'videoinput'
type VQ = 'sd'|'hd'
const LS = { mic: 'audioDeviceId', cam: 'videoDeviceId', vq: 'videoQuality' }
const saveLS = (k: string, v: string) => { try { localStorage.setItem(k, v) } catch {} }
const loadLS = (k: string) => { try { return localStorage.getItem(k) } catch { return null } }

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
  initRoom: (opts?: {
    onMediaDevicesError?: (e: unknown) => void
    publishDefaults?: Parameters<typeof LkRoom>[0]['publishDefaults']
    audioCaptureDefaults?: Parameters<typeof LkRoom>[0]['audioCaptureDefaults']
    videoCaptureDefaults?: Parameters<typeof LkRoom>[0]['videoCaptureDefaults']
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
  setRemoteQualityForAll: (q: VQ) => void
  refreshDevices: () => Promise<void>
  isBusyError: (e: unknown) => boolean
  fallback: (kind: DeviceKind) => Promise<void>
  onDeviceChange: (kind: DeviceKind) => Promise<void>
  enable: (kind: DeviceKind) => Promise<boolean>
  permProbed: Ref<boolean>
  probePermissions: (opts?: { audio?: boolean; video?: boolean | MediaTrackConstraints }) => Promise<boolean>
  clearProbeFlag: () => void
  hasAudioInput: Ref<boolean>
  hasVideoInput: Ref<boolean>
  disable: (kind: DeviceKind) => Promise<void>
  isSpeaking: (id: string) => boolean
}

export function useRTC(): UseRTC {
  const lk = ref<LkRoom | null>(null)
  const localId = ref('')
  const peerIds = ref<string[]>([])
  const videoEls = new Map<string, HTMLVideoElement>()
  const audioEls = new Map<string, HTMLAudioElement>()
  const mics = ref<MediaDeviceInfo[]>([])
  const cams = ref<MediaDeviceInfo[]>([])
  const selectedMicId = ref<string>('')
  const selectedCamId = ref<string>('')
  const wantAudio = ref(true)
  const wantVideo = ref(true)
  const permProbed = ref<boolean>(loadLS('mediaPermProbed') === '1')
  const hasAudioInput = ref(false)
  const hasVideoInput = ref(false)
  const activeSpeakers = ref<Set<string>>(new Set())
  const audibleIds = ref<Set<string>>(new Set())
  const isSub = (pub: RemoteTrackPublication) => pub.isSubscribed

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

  const LOG = (evt: string, data?: any) => console.log(`[RTC] ${new Date().toISOString()} — ${evt}`, data ?? '')
  const WRN = (evt: string, data?: any) => console.warn(`[RTC] ${new Date().toISOString()} — ${evt}`, data ?? '')

  const getByIdentity = (room: LkRoom, id: string) => room.getParticipantByIdentity?.(id) ?? room.remoteParticipants.get(id)

  function setPermFlag(v: boolean) {
    try {
      permProbed.value = v
      if (v) localStorage.setItem('mediaPermProbed', '1')
      else localStorage.removeItem('mediaPermProbed')
    } catch {}
  }

  async function probePermissions(opts?: { audio?: boolean; video?: boolean | MediaTrackConstraints }): Promise<boolean> {
    const audio = opts?.audio ?? true
    const video = opts?.video ?? true
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio, video })
      stream.getTracks().forEach(t => { try { t.stop() } catch {} })
      await refreshDevices()
      setPermFlag(true)
      return true
    } catch {
      setPermFlag(false)
      return false
    }
  }

  function clearProbeFlag() { setPermFlag(false) }

  async function disable(kind: DeviceKind) {
    try {
      if (kind === 'audioinput') await lk.value?.localParticipant.setMicrophoneEnabled(false)
      else await lk.value?.localParticipant.setCameraEnabled(false)
    } catch {}
  }

  function setVideoRef(id: string, el: HTMLVideoElement | null) {
    const prev = videoEls.get(id)
    if (!el) {
      if (prev) { try { prev.srcObject = null } catch {} }
      videoEls.delete(id)
      return
    }
    el.autoplay = true
    el.playsInline = true
    el.muted = id === localId.value
    videoEls.set(id, el)
    const room = lk.value
    if (!room) return
    const pubs = id === String(room.localParticipant.identity)
      ? room.localParticipant.getTrackPublications()
      : getByIdentity(room, id)?.getTrackPublications()
    pubs?.forEach(pub => { if (pub.kind === Track.Kind.Video && pub.track) { try { pub.track.attach(el) } catch {} } })
  }
  const videoRef = (id: string) => (el: HTMLVideoElement | null) => setVideoRef(id, el)

  function ensureAudioEl(id: string): HTMLAudioElement {
    let a = audioEls.get(id)
    if (!a) {
      a = new Audio()
      a.autoplay = true
      a.playsInline = true
      a.muted = false
      a.style.display = 'none'
      audioEls.set(id, a)
      document.body.appendChild(a)
    }
    return a
  }

  async function refreshDevices() {
    try {
      const list = await navigator.mediaDevices.enumerateDevices()
      mics.value = list.filter(d => d.kind === 'audioinput')
      cams.value = list.filter(d => d.kind === 'videoinput')
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
    } catch {}
  }

  async function onDeviceChange(kind: DeviceKind) {
    const room = lk.value
    if (!room) return
    const deviceId = kind === 'audioinput' ? selectedMicId.value : selectedCamId.value
    saveLS(kind === 'audioinput' ? LS.mic : LS.cam, deviceId)
    try { await room.switchActiveDevice(kind, deviceId) } catch {}
  }

  const isBusyError = (e: unknown) => {
    const name = ((e as any)?.name || '') + ''
    const msg  = ((e as any)?.message || '') + ''
    return name === 'NotReadableError' || /Could not start .* source/i.test(msg)
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

  async function enable(kind: DeviceKind): Promise<boolean> {
    const room = lk.value
    if (!room) return false
    if ((kind === 'audioinput' ? mics.value.length : cams.value.length) === 0) {
      await refreshDevices()
    }
    const id = kind === 'audioinput' ? selectedMicId.value : selectedCamId.value
    try {
      if (kind === 'audioinput') {
        await room.localParticipant.setMicrophoneEnabled(true, id ? ({ deviceId: { exact: id } } as any) : undefined)
      } else {
        await room.localParticipant.setCameraEnabled(true, id
            ? ({ deviceId: { exact: id }, resolution: VideoPresets.h360.resolution } as any)
            : ({ resolution: VideoPresets.h360.resolution } as any)
        )
      }
      return true
    } catch {
      await fallback(kind)
      const nextId = kind === 'audioinput' ? selectedMicId.value : selectedCamId.value
      if (!nextId) return false
      try {
        if (kind === 'audioinput') {
          await room.localParticipant.setMicrophoneEnabled(true, { deviceId: { exact: nextId } } as any)
        } else {
          await room.localParticipant.setCameraEnabled(true, { deviceId: { exact: nextId }, resolution: VideoPresets.h360.resolution } as any)
        }
        return true
      } catch { return false }
    }
  }

  function setSubscriptions(kind: Track.Kind, on: boolean) {
    const room = lk.value
    if (!room) return
    room.remoteParticipants.forEach(p => {
      p.getTrackPublications().forEach(pub => {
        if (pub.kind === kind) { try { pub.setSubscribed(on) } catch {} }
      })
    })
  }
  const setAudioSubscriptionsForAll = (on: boolean) => {
    wantAudio.value = on
    LOG('setAudioSubscriptionsForAll', { on })
    setSubscriptions(Track.Kind.Audio, on)
    if (!on) audibleIds.value = new Set()
    else refreshAudibleIds()
  }
  const setVideoSubscriptionsForAll = (on: boolean) => {
    wantVideo.value = on
    LOG('setVideoSubscriptionsForAll', { on })
    setSubscriptions(Track.Kind.Video, on)
  }
  function applyVideoQuality(pub: RemoteTrackPublication) {
    if (pub.kind !== Track.Kind.Video || !pub.isSubscribed) return
    try {
      pub.setVideoQuality(remoteQuality.value === 'hd' ? VideoQuality.HIGH : VideoQuality.LOW)
    } catch (e) { WRN('setVideoQuality error', e) }
  }
  const applySubsFor = (p: RemoteParticipant) => {
    p.getTrackPublications().forEach(pub => {
      if (pub.kind === Track.Kind.Audio) {
        try { pub.setSubscribed(wantAudio.value) } catch {}
        return
      }
      if (pub.kind === Track.Kind.Video) {
        try {
          pub.setSubscribed(wantVideo.value)
          if (wantVideo.value) applyVideoQuality(pub as RemoteTrackPublication)
        } catch {}
      }
    })
  }

  const remoteQuality = ref<VQ>((loadLS(LS.vq) as VQ) === 'sd' ? 'sd' : 'hd')

  function setRemoteQualityForAll(q: VQ) {
    LOG('setRemoteQualityForAll request', { to: q })
    remoteQuality.value = q
    saveLS(LS.vq, q)
    const room = lk.value
    if (!room) return
    room.remoteParticipants.forEach((p) => {
      p.getTrackPublications().forEach((pub) => {
        if (pub.kind === Track.Kind.Video) {
          applyVideoQuality(pub as RemoteTrackPublication)
          LOG('apply quality', { to: q, participant: p.identity })
        }
      })
    })
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
    peerIds.value = []
    localId.value = ''
  }

  function initRoom(opts?: {
    onMediaDevicesError?: (e: unknown) => void
    publishDefaults?: Parameters<typeof LkRoom>[0]['publishDefaults']
    audioCaptureDefaults?: Parameters<typeof LkRoom>[0]['audioCaptureDefaults']
    videoCaptureDefaults?: Parameters<typeof LkRoom>[0]['videoCaptureDefaults']
  }): LkRoom {
    if (lk.value) return lk.value
    const room = new LkRoom({
      dynacast: true,
      publishDefaults: {
        videoCodec: 'vp8',
        red: true,
        dtx: true,
        simulcast: true,
        videoSimulcastLayers: [VideoPresets.h180, VideoPresets.h360],
        ...(opts?.publishDefaults || {})
      },
      audioCaptureDefaults: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        ...(opts?.audioCaptureDefaults || {})
      },
      videoCaptureDefaults: {
        resolution: VideoPresets.h360.resolution,
        ...(opts?.videoCaptureDefaults || {})
      },
    })
    lk.value = room

    room.on(RoomEvent.Disconnected, cleanupMedia)

    room.on(RoomEvent.LocalTrackPublished, (pub: LocalTrackPublication) => {
      if (pub.kind !== Track.Kind.Video) return
      const el = videoEls.get(localId.value)
      if (el && pub.track) { try { pub.track.attach(el) } catch {} }
    })

    room.on(RoomEvent.LocalTrackUnpublished, (pub: LocalTrackPublication) => {
      if (pub.kind !== Track.Kind.Video) return
      const el = videoEls.get(localId.value)
      if (el && pub.track) { try { pub.track.detach(el) } catch {} }
    })

    room.on(RoomEvent.TrackSubscribed, (t: RemoteTrack, pub, part) => {
      const id = String(part.identity)
      if (t.kind === Track.Kind.Video) {
        const el = videoEls.get(id)
        if (el) { try { t.attach(el) } catch {} }
        LOG('TrackSubscribed', { from: String(part.identity), kind: t.kind })
        applyVideoQuality(pub as RemoteTrackPublication)
      } else if (t.kind === Track.Kind.Audio) {
        const a = ensureAudioEl(id)
        try { t.attach(a) } catch {}
      }
    })

    room.on(RoomEvent.TrackUnsubscribed, (t: RemoteTrack, _pub, part) => {
      const id = String(part.identity)
      if (t.kind === Track.Kind.Video) {
        const el = videoEls.get(id)
        if (el) { try { t.detach(el) } catch {} }
      } else if (t.kind === Track.Kind.Audio) {
        const a = audioEls.get(id)
        if (a) { try { t.detach(a) } catch {} }
      }
    })

    room.on(RoomEvent.TrackPublished, (_pub, part) => applySubsFor(part as RemoteParticipant))

    room.on(RoomEvent.ParticipantConnected, (p: RemoteParticipant) => {
      const id = String(p.identity)
      if (!peerIds.value.includes(id)) { peerIds.value = [...peerIds.value, id] }
      applySubsFor(p)
      refreshAudibleIds()
    })

    room.on(RoomEvent.ParticipantDisconnected, (p) => {
      const id = String(p.identity)
      peerIds.value = peerIds.value.filter(x => x !== id)
      const a = audioEls.get(id)
      if (a) {
        try { a.srcObject = null } catch {}
        try { a.remove() } catch {}
        audioEls.delete(id)
      }
      const v = videoEls.get(id)
      if (v) {
        try { v.srcObject = null } catch {}
        videoEls.delete(id)
      }
      const s1 = new Set(audibleIds.value)
      s1.delete(id)
      audibleIds.value = s1
      const s2 = new Set(activeSpeakers.value)
      s2.delete(id)
      activeSpeakers.value = s2
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

    room.on(RoomEvent.MediaDevicesError, (e: any) => { opts?.onMediaDevicesError?.(e) })

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
    await room.connect(wsUrl, token, {
      autoSubscribe: opts?.autoSubscribe ?? false,
      maxRetries: opts?.maxRetries ?? 2,
      peerConnectionTimeout: opts?.peerConnectionTimeout ?? 20_000,
      websocketTimeout: opts?.websocketTimeout ?? 10_000,
    })
    localId.value = String(room.localParticipant.identity)
    const ids: string[] = [localId.value]
    room.remoteParticipants.forEach(p => ids.push(String(p.identity)))
    peerIds.value = Array.from(new Set(ids))
    await refreshDevices()
    refreshAudibleIds()
    LOG('connect ok', { url: wsUrl, local: room.localParticipant.identity, remotes: Array.from(room.remoteParticipants.keys()) })
  }

  async function disconnect() {
    try {
      const pubs = lk.value?.localParticipant.getTrackPublications() ?? []
      for (const p of pubs) { try { p.track?.stop() } catch {} }
    } catch {}
    try { await lk.value?.localParticipant.setMicrophoneEnabled(false) } catch {}
    try { await lk.value?.localParticipant.setCameraEnabled(false) } catch {}
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
    permProbed,
    hasAudioInput,
    hasVideoInput,

    videoRef,
    initRoom,
    connect,
    disconnect,
    setAudioSubscriptionsForAll,
    setVideoSubscriptionsForAll,
    saveLS,
    loadLS,
    refreshDevices,
    isBusyError,
    fallback,
    onDeviceChange,
    enable,
    probePermissions,
    clearProbeFlag,
    disable,
    setRemoteQualityForAll,
    isSpeaking,
  }
}
