<template>
  <section class="card">
    <div class="grid" :style="gridStyle">
      <div v-for="id in peerIds" :key="id" class="tile">
        <video :ref="videoRef(id)" playsinline autoplay :muted="id === localId" />
        <div class="veil" :class="{ visible: veilVisible(id) }"></div>
        <div class="badges">
          <span class="badge" title="Микрофон">{{ em('mic', isOn(id, 'mic')) }}</span>
          <span class="badge" title="Камера">{{ em('cam', isOn(id, 'cam')) }}</span>
          <span class="badge" title="Звук">{{ em('speakers', isOn(id, 'speakers')) }}</span>
          <span class="badge" title="Видимость">{{ em('visibility', isOn(id, 'visibility')) }}</span>
        </div>
      </div>
    </div>

    <div class="controls">
      <button class="ctrl" @click="toggleMic">{{ micOn ? 'Выключить микрофон' : 'Включить микрофон' }}</button>
      <button class="ctrl" @click="toggleCam">{{ camOn ? 'Выключить камеру' : 'Включить камеру' }}</button>
      <button class="ctrl" @click="toggleSpeakers">{{ speakersOn ? 'Выключить звук участников' : 'Включить звук участников' }}</button>
      <button class="ctrl" @click="toggleVisibility">{{ visibilityOn ? 'Скрыть видео участников' : 'Показать видео участников' }}</button>
      <button class="ctrl danger" @click="closeRoomAndExit">Покинуть комнату</button>
    </div>

    <div class="devices">
      <label :class="{ disabled: !micOn }">
        {{ micOn ? 'Микрофон' : 'Включите микрофон для выбора устройства' }}
        <select v-model="selectedMicId" @change="onMicChange" :disabled="!micOn || mics.length===0">
          <option v-for="d in mics" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Microphone' }}</option>
        </select>
      </label>

      <label :class="{ disabled: !camOn }">
        {{ camOn ? 'Камера' : 'Включите камеру для выбора устройства' }}
        <select v-model="selectedCamId" @change="onCamChange" :disabled="!camOn || cams.length===0">
          <option v-for="d in cams" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Camera' }}</option>
        </select>
      </label>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * Однофайловая реализация комнаты с упором на простоту и надёжность:
 * - Машина состояний (idle → joining → connecting → connected → leaving → idle).
 * - ACK-сначала для публикации состояния + коалесcирование быстрых кликов.
 * - Отвязка внешних объектов от реактивности (markRaw + shallowRef).
 * - Детерминированный shutdown и sendBeacon при закрытии вкладки.
 * - Минимум реактивности на тяжёлых структурах (DOM-карты не реактивны).
 */
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { io, Socket } from 'socket.io-client'
import { api } from '@/services/axios'
import { useAuthStore } from '@/store/modules/auth'
import {
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

/* ========== Константы и типы ========== */
setLogLevel(LogLevel.warn)

type B01 = 0 | 1
type Flags01 = Readonly<{ mic: B01; cam: B01; speakers: B01; visibility: B01 }>
type Phase = 'idle' | 'joining' | 'connecting' | 'connected' | 'leaving' | 'error'

const DEF_REMOTE: Flags01 = Object.freeze({ mic: 0, cam: 0, speakers: 1, visibility: 1 })
const LS_KEYS = { mic: 'audioDeviceId', cam: 'videoDeviceId' } as const

/* ========== Реактивные поля ========== */
const phase = ref<Phase>('idle')

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const roomId = ref<number>(Number(route.params.id))
const localId = ref<string>('')

/** Внешние клиенты держим вне реактивности Vue */
const lk = shallowRef<LkRoom | null>(null)
const socket = shallowRef<Socket | null>(null)

/** Серверные флаги удалённых участников */
const statusMap = reactive<Record<string, Flags01>>({})

/** Локальные флаги (UI-источник правды для себя) */
const micOn = ref(false)
const camOn = ref(false)
const speakersOn = ref(true)
const visibilityOn = ref(true)

/** Устройства */
const mics = ref<MediaDeviceInfo[]>([])
const cams = ref<MediaDeviceInfo[]>([])
const selectedMicId = ref<string>('')
const selectedCamId = ref<string>('')

/** Список участников (для v-for). Порядок не критичен → простой массив id */
const peerIds = ref<string[]>([])

/** Видео/аудио DOM-карты не реактивны */
const videoEls = new Map<string, HTMLVideoElement>()
const audioEls = new Map<string, HTMLAudioElement>()

/* ========== Утилиты ========== */
const to01 = (v: unknown, def: B01 = 0): B01 =>
  v === 1 || v === true || v === '1' || v === 'true' || v === 'yes' || v === 'on'
    ? 1
    : v === 0 || v === false || v === '0' || v === 'false' || v === 'no' || v === 'off'
    ? 0
    : def

function applyRemotePatch(uid: string, patch: Partial<Flags01>) {
  const cur = statusMap[uid] ?? DEF_REMOTE
  statusMap[uid] = {
    mic: to01(patch.mic, cur.mic),
    cam: to01(patch.cam, cur.cam),
    speakers: to01(patch.speakers, cur.speakers),
    visibility: to01(patch.visibility, cur.visibility),
  }
  if (!peerIds.value.includes(uid)) peerIds.value = [...peerIds.value, uid]
}

function applySelfPref(pref: Partial<Flags01>) {
  if (pref.mic !== undefined) micOn.value = to01(pref.mic) === 1
  if (pref.cam !== undefined) camOn.value = to01(pref.cam) === 1
  if (pref.speakers !== undefined) speakersOn.value = to01(pref.speakers, 1) === 1
  if (pref.visibility !== undefined) visibilityOn.value = to01(pref.visibility, 1) === 1
}

function em(kind: keyof Flags01, on: boolean) {
  const ON = { mic: '🎤', cam: '🎥', speakers: '🔈', visibility: '👁️' } as const
  const OFF = { mic: '🔇', cam: '🚫', speakers: '🔇', visibility: '🙈' } as const
  return on ? ON[kind] : OFF[kind]
}

function isOn(id: string, k: keyof Flags01): boolean {
  if (id === localId.value) {
    if (k === 'mic') return micOn.value
    if (k === 'cam') return camOn.value
    if (k === 'speakers') return speakersOn.value
    return visibilityOn.value
  }
  const st = statusMap[id]
  if (!st) return DEF_REMOTE[k] === 1
  return st[k] === 1
}

/** Вуаль прячем, если:
 *  - для себя: камера выкл;
 *  - для удалённого: либо локально выключена видимость всех, либо у удалённого cam=0.
 */
function veilVisible(id: string): boolean {
  if (id === localId.value) return !camOn.value
  return !visibilityOn.value || !isOn(id, 'cam')
}

/* ========== Сетка ========== */
const gridStyle = computed(() => {
  const n = peerIds.value.length || 1
  const cols = n <= 6 ? 3 : n <= 12 ? 4 : 5
  const rows = Math.ceil(n / cols)
  return { gridTemplateColumns: `repeat(${cols}, 1fr)`, gridTemplateRows: `repeat(${rows}, 1fr)` }
})

/* ========== DOM refs ========== */
function attachVideoTrackTo(id: string, track?: Track | null) {
  const el = videoEls.get(id)
  if (el && track) {
    try {
      track.attach(el)
      if (id === localId.value) el.muted = true
    } catch {}
  }
}
function setVideoRef(id: string, el: HTMLVideoElement | null) {
  if (!el) {
    const prev = videoEls.get(id)
    if (prev) {
      try { prev.srcObject = null } catch {}
    }
    videoEls.delete(id)
    return
  }
  el.autoplay = true
  el.playsInline = true
  el.muted = id === localId.value
  videoEls.set(id, el)
  const room = lk.value
  if (!room) return
  // если трек уже есть — прикрепим
  const isSelf = id === String(room.localParticipant.identity)
  const pubs = isSelf
    ? room.localParticipant.getTrackPublications()
    : room.getParticipantByIdentity?.(id)?.getTrackPublications()
  pubs?.forEach(pub => pub.kind === Track.Kind.Video && pub.track && attachVideoTrackTo(id, pub.track))
}
const videoRef = (id: string) => (el: HTMLVideoElement | null) => setVideoRef(id, el)

/* ========== Устройства ========== */
function saveLS(k: string, v: string) { try { localStorage.setItem(k, v) } catch {} }
function loadLS(k: string) { try { return localStorage.getItem(k) } catch { return null } }

async function refreshDevices() {
  try {
    const list = await navigator.mediaDevices.enumerateDevices()
    mics.value = list.filter(d => d.kind === 'audioinput')
    cams.value = list.filter(d => d.kind === 'videoinput')
    if (!mics.value.find(d => d.deviceId === selectedMicId.value)) {
      const ls = loadLS(LS_KEYS.mic)
      selectedMicId.value = (ls && mics.value.find(d => d.deviceId === ls)) ? ls! : (mics.value[0]?.deviceId || '')
    }
    if (!cams.value.find(d => d.deviceId === selectedCamId.value)) {
      const ls = loadLS(LS_KEYS.cam)
      selectedCamId.value = (ls && cams.value.find(d => d.deviceId === ls)) ? ls! : (cams.value[0]?.deviceId || '')
    }
  } catch {}
}

async function ensureDevice(kind: 'audioinput' | 'videoinput', preferredId?: string): Promise<string | null> {
  const room = lk.value
  if (!room) return null
  const list = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === kind) as MediaDeviceInfo[]
  if (list.length === 0) return null
  const ids = Array.from(new Set([preferredId, ...list.map(d => d.deviceId)].filter(Boolean) as string[]))
  for (const id of ids) {
    try {
      if (kind === 'audioinput') {
        await room.localParticipant.setMicrophoneEnabled(true, { deviceId: { exact: id } } as any)
      } else {
        await room.localParticipant.setCameraEnabled(true, { deviceId: { exact: id }, resolution: VideoPresets.h360.resolution } as any)
        const vpub = Array.from(room.localParticipant.videoTrackPublications.values())[0]
        await nextTick(); attachVideoTrackTo(localId.value, vpub?.track ?? null)
      }
      return id
    } catch {
      try { kind === 'audioinput' ? await room.localParticipant.setMicrophoneEnabled(false) : await room.localParticipant.setCameraEnabled(false) } catch {}
    }
  }
  return null
}

