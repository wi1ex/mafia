<template>
  <section class="card">
    <div class="grid" :style="gridStyle">
      <div v-for="id in peerIds" :key="id" class="tile">
        <video :ref="el => setVideoRef(id, el as HTMLVideoElement)" playsinline autoplay :muted="id === localId" />
        <div class="veil" :class="{ visible: covers.has(id) }"></div>
        <div class="badges">
          <span class="badge" title="Микрофон">{{ em('mic', statusMap[id]?.mic === 1) }}</span>
          <span class="badge" title="Камера">{{ em('cam', statusMap[id]?.cam === 1) }}</span>
          <span class="badge" title="Звук">{{ em('speakers', statusMap[id]?.speakers === 1) }}</span>
          <span class="badge" title="Видимость">{{ em('visibility', statusMap[id]?.visibility === 1) }}</span>
        </div>
      </div>
    </div>

    <div class="controls">
      <button class="ctrl" @click="toggleMic">{{ micOn ? 'Микрофон вкл' : 'Микрофон выкл' }}</button>
      <button class="ctrl" @click="toggleCam">{{ camOn ? 'Камера вкл' : 'Камера выкл' }}</button>
      <button class="ctrl" @click="toggleSpeakers">{{ speakersOn ? 'Звук вкл' : 'Звук выкл' }}</button>
      <button class="ctrl" @click="toggleVisibility">{{ visibilityOn ? 'Видео вкл' : 'Видео выкл' }}</button>
      <button class="ctrl danger" @click="onLeave">Покинуть комнату</button>
    </div>

    <div class="devices">
      <label>
        Микрофон:
        <select v-model="selectedMicId" @change="onMicChange" :disabled="mics.length===0">
          <option v-for="d in mics" :key="d.deviceId" :value="d.deviceId">
            {{ d.label || 'Микрофон' }}
          </option>
        </select>
      </label>
      <label>
        Камера:
        <select v-model="selectedCamId" @change="onCamChange" :disabled="cams.length===0">
          <option v-for="d in cams" :key="d.deviceId" :value="d.deviceId">
            {{ d.label || 'Камера' }}
          </option>
        </select>
      </label>
    </div>
  </section>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, reactive, ref, computed, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRtcStore } from '@/store'
import { storeToRefs } from 'pinia'
import {
  LocalParticipant,
  LocalTrackPublication,
  RemoteParticipant,
  RemoteTrack,
  Room as LkRoom,
  RoomEvent,
  Track,
  VideoPresets,
  setLogLevel,
  LogLevel,
} from 'livekit-client'

setLogLevel(LogLevel.info)

const route = useRoute()
const router = useRouter()
const rtc = useRtcStore()

const { micOn, camOn, speakersOn, visibilityOn, statusMap } = storeToRefs(rtc)
const rid = Number(route.params.id)
const lk = ref<LkRoom | null>(null)

const localId = ref<string>('')
type Peer = { id: string; joinedAt: number; isLocal: boolean }
const peers = ref<Peer[]>([])
const peerIds = computed(() => peers.value.map(p => p.id))
const videoEls = new Map<string, HTMLVideoElement>()
const audioEls = new Map<string, HTMLAudioElement>()

const LS = { mic: 'audioDeviceId', cam: 'videoDeviceId' }
const mics = ref<MediaDeviceInfo[]>([])
const cams = ref<MediaDeviceInfo[]>([])
const selectedMicId = ref<string>('')
const selectedCamId = ref<string>('')

