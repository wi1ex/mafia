<template>
  <section class="card">
    <div class="grid" :style="gridStyle">
      <div v-for="id in peerIds" :key="id" class="tile">
        <video :ref="el => setVideoRef(id, el as HTMLVideoElement)" playsinline autoplay :muted="id === localId" />
        <div class="veil" :class="{ visible: covers.has(id) }"></div>
        <div class="badges">
          <span class="badge" title="Микрофон">{{ em('mic', isOn(id, 'mic')) }}</span>
          <span class="badge" title="Камера">{{ em('cam', isOn(id, 'cam')) }}</span>
          <span class="badge" title="Звук">{{ em('speakers', isOn(id, 'speakers')) }}</span>
          <span class="badge" title="Видимость">{{ em('visibility', isOn(id, 'visibility')) }}</span>
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
import { onBeforeUnmount, onMounted, reactive, ref, computed, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { io, Socket } from 'socket.io-client'
import { api } from '@/services/axios'
import { useAuthStore } from '@/store/modules/auth'
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

/* --------------------------
   ЛОКАЛЬНОЕ СОСТОЯНИЕ + SIO
---------------------------*/
type State01 = 0 | 1
type UserState = { mic: State01; cam: State01; speakers: State01; visibility: State01 }

setLogLevel(LogLevel.warn)

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const rid = Number(route.params.id)
const roomId = ref<number | null>(rid)
const localId = ref<string>('')
const socket = ref<Socket | null>(null)

const statusMap = reactive<Record<string, UserState>>({})

const micOn = ref(false)
const camOn = ref(false)
const speakersOn = ref(true)
const visibilityOn = ref(true)

/* --------------------------
   LiveKit / медиаплееры
---------------------------*/
const leaving = ref(false)
const lk = ref<LkRoom | null>(null)
type Peer = { id: string; joinedAt: number; isLocal: boolean }
const ws_url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
const peers = ref<Peer[]>([])
const peerIds = computed(() => peers.value.map(p => p.id))
const videoEls = new Map<string, HTMLVideoElement>()
const audioEls = new Map<string, HTMLAudioElement>()

const gridCols = computed(() => {
  const n = peerIds.value.length
  return (n <= 6) ? 3 : (n <= 12) ? 4 : 5
})
const gridRows = computed(() => {
  const n = peerIds.value.length
  return (n <= 6) ? 2 : (n <= 12) ? 3 : 4
})
const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${gridCols.value}, 1fr)`,
  gridTemplateRows: `repeat(${gridRows.value}, 1fr)`,
}))

/* --------------------------
   Устройства
---------------------------*/
const LS = { mic: 'audioDeviceId', cam: 'videoDeviceId' }
const mics = ref<MediaDeviceInfo[]>([])
const cams = ref<MediaDeviceInfo[]>([])
const selectedMicId = ref<string>('')
const selectedCamId = ref<string>('')

const onHide = () => {
  const ridNow = roomId.value
  try { socket.value?.emit('goodbye') } catch {}
  try { if (ridNow) void api.post(`/rooms/${ridNow}/leave`, {}, { keepalive: true as any }) } catch {}
}
const onVis = () => { if (document.visibilityState === 'hidden') onHide() }


function saveLS(k: string, v: string) { try { localStorage.setItem(k, v) } catch {} }
function loadLS(k: string): string | null { try { return localStorage.getItem(k) } catch { return null } }

async function refreshDevices() {
  try {
    const list = await navigator.mediaDevices.enumerateDevices()
    mics.value = list.filter(d => d.kind === 'audioinput')
    cams.value = list.filter(d => d.kind === 'videoinput')
    if (!mics.value.find(d => d.deviceId === selectedMicId.value)) {
      const fromLS = loadLS(LS.mic)
      selectedMicId.value = (fromLS && mics.value.find(d => d.deviceId === fromLS)) ? fromLS! : (mics.value[0]?.deviceId || '')
    }
    if (!cams.value.find(d => d.deviceId === selectedCamId.value)) {
      const fromLS = loadLS(LS.cam)
      selectedCamId.value = (fromLS && cams.value.find(d => d.deviceId === fromLS)) ? fromLS! : (cams.value[0]?.deviceId || '')
    }
  } catch {}
}

function attachLocalVideo(room: LkRoom) {
  const el = videoEls.get(localId.value)
  const vpub = Array.from(room.localParticipant.videoTrackPublications.values())[0]
  if (el && vpub?.track) { try { vpub.track.attach(el); el.muted = true } catch {} }
}

async function ensureDevice(room: LkRoom, kind: 'audioinput' | 'videoinput', preferredId?: string): Promise<string | null> {
  const list = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === kind) as MediaDeviceInfo[]
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

function isBusyErr(e:any){
  const name=(e?.name||'')+''
  const msg=(e?.message||'')+''
  return name==='NotReadableError' || /Could not start .* source/i.test(msg)
}

async function fallbackVideo(room:LkRoom){
  await refreshDevices()
  if (!cams.value.length){
    alert('Камера отсутствует или недоступна.')
    selectedCamId.value = ''
    saveLS(LS.cam, '')
    try { await room.localParticipant.setCameraEnabled(false) } catch {}
    await setCam(false)
    return
  }
  const newId = cams.value[0].deviceId
  selectedCamId.value = newId
  saveLS(LS.cam, newId)
  try {
    await room.switchActiveDevice('videoinput', newId)
    if (!camOn.value) {
      await room.localParticipant.setCameraEnabled(true)
      await setCam(true)
    }
  } catch (e) { console.warn('fallback cam failed', e) }
}

async function fallbackAudio(room:LkRoom){
  await refreshDevices()
  if (!mics.value.length){
    alert('Микрофон отсутствует или недоступен.')
    selectedMicId.value = ''
    saveLS(LS.mic, '')
    try { await room.localParticipant.setMicrophoneEnabled(false) } catch {}
    await setMic(false)
    return
  }
  const newId = mics.value[0].deviceId
  selectedMicId.value = newId
  saveLS(LS.mic, newId)
  try {
    await room.switchActiveDevice('audioinput', newId)
    if (!micOn.value) {
      await room.localParticipant.setMicrophoneEnabled(true)
      await setMic(true)
    }
  } catch (e) { console.warn('fallback mic failed', e) }
}

/* --------------------------
   UI helpers
---------------------------*/
function em(kind: 'mic'|'cam'|'speakers'|'visibility', on?: boolean) {
  const ON  = { mic:'🎤', cam:'🎥', speakers:'🔈', visibility:'👁️' } as const
  const OFF = { mic:'🔇', cam:'🚫', speakers:'🔇', visibility:'🙈' } as const
  return (on ?? true) ? ON[kind] : OFF[kind]
}

function isOn(id: string, kind: 'mic'|'cam'|'speakers'|'visibility') {
  if (id === localId.value) {
    if (kind === 'mic') return micOn.value
    if (kind === 'cam') return camOn.value
    if (kind === 'speakers') return speakersOn.value
    return visibilityOn.value
  }
  const st = statusMap[id]
  return st ? st[kind] === 1 : true
}

const covers = reactive(new Set<string>())
const cover = (id: string, on: boolean) => { on ? covers.add(id) : covers.delete(id) }

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
  const pubs = id === String(room.localParticipant.identity) ? room.localParticipant.getTrackPublications() : getByIdentity(room, id)?.getTrackPublications()
  pubs?.forEach(pub => { if (pub.kind === Track.Kind.Video && pub.track) { try { pub.track.attach(el) } catch {} } })
}

/* --------------------------
   Socket.IO (ACK-first)
---------------------------*/
function connectSocket() {
  if (socket.value?.connected) return
  socket.value = io('/room', {
    path: '/ws/socket.io',
    transports: ['websocket'],
    auth: { token: auth.accessToken },
    autoConnect: true,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 500,
    reconnectionDelayMax: 5000,
  })

  socket.value.on('connect', () => {
    if (roomId.value) socket.value?.emit('join', { room_id: roomId.value, state: curStatePayload() })
  })

  socket.value.on('connect_error', (e) => console.warn('rtc sio error', e?.message))

  socket.value.on('snapshot', (snap: Record<string, Record<string, string>>) => {
    Object.keys(statusMap).forEach(k => delete statusMap[k])
    for (const [uid, st] of Object.entries(snap || {})) {
      statusMap[uid] = {
        mic: to01(st.mic, 0),
        cam: to01(st.cam, 0),
        speakers: to01(st.speakers, 0),
        visibility: to01(st.visibility, 0),
      }
    }
  })

  socket.value.on('self_pref', (pref: Record<string, string>) => {
    micOn.value = to01(pref.mic, 0) === 1
    camOn.value = to01(pref.cam, 0) === 1
    speakersOn.value = to01(pref.speakers, 0) === 1
    visibilityOn.value = to01(pref.visibility, 0) === 1
  })

  socket.value.on('state_changed', (p: any) => {
    const uid = String(p.user_id)
    const cur = statusMap[uid] || { mic: 1, cam: 1, speakers: 1, visibility: 1 }
    statusMap[uid] = {
      mic: to01(p.mic ?? cur.mic),
      cam: to01(p.cam ?? cur.cam),
      speakers: to01(p.speakers ?? cur.speakers),
      visibility: to01(p.visibility ?? cur.visibility),
    }
  })

  socket.value.on('member_left', (p: any) => {
    const uid = String(p.user_id)
    delete statusMap[uid]
    removePeer(uid)
  })

  socket.value.on('member_joined', (p: any) => {
    const uid = String(p.user_id)
    const st = p.state || {}
    statusMap[uid] = {
      mic: to01(st.mic, 0),
      cam: to01(st.cam, 0),
      speakers: to01(st.speakers, 0),
      visibility: to01(st.visibility, 0),
    }
  })
}

function to01(v: unknown, d: 0|1 = 0 as 0|1): 0|1 {
  if (typeof v === 'boolean') return (v ? 1 : 0) as 0|1
  if (v === '1' || v === 1) return 1
  if (v === '0' || v === 0) return 0
  return d
}

function curStatePayload() {
  return { mic: micOn.value, cam: camOn.value, speakers: speakersOn.value, visibility: visibilityOn.value }
}

function emitWithAck<T=any>(evt:string, payload:any, timeout=1500): Promise<T> {
  return new Promise((resolve, reject) => {
    let done=false
    const t=setTimeout(() => {
      if (!done) {
        done=true
        reject(new Error('ack timeout'))
      }
    }, timeout)
    socket.value?.emit(evt, payload, (resp:T) => {
      if (!done) {
        done=true
        clearTimeout(t)
        resolve(resp)
      }
    })
  })
}

async function publishState(delta: Partial<{ mic:boolean; cam:boolean; speakers:boolean; visibility:boolean }>) {
  if (!roomId.value) return false
  try {
    const resp:any = await emitWithAck('state', delta)
    return !!resp?.ok
  } catch {
    try { await api.post(`/rooms/${roomId.value}/state`, delta) } catch { return false }
    return true
  }
}

async function setMic(next:boolean) {
  if (micOn.value===next) return true
  const ok = await publishState({ mic: next })
  if (ok) micOn.value = next
  return ok
}

async function setCam(next:boolean) {
  if (camOn.value===next) return true
  const ok = await publishState({ cam: next })
  if (ok) camOn.value = next
  return ok
}

async function setSpeakers(next:boolean) {
  if (speakersOn.value===next) return true
  const ok = await publishState({ speakers: next })
  if (ok) speakersOn.value = next
  return ok
}

async function setVisibility(next:boolean) {
  if (visibilityOn.value===next) return true
  const ok = await publishState({ visibility: next })
  if (ok) visibilityOn.value = next
  return ok
}

/* --------------------------
   Тогглы (ACK → железо)
---------------------------*/
function waitLocalPub(room: LkRoom, kind: Track.Kind, timeout = 2000) {
  return new Promise<void>((resolve) => {
    const pubs = kind === Track.Kind.Audio ? room.localParticipant.audioTrackPublications : room.localParticipant.videoTrackPublications
    if (pubs.size > 0) return resolve()
    const onPub = (pub: LocalTrackPublication) => {
      if (pub.kind === kind) {
        room.off(RoomEvent.LocalTrackPublished, onPub)
        resolve()
      }
    }
    room.on(RoomEvent.LocalTrackPublished, onPub)
    setTimeout(() => {
      room.off(RoomEvent.LocalTrackPublished, onPub)
      resolve()
    }, timeout)
  })
}

async function toggleCam() {
  const room = lk.value
  if (!room) return
  const want = !camOn.value
  const ok = await setCam(want)
  if (!ok) return
  try {
    if (want) {
      const id = await ensureDevice(room, 'videoinput', selectedCamId.value || loadLS(LS.cam) || undefined)
      if (!id) {
        await setCam(false)
        alert('Камера недоступна')
        return
      }
      selectedCamId.value = id
      saveLS(LS.cam, id)
      await waitLocalPub(room, Track.Kind.Video)
      attachLocalVideo(room)
    } else {
      await room.localParticipant.setCameraEnabled(false)
    }
  } catch (e) {
    console.warn('toggleCam', e)
    await setCam(!want)
  }
}

async function toggleMic() {
  const room = lk.value
  if (!room) return
  const want = !micOn.value
  const ok = await setMic(want)
  if (!ok) return
  try {
    if (want) {
      const id = await ensureDevice(room, 'audioinput', selectedMicId.value || loadLS(LS.mic) || undefined)
      if (!id) {
        await setMic(false)
        alert('Микрофон недоступен')
        return
      }
      selectedMicId.value = id
      saveLS(LS.mic, id)
      await waitLocalPub(room, Track.Kind.Audio)
    } else {
      await room.localParticipant.setMicrophoneEnabled(false)
    }
  } catch (e) {
    console.warn('toggleMic', e)
    await setMic(!want)
  }
}

async function toggleSpeakers() {
  const want = !speakersOn.value
  const ok = await setSpeakers(want)
  if (ok) setAudioSubscriptionsForAll(want)
}

async function toggleVisibility() {
  const room = lk.value
  if (!room) return
  const want = !visibilityOn.value
  const ok = await setVisibility(want)
  if (ok) setVideoSubscriptionsForAll(want)
}

/* --------------------------
   Сабскрипшены
---------------------------*/
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

/* --------------------------
   Жизненный цикл
---------------------------*/
watchEffect(() => {
  peerIds.value.forEach((id) => {
    const isSelf = id === localId.value
    const camOnServer = statusMap[id]?.cam === 1
    const show = isSelf ? !camOn.value : !camOnServer
    const unsubscribedByMe = (!isSelf) && !visibilityOn.value
    cover(id, show || unsubscribedByMe)
  })
})

async function onMicChange() {
  const room = lk.value
  const id = selectedMicId.value
  if (!room || !id) return
  saveLS(LS.mic, id)
  try { await room.switchActiveDevice('audioinput', id) }
  catch (e) {
    console.warn('mic switch failed', e)
    if (isBusyErr(e)) await fallbackAudio(room)
    else alert('Не удалось переключить микрофон.')
  }
}

async function onCamChange() {
  const room = lk.value
  const id = selectedCamId.value
  if (!room || !id) return
  saveLS(LS.cam, id)
  try {
    await room.switchActiveDevice('videoinput', id)
    attachLocalVideo(room)
  } catch (e) {
    console.warn('cam switch failed', e)
    if (isBusyErr(e)) await fallbackVideo(room)
    else alert('Не удалось переключить камеру.')
  }
}

function cleanupMedia() {
  videoEls.forEach(el => { try { el.srcObject = null } catch {} })
  videoEls.clear()
  audioEls.forEach(a => { try { a.remove() } catch {} })
  audioEls.clear()
  peers.value = []
  localId.value = ''
  Object.keys(statusMap).forEach(k => delete statusMap[k])
}

async function onLeave() {
  if (leaving.value) return
  leaving.value = true

  window.removeEventListener('pagehide', onHide)
  window.removeEventListener('beforeunload', onHide)
  document.removeEventListener('visibilitychange', onVis)

  const room = lk.value
  const ridNow = roomId.value

  try { await room?.localParticipant.setMicrophoneEnabled(false) } catch {}
  try { await room?.localParticipant.setCameraEnabled(false) } catch {}

  try { await room?.disconnect() } catch {}
  try { socket.value?.emit('goodbye') } catch {}
  try { if (ridNow) await api.post(`/rooms/${ridNow}/leave`, {}, { keepalive: true as any }) } catch {}
  try { socket.value && (socket.value.io.opts.reconnection = false) } catch {}
  try { socket.value?.off?.(); socket.value?.close?.() } catch {}
  socket.value = null

  cleanupMedia()
  lk.value = null
  roomId.value = null
  leaving.value = false

  try { await router.replace('/') } catch {}
}

onMounted(async () => {
  try {
    selectedMicId.value = loadLS(LS.mic) || ''
    selectedCamId.value = loadLS(LS.cam) || ''
    await refreshDevices()

    const { data } = await api.post<{
      token: string; room_id: number;
      snapshot: Record<string, Record<string, string>>;
      self_pref: Record<string, string>;
    }>(`/rooms/${rid}/join`, {})

    Object.keys(statusMap).forEach(k => delete statusMap[k])
    for (const [uid, st] of Object.entries(data.snapshot || {})) {
      statusMap[uid] = {
        mic: to01(st.mic, 0),
        cam: to01(st.cam, 0),
        speakers: to01(st.speakers, 0),
        visibility: to01(st.visibility, 0)
      }
    }
    if (data.self_pref) {
      micOn.value        = to01(data.self_pref.mic, 0) === 1
      camOn.value        = to01(data.self_pref.cam, 0) === 1
      speakersOn.value   = to01(data.self_pref.speakers, 0) === 1
      visibilityOn.value = to01(data.self_pref.visibility, 0) === 1
    }

    connectSocket()

    const room = new LkRoom({
      publishDefaults: {
        videoCodec: 'vp8',
        red: true,
        dtx: true,
        stopMicTrackOnMute: false
      },
      audioCaptureDefaults: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      },
      videoCaptureDefaults: {
        resolution: VideoPresets.h360.resolution
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
      upsertPeerFromParticipant(part)
      const id = String(part.identity)
      if (t.kind === Track.Kind.Video) {
        const el = videoEls.get(id)
        if (el) {
          try { t.attach(el) } catch {}
          const onReady = () => {
            cover(id, false)
            el.removeEventListener('loadeddata', onReady)
            el.removeEventListener('resize', onReady) }
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
        if (el) { try { t.detach(el) } catch {} } }
      else if (t.kind === Track.Kind.Audio) {
        const a = audioEls.get(id)
        if (a) { try { t.detach(a) } catch {} } }
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

    room.on(RoomEvent.MediaDevicesError, async (e:any) => {
      console.error('MediaDevicesError', { name: e?.name, message: e?.message, constraint: e?.constraint || e?.constraintName || e?.cause?.constraint })
      const msg = (e?.message||'')+''
      const name=(e?.name||'')+''
      const isVideo = /video|camera/i.test(msg) || /video/i.test(name)
      const isAudio = /audio|microphone/i.test(msg) || /audio/i.test(name)
      if (isBusyErr(e)) {
        if (isVideo || (!isAudio && camOn.value)) await fallbackVideo(room)
        if (isAudio || (!isVideo && micOn.value)) await fallbackAudio(room)
      }
    })

    await room.connect(ws_url, data.token, {
      autoSubscribe: false,
      maxRetries: 2,
      peerConnectionTimeout: 20_000,
      websocketTimeout: 10_000,
    })

    localId.value = String(room.localParticipant.identity)
    upsertPeerFromParticipant(room.localParticipant, true)
    participantsMap(room)?.forEach(p => upsertPeerFromParticipant(p))

    if (camOn.value) {
      const sel = loadLS(LS.cam) || undefined
      const okId = await ensureDevice(room, 'videoinput', sel)
      if (!okId) {
        alert('Не удалось запустить камеру')
        await onLeave()
        return }
      selectedCamId.value = okId
      saveLS(LS.cam, okId)
    }
    if (micOn.value) {
      const sel = loadLS(LS.mic) || undefined
      const okId = await ensureDevice(room, 'audioinput', sel)
      if (!okId) {
        alert('Не удалось запустить микрофон')
        await onLeave()
        return }
      selectedMicId.value = okId
      saveLS(LS.mic, okId)
    }

    navigator.mediaDevices.addEventListener?.('devicechange', refreshDevices)
    window.addEventListener('pagehide', onHide)
    window.addEventListener('beforeunload', onHide)
    document.addEventListener('visibilitychange', onVis)

    participantsMap(room)?.forEach((p) => applySubsFor(p))
  } catch (e) {
    console.warn(e)
    try { await lk.value?.disconnect() } catch {}
    lk.value = null
  }
})

onBeforeUnmount(() => {
  void onLeave()
})
</script>

<style lang="scss" scoped>
.title {
  color: $fg;
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
      background: $color-danger;
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