async function ensureMicEnabled() {
  const id = await ensureDevice('audioinput', selectedMicId.value || loadLS(LS_KEYS.mic) || undefined)
  if (!id) throw new Error('no-mic')
  selectedMicId.value = id; saveLS(LS_KEYS.mic, id)
}

async function ensureCamEnabled() {
  const id = await ensureDevice('videoinput', selectedCamId.value || loadLS(LS_KEYS.cam) || undefined)
  if (!id) throw new Error('no-cam')
  selectedCamId.value = id; saveLS(LS_KEYS.cam, id)
}

async function onMicChange() {
  const room = lk.value
  if (!room || !selectedMicId.value || !micOn.value) return
  try { await room.switchActiveDevice('audioinput', selectedMicId.value); saveLS(LS_KEYS.mic, selectedMicId.value) } catch {}
}
async function onCamChange() {
  const room = lk.value
  if (!room || !selectedCamId.value || !camOn.value) return
  try {
    await room.switchActiveDevice('videoinput', selectedCamId.value)
    const vpub = Array.from(room.localParticipant.videoTrackPublications.values())[0]
    attachVideoTrackTo(localId.value, vpub?.track ?? null)
    saveLS(LS_KEYS.cam, selectedCamId.value)
  } catch {}
}

/* ========== Socket.IO (ACK-сначала) ========== */
function connectSocket(token?: string) {
  if (socket.value && (socket.value.connected || (socket.value as any).connecting)) return
  socket.value = markRaw(io('/room', {
    path: '/ws/socket.io',
    transports: ['websocket'],
    auth: { token },
    autoConnect: true,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 500,
    reconnectionDelayMax: 5000,
  }))

  socket.value.on('connect', () => {
    socket.value?.emit('join', { room_id: roomId.value, state: { mic: micOn.value, cam: camOn.value, speakers: speakersOn.value, visibility: visibilityOn.value } })
  })
  socket.value.on('snapshot', (snap: Record<string, Partial<Flags01>>) => {
    Object.keys(statusMap).forEach(k => delete statusMap[k])
    peerIds.value = []
    Object.entries(snap || {}).forEach(([uid, st]) => applyRemotePatch(uid, st))
  })
  socket.value.on('self_pref', (st: Partial<Flags01>) => applySelfPref(st))
  socket.value.on('state_changed', (p: any) => applyRemotePatch(String(p.user_id), p))
  socket.value.on('member_joined', (p: any) => applyRemotePatch(String(p.user_id), p?.state || {}))
  socket.value.on('member_left', (p: any) => removePeer(String(p.user_id)))
}

