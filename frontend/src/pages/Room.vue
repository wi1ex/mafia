<template>
  <div class="container">
    <div class="card">
      <h2 class="title">Комната #{{ rid }}</h2>
      <div ref="gridRef" class="grid" />
      <button class="btn btn-danger" type="button" @click="onLeave">Покинуть комнату</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Room as LkRoom, RoomEvent, createLocalTracks, Track, RemoteTrack, LocalTrack } from 'livekit-client'
import { useRtcStore } from '@/store'

const route = useRoute()
const router = useRouter()
const rtc = useRtcStore()

const rid = Number(route.params.id)
const gridRef = ref<HTMLDivElement | null>(null)

const lk = ref<LkRoom | null>(null)
const localTracks: LocalTrack[] = []
const wrappers = new Map<string, HTMLDivElement>()

function makeWrapper(id: string, muted: boolean): HTMLDivElement {
  const wrap = document.createElement('div')
  wrap.className = 'tile'
  const el = document.createElement('video')
  el.autoplay = true
  el.playsInline = true
  el.muted = muted
  el.dataset.rtcEl = '1'
  wrap.appendChild(el)
  wrappers.set(id, wrap)
  gridRef.value?.appendChild(wrap)
  return wrap
}

function videoEl(id: string, isLocal = false): HTMLVideoElement {
  const wrap = wrappers.get(id) ?? makeWrapper(id, isLocal)
  return wrap.querySelector('video') as HTMLVideoElement
}

function removeWrapper(id: string) {
  const wrap = wrappers.get(id)
  if (!wrap) return
  try {
    wrap.querySelector('video')?.remove()
  } catch {}
  try {
    wrap.remove()
  } catch {}
  wrappers.delete(id)
}

async function onLeave() {
  try {
    await rtc.requestLeave(rid)
  } catch {}
  for (const t of localTracks) {
    try {
      t.detach()
      await lk.value?.localParticipant.unpublishTrack(t)
    } catch {}
    try {
      (t.mediaStreamTrack as MediaStreamTrack | undefined)?.stop()
    } catch {}
  }
  localTracks.length = 0
  try {
    await lk.value?.disconnect()
  } catch {}
  for (const id of Array.from(wrappers.keys())) {
    removeWrapper(id)
  }
  lk.value = null
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
        screenShareEncoding: { maxBitrate: 2_000_000, maxFramerate: 25 },
      },
      videoCaptureDefaults: { resolution: { width: 640, height: 360 } },
    })
    lk.value = room

    const onTrackSub = (t: RemoteTrack, _p: any, part: any) => {
      const el = videoEl(part.identity, false)
      if (t.kind === Track.Kind.Audio || t.kind === Track.Kind.Video) {
        try {
          t.attach(el)
        } catch {}
      }
    }
    const onTrackUnsub = (t: RemoteTrack, _p: any, part: any) => {
      const el = wrappers.get(part.identity)?.querySelector('video')
      if (el) try {
        t.detach(el as HTMLVideoElement)
      } catch {}
      removeWrapper(part.identity)
    }
    const onPartDisc = (p: any) => removeWrapper(p.identity)
    const onDisc = () => {
      for (const id of Array.from(wrappers.keys())) {
        removeWrapper(id)
      }
    }

    room.on(RoomEvent.TrackSubscribed, onTrackSub as any)

    room.on(RoomEvent.TrackUnsubscribed, onTrackUnsub as any)

    room.on(RoomEvent.ParticipantDisconnected, onPartDisc as any)

    room.on(RoomEvent.Disconnected, onDisc)

    const created = await createLocalTracks({
      audio: true,
      video: {
        resolution: {
          width: 640,
          height: 360
        }
      }
    })
    localTracks.push(...created)

    await room.connect(ws_url, token)
    for (const t of localTracks) {
      await room.localParticipant.publishTrack(t)
    }

    const localEl = videoEl(room.localParticipant.identity, true)
    for (const t of localTracks) {
      if (t.kind === Track.Kind.Audio || t.kind === Track.Kind.Video) {
        t.attach(localEl)
      }
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
.title { color: var(--bg); }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(260px,1fr)); gap:12px; margin-top:12px; }
.tile { position:relative; border-radius:12px; overflow:hidden; background:#0b0f14; min-height:180px; }
video { width:100%; height:100%; min-height:180px; display:block; object-fit:cover; background:#000; }
.btn { margin-top:12px; padding:8px 12px; border-radius:8px; border:0; cursor:pointer; }
.btn-danger { background:var(--color-danger); color:#190808; }
</style>
