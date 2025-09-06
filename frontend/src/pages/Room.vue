<template>
  <div class="container">
    <div class="card">
      <h2 class="title">Комната #{{ rid }}</h2>

      <div class="grid">
        <div v-for="n in nodes" :key="n.id" class="tile" />
      </div>

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

const rid = Number(route.params.id)
const lk = ref<LkRoom | null>(null)

// участник -> <video>
const elements = new Map<string, HTMLVideoElement>()
type NodeRec = { id: string; el: HTMLVideoElement }
const nodes = ref<NodeRec[]>([])

function mount(el: HTMLElement){
  requestAnimationFrame(() => {
    const last = document.querySelector('.grid .tile:last-child') as HTMLElement | null
    if (last) last.appendChild(el)
  })
}
function addElement(id:string, isLocal:boolean){
  if (elements.has(id)) return elements.get(id)!
  const el = document.createElement('video')
  el.autoplay = true; el.playsInline = true; el.muted = isLocal
  el.setAttribute('data-rtc-el', '1')
  elements.set(id, el)
  const rec: NodeRec = { id, el }
  nodes.value.push(rec)
  mount(el)
  return el
}
function removeElement(id:string){
  const recIdx = nodes.value.findIndex(n => n.id === id)
  if (recIdx >= 0){ try { nodes.value[recIdx].el.remove() } catch {} ; nodes.value.splice(recIdx,1) }
  const el = elements.get(id); if (el){ el.srcObject = null; elements.delete(id) }
}

async function onLeave(){
  try { await rtc.requestLeave(rid) } catch {}
  try { await lk.value?.disconnect() } catch {}
  elements.forEach((_el,id) => removeElement(id))
  router.push('/')
}

onMounted(async () => {
  // получить ws_url + token
  const { ws_url, token } = await rtc.requestJoin(rid)

  const room = new LkRoom({ adaptiveStream:false, dynacast:false, publishDefaults:{ videoSimulcastLayers: [] } })
  lk.value = room

  // входящие треки
  room.on(RoomEvent.TrackSubscribed, (track, _pub, participant) => {
    const el = addElement(participant.identity, false)
    if (track.kind === Track.Kind.Audio || track.kind === Track.Kind.Video){
      (track as RemoteTrack).attach(el)
    }
  })
  room.on(RoomEvent.TrackUnsubscribed, (track, _pub, participant) => {
    const el = elements.get(participant.identity); if (!el) return
    try { (track as any).detach(el) } catch {}
  })
  room.on(RoomEvent.ParticipantDisconnected, (p) => removeElement(p.identity))
  room.on(RoomEvent.Disconnected, () => { elements.forEach((_el,id)=>removeElement(id)) })

  // локальные треки
  const localTracks = await createLocalTracks({
    audio: true,
    video: { resolution: { width:1280, height:720 } },
  })

  await room.connect(ws_url, token)

  for (const t of localTracks) await room.localParticipant.publishTrack(t)

  const localEl = addElement(room.localParticipant.identity, true)
  for (const t of localTracks){
    if (t.kind === Track.Kind.Audio || t.kind === Track.Kind.Video) t.attach(localEl)
  }
})

onBeforeUnmount(() => onLeave())
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
  border: none;
  cursor: pointer;
}
.btn-danger {
  background: var(--color-danger);
  color: #190808;
}
</style>