function emitWithAck<T = any>(evt: string, payload: any, timeout = 1200): Promise<T> {
  return new Promise((resolve, reject) => {
    if (!socket.value || !socket.value.connected) return reject(new Error('socket-offline'))
    let done = false
    const t = setTimeout(() => { if (!done) { done = true; reject(new Error('ack-timeout')) } }, timeout)
    socket.value.emit(evt, payload, (resp: T) => {
      if (!done) { done = true; clearTimeout(t); resolve(resp) }
    })
  })
}

/** Коалесcирование дельт состояний при быстрых кликах */
let pubInFlight = false
let pubPending: Partial<{ mic: boolean; cam: boolean; speakers: boolean; visibility: boolean }> | null = null

async function publishCoalesced(delta: typeof pubPending) {
  pubPending = { ...(pubPending || {}), ...delta }
  if (pubInFlight) return
  pubInFlight = true
  while (pubPending) {
    const batch = pubPending; pubPending = null
    const ok = await publishState(batch)
    if (!ok) break
  }
  pubInFlight = false
}

async function publishState(delta: Partial<{ mic: boolean; cam: boolean; speakers: boolean; visibility: boolean }>) {
  try {
    const ack: any = await emitWithAck('state', delta)
    return !!ack?.ok
  } catch {
    try { await api.post(`/rooms/${roomId.value}/state`, delta) } catch { return false }
    return true
  }
}

