<template>
  <div class="container">
    <div class="card">
      <h2 class="title">Комната #{{ rid }}</h2>

      <div class="grid">
        <div v-for="id in peerIds" :key="id" class="tile">
          <video :ref="el => setVideoRef(id, el as HTMLVideoElement)" playsinline autoplay :muted="id === localId" />
          <div class="veil" :class="{ visible: covers.has(id) }"></div>
          <div class="badges">
            <span class="badge" title="Микрофон">{{ em('mic', statusMap[id]?.mic) }}</span>
            <span class="badge" title="Камера">{{ em('cam', statusMap[id]?.cam) }}</span>
            <span class="badge" title="Звук">{{ em('speakers', statusMap[id]?.speakers) }}</span>
            <span class="badge" title="Видимость">{{ em('visibility', statusMap[id]?.visibility) }}</span>
          </div>
        </div>
      </div>

      <div class="controls">
        <button class="ctrl" :aria-pressed="micOn" @click="toggleMic">{{ micOn ? 'Микрофон вкл' : 'Микрофон выкл' }}</button>
        <button class="ctrl" :aria-pressed="camOn" @click="toggleCam">{{ camOn ? 'Камера вкл' : 'Камера выкл' }}</button>
        <button class="ctrl" :aria-pressed="speakersOn" @click="toggleSpeakers">{{ speakersOn ? 'Звук вкл' : 'Звук выкл' }}</button>
        <button class="ctrl" :aria-pressed="visibilityOn" @click="toggleVisibility">{{ visibilityOn ? 'Видео вкл' : 'Видео выкл' }}</button>
        <button class="ctrl danger" @click="onLeave">Покинуть комнату</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  LocalParticipant,
  LocalTrackPublication,
  RemoteParticipant,
  RemoteTrack,
  RemoteTrackPublication,
  Room as LkRoom,
  RoomEvent,
  Track,
} from 'livekit-client'
import { useRtcStore } from '@/store'

type Status = { mic: boolean; cam: boolean; speakers: boolean; visibility: boolean }

const route = useRoute()
const router = useRouter()
const rtc = useRtcStore()

const rid = Number(route.params.id)
const lk = ref<LkRoom | null>(null)
let visibilityOp: Promise<void> | null = null
let joined = false

const localId = ref<string>('')
const peerIds = ref<string[]>([])
const videoEls = new Map<string, HTMLVideoElement>()
const audioEls = new Map<string, HTMLAudioElement>()
const statusMap = reactive<Record<string, Status>>({})

const micOn = ref(true)
const camOn = ref(true)
const speakersOn = ref(true)
const visibilityOn = ref(true)

const covers = reactive(new Set<string>())
const cover = (id: string, on: boolean) => { on ? covers.add(id) : covers.delete(id) }

function participantsMap(room?: LkRoom | null) {
  return (room as any)?.participants ?? (room as any)?.remoteParticipants as | Map<string, RemoteParticipant> | undefined
}
function getByIdentity(room: LkRoom, id: string) {
  return (room as any)?.getParticipantByIdentity?.(id) ?? participantsMap(room)?.get?.(id)
}

function ensurePeer(id: string) {
  if (!peerIds.value.includes(id)) peerIds.value.push(id)
  if (!statusMap[id]) statusMap[id] = { mic: true, cam: true, speakers: true, visibility: true }
}
function removePeer(id: string) {
  peerIds.value = peerIds.value.filter(x => x !== id)
  const v = videoEls.get(id)
  if (v) { try { v.srcObject = null } catch {} videoEls.delete(id) }
  const a = audioEls.get(id)
  if (a) { try { a.remove() } catch {} audioEls.delete(id) }
  delete statusMap[id]
  covers.delete(id)
}

