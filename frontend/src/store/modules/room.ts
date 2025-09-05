import { defineStore } from 'pinia'
import { api } from '@/services/axios'
import { Room as LkRoom, RoomEvent, Participant, RemoteParticipant, Track, RemoteTrackPublication } from 'livekit-client'

export interface Member { id:string; name:string }

export const useRoomStore = defineStore('room', {
  state: () => ({
    roomId: null as number | null,
    lk: null as LkRoom | null,
    members: [] as Member[],
    videoTracks: new Map<string, Track>(), // participantId -> last video Track
  }),
  getters: {
    connected: s => !!s.lk,
  },
  actions: {
    reset(){
      this.roomId = null
      this.lk?.disconnect().catch(()=>{})
      this.lk = null
      this.members = []
      this.videoTracks.clear()
    },
    async connect(roomId:number){
      if (this.lk) await this.leave()
      const { data } = await api.post<{ ws_url:string; token:string }>(`/v1/rooms/${roomId}/join`, {})
      const lk = new LkRoom()
      await lk.connect(data.ws_url, data.token)
      await lk.localParticipant.enableCameraAndMicrophone()
      this.lk = lk
      this.roomId = roomId

      // существующие участники
      lk.participants.forEach(p => this._trackParticipant(p))
      // локальный как участник
      this._trackParticipant(lk.localParticipant as unknown as Participant)

      lk.on(RoomEvent.ParticipantConnected, (p: RemoteParticipant) => this._trackParticipant(p))
      lk.on(RoomEvent.ParticipantDisconnected, (p: RemoteParticipant) => this._removeParticipant(p.identity))
      lk.on(RoomEvent.TrackSubscribed, (track, pub: RemoteTrackPublication, participant: RemoteParticipant) => {
        if (track.kind === Track.Kind.Video) this.videoTracks.set(participant.identity, track)
      })
      lk.on(RoomEvent.TrackUnsubscribed, (_track, _pub, participant) => {
        this.videoTracks.delete(participant.identity)
      })
    },
    async leave(){
      if (!this.roomId) return
      try { await api.post(`/v1/rooms/${this.roomId}/leave`, {}) } finally { /* ignore */ }
      await this.lk?.disconnect().catch(()=>{})
      this.reset()
    },
    attachVideo(participantId:string, el: HTMLVideoElement){
      const tr = this.videoTracks.get(participantId)
      if (tr){ (tr as any).attach(el) }
    },
    _trackParticipant(p: Participant){
      const id = p.identity
      const name = p.name ?? id
      if (!this.members.find(m => m.id === id)) this.members.push({ id, name })
      // если уже есть видео, зафиксировать
      p.tracks.forEach(pub => {
        const t = pub.track
        if (t && t.kind === Track.Kind.Video) this.videoTracks.set(id, t)
      })
    },
    _removeParticipant(id:string){
      this.members = this.members.filter(m => m.id !== id)
      this.videoTracks.delete(id)
    },
  }
})
