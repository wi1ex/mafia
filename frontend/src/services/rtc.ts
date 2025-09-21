import { ref, reactive, computed, type Ref } from 'vue'
import {
  LocalParticipant,
  LocalTrackPublication,
  RemoteParticipant,
  RemoteTrack,
  Room as LkRoom,
  RoomEvent,
  Track,
  VideoPresets,
} from 'livekit-client'

type Peer = { id: string; joinedAt: number; isLocal: boolean }
type DeviceKind = 'audioinput' | 'videoinput'

const LS = { mic: 'audioDeviceId', cam: 'videoDeviceId' }

function saveLS(k: string, v: string) { try { localStorage.setItem(k, v) } catch {} }
function loadLS(k: string): string | null { try { return localStorage.getItem(k) } catch { return null } }

export type UseRTC = {
  lk: Ref<LkRoom | null>
  localId: Ref<string>
  peers: Ref<Peer[]>
  mics: Ref<MediaDeviceInfo[]>
  cams: Ref<MediaDeviceInfo[]>
  selectedMicId: Ref<string>
  selectedCamId: Ref<string>

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
  applySubsForAll: () => void

  refreshDevices: () => Promise<void>
  onDeviceChange: (kind: DeviceKind) => Promise<void>
  ensureTrack: (kind: DeviceKind, preferredId?: string) => Promise<string | null>
  attachLocalVideo: (room?: LkRoom | null) => void

  getByIdentity: (room: LkRoom, id: string) => RemoteParticipant | undefined
}