/* ========== LiveKit события/подписки ========== */
function applySubsFor(p: RemoteParticipant) {
  p.getTrackPublications().forEach(pub => {
    if (pub.kind === Track.Kind.Audio) { try { pub.setSubscribed(speakersOn.value) } catch {} }
    if (pub.kind === Track.Kind.Video) { try { pub.setSubscribed(visibilityOn.value) } catch {} }
  })
}

function removePeer(id: string) {
  peerIds.value = peerIds.value.filter(x => x !== id)
  delete statusMap[id]
  const v = videoEls.get(id); if (v) { try { v.srcObject = null } catch {}; videoEls.delete(id) }
  const a = audioEls.get(id); if (a) { try { a.srcObject = null } catch {}; try { a.remove() } catch {}; audioEls.delete(id) }
}

/* ========== Тогглы (ACK → железо) ========== */
const toggleMic = async () => {
  const want = !micOn.value
  const ok = await publishCoalesced({ mic: want }); if (ok === undefined) {/* coalesced gate */}
  if (want) { await ensureMicEnabled() } else { try { await lk.value?.localParticipant.setMicrophoneEnabled(false) } catch {} }
  micOn.value = want
}
const toggleCam = async () => {
  const want = !camOn.value
  const ok = await publishCoalesced({ cam: want }); if (ok === undefined) {}
  if (want) { await ensureCamEnabled() } else { try { await lk.value?.localParticipant.setCameraEnabled(false) } catch {} }
  camOn.value = want
}
const toggleSpeakers = async () => {
  const want = !speakersOn.value
  const ok = await publishCoalesced({ speakers: want }); if (ok === undefined) {}
  speakersOn.value = want
  // пересобрать подписки
  const room = lk.value
  room?.remoteParticipants.forEach(p => applySubsFor(p))
}
const toggleVisibility = async () => {
  const want = !visibilityOn.value
  const ok = await publishCoalesced({ visibility: want }); if (ok === undefined) {}
  visibilityOn.value = want
  const room = lk.value
  room?.remoteParticipants.forEach(p => applySubsFor(p))
}

