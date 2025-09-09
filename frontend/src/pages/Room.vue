<template>
  <div class="container">
    <div class="card">
      <h2 class="title">Комната #{{ rid }}</h2>
      <div class="grid"><div v-for="n in nodes" :key="n.id" class="tile" /></div>
      <button class="btn btn-danger" @click="onLeave">Покинуть комнату</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Room as LkRoom, RoomEvent, createLocalTracks, Track, RemoteTrack } from 'livekit-client'
import { useRtcStore } from '@/store'

const route = useRoute()
const router = useRouter()

const rtc = useRtcStore()

const lk = ref<LkRoom|null>(null)
const elements = new Map<string, HTMLVideoElement>()
type NodeRec = {
  id: string;
  el: HTMLVideoElement
}
const nodes = ref<NodeRec[]>([])
const rid = Number(route.params.id)

function mount(el: HTMLElement) {
  requestAnimationFrame(() => {
    document.querySelector('.grid .tile:last-child')?.appendChild(el)
  })
}

function addElement(id: string, isLocal: boolean) {
  if (elements.has(id)) return elements.get(id)!
  const el = document.createElement('video')
  el.autoplay = true
  el.playsInline = true
  el.muted = isLocal
  el.dataset.rtcEl = '1'
  elements.set(id, el)
  nodes.value.push({ id, el })
  mount(el)
  return el
}

function removeElement(id: string) {
  const i = nodes.value.findIndex(n => n.id === id)
  if (i >= 0) {
    try {
      nodes.value[i].el.remove()
    } catch {}
    nodes.value.splice(i,1)
  }
  const el = elements.get(id)
  if (el) {
    el.srcObject = null
    elements.delete(id)
  }
}

async function onLeave() {
  try {
    await rtc.requestLeave(rid)
  } catch {}
  try {
    await lk.value?.disconnect()
  } catch {}
  elements.forEach((_e,id)=>removeElement(id))
  await router.push('/')
}

onMounted(async () => {
  try {
    const { ws_url, token } = await rtc.requestJoin(rid)
    const room = new LkRoom({
      adaptiveStream: false,
      dynacast: false,
      publishDefaults: {
        videoSimulcastLayers: []
      }
    })
    lk.value = room

    room.on(RoomEvent.TrackSubscribed, (t,_p,part) => {
      const el = addElement(part.identity,false)
      if (t.kind === Track.Kind.Audio || t.kind === Track.Kind.Video) {
        (t as RemoteTrack).attach(el)
      }
    })

    room.on(RoomEvent.TrackUnsubscribed, (t,_p,part) => {
      const el = elements.get(part.identity)
      if (el) try {
        (t as any).detach(el)
      } catch {}
    })

    room.on(RoomEvent.ParticipantDisconnected, p => {
      removeElement(p.identity)
    })

    room.on(RoomEvent.Disconnected, () => {
      elements.forEach((_e,id) => {
        removeElement(id)
      })
    })

    const localTracks = await createLocalTracks({
      audio: true, video: {
        resolution: { width: 1280, height: 720
        }
      }
    })

    await room.connect(ws_url, token)
    for (const t of localTracks) {
      await room.localParticipant.publishTrack(t)
    }
    const localEl = addElement(room.localParticipant.identity, true)
    for (const t of localTracks) {
      if (t.kind === Track.Kind.Audio || t.kind === Track.Kind.Video) {
        t.attach(localEl)
      }
    }
  } catch {
    await router.replace('/')
  }
})

onBeforeUnmount(()=> {
  onLeave()
})
</script>

<style lang="scss" scoped>
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
}
video {
  width: 100%;
  height: 100%;
  min-height: 180px;
  display: block;
  object-fit: cover;
  background: #000;
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
</style>