export function useRTC(): UseRTC {
  const lk = ref<LkRoom | null>(null)
  const localId = ref('')
  const peers = ref<Peer[]>([])

  const videoEls = new Map<string, HTMLVideoElement>()
  const audioEls = new Map<string, HTMLAudioElement>()

  const mics = ref<MediaDeviceInfo[]>([])
  const cams = ref<MediaDeviceInfo[]>([])
  const selectedMicId = ref<string>('')
  const selectedCamId = ref<string>('')

  const wantAudio = ref(true)
  const wantVideo = ref(true)

  function upsertPeerFromParticipant(p: RemoteParticipant | LocalParticipant, isLocal = false) {
    const id = String(p.identity)
    const ja: any = (p as any).joinedAt
    const ts = typeof ja === 'number' ? ja : ja instanceof Date ? ja.getTime() : Date.now()
    const i = peers.value.findIndex(x => x.id === id)
    const rec: Peer = { id, joinedAt: ts, isLocal }
    if (i >= 0) peers.value[i] = { ...peers.value[i], ...rec }
    else peers.value.push(rec)
    peers.value.sort((a, b) => a.joinedAt - b.joinedAt || Number(a.isLocal) - Number(b.isLocal) || a.id.localeCompare(b.id))
  }

  function removePeer(id: string) {
    peers.value = peers.value.filter(x => x.id !== id)
    const v = videoEls.get(id)
    if (v) {
      try { v.srcObject = null } catch {}
      videoEls.delete(id)
    }
    const a = audioEls.get(id)
    if (a) {
      try { a.srcObject = null } catch {}
      try { a.remove() } catch {}
      audioEls.delete(id)
    }
  }

  function getByIdentity(room: LkRoom, id: string) {
    return room.getParticipantByIdentity?.(id) ?? room.remoteParticipants.get(id)
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

  function attachLocalVideo(room?: LkRoom | null) {
    const r = room ?? lk.value
    if (!r) return
    const el = videoEls.get(localId.value)
    const vpub = Array.from(r.localParticipant.getTrackPublications()).find(p => p.kind === Track.Kind.Video)
    if (el && vpub?.track) {
      try {
        vpub.track.attach(el)
        el.muted = true
      } catch {}
    }
  }

  async function refreshDevices() {
    try {
      const list = await navigator.mediaDevices.enumerateDevices()
      mics.value = list.filter(d => d.kind === 'audioinput')
      cams.value = list.filter(d => d.kind === 'videoinput')
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

  async function ensureTrack(kind: DeviceKind, preferredId?: string): Promise<string | null> {
    const room = lk.value
    if (!room) return null
    if ((kind === 'audioinput' ? mics.value.length : cams.value.length) === 0) {
      await refreshDevices()
    }
    const list = (kind === 'audioinput' ? mics.value : cams.value)
    if (list.length === 0) return null
    const ids = Array.from(new Set([preferredId && list.some(d => d.deviceId === preferredId) ? preferredId : null, ...list.map(d => d.deviceId)].filter(Boolean) as string[]))
    for (const id of ids) {
      try {
        if (kind === 'audioinput') {
          await room.localParticipant.setMicrophoneEnabled(true, { deviceId: { exact: id } } as any)
        } else {
          await room.localParticipant.setCameraEnabled(true, { deviceId: { exact: id }, resolution: VideoPresets.h360.resolution } as any)
          attachLocalVideo(room)
        }
        return id
      } catch {
        try { kind === 'audioinput' ? await room.localParticipant.setMicrophoneEnabled(false) : await room.localParticipant.setCameraEnabled(false) } catch {}
      }
    }
    return null
  }

  async function onDeviceChange(kind: DeviceKind) {
    const room = lk.value
    if (!room) return
    const deviceId = kind === 'audioinput' ? selectedMicId.value : selectedCamId.value
    const lsKey = kind === 'audioinput' ? LS.mic : LS.cam
    saveLS(lsKey, deviceId)
    await room.switchActiveDevice(kind, deviceId)
    if (kind === 'videoinput') attachLocalVideo(room)
  }

  function setSubscriptions(kind: Track.Kind, on: boolean) {
    const room = lk.value
    if (!room) return
    room.remoteParticipants.forEach((p) => {
      p.getTrackPublications().forEach(pub => {
        if (pub.kind === kind) { try { pub.setSubscribed(on) } catch {} }
      })
    })
  }
  const setAudioSubscriptionsForAll = (on: boolean) => {
    wantAudio.value = on
    setSubscriptions(Track.Kind.Audio, on)
  }
  const setVideoSubscriptionsForAll = (on: boolean) => {
    wantVideo.value = on
    setSubscriptions(Track.Kind.Video, on)
  }
  const applySubsForAll = () => {
    const room = lk.value
    if (!room) return
    room.remoteParticipants.forEach(applySubsFor)
  }
  function applySubsFor(p: RemoteParticipant) {
    p.getTrackPublications().forEach(pub => {
      if (pub.kind === Track.Kind.Audio) { try { pub.setSubscribed(wantAudio.value) } catch {} }
      if (pub.kind === Track.Kind.Video) { try { pub.setSubscribed(wantVideo.value) } catch {} }
    })
  }

  function cleanupMedia() {
    videoEls.forEach(el => { try { el.srcObject = null } catch {} })
    videoEls.clear()
    audioEls.forEach(a => {
      try { a.srcObject = null } catch {}
      try { a.remove() } catch {}
    })
    audioEls.clear()
    peers.value = []
    localId.value = ''
  }

  let deviceListenerAttached = false
  function attachDeviceListener() {
    if (deviceListenerAttached) return
    navigator.mediaDevices.addEventListener?.('devicechange', refreshDevices)
    deviceListenerAttached = true
  }
  function detachDeviceListener() {
    if (!deviceListenerAttached) return
    navigator.mediaDevices.removeEventListener?.('devicechange', refreshDevices)
    deviceListenerAttached = false
  }

  function initRoom(opts?: {
    onMediaDevicesError?: (e: unknown) => void
    publishDefaults?: Parameters<typeof LkRoom>[0]['publishDefaults']
    audioCaptureDefaults?: Parameters<typeof LkRoom>[0]['audioCaptureDefaults']
    videoCaptureDefaults?: Parameters<typeof LkRoom>[0]['videoCaptureDefaults']
  }): LkRoom {
    if (lk.value) return lk.value
    const room = new LkRoom({
      publishDefaults: { videoCodec: 'vp8', red: true, dtx: true, ...(opts?.publishDefaults || {}) },
      audioCaptureDefaults: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, ...(opts?.audioCaptureDefaults || {}) },
      videoCaptureDefaults: { resolution: VideoPresets.h360.resolution, ...(opts?.videoCaptureDefaults || {}) },
    })
    lk.value = room

    room.on(RoomEvent.Disconnected, () => { cleanupMedia() })

    room.on(RoomEvent.LocalTrackPublished, (pub: LocalTrackPublication) => {
      if (pub.kind === Track.Kind.Video) {
        const el = videoEls.get(localId.value)
        if (el) try { pub.track?.attach(el) } catch {}
      }
    })

    room.on(RoomEvent.LocalTrackUnpublished, (pub: LocalTrackPublication) => {
      if (pub.kind === Track.Kind.Video) {
        const el = videoEls.get(localId.value)
        if (el) try { pub.track?.detach(el) } catch {}
      }
    })

    room.on(RoomEvent.TrackSubscribed, (t: RemoteTrack, _pub, part) => {
      const id = String(part.identity)
      upsertPeerFromParticipant(part)
      if (t.kind === Track.Kind.Video) {
        const el = videoEls.get(id)
        if (el) { try { t.attach(el) } catch {} }
      } else if (t.kind === Track.Kind.Audio) {
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
      upsertPeerFromParticipant(p)
      applySubsFor(p)
    })
    room.on(RoomEvent.ParticipantDisconnected, (p) => removePeer(String(p.identity)))

    room.on(RoomEvent.MediaDevicesError, (e: any) => { opts?.onMediaDevicesError?.(e) })

    return room
  }

  async function connect(
    wsUrl: string,
    token: string,
    opts?: { autoSubscribe?: boolean; maxRetries?: number; peerConnectionTimeout?: number; websocketTimeout?: number }
  ) {
    const room = lk.value ?? initRoom()
    await room.connect(wsUrl, token, {
      autoSubscribe: opts?.autoSubscribe ?? false,
      maxRetries: opts?.maxRetries ?? 2,
      peerConnectionTimeout: opts?.peerConnectionTimeout ?? 20_000,
      websocketTimeout: opts?.websocketTimeout ?? 10_000,
    })

    localId.value = String(room.localParticipant.identity)
    upsertPeerFromParticipant(room.localParticipant, true)
    room.remoteParticipants.forEach(p => upsertPeerFromParticipant(p))
    attachDeviceListener()
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
    detachDeviceListener()
    cleanupMedia()
    lk.value = null
  }

  return {
    lk,
    localId,
    peers,
    mics,
    cams,
    selectedMicId,
    selectedCamId,

    videoRef,

    initRoom,
    connect,
    disconnect,

    setAudioSubscriptionsForAll,
    setVideoSubscriptionsForAll,
    applySubsForAll,

    refreshDevices,
    onDeviceChange,
    ensureTrack,
    attachLocalVideo,

    getByIdentity,
  }
}
