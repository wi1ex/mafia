<template>
  <section class="card">
    <div class="grid" :style="gridStyle">
      <div v-for="id in peerIds" :key="id" class="tile">
        <video :ref="videoRef(id)" playsinline autoplay :muted="id === localId" />
        <div class="veil" :class="{ visible: hiddenPeers.has(id) }"></div>
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
      <label :class="{ disabled: !micOn }">
        {{ !micOn ? 'Включите микрофон, чтобы выбрать устройство' : 'Микрофон' }}
        <select v-model="selectedMicId" @change="onMicChange" :disabled="!micOn || mics.length===0">
          <option v-for="d in mics" :key="d.deviceId" :value="d.deviceId">
            {{ d.label || 'Микрофон' }}
          </option>
        </select>
      </label>
      <label :class="{ disabled: !camOn }">
        {{ !camOn ? 'Включите камеру, чтобы выбрать устройство' : 'Камера' }}
        <select v-model="selectedCamId" @change="onCamChange" :disabled="!camOn || cams.length===0">
          <option v-for="d in cams" :key="d.deviceId" :value="d.deviceId">
            {{ d.label || 'Камера' }}
          </option>
        </select>
      </label>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { io, Socket } from 'socket.io-client'
import { useAuthStore } from '@/store'
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
type UserState = {
  mic: State01
  cam: State01
  speakers: State01
  visibility: State01
}

setLogLevel(LogLevel.warn)

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const rid = Number(route.params.id)
const roomId = ref<number | null>(rid)
const localId = ref<string>('')
const socket = ref<Socket | null>(null)

const statusMap = reactive<Record<string, UserState>>({})

const local = reactive({
  mic: false,
  cam: false,
  speakers: true,
  visibility: true,
})
const micOn = computed({ get:()=>local.mic, set:(v:boolean)=>{ local.mic = v } })
const camOn = computed({ get:()=>local.cam, set:(v:boolean)=>{ local.cam = v } })
const speakersOn = computed({ get:()=>local.speakers, set:(v:boolean)=>{ local.speakers = v } })
const visibilityOn = computed({ get:()=>local.visibility, set:(v:boolean)=>{ local.visibility = v } })

const curStatePayload = () => ({ ...local })

const isEmpty = (v:any) => v === undefined || v === null || v === ''
const pick01 = (v:any, fallback:0|1) => isEmpty(v) ? fallback : norm01(v, fallback)

function norm01(v: unknown, fallback: 0|1): 0|1 {
  if (typeof v === 'boolean') return v ? 1 : 0
  if (typeof v === 'number')  return v === 1 ? 1 : v === 0 ? 0 : fallback
  if (typeof v === 'string') {
    const s = v.trim().toLowerCase()
    if (s === '1' || s === 'true'  || s === 'yes' || s === 'on')  return 1
    if (s === '0' || s === 'false' || s === 'no'  || s === 'off') return 0
  }
  return fallback
}

function applyPeerState(uid:string, patch:any) {
  const cur = statusMap[uid] ?? { mic:1, cam:1, speakers:1, visibility:1 }
  statusMap[uid] = {
    mic:        pick01(patch?.mic,        cur.mic),
    cam:        pick01(patch?.cam,        cur.cam),
    speakers:   pick01(patch?.speakers,   cur.speakers),
    visibility: pick01(patch?.visibility, cur.visibility),
  }
}

function applySelfPref(pref:any) {
  if (!isEmpty(pref?.mic))        local.mic        = norm01(pref.mic,        local.mic?1:0) === 1
  if (!isEmpty(pref?.cam))        local.cam        = norm01(pref.cam,        local.cam?1:0) === 1
  if (!isEmpty(pref?.speakers))   local.speakers   = norm01(pref.speakers,   local.speakers?1:0) === 1
  if (!isEmpty(pref?.visibility)) local.visibility = norm01(pref.visibility, local.visibility?1:0) === 1
}

