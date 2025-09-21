<template>
  <section class="card">
    <div class="grid" :style="gridStyle">
      <div v-for="id in peerIds" :key="id" class="tile">
        <video :ref="videoRef(id)" playsinline autoplay :muted="id === localId" />
        <div class="veil" :class="{ visible: isCovered(id) }"></div>
        <div class="badges">
          <span class="badge" title="Микрофон">{{ em('mic', isOn(id, 'mic')) }}</span>
          <span class="badge" title="Камера">{{ em('cam', isOn(id, 'cam')) }}</span>
          <span class="badge" title="Звук">{{ em('speakers', isOn(id, 'speakers')) }}</span>
          <span class="badge" title="Видимость">{{ em('visibility', isOn(id, 'visibility')) }}</span>
        </div>
      </div>
    </div>

    <div class="controls">
      <button class="ctrl" @click="toggleMic" :disabled="pending.mic">{{ micOn ? 'Микрофон ВКЛ' : 'Микрофон ВЫКЛ' }}</button>
      <button class="ctrl" @click="toggleCam" :disabled="pending.cam">{{ camOn ? 'Камера ВКЛ' : 'Камера ВЫКЛ' }}</button>
      <button class="ctrl" @click="toggleSpeakers" :disabled="pending.speakers">{{ speakersOn ? 'Звук ВКЛ' : 'Звук ВЫКЛ' }}</button>
      <button class="ctrl" @click="toggleVisibility" :disabled="pending.visibility">{{ visibilityOn ? 'Видео ВКЛ' : 'Видео ВЫКЛ' }}</button>
      <button class="ctrl danger" @click="onLeave">Покинуть комнату</button>
    </div>

    <div class="devices">
      <label :class="{ disabled: !micOn }">
        {{ !micOn ? 'Включите микрофон, чтобы выбрать устройство' : 'Микрофон' }}
        <select v-model="selectedMicId" @change="onDeviceChange('audioinput')" :disabled="!micOn || mics.length===0">
          <option v-for="d in mics" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Микрофон' }}</option>
        </select>
      </label>

      <label :class="{ disabled: !camOn }">
        {{ !camOn ? 'Включите камеру, чтобы выбрать устройство' : 'Камера' }}
        <select v-model="selectedCamId" @change="onDeviceChange('videoinput')" :disabled="!camOn || cams.length===0">
          <option v-for="d in cams" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Камера' }}</option>
        </select>
      </label>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { io, Socket } from 'socket.io-client'
import { useAuthStore } from '@/store'
import { useRTC } from '@/services/rtc'

type State01 = 0 | 1
type UserState = { mic: State01; cam: State01; speakers: State01; visibility: State01 }

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const rid = Number(route.params.id)
const roomId = ref<number | null>(rid)
const local = reactive({ mic: false, cam: false, speakers: true, visibility: true })
const pending = reactive<{ [k in keyof typeof local]: boolean }>({ mic: false, cam: false, speakers: false, visibility: false })
const micOn = computed({ get: () => local.mic, set: (v: boolean) => { local.mic = v } })
const camOn = computed({ get: () => local.cam, set: (v: boolean) => { local.cam = v } })
const speakersOn = computed({ get: () => local.speakers, set: (v: boolean) => { local.speakers = v } })
const visibilityOn = computed({ get: () => local.visibility, set: (v: boolean) => { local.visibility = v } })

const socket = ref<Socket | null>(null)
const statusMap = reactive<Record<string, UserState>>({})

const leaving = ref(false)
const ws_url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host

const rtc = useRTC()
const { localId, peers, mics, cams, selectedMicId, selectedCamId, videoRef, refreshDevices, ensureTrack, onDeviceChange } = rtc

const peerIds = computed(() => peers.value.map(p => p.id))
const gridStyle = computed(() => {
  const count = peerIds.value.length
  const cols = count <= 6 ? 3 : count <= 12 ? 4 : 5
  const rows = count <= 6 ? 2 : count <= 12 ? 3 : 4
  return { gridTemplateColumns: `repeat(${cols}, 1fr)`, gridTemplateRows: `repeat(${rows}, 1fr)` }
})