/* ========== Закрытие/очистка ========== */
function pageHideLeave() {
  // гарантированная отправка при закрытии вкладки
  const url = `/api/rooms/${roomId.value}/leave`
  try {
    if (navigator.sendBeacon) navigator.sendBeacon(url, new Blob([], { type: 'text/plain' }))
    else void api.post(url, {}, { keepalive: true as any })
  } catch {}
  try { socket.value?.emit('goodbye') } catch {}
}

let closing = false
async function closeRoom(reason?: string) {
  if (closing || phase.value === 'leaving') return
  closing = true
  phase.value = 'leaving'
  try {
    try { await lk.value?.localParticipant.setCameraEnabled(false) } catch {}
    try { await lk.value?.localParticipant.setMicrophoneEnabled(false) } catch {}
    try { await lk.value?.disconnect() } catch {}
    pageHideLeave()
    try { if (socket.value) (socket.value.io.opts.reconnection = false) } catch {}
    try { socket.value?.close() } catch {}
  } finally {
    // чистка DOM
    videoEls.forEach(el => { try { el.srcObject = null } catch {} })
    videoEls.clear()
    audioEls.forEach(a => { try { a.srcObject = null } catch {}; try { a.remove() } catch {} })
    audioEls.clear()
    // чистка состояний
    peerIds.value = []
    Object.keys(statusMap).forEach(k => delete statusMap[k])
    localId.value = ''
    lk.value = null
    socket.value = null
    phase.value = 'idle'
    closing = false
  }
}

async function closeRoomAndExit() {
  await closeRoom('manual-exit')
  try { await router.replace('/') } catch {}
}