const gridCols = computed(() => {
  const n = peerIds.value.length
  if (n <= 6) return 3
  if (n <= 12) return 4
  return 5
})
const gridRows = computed(() => {
  const n = peerIds.value.length
  if (n <= 6) return 2
  if (n <= 12) return 3
  return 4
})
const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${gridCols.value}, 1fr)`,
  gridTemplateRows: `repeat(${gridRows.value}, 1fr)`,
}))

const covers = reactive(new Set<string>())
const cover = (id: string, on: boolean) => { on ? covers.add(id) : covers.delete(id) }

function saveLS(k: string, v: string) { try { localStorage.setItem(k, v) } catch {} }
function loadLS(k: string): string | null { try { return localStorage.getItem(k) } catch { return null } }

async function refreshDevices() {
  try {
    const list = await navigator.mediaDevices.enumerateDevices()
    mics.value = list.filter(d => d.kind === 'audioinput')
    cams.value = list.filter(d => d.kind === 'videoinput')
    if (!mics.value.find(d => d.deviceId === selectedMicId.value)) {
      selectedMicId.value = loadLS(LS.mic) && mics.value.find(d => d.deviceId === loadLS(LS.mic)!) ? loadLS(LS.mic)! : (mics.value[0]?.deviceId || '')
    }
    if (!cams.value.find(d => d.deviceId === selectedCamId.value)) {
      selectedCamId.value = loadLS(LS.cam) && cams.value.find(d => d.deviceId === loadLS(LS.cam)!) ? loadLS(LS.cam)! : (cams.value[0]?.deviceId || '')
    }
  } catch {}
}

async function onMicChange() {
  const room = lk.value
  if (!room) return
  const id = selectedMicId.value
  saveLS(LS.mic, id)
  try {
    await room.switchActiveDevice('audioinput', id)
  } catch (e) { console.warn('mic switch failed', e) }
}

async function onCamChange() {
  const room = lk.value
  if (!room) return
  const id = selectedCamId.value
  saveLS(LS.cam, id)
  try {
    await room.switchActiveDevice('videoinput', id)
    const el = videoEls.get(localId.value)
    const vpub = Array.from(room.localParticipant.videoTrackPublications.values())[0]
    if (el && vpub?.track) {
      vpub.track.attach(el)
      el.muted = true
    }
  } catch (e) { console.warn('cam switch failed', e) }
}

function participantsMap(room?: LkRoom | null) {
  return (room as any)?.participants ?? (room as any)?.remoteParticipants as | Map<string, RemoteParticipant> | undefined
}
function getByIdentity(room: LkRoom, id: string) {
  return (room as any)?.getParticipantByIdentity?.(id) ?? participantsMap(room)?.get?.(id)
}

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
  if (v) { try { v.srcObject = null } catch {} videoEls.delete(id) }
  const a = audioEls.get(id)
  if (a) { try { a.remove() } catch {} audioEls.delete(id) }
  delete statusMap.value[id]
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

async function toggleMic() {
  const room = lk.value
  if (!room) return
  const next = !micOn.value
  try {
    await room.localParticipant.setMicrophoneEnabled(next)
    micOn.value = next
    await rtc.toggleMic()
  } catch { micOn.value = !next }
}

async function toggleCam() {
  const room = lk.value
  if (!room) return
  const next = !camOn.value
  try {
    await room.localParticipant.setCameraEnabled(next)
    camOn.value = next
    await rtc.toggleCam()
  } catch { camOn.value = !next }
}

async function toggleSpeakers() {
  const next = !speakersOn.value
  speakersOn.value = next
  setAudioSubscriptionsForAll(next)
  await rtc.toggleSpeakers()
}

async function toggleVisibility() {
  const room = lk.value
  if (!room) return
  visibilityOn.value = !visibilityOn.value
  setVideoSubscriptionsForAll(visibilityOn.value)
  await rtc.toggleVisibility()
}

async function onLeave() {
  const room = lk.value
  lk.value = null
  try { await rtc.leave() } catch {}
  try { await room?.disconnect() } catch {}
  cleanupMedia()
  try { await router.push('/') } catch {}
}

function cleanupMedia() {
  videoEls.forEach(el => { try { el.srcObject = null } catch {} })
  videoEls.clear()
  audioEls.forEach(a => { try { a.remove() } catch {} })
  audioEls.clear()
  peers.value = []
  localId.value = ''
}

watchEffect(() => {
  peerIds.value.forEach((id) => {
    const st = statusMap.value[id]
    const camOff = !st || st.cam !== 1
    const unsubscribedByMe = (id !== localId.value) && !visibilityOn.value
    cover(id, camOff || unsubscribedByMe)
  })
})

onMounted(async () => {
  try {
    selectedMicId.value = loadLS(LS.mic) || ''
    selectedCamId.value = loadLS(LS.cam) || ''

    const { ws_url, token } = await rtc.join(rid)
    const room = new LkRoom({
      // dynacast: true,
      publishDefaults: {
        videoCodec: 'vp8',
        // simulcast: true,
        // videoSimulcastLayers: [VideoPresets.h180, VideoPresets.h360],
        // screenShareEncoding: { maxBitrate: 3_000_000, maxFramerate: 25 },
        red: true,
        dtx: true,
        stopMicTrackOnMute: false,
      },
      audioCaptureDefaults: {
        deviceId: selectedMicId.value ? ({ exact: selectedMicId.value } as any) : undefined,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      videoCaptureDefaults: {
        deviceId: selectedCamId.value ? ({ exact: selectedCamId.value } as any) : undefined,
        resolution: VideoPresets.h360.resolution,
        // frameRate: 25,
      },
    })
    lk.value = room

    room.on(RoomEvent.LocalTrackPublished, (pub: LocalTrackPublication) => {
      if (pub.kind === Track.Kind.Video) {
        const el = videoEls.get(localId.value)
        if (el) try { pub.track?.attach(el) } catch {}
      }
      if (pub.kind === Track.Kind.Video) camOn.value = true
      if (pub.kind === Track.Kind.Audio) micOn.value = true
    })

    room.on(RoomEvent.LocalTrackUnpublished, (pub: LocalTrackPublication) => {
      if (pub.kind === Track.Kind.Video) {
        const el = videoEls.get(localId.value)
        if (el) try { pub.track?.detach(el) } catch {}
      }
      if (pub.kind === Track.Kind.Video) camOn.value = false
      if (pub.kind === Track.Kind.Audio) micOn.value = false
    })

    room.on(RoomEvent.TrackSubscribed, (t: RemoteTrack, _pub, part) => {
      upsertPeerFromParticipant(part)
      const id = String(part.identity)
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
      upsertPeerFromParticipant(p)
      applySubsFor(p)
    })

    room.on(RoomEvent.ParticipantDisconnected, (p) => removePeer(String(p.identity)))

    room.on(RoomEvent.MediaDevicesError, (e) => console.error('MediaDevicesError:', e))

    await room.connect(ws_url, token, {
      autoSubscribe: false,
      maxRetries: 2,
      peerConnectionTimeout: 20_000,
      websocketTimeout: 10_000,
    })

    localId.value = String(room.localParticipant.identity)
    upsertPeerFromParticipant(room.localParticipant, true)
    participantsMap(room)?.forEach(p => upsertPeerFromParticipant(p))
    await nextTick()

    if (camOn.value) { try { await room.localParticipant.setCameraEnabled(true) } catch {} }
    if (micOn.value) { try { await room.localParticipant.setMicrophoneEnabled(true) } catch {} }

    const vpub = room.localParticipant.videoTrackPublications.values().next().value
    const el = videoEls.get(localId.value)
    if (vpub?.track && el) {
      el.muted = true
      vpub.track.attach(el)
    }

    micOn.value = room.localParticipant.audioTrackPublications.size > 0
    camOn.value = room.localParticipant.videoTrackPublications.size > 0

    await refreshDevices()
    navigator.mediaDevices.addEventListener?.('devicechange', refreshDevices)

    participantsMap(room)?.forEach((p) => applySubsFor(p))
  } catch {
    try { await lk.value?.disconnect() } catch {}
    lk.value = null
  }
})

onBeforeUnmount(() => {
  navigator.mediaDevices.removeEventListener?.('devicechange', refreshDevices)
  try { void rtc.leave() } catch {}
  try { lk.value?.disconnect() } catch {}
  cleanupMedia()
})
</script>

<style lang="scss" scoped>
.title {
  color: var(--fg);
}
.grid {
  display: grid;
  gap: 12px;
  margin: 12px;
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
  filter: none !important;
  mix-blend-mode: normal !important;
  opacity: 1 !important;
}
.veil {
  position: absolute;
  inset: 0;
  background: #000;
  opacity: 0;
  transition: opacity 120ms ease-in-out;
  pointer-events: none;
  &.visible {
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
    backdrop-filter: none !important;
  }
}
.controls {
  margin: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  .ctrl {
    padding: 8px 12px;
    border-radius: 8px;
    border: 0;
    cursor: pointer;
    background: #12202e;
    color: #e5e7eb;
    &.danger {
      background: var(--color-danger);
      color: #883c3c;
    }
  }
}
.devices {
  margin: 12px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  select {
    padding: 6px 8px;
    border-radius: 8px;
    border: 1px solid #334155;
    background: #0b0f14;
    color: #e5e7eb;
  }
}
</style>