const isEmpty = (v: any) => v === undefined || v === null || v === ''
function norm01(v: unknown, fallback: 0 | 1): 0 | 1 {
  if (typeof v === 'boolean') return v ? 1 : 0
  if (typeof v === 'number') return v === 1 ? 1 : v === 0 ? 0 : fallback
  if (typeof v === 'string') {
    const s = v.trim().toLowerCase()
    if (s === '1' || s === 'true') return 1
    if (s === '0' || s === 'false') return 0
  }
  return fallback
}
const pick01 = (v: any, fallback: 0 | 1) => isEmpty(v) ? fallback : norm01(v, fallback)

function applyPeerState(uid: string, patch: any) {
  const cur = statusMap[uid] ?? { mic: 1, cam: 1, speakers: 1, visibility: 1 }
  statusMap[uid] = {
    mic: pick01(patch?.mic, cur.mic),
    cam: pick01(patch?.cam, cur.cam),
    speakers: pick01(patch?.speakers, cur.speakers),
    visibility: pick01(patch?.visibility, cur.visibility),
  }
}
function applySelfPref(pref: any) {
  if (!isEmpty(pref?.mic)) local.mic = norm01(pref.mic, local.mic ? 1 : 0) === 1
  if (!isEmpty(pref?.cam)) local.cam = norm01(pref.cam, local.cam ? 1 : 0) === 1
  if (!isEmpty(pref?.speakers)) local.speakers = norm01(pref.speakers, local.speakers ? 1 : 0) === 1
  if (!isEmpty(pref?.visibility)) local.visibility = norm01(pref.visibility, local.visibility ? 1 : 0) === 1
}

function em(kind: 'mic' | 'cam' | 'speakers' | 'visibility', on?: boolean) {
  const ON = { mic: '🎤', cam: '🎥', speakers: '🔈', visibility: '👁️' } as const
  const OFF = { mic: '🔇', cam: '🚫', speakers: '🔇', visibility: '🙈' } as const
  return (on ?? true) ? ON[kind] : OFF[kind]
}
function isOn(id: string, kind: 'mic' | 'cam' | 'speakers' | 'visibility') {
  if (id === localId.value) {
    if (kind === 'mic') return micOn.value
    if (kind === 'cam') return camOn.value
    if (kind === 'speakers') return speakersOn.value
    return visibilityOn.value
  }
  const st = statusMap[id]
  return st ? st[kind] === 1 : true
}
function isCovered(id: string): boolean {
  const isSelf = id === localId.value
  const remoteCamOn = statusMap[id]?.cam === 1
  return (isSelf && !camOn.value) || (!isSelf && (!remoteCamOn || !visibilityOn.value))
}

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
  socket.value.on('state_changed', (p: any) => applyPeerState(String(p.user_id), p))
  socket.value.on('member_joined', (p: any) => applyPeerState(String(p.user_id), p?.state || {}))
  socket.value.on('member_left', (p: any) => delete statusMap[String(p.user_id)])
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
  return await socket.value!.timeout(1500).emitWithAck('join', { room_id: rid, state: { ...local } })
}
async function publishState(delta: Partial<{ mic: boolean; cam: boolean; speakers: boolean; visibility: boolean }>) {
  if (!roomId.value || !socket.value || !socket.value.connected) return false
  try {
    const resp: any = await socket.value.timeout(1500).emitWithAck('state', delta)
    return !!resp?.ok
  } catch { return false }
}

const toggleFactory = (k: keyof typeof local, onEnable?: () => Promise<void>, onDisable?: () => Promise<void>) => {
  return async () => {
    if (pending[k]) return
    pending[k] = true
    const want = !local[k]
    try {
      const ok = await publishState({ [k]: want } as any)
      if (!ok) return
      if (want) await onEnable?.()
      else await onDisable?.()
      local[k] = want
      if (k === 'speakers') rtc.setAudioSubscriptionsForAll(local.speakers)
      if (k === 'visibility') rtc.setVideoSubscriptionsForAll(local.visibility)
    } catch {
      try { await publishState({ [k]: !want } as any) } catch {}
    } finally {
      pending[k] = false
    }
  }
}

