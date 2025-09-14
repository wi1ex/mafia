<template>
  <div class="container">
    <div class="card">
      <h2 class="title">Комната #{{ rid }}</h2>

      <div class="grid">
        <div v-for="id in peerIds" :key="id" class="tile">
          <video
            :ref="el => setVideoRef(id, el as HTMLVideoElement)"
            playsinline
            autoplay
            :muted="id === localId"
          />
          <div class="badges">
            <span class="badge" :class="badgeClass(statusMap[id]?.mic) " title="Микрофон">
              🎤
            </span>
            <span class="badge" :class="badgeClass(statusMap[id]?.cam) " title="Камера">
              🎥
            </span>
            <span class="badge" :class="badgeClass(statusMap[id]?.speakers)" title="Звук">
              🔈
            </span>
            <span class="badge" :class="badgeClass(statusMap[id]?.visibility)" title="Видимость">
              👁️
            </span>
          </div>
        </div>
      </div>

      <div class="controls">
        <button class="ctrl" :aria-pressed="micOn" @click="toggleMic">
          {{ micOn ? 'Микрофон вкл' : 'Микрофон выкл' }}
        </button>
        <button class="ctrl" :aria-pressed="camOn" @click="toggleCam">
          {{ camOn ? 'Камера вкл' : 'Камера выкл' }}
        </button>
        <button class="ctrl" :aria-pressed="speakersOn" @click="toggleSpeakers">
          {{ speakersOn ? 'Звук вкл' : 'Звук выкл' }}
        </button>
        <button class="ctrl" :aria-pressed="visibilityOn" @click="toggleVisibility">
          {{ visibilityOn ? 'Видео вкл' : 'Видео выкл' }}
        </button>

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
  setLogLevel,
  LogLevel
} from 'livekit-client'
import { useRtcStore } from '@/store'

setLogLevel(LogLevel.debug)

type Status = { mic: boolean; cam: boolean; speakers: boolean; visibility: boolean }

const route = useRoute()
const router = useRouter()
const rtc = useRtcStore()

const rid = Number(route.params.id)
const lk = ref<LkRoom | null>(null)
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

function participantsMap(room?: LkRoom | null) {
  return (room as any)?.participants ?? (room as any)?.remoteParticipants as | Map<string, RemoteParticipant> | undefined
}

function getByIdentity(room: LkRoom, id: string) {
  return (room as any)?.getParticipantByIdentity?.(id)
      ?? participantsMap(room)?.get?.(id)
      ?? undefined
}

function ensurePeer(id: string) {
  if (!peerIds.value.includes(id)) peerIds.value.push(id)
  if (!statusMap[id]) statusMap[id] = { mic: true, cam: true, speakers: true, visibility: true }
}

function removePeer(id: string) {
  peerIds.value = peerIds.value.filter(x => x !== id)
  const el = videoEls.get(id)
  if (el) {
    try { el.srcObject = null } catch {}
    videoEls.delete(id)
  }
  delete statusMap[id]
}

function setVideoRef(id: string, el: HTMLVideoElement | null) {
  if (!el) { videoEls.delete(id); return }
  el.autoplay = true
  el.playsInline = true
  el.muted = id === localId.value
  videoEls.set(id, el)

  // если участник уже публиковал видео — прикрепим сразу
  const room = lk.value
  if (!room) return
  if (id === String(room.localParticipant.identity)) {
    room.localParticipant.getTrackPublications().forEach(pub => {
      if (pub.kind === Track.Kind.Video && pub.track) {
        try { pub.track.attach(el) } catch {}
      }
    })
  } else {
    const p = getByIdentity(room, id)
    p?.getTrackPublications().forEach(pub => {
      if (pub.kind === Track.Kind.Video && pub.track) {
        try { pub.track.attach(el) } catch {}
      }
    })
  }
}

function badgeClass(on?: boolean) { return on ? 'on' : 'off' }

