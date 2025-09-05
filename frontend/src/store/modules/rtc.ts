import { defineStore } from 'pinia'
import { ref } from 'vue'
import { Room, createLocalTracks, RoomEvent, Track, RemoteTrack } from 'livekit-client'
import { api } from '@/services/axios'

export const useRtcStore = defineStore('rtc', () => {
  const room = ref<Room | null>(null)
  const joinedRoomId = ref<number>(0)

  async function join(roomId: number){
    if (room.value) await leave()
    const { data } = await api.post(`/v1/rooms/${roomId}/join`)
    const lk = new Room({
      adaptiveStream: false,
      dynacast: false,
      publishDefaults: { videoSimulcastLayers: [] },
    })
    room.value = lk
    joinedRoomId.value = roomId

    lk.on(RoomEvent.TrackSubscribed, (track) => {
      const el = (track as RemoteTrack).attach()
      if (track.kind === 'video') (el as HTMLVideoElement).playsInline = true
      document.dispatchEvent(new CustomEvent('rtc:add', { detail: { el, isLocal:false, kind: track.kind }}))
    })

    lk.on(RoomEvent.TrackUnsubscribed, (track) => {
      if (!track || typeof (track as any).detach !== 'function') return
      const els: HTMLElement[] = (track as any).detach() || []
      els.forEach(el => el.remove())
    })

    lk.on(RoomEvent.Disconnected, () => {
      document.querySelectorAll('[data-rtc-el]').forEach(n => n.remove())
    })

    const local = await createLocalTracks({ audio: true, video: { resolution: { width:1280, height:720 } } })
    await lk.connect(data.ws_url, data.token)

    for (const t of local) await lk.localParticipant.publishTrack(t)

    for (const t of local){
      const el = t.attach()
      if (t.kind === 'video'){
        const v = el as HTMLVideoElement
        v.muted = true
        v.playsInline = true
      }
      document.dispatchEvent(new CustomEvent('rtc:add', { detail: { el, isLocal:true, kind: t.kind }}))
    }
  }

  async function leave(){
    const rid = joinedRoomId.value
    const r = room.value
    room.value = null
    joinedRoomId.value = 0

    try { await r?.disconnect() } catch {}
    document.querySelectorAll('[data-rtc-el]').forEach(n => n.remove())

    if (rid) { try { await api.post(`/v1/rooms/${rid}/leave`, {}) } catch {} }
  }

  return { room, joinedRoomId, join, leave }
})