/* --------------------------
   LiveKit / медиаплееры
---------------------------*/
type Peer = {
  id: string
  joinedAt: number
  isLocal: boolean
}
type JoinAck = {
  ok?: boolean
  error?: string
  status?: number
  room_id?: number
  token?: string
  snapshot?: Record<string, Record<string, string>>
  self_pref?: Record<string, string>
}
const leaving = ref(false)
const lk = ref<LkRoom | null>(null)
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

type LocalKey = keyof typeof local
function toggleFactory(k: LocalKey, onEnable?: ()=>Promise<void>, onDisable?: ()=>Promise<void>){
  return async () => {
    const want = !local[k]
    const ok = await publishState({ [k]: want } as any)
    if (!ok) return
    try {
      if (want) await onEnable?.()
      else await onDisable?.()
      local[k] = want
    } catch {
      await publishState({ [k]: !want } as any)
    }
  }
}

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
  if (el && vpub?.track) {
    try {
      vpub.track.attach(el)
      el.muted = true
    } catch {}
  }
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

async function ensureMicSelectedThenEnable() {
  const room = lk.value
  if (!room) return
  const id = await ensureDevice(room, 'audioinput', selectedMicId.value || loadLS(LS.mic) || undefined)
  if (!id) throw new Error('no-mic')
  selectedMicId.value = id
  saveLS(LS.mic, id)
  await waitLocalPub(room, Track.Kind.Audio)
}

async function ensureCamSelectedThenEnable() {
  const room = lk.value
  if (!room) return
  const id = await ensureDevice(room, 'videoinput', selectedCamId.value || loadLS(LS.cam) || undefined)
  if (!id) throw new Error('no-cam')
  selectedCamId.value = id
  saveLS(LS.cam, id)
  await waitLocalPub(room, Track.Kind.Video)
  attachLocalVideo(room)
}

function isBusyErr(e:any){
  const name=(e?.name||'')+''
  const msg=(e?.message||'')+''
  return name==='NotReadableError' || /Could not start .* source/i.test(msg)
}