// ---------- LiveKit helpers ----------

async function publishMyMetadata(lp: LocalParticipant) {
  const payload: Status = { mic: micOn.value, cam: camOn.value, speakers: speakersOn.value, visibility: visibilityOn.value }
  try {
    await lp.setMetadata(JSON.stringify(payload))
    statusMap[localId.value] = payload
  } catch { /* ignore */ }
}

function parseMeta(s: unknown): Status | null {
  if (!s || typeof s !== 'string') return null
  try {
    const j = JSON.parse(s) as Partial<Status>
    return {
      mic: !!j.mic, cam: !!j.cam, speakers: !!j.speakers, visibility: !!j.visibility,
    }
  } catch { return null }
}

function applySubscriptionsForParticipant(p: RemoteParticipant) {
  p.getTrackPublications().forEach((pub) => {
    try {
      if (pub.kind === Track.Kind.Audio) pub.setSubscribed(speakersOn.value)
      if (pub.kind === Track.Kind.Video) pub.setSubscribed(visibilityOn.value)
    } catch {}
  })
}

function applySubscriptionsForAll() {
  const room = lk.value
  if (!room) return
  participantsMap(room)?.forEach((p) => applySubscriptionsForParticipant(p))
}

async function toggleMic() {
  const room = lk.value
  if (!room) return
  const next = !micOn.value
  micOn.value = next
  try {
    await room.localParticipant.setMicrophoneEnabled(next)
    await publishMyMetadata(room.localParticipant)
  } catch {
    micOn.value = !next
  }
}

async function toggleCam() {
  const room = lk.value
  if (!room) return
  const next = !camOn.value
  camOn.value = next
  try {
    await room.localParticipant.setCameraEnabled(next, next ? { resolution: { width: 640, height: 360 } } : undefined)
    await publishMyMetadata(room.localParticipant)
  } catch {
    camOn.value = !next
  }
}

async function toggleSpeakers() {
  const room = lk.value
  if (!room) return
  speakersOn.value = !speakersOn.value
  applySubscriptionsForAll()
  await publishMyMetadata(room.localParticipant)
}

async function toggleVisibility() {
  const room = lk.value
  if (!room) return
  visibilityOn.value = !visibilityOn.value
  applySubscriptionsForAll()
  await publishMyMetadata(room.localParticipant)
}

async function onLeave() {
  const room = lk.value
  lk.value = null
  if (joined) { try { await rtc.requestLeave(rid) } catch {} }
  try { await room?.disconnect() } catch {}
  for (const [, el] of Array.from(videoEls.entries())) {
    try { el.srcObject = null } catch {}
  }
  videoEls.clear()
  peerIds.value = []
  localId.value = ''
  try { await router.push('/') } catch {}
}

// ---------- Mount ----------