const toggleMic = toggleFactory('mic',
  async () => {
    const id = await ensureTrack('audioinput', rtc.selectedMicId.value || null || undefined)
    if (!id) throw new Error('no-mic')
    rtc.selectedMicId.value = id
  },
  async () => { await rtc.lk.value?.localParticipant.setMicrophoneEnabled(false) },
)

const toggleCam = toggleFactory('cam',
  async () => {
    const id = await ensureTrack('videoinput', rtc.selectedCamId.value || null || undefined)
    if (!id) throw new Error('no-cam')
    rtc.selectedCamId.value = id
    rtc.attachLocalVideo()
  },
  async () => { await rtc.lk.value?.localParticipant.setCameraEnabled(false) },
)

const toggleSpeakers  = toggleFactory('speakers',
  async () => rtc.setAudioSubscriptionsForAll(true),
  async () => rtc.setAudioSubscriptionsForAll(false),
)

const toggleVisibility = toggleFactory('visibility',
  async () => rtc.setVideoSubscriptionsForAll(true),
  async () => rtc.setVideoSubscriptionsForAll(false),
)

async function onLeave() {
  if (leaving.value) return
  leaving.value = true
  try {
    window.removeEventListener('pagehide', onPageHide)
    window.removeEventListener('beforeunload', onPageHide)
  } catch {}
  try {
    await rtc.disconnect()
    try {
      if (socket.value) {
        socket.value.io.opts.reconnection = false
        socket.value.removeAllListeners?.()
        socket.value.close()
      }
    } catch {}
    socket.value = null
    roomId.value = null
    await router.replace('/')
  } finally {
    leaving.value = false
  }
}

const onPageHide = () => {
  void onLeave()
}

onMounted(async () => {
  try {
    connectSocket()
    const j = await joinViaSocket() as any
    if (!j?.ok) {
      if (j?.status === 404) alert('Комната не найдена')
      else if (j?.status === 409) alert('Комната заполнена')
      else alert('Ошибка входа в комнату')
      await router.replace('/')
      return
    }

    rtc.selectedMicId.value = localStorage.getItem('audioDeviceId') || ''
    rtc.selectedCamId.value = localStorage.getItem('videoDeviceId') || ''
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

    rtc.initRoom({
      onMediaDevicesError: async (e: any) => {
        const msg = (e?.message || '') + ''
        const name = (e?.name || '') + ''
        const isVideo = /video|camera/i.test(msg) || /video/i.test(name)
        const isAudio = /audio|microphone/i.test(msg) || /audio/i.test(name)
        if (name === 'NotReadableError' || /Could not start .* source/i.test(msg)) {
          if (isVideo || (!isAudio && camOn.value)) await rtc.refreshDevices()
          if (isAudio || (!isVideo && micOn.value)) await rtc.refreshDevices()
        }
      }
    })

    await rtc.connect(ws_url, j.token, { autoSubscribe: false })

    rtc.setAudioSubscriptionsForAll(speakersOn.value)
    rtc.setVideoSubscriptionsForAll(visibilityOn.value)
    rtc.applySubsForAll()

    if (camOn.value) {
      const okId = await ensureTrack('videoinput', rtc.selectedCamId.value || undefined)
      if (!okId) {
        alert('Не удалось запустить камеру')
        await onLeave()
        return
      }
      rtc.selectedCamId.value = okId
    }
    if (micOn.value) {
      const okId = await ensureTrack('audioinput', rtc.selectedMicId.value || undefined)
      if (!okId) {
        alert('Не удалось запустить микрофон')
        await onLeave()
        return
      }
      rtc.selectedMicId.value = okId
    }

    window.addEventListener('pagehide', onPageHide)
    window.addEventListener('beforeunload', onPageHide)
  } catch (e) {
    console.warn(e)
    try { await rtc.disconnect() } catch {}
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
    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
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