async function fallback(kind:'audioinput'|'videoinput'){
  await refreshDevices()
  const list = kind==='audioinput' ? mics.value : cams.value
  const setEnabled = (on:boolean) => kind==='audioinput'
    ? lk.value?.localParticipant.setMicrophoneEnabled(on)
    : lk.value?.localParticipant.setCameraEnabled(on)
  if (!list.length){
    await setEnabled(false)
    const k = kind==='audioinput' ? 'mic' : 'cam'
    local[k] = false
    await publishState({ [k]: false } as any)
    if (kind==='audioinput') {
      selectedMicId.value=''
      saveLS(LS.mic,'')
    }
    else {
      selectedCamId.value=''
      saveLS(LS.cam,'')
    }
    return
  }
  const newId = list[0].deviceId
  try {
    await lk.value?.switchActiveDevice(kind, newId)
    if (kind==='audioinput') {
      selectedMicId.value = newId
      saveLS(LS.mic, newId)
    }
    else {
      selectedCamId.value = newId
      saveLS(LS.cam, newId)
    }
  } catch {}
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

const hiddenPeers = reactive(new Set<string>())
const cover = (id: string, on: boolean) => { on ? hiddenPeers.add(id) : hiddenPeers.delete(id) }

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

function removePeer(id:string){
  peers.value = peers.value.filter(x => x.id !== id)
  const v = videoEls.get(id)
  if (v) {
    try { v.srcObject = null } catch {}
    videoEls.delete(id)
  }
  const a = audioEls.get(id)
  if (a) {
    try { a.srcObject = null } catch {}
    try { a.remove() } catch {}
    audioEls.delete(id)
  }
  delete statusMap[id]
  hiddenPeers.delete(id)
}

function setVideoRef(id: string, el: HTMLVideoElement | null) {
  const prev = videoEls.get(id)
  if (!el) {
    if (prev) { try { prev.srcObject = null } catch {} }
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

const videoRef = (id:string) => (el: HTMLVideoElement | null) => setVideoRef(id, el)

/* --------------------------
   Socket.IO (ACK-first)
---------------------------*/
function connectSocket() {
  if (socket.value && (socket.value.connected || (socket.value as any).connecting)) return
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

  socket.value.on('connect_error', (e) => console.warn('rtc sio error', e?.message))

  socket.value.on('state_changed', (p:any) => applyPeerState(String(p.user_id), p))

  socket.value.on('member_joined', (p:any) => applyPeerState(String(p.user_id), p?.state || {}))

  socket.value.on('member_left', (p:any) => removePeer(String(p.user_id)))
}

async function joinViaSocket() {
  if (!socket.value) connectSocket()
  if (!socket.value!.connected) {
    await new Promise<void>((res, rej) => {
      const t = setTimeout(() => rej(new Error('connect timeout')), 5000)
      socket.value!.once('connect', () => {
        clearTimeout(t)
        res()
      })
    })
  }
  return await socket.value!.timeout(1500).emitWithAck('join', { room_id: rid, state: curStatePayload() })
}

async function publishState(delta: Partial<{
  mic:boolean
  cam:boolean
  speakers:boolean
  visibility:boolean
}>) {
  if (!roomId.value || !socket.value || !socket.value.connected) return false
  try {
    const resp: any = await socket.value.timeout(1500).emitWithAck('state', delta)
    return !!resp?.ok
  } catch { return false }
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

const toggleMic = toggleFactory('mic',
  async () => { await ensureMicSelectedThenEnable() },
  async () => { await lk.value?.localParticipant.setMicrophoneEnabled(false) },
)

const toggleCam = toggleFactory('cam',
  async () => { await ensureCamSelectedThenEnable() },
  async () => { await lk.value?.localParticipant.setCameraEnabled(false) },
)

const toggleSpeakers = toggleFactory('speakers',
  async() => setAudioSubscriptionsForAll(true),
  async() => setAudioSubscriptionsForAll(false),
)

const toggleVisibility = toggleFactory('visibility',
  async() => setVideoSubscriptionsForAll(true),
  async() => setVideoSubscriptionsForAll(false),
)

/* --------------------------
   Сабскрипшены
---------------------------*/
function forEachRemote(cb: (id: string, p: RemoteParticipant) => void) {
  const room = lk.value
  if (!room) return
  participantsMap(room)?.forEach((p) => cb(String(p.identity), p))
}

function setSubscriptions(kind: Track.Kind, on:boolean) {
  forEachRemote((_id, p) => {
    p.getTrackPublications().forEach(pub => {
      if (pub.kind === kind) { try { pub.setSubscribed(on) } catch {} }
    })
  })
}

const setAudioSubscriptionsForAll = (on:boolean) => setSubscriptions(Track.Kind.Audio, on)

const setVideoSubscriptionsForAll = (on:boolean) => setSubscriptions(Track.Kind.Video, on)

/* --------------------------
   Жизненный цикл
---------------------------*/
const camSig = computed(() => peerIds.value.map(id => statusMap[id]?.cam ?? 1).join('|'))

watch([peerIds, () => local.cam, () => local.visibility, camSig], () => {
  peerIds.value.forEach((id) => {
    const isSelf = id === localId.value
    const camOnServer = statusMap[id]?.cam === 1
    const show = isSelf ? !local.cam : !camOnServer
    const unsubscribedByMe = (!isSelf) && !local.visibility
    cover(id, show || unsubscribedByMe)
  })
}, { immediate: true })

async function onMicChange() {
  const room = lk.value
  const id = selectedMicId.value
  if (!room || !id) return
  saveLS(LS.mic, id)
  try { await room.switchActiveDevice('audioinput', id) }
  catch (e) {
    console.warn('mic switch failed', e)
    if (isBusyErr(e)) await fallback('audioinput')
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
    if (isBusyErr(e)) await fallback('videoinput')
    else alert('Не удалось переключить камеру.')
  }
}

function applySubsFor(p: RemoteParticipant) {
  p.getTrackPublications().forEach(pub => {
    if (pub.kind === Track.Kind.Audio) { try { pub.setSubscribed(speakersOn.value) } catch {} }
    if (pub.kind === Track.Kind.Video) { try { pub.setSubscribed(visibilityOn.value) } catch {} }
  })
}

function cleanupMedia() {
  videoEls.forEach(el => {
    try { el.srcObject = null } catch {}
  })
  videoEls.clear()
  audioEls.forEach(a => {
    try { a.srcObject = null } catch {}
    try { a.remove() } catch {}
  })
  audioEls.clear()
  peers.value = []
  localId.value = ''
  Object.keys(statusMap).forEach(k => delete statusMap[k])
}

function teardownSocket(){
  if (!socket.value) return
  socket.value.off('connect_error')
  socket.value.off('state_changed')
  socket.value.off('member_joined')
  socket.value.off('member_left')
}

async function safeDisableLocalTracks(){
  try { await lk.value?.localParticipant.setMicrophoneEnabled(false) } catch {}
  try { await lk.value?.localParticipant.setCameraEnabled(false) } catch {}
}

async function onLeave() {
  if (leaving.value) return
  leaving.value = true
  try {
    await safeDisableLocalTracks()
    try { await lk.value?.disconnect() } catch {}
    try { socket.value && (socket.value.io.opts.reconnection = false) } catch {}
    try { socket.value?.close?.() } catch {}
    socket.value = null
    cleanupMedia()
    lk.value = null
    roomId.value = null
    await router.replace('/')
  } finally {
    navigator.mediaDevices.removeEventListener?.('devicechange', refreshDevices)
    leaving.value = false
  }
}

onMounted(async () => {
  try {
    connectSocket()
    const j = await joinViaSocket() as JoinAck
    if (!j?.ok) {
      if (j?.status === 404) alert('Комната не найдена')
      else if (j?.status === 409) alert('Комната заполнена')
      else alert('Ошибка входа в комнату')
      await router.replace('/')
      return
    }

    selectedMicId.value = loadLS(LS.mic) || ''
    selectedCamId.value = loadLS(LS.cam) || ''
    await refreshDevices()

    Object.keys(statusMap).forEach(k => delete statusMap[k])
    Object.entries(j.snapshot || {}).forEach(([uid, st]: any) => {
      statusMap[uid] = {
        mic:        pick01(st.mic, 0),
        cam:        pick01(st.cam, 0),
        speakers:   pick01(st.speakers, 1),
        visibility: pick01(st.visibility, 1),
      }
    })
    if (j.self_pref) applySelfPref(j.self_pref)

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

    room.on(RoomEvent.Disconnected, () => {
      teardownSocket()
      cleanupMedia()
    })

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
        if (isVideo || (!isAudio && camOn.value)) await fallback('videoinput')
        if (isAudio || (!isVideo && micOn.value)) await fallback('audioinput')
      }
    })

    await room.connect(ws_url, j.token, {
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

    participantsMap(room)?.forEach((p) => applySubsFor(p))

    navigator.mediaDevices.addEventListener?.('devicechange', refreshDevices)

  } catch (e) {
    console.warn(e)
    try { await lk.value?.disconnect() } catch {}
    lk.value = null
    alert('Ошибка входа в комнату')
    await router.replace('/')
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
  transition: opacity 0.25s ease-in-out;
  pointer-events: auto;
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
    background: #000000;
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
  label {
    width: 100%;
    select {
      padding: 6px 8px;
      border-radius: 8px;
      border: 1px solid #334155;
      background: #0b0f14;
      color: #e5e7eb;
    }
  }
}
</style>