function setVideoRef(id: string, el: HTMLVideoElement | null) {
  if (!el) {
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

function em(kind: 'mic'|'cam'|'speakers'|'visibility', on?: boolean) {
  const ON  = { mic:'🎤', cam:'🎥', speakers:'🔈', visibility:'👁️' } as const
  const OFF = { mic:'🔇', cam:'🚫', speakers:'🔇', visibility:'🙈' } as const
  return (on ?? true) ? ON[kind] : OFF[kind]
}

// ---- metadata
async function publishMyMetadata(lp: LocalParticipant) {
  const payload: Status = { mic: micOn.value, cam: camOn.value, speakers: speakersOn.value, visibility: visibilityOn.value }
  try {
    await lp.setMetadata(JSON.stringify(payload))
    statusMap[localId.value] = payload
  } catch {}
}
function parseMeta(s: unknown): Status | null {
  if (!s || typeof s !== 'string') return null
  try {
    const j = JSON.parse(s) as Partial<Status>
    return { mic: !!j.mic, cam: !!j.cam, speakers: !!j.speakers, visibility: !!j.visibility }
  }
  catch { return null }
}

// ---- subscriptions
function forEachRemote(cb: (id: string, p: RemoteParticipant) => void) {
  const room = lk.value
  if (!room) return
  participantsMap(room)?.forEach((p) => cb(String(p.identity), p))
}
function setAudioSubscriptionsForAll(on: boolean) {
  forEachRemote((_id, p) => {
    p.getTrackPublications().forEach(pub => { if (pub.kind === Track.Kind.Audio) { try { pub.setSubscribed(on) } catch {} } })
  })
}
function setVideoSubscriptionsForAll(on: boolean) {
  forEachRemote((_id, p) => {
    p.getTrackPublications().forEach(pub => { if (pub.kind === Track.Kind.Video) { try { pub.setSubscribed(on) } catch {} } })
  })
}

// ---- toggles
async function toggleMic() {
  const room = lk.value
  if (!room) return
  const next = !micOn.value
  micOn.value = next
  try {
    await room.localParticipant.setMicrophoneEnabled(next)
    await publishMyMetadata(room.localParticipant)
  }
  catch { micOn.value = !next }
}
async function toggleCam() {
  const room = lk.value
  if (!room) return
  const next = !camOn.value
  camOn.value = next
  try {
    await room.localParticipant.setCameraEnabled(next, next ? { resolution: { width: 640, height: 360 } } : undefined)
    await publishMyMetadata(room.localParticipant)
  } catch { camOn.value = !next }
}
async function toggleSpeakers() {
  const room = lk.value
  if (!room) return
  const next = !speakersOn.value
  speakersOn.value = next
  setAudioSubscriptionsForAll(next)
  await publishMyMetadata(room.localParticipant)
}
async function toggleVisibility() {
  const room = lk.value
  if (!room) return
  visibilityOp = (async () => {
    const next = !visibilityOn.value
    visibilityOn.value = next

    if (!next) {
      forEachRemote((id) => { if (id !== localId.value) cover(id, true) })
      await new Promise(r => requestAnimationFrame(() => setTimeout(r, 100)))
      setVideoSubscriptionsForAll(false)
    } else {
      setVideoSubscriptionsForAll(true)
    }
    await publishMyMetadata(room.localParticipant)
  })()
  await visibilityOp
  visibilityOp = null
}

async function onLeave() {
  const room = lk.value
  lk.value = null
  if (joined) { try { await rtc.requestLeave(rid) } catch {} }
  try { await room?.disconnect() } catch {}
  videoEls.forEach(el => { try { el.srcObject = null } catch {} })
  videoEls.clear()
  audioEls.clear()
  peerIds.value = []
  localId.value = ''
  try { await router.push('/') } catch {}
}

// ---- lifecycle
onMounted(async () => {
  try {
    const { ws_url, token } = await rtc.requestJoin(rid)
    const room = new LkRoom({
      dynacast: true,
      publishDefaults: {
        videoCodec: 'vp8',
        simulcast: true,
        videoSimulcastLayers: [{ width: 320, height: 180 }, { width: 640, height: 360 }],
        screenShareEncoding: { maxBitrate: 3_000_000, maxFramerate: 25 },
        red: true,
        dtx: true,
        stopMicTrackOnMute: true,
      },
      audioCaptureDefaults: {
        // deviceId: { exact: '...' } | '...'
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      videoCaptureDefaults: {
        // deviceId: { exact: '...' } | '...'
        resolution: { width: 640, height: 360 },
        frameRate: { ideal: 25, max: 30 },
      },
      audioOutput: {
        // deviceId: '...' // если нужен конкретный динамик/гарнитура
      },
    })
    lk.value = room

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
      ensurePeer(id)
      if (t.kind === Track.Kind.Video) {
        const el = videoEls.get(id)
        if (el) {
          try { t.attach(el) } catch {}
          const onReady = () => {
            cover(id, false)
            el.removeEventListener('loadeddata', onReady)
            el.removeEventListener('resize', onReady)
          }
          el.addEventListener('loadeddata', onReady)
          el.addEventListener('resize', onReady)
        }
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

    function applySubsFor(p: RemoteParticipant) {
      p.getTrackPublications().forEach(pub => {
        if (pub.kind === Track.Kind.Audio) { try { pub.setSubscribed(speakersOn.value) } catch {} }
        if (pub.kind === Track.Kind.Video) { try { pub.setSubscribed(visibilityOn.value) } catch {} }
      })
    }

    room.on(RoomEvent.TrackPublished, (_pub, part) => applySubsFor(part as RemoteParticipant))

    room.on(RoomEvent.ParticipantConnected, (p: RemoteParticipant) => {
      ensurePeer(String(p.identity))
      applySubsFor(p)
      const st = parseMeta(p.metadata)
      if (st) statusMap[String(p.identity)] = st
    })
    room.on(RoomEvent.ParticipantDisconnected, (p) => removePeer(String(p.identity)))

    room.on(RoomEvent.ParticipantMetadataChanged, (_prev, participant) => {
      const id = String(participant.identity)
      ensurePeer(id)
      const st = parseMeta(participant.metadata)
      if (st) statusMap[id] = st
    })

    await room.connect(ws_url, token, {
      autoSubscribe: false,
      maxRetries: 2,
      peerConnectionTimeout: 20_000,
      websocketTimeout: 10_000,
    })
    joined = true

    localId.value = String(room.localParticipant.identity)
    ensurePeer(localId.value)
    await nextTick()

    try {
      await room.localParticipant.enableCameraAndMicrophone()
      const vpub = Array.from(room.localParticipant.videoTrackPublications.values())[0]
      const el = videoEls.get(localId.value)
      if (vpub?.track && el) {
        el.muted = true
        vpub.track.attach(el)
      }
      micOn.value = true
      camOn.value = true
    } catch {
      micOn.value = false
      camOn.value = false
    }

    await publishMyMetadata(room.localParticipant)

    participantsMap(room)?.forEach((p) => {
      ensurePeer(String(p.identity))
      const st = parseMeta(p.metadata)
      if (st) statusMap[String(p.identity)] = st
      applySubsFor(p)
    })
  } catch {
    try { await lk.value?.disconnect() } catch {}
    lk.value = null
  }
})

onBeforeUnmount(() => {
  onLeave()
})
</script>

<style lang="scss" scoped>
.title {
  color: var(--fg);
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.tile {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  background: #0b0f14;
  aspect-ratio: 16 / 9;
}
video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  background: #000;
}
.veil {
  position: absolute;
  inset: 0;
  background: #000;
  opacity: 0;
  pointer-events: none;
  .visible {
    opacity: 1;
  }
}
.badges {
  position: absolute;
  left: 8px;
  top: 8px;
  display: flex;
  gap: 6px;
  z-index: 2;
  .badge {
    font-size: 14px;
    line-height: 1;
    padding: 4px 6px;
    border-radius: 8px;
    background: #0a121acc;
    border: 1px solid #12202e;
    color: #e5e7eb;
  }
}
.controls {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  .ctrl {
    padding: 8px 12px;
    border-radius: 8px;
    border: 0;
    cursor: pointer;
    background: #12202e;
    color: #e5e7eb;
    &[aria-pressed="false"] {
      opacity: 0.75
    }
    &.danger {
      background: var(--color-danger);
      color: #883c3c;
    }
  }
}
</style>