/* ========== Монтирование ========== */
onMounted(async () => {
  phase.value = 'joining'
  await auth.init()

  // Предпочтительные устройства
  selectedMicId.value = loadLS(LS_KEYS.mic) || ''
  selectedCamId.value = loadLS(LS_KEYS.cam) || ''
  await refreshDevices()

  // JOIN → токен + snapshot + self_pref
  const { data } = await api.post<{ token: string; room_id: number; snapshot: Record<string, Partial<Flags01>>; self_pref: Partial<Flags01> }>(`/rooms/${roomId.value}/join`, {})
  Object.keys(statusMap).forEach(k => delete statusMap[k]); peerIds.value = []
  Object.entries(data.snapshot || {}).forEach(([uid, st]) => applyRemotePatch(uid, st))
  if (data.self_pref) applySelfPref(data.self_pref)

  // Socket
  connectSocket(auth.accessToken)

  // LiveKit
  phase.value = 'connecting'
  const room = markRaw(new LkRoom({
    publishDefaults: { videoCodec: 'vp8', red: true, dtx: true, stopMicTrackOnMute: false },
    audioCaptureDefaults: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    videoCaptureDefaults: { resolution: VideoPresets.h360.resolution },
  }))
  lk.value = room

  // Слушатели LiveKit
  room.on(RoomEvent.Disconnected, () => { /* чистка произойдёт в closeRoom() */ })
  room.on(RoomEvent.LocalTrackPublished, (pub: LocalTrackPublication) => {
    if (pub.kind === Track.Kind.Video) attachVideoTrackTo(localId.value, pub.track ?? null)
  })
  room.on(RoomEvent.LocalTrackUnpublished, (pub: LocalTrackPublication) => {
    if (pub.kind === Track.Kind.Video) attachVideoTrackTo(localId.value, null)
  })
  room.on(RoomEvent.TrackSubscribed, (t: RemoteTrack, _pub, part) => {
    const id = String(part.identity)
    if (!peerIds.value.includes(id)) peerIds.value = [...peerIds.value, id]
    if (t.kind === Track.Kind.Video) {
      const v = videoEls.get(id)
      if (v) {
        try { t.attach(v) } catch {}
        const ready = () => { v.removeEventListener('loadeddata', ready); v.removeEventListener('resize', ready) }
        v.addEventListener('loadeddata', ready); v.addEventListener('resize', ready)
      }
    } else if (t.kind === Track.Kind.Audio) {
      let a = audioEls.get(id)
      if (!a) {
        a = new Audio()
        a.autoplay = true; a.playsInline = true; a.style.display = 'none'
        document.body.appendChild(a); audioEls.set(id, a)
      }
      try { t.attach(a) } catch {}
    }
  })
  room.on(RoomEvent.TrackUnsubscribed, (t: RemoteTrack, _pub, part) => {
    const id = String(part.identity)
    if (t.kind === Track.Kind.Video) {
      const v = videoEls.get(id); if (v) { try { t.detach(v) } catch {} }
    } else if (t.kind === Track.Kind.Audio) {
      const a = audioEls.get(id); if (a) { try { t.detach(a) } catch {} }
    }
  })
  room.on(RoomEvent.TrackPublished, (_pub, part) => applySubsFor(part as RemoteParticipant))
  room.on(RoomEvent.ParticipantConnected, (p: RemoteParticipant) => applySubsFor(p))
  room.on(RoomEvent.ParticipantDisconnected, (p) => removePeer(String(p.identity)))

  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
  await room.connect(wsUrl, data.token, { autoSubscribe: false, maxRetries: 2, peerConnectionTimeout: 20_000, websocketTimeout: 10_000 })
  localId.value = String(room.localParticipant.identity)
  if (!peerIds.value.includes(localId.value)) peerIds.value = [localId.value, ...peerIds.value]

  // Стартовые подписки
  room.remoteParticipants.forEach(p => applySubsFor(p))

  // Автозапуск устройств по self_pref
  if (camOn.value) { try { await ensureCamEnabled() } catch {} }
  if (micOn.value) { try { await ensureMicEnabled() } catch {} }

  // Глобальные слушатели «ухода»
  window.addEventListener('pagehide', pageHideLeave)
  window.addEventListener('beforeunload', pageHideLeave)
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') pageHideLeave() })

  phase.value = 'connected'
})

onBeforeUnmount(async () => { await closeRoom('unmount') })
</script>

<style scoped lang="scss">
.card { padding: 16px; }
.grid { display: grid; gap: 12px; margin: 12px; }
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
  object-fit: cover;
  display: block;
  background: #000;
}
.veil {
  position: absolute; inset: 0;
  background: #000;
  opacity: 0; transition: opacity .2s ease;
}
.veil.visible { opacity: .75; }
.badges {
  position: absolute; left: 8px; top: 8px; display: flex; gap: 6px; z-index: 2;
}
.badge {
  font-size: 14px; line-height: 1;
  padding: 4px 6px; border-radius: 8px;
  background: #000; border: 1px solid #12202e; color: #e5e7eb;
}
.controls {
  margin: 12px; display: flex; gap: 12px; flex-wrap: wrap;
}
.ctrl {
  padding: 8px 12px; border-radius: 8px; border: 0; cursor: pointer;
  background: #12202e; color: #e5e7eb;
}
.ctrl.danger { background: #320e0e; color: #fca5a5; }
.devices {
  margin: 12px; display: flex; gap: 12px; flex-wrap: wrap;
}
.devices label { display: grid; gap: 6px; }
.devices label.disabled { opacity: .6; }
.devices select {
  padding: 6px 8px; border-radius: 8px; border: 1px solid #334155;
  background: #0b0f14; color: #e5e7eb;
}
</style>