onMounted(async () => {
  try {
    const { ws_url, token } = await rtc.requestJoin(rid)
    const room = new LkRoom({
      adaptiveStream: true,
      dynacast: true,
      disconnectOnPageLeave: false,
      publishDefaults: {
        videoCodec: 'vp8',
        red: true,
        dtx: true,
      },
      videoCaptureDefaults: { resolution: { width: 640, height: 360 } },
    })
    // const room = new LkRoom({
    //   adaptiveStream: true,
    //   dynacast: true,
    //   disconnectOnPageLeave: true,
    //   publishDefaults: {
    //     videoCodec: 'vp9',
    //     videoSimulcastLayers: [],
    //     dtx: true,
    //     red: true,
    //     screenShareEncoding: { maxBitrate: 2_000_000, maxFramerate: 25 },
    //   },
    //   videoCaptureDefaults: { resolution: { width: 640, height: 360 } },
    // })
    lk.value = room

    // Диагностика причин разрыва
    room.on(RoomEvent.Disconnected, (_reason) => {
      console.warn('LK disconnected', _reason)
    })

    room.on(RoomEvent.ConnectionStateChanged, (state) => {
      console.log('LK state:', state)
    })

    // локальные публикации → прикрепляем к своему <video>
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

    // подписки на удалённые → прикрепляем к их <video>
    room.on(RoomEvent.TrackSubscribed, (t: RemoteTrack, _pub, part) => {
      const id = String(part.identity)
      ensurePeer(id)
      if (t.kind === Track.Kind.Video) {
        const el = videoEls.get(id)
        if (el) try { t.attach(el) } catch {}
      } else if (t.kind === Track.Kind.Audio) {
        let a = audioEls.get(id)
        if (!a) {
          a = new Audio()
          a.autoplay = true
          a.playsInline = true
          audioEls.set(id, a)
          document.body.appendChild(a) // можно скрыть через CSS, но пусть будет в DOM
        }
        try { t.attach(a) } catch {}
      }
    })

    room.on(RoomEvent.TrackUnsubscribed, (t: RemoteTrack, _pub, part) => {
      const el = videoEls.get(String(part.identity))
      if (el) try { t.detach(el) } catch {}
    })

    // новые публикации: применяем текущие правила подписок
    room.on(RoomEvent.TrackPublished, (_pub, part) => {
      applySubscriptionsForParticipant(part as RemoteParticipant)
    })

    // участники
    room.on(RoomEvent.ParticipantConnected, (p: RemoteParticipant) => {
      ensurePeer(String(p.identity))
      applySubscriptionsForParticipant(p)
      const st = parseMeta(p.metadata)
      if (st) statusMap[String(p.identity)] = st
    })

    room.on(RoomEvent.ParticipantDisconnected, (p) => {
      removePeer(String(p.identity))
    })

    // метаданные меняются → обновляем статусы
    room.on(RoomEvent.ParticipantMetadataChanged, (p) => {
      const id = String(p.identity)
      ensurePeer(id)
      const st = parseMeta(p.metadata)
      if (st) statusMap[id] = st
    })

    await room.connect(ws_url, token)
    joined = true

    localId.value = String(room.localParticipant.identity)
    ensurePeer(localId.value)
    await nextTick()

    // Публикуем одним вызовом — так надёжнее
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
    } catch (e) {
      console.error('enableCameraAndMicrophone failed', e)
      micOn.value = false
      camOn.value = false
    }

    // первый экспорт статусов после фактического состояния
    await publishMyMetadata(room.localParticipant)

    // подстроить подписки для уже присутствующих
    participantsMap(room)?.forEach((p) => {
      ensurePeer(String(p.identity))
      const st = parseMeta(p.metadata)
      if (st) statusMap[String(p.identity)] = st
      applySubscriptionsForParticipant(p)
    })
  } catch (err) {
    console.error('room.connect failed', err)
    try { await lk.value?.disconnect() } catch {}
    lk.value = null
  }
})

</script>

<style lang="scss" scoped>
.title { color: var(--fg); }
.grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(260px,1fr)); gap:12px; margin-top:12px; }
.tile { position:relative; border-radius:12px; overflow:hidden; background:#0b0f14; min-height:180px; }
video { width:100%; height:100%; min-height:180px; display:block; object-fit:cover; background:#000; }

.badges {
  position:absolute; left:8px; top:8px; display:flex; gap:6px; z-index:2;
  .badge {
    font-size:14px; line-height:1; padding:4px 6px; border-radius:8px;
    background:#0a121acc; border:1px solid #12202e; color:#e5e7eb;
    &.off { opacity:.45; filter:grayscale(1); }
  }
}

.controls {
  margin-top:12px; display:flex; flex-wrap:wrap; gap:8px;
  .ctrl {
    padding:8px 12px; border-radius:8px; border:0; cursor:pointer;
    background:#12202e; color:#e5e7eb;
    &[aria-pressed="false"] { opacity:.75 }
    &.danger { background: var(--color-danger); color: #883c3c; }
  }
}
</style>
