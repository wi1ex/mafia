<template>
  <div class="container">
    <div class="card">
      <h2 class="title">Комната #{{ rid }}</h2>
      <div class="grid">
        <div v-for="id in peerIds" :key="id" class="tile">
          <video :ref="el => setVideoRef(id, el as HTMLVideoElement)" playsinline autoplay :muted="id === localId" />
        </div>
      </div>
      <button class="btn btn-danger" type="button" @click="onLeave">Покинуть комнату</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Room as LkRoom, RoomEvent, createLocalTracks, Track, RemoteTrack, LocalTrack } from 'livekit-client'
import { useRtcStore } from '@/store'

const route = useRoute()
const router = useRouter()
const rtc = useRtcStore()

const rid = Number(route.params.id)
const lk = ref<LkRoom | null>(null)
const localTracks: LocalTrack[] = []
const peerIds = ref<string[]>([])
const localId = ref<string>('')
const videoEls = new Map<string, HTMLVideoElement>()

function ensurePeer(id: string) {
  if (!peerIds.value.includes(id)) peerIds.value.push(id)
}

function removePeer(id: string) {
  peerIds.value = peerIds.value.filter(x => x !== id)
  const el = videoEls.get(id)
  if (el) {
    try {
      el.srcObject = null
    } catch {}
    videoEls.delete(id)
  }
}

function attachLocalToEl() {
  const el = videoEls.get(localId.value)
  if (!el) return
  el.muted = true
  for (const t of localTracks) {
    if (t.kind === Track.Kind.Video) {
      try {
        t.attach(el)
      } catch {}
    }
  }
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
  if (id === localId.value) {
    attachLocalToEl()
  }
}

async function onLeave() {
  try {
    await rtc.requestLeave(rid)
  } catch {}
  for (const t of localTracks) {
    try {
      t.detach()
    } catch {}
    try {
      (t.mediaStreamTrack as MediaStreamTrack | undefined)?.stop()
    } catch {}
  }
  localTracks.length = 0
  const room = lk.value
  lk.value = null
  try {
    await room?.disconnect()
  } catch {}
  for (const [id, el] of Array.from(videoEls.entries())) {
    try {
      el.srcObject = null
    } catch {}
    videoEls.delete(id)
  }
  peerIds.value = []
  localId.value = ''
  try {
    await router.push('/')
  } catch {}
}

onMounted(async () => {
  try {
    const { ws_url, token } = await rtc.requestJoin(rid)
    const room = new LkRoom({
      adaptiveStream: true,
      dynacast: true,
      disconnectOnPageLeave: true,
      publishDefaults: {
        videoCodec: 'vp9',
        videoSimulcastLayers: [],
        dtx: true,
        red: true,
        screenShareEncoding: {
          maxBitrate: 2_000_000,
          maxFramerate: 25
        },
      },
      videoCaptureDefaults: {
        resolution: {
          width: 640,
          height: 360
        }
      },
    })
    lk.value = room

    room.on(RoomEvent.TrackSubscribed, (t, _pub, part) => {
      const id = String(part.identity)
      ensurePeer(id)
      if (t.kind === Track.Kind.Video) {
        const el = videoEls.get(id)
        if (el) try {
          t.attach(el)
        } catch {}
      } else if (t.kind === Track.Kind.Audio) {
        const a = new Audio()
        a.autoplay = true
        try {
          t.attach(a)
        } catch {}
      }
    })

    room.on(RoomEvent.TrackUnsubscribed, (t, _pub, part) => {
      if (t.kind === Track.Kind.Video) {
        const el = videoEls.get(String(part.identity))
        if (el) try {
          t.detach(el)
        } catch {}
      }
    })

    room.on(RoomEvent.ParticipantDisconnected, (part) => {
      removePeer(String(part.identity))
    })

    room.on(RoomEvent.Disconnected, () => {
      for (const id of [...videoEls.keys()]) {
        removePeer(id)
      }
    })

    const created = await createLocalTracks({
      audio: true,
      video: {
        resolution: {
          width: 640,
          height: 360,
        },
      },
    })
    localTracks.push(...created)

    await room.connect(ws_url, token)

    localId.value = String(room.localParticipant.identity)
    ensurePeer(localId.value)
    await nextTick()
    attachLocalToEl()

    for (const t of localTracks) {
      try {
        await room.localParticipant.publishTrack(t)
      } catch {}
    }
  } catch {
    try {
      await router.replace('/')
    } catch {}
  }
})

onBeforeUnmount(() => {
  onLeave()
})
</script>

<style lang="scss" scoped>
.card {
  .title {
    color: var(--bg);
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
    min-height: 180px;
    video {
      width: 100%;
      height: 100%;
      min-height: 180px;
      display: block;
      object-fit: cover;
      background: #000;
    }
  }
  .btn {
    margin-top: 12px;
    padding: 8px 12px;
    border-radius: 8px;
    border: 0;
    cursor: pointer;
  }
  .btn-danger {
    background: var(--color-danger);
    color: #190808;
  }
}
</style>
