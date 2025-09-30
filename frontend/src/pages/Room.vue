<template>
  <section class="card">
    <div class="grid" :style="gridStyle">
      <div v-for="id in sortedPeerIds" :key="id" class="tile" :class="{ speaking: rtc.isSpeaking(id) }">
        <video :ref="rtc.videoRef(id)" playsinline autoplay :muted="id === localId" />
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
      <button class="ctrl" @click="toggleQuality" :disabled="pendingQuality">{{ videoQuality === 'hd' ? 'HD' : 'SD' }}</button>
      <button class="ctrl danger" @click="onLeave">Покинуть комнату</button>
    </div>

    <div v-if="showPermProbe" class="perm-probe">
      <button class="ctrl" @click="rtc.probePermissions({ audio: true, video: true })">
        Разрешить доступ к камере и микрофону
      </button>
    </div>

    <div class="devices">
      <label :class="{ disabled: !micOn }">
        {{ !micOn ? 'Включите микрофон, чтобы выбрать устройство' : 'Микрофон' }}
        <select v-model="selectedMicId" @change="rtc.onDeviceChange('audioinput')" :disabled="!micOn || mics.length === 0">
          <option v-for="d in mics" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Микрофон' }}</option>
        </select>
      </label>

      <label :class="{ disabled: !camOn }">
        {{ !camOn ? 'Включите камеру, чтобы выбрать устройство' : 'Камера' }}
        <select v-model="selectedCamId" @change="rtc.onDeviceChange('videoinput')" :disabled="!camOn || cams.length === 0">
          <option v-for="d in cams" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Камера' }}</option>
        </select>
      </label>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Socket } from 'socket.io-client'
import { useAuthStore } from '@/store'
import { useRTC } from '@/services/rtc'
import { createAuthedSocket } from '@/services/sio'

const logState = true
const L = (evt: string, data?: any) => { if (logState) console.log(`[Room] ${new Date().toISOString()} — ${evt}`, data ?? '') }
const W = (evt: string, data?: any) => { if (logState) console.warn(`[Room] ${new Date().toISOString()} — ${evt}`, data ?? '') }

type State01 = 0 | 1
type UserState = { mic: State01; cam: State01; speakers: State01; visibility: State01 }

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const rtc = useRTC()
const { localId, mics, cams, selectedMicId, selectedCamId, peerIds } = rtc

const rid = Number(route.params.id)
const roomId = ref<number | null>(rid)
const local = reactive({ mic: false, cam: false, speakers: true, visibility: true })
const pending = reactive<{ [k in keyof typeof local]: boolean }>({ mic: false, cam: false, speakers: false, visibility: false })
const micOn = computed({ get: () => local.mic, set: v => { local.mic = v } })
const camOn = computed({ get: () => local.cam, set: v => { local.cam = v } })
const speakersOn = computed({ get: () => local.speakers, set: v => { local.speakers = v } })
const visibilityOn = computed({ get: () => local.visibility, set: v => { local.visibility = v } })
const socket = ref<Socket | null>(null)
const joinInFlight = ref<Promise<any> | null>(null)
const joinedRoomId = ref<number | null>(null)
const statusByUser = reactive<Record<string, UserState>>({})
const positionByUser = reactive<Record<string, number>>({})
const leaving = ref(false)
const ws_url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
const pendingQuality = ref(false)
const videoQuality = computed(() => rtc.remoteQuality.value)

const BADGE_ON  = { mic:'🎤', cam:'🎥', speakers:'🔈', visibility:'👁️' } as const
const BADGE_OFF = { mic:'🔇', cam:'🚫', speakers:'🔇', visibility:'🙈' } as const
function em(kind: keyof typeof BADGE_ON, on = true) { return on ? BADGE_ON[kind] : BADGE_OFF[kind] }

const showPermProbe = computed(() => !rtc.permProbed.value && !micOn.value && !camOn.value)
const sortedPeerIds = computed(() => {
  return [...peerIds.value].sort((a, b) => {
    const pa = positionByUser[a] ?? Number.POSITIVE_INFINITY
    const pb = positionByUser[b] ?? Number.POSITIVE_INFINITY
    return pa !== pb ? pa - pb : String(a).localeCompare(String(b))
  })
})
const gridStyle = computed(() => {
  const count = sortedPeerIds.value.length
  const cols = count <= 6 ? 3 : count <= 12 ? 4 : 5
  const rows = count <= 6 ? 2 : count <= 12 ? 3 : 4
  return { gridTemplateColumns: `repeat(${cols}, 1fr)`, gridTemplateRows: `repeat(${rows}, 1fr)` }
})

const isEmpty = (v: any) => v === undefined || v === null || v === ''
const pick01 = (v: any, fallback: 0 | 1) => isEmpty(v) ? fallback : norm01(v, fallback)
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

function isOn(id: string, kind: 'mic' | 'cam' | 'speakers' | 'visibility') {
  if (id === localId.value) {
    if (kind === 'mic') return micOn.value
    if (kind === 'cam') return camOn.value
    if (kind === 'speakers') return speakersOn.value
    return visibilityOn.value
  }
  const st = statusByUser[id]
  return st ? st[kind] === 1 : true
}

function toggleQuality() {
  if (pendingQuality.value) return
  const next = videoQuality.value === 'hd' ? 'sd' : 'hd'
  L('toggleQuality click', { current: videoQuality.value, next })
  pendingQuality.value = true
  try {
    rtc.setRemoteQualityForAll(next)
  } finally { pendingQuality.value = false }
}

function applyPeerState(uid: string, patch: any) {
  const cur = statusByUser[uid] ?? { mic: 1, cam: 1, speakers: 1, visibility: 1 }
  statusByUser[uid] = {
    mic:        pick01(patch?.mic, cur.mic),
    cam:        pick01(patch?.cam, cur.cam),
    speakers:   pick01(patch?.speakers, cur.speakers),
    visibility: pick01(patch?.visibility, cur.visibility),
  }
  L('peer state changed', { uid, state: statusByUser[uid] })
}
function applySelfPref(pref: any) {
  if (!isEmpty(pref?.mic))        local.mic        = norm01(pref.mic, local.mic ? 1 : 0) === 1
  if (!isEmpty(pref?.cam))        local.cam        = norm01(pref.cam, local.cam ? 1 : 0) === 1
  if (!isEmpty(pref?.speakers))   local.speakers   = norm01(pref.speakers, local.speakers ? 1 : 0) === 1
  if (!isEmpty(pref?.visibility)) local.visibility = norm01(pref.visibility, local.visibility ? 1 : 0) === 1
  L('self prefs applied', { ...local })
}

function connectSocket() {
  if (socket.value && (socket.value.connected || (socket.value as any).connecting)) return
  L('socket: init', { ns: '/room' })
  socket.value = createAuthedSocket('/room', {
    path: '/ws/socket.io',
    transports: ['websocket'],
    autoConnect: true,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 500,
    reconnectionDelayMax: 5000,
  })

  socket.value?.on('connect', async () => {
    joinedRoomId.value = null
    if (joinInFlight.value || joinedRoomId.value === rid) return
    L('socket: connected', { id: socket.value?.id })
    try {
      const j:any = await safeJoin()
      if (j?.ok) applyJoinAck(j)
    } catch (e) { W('socket: join-after-connect failed', e) }
    if (pendingDeltas.length) {
      const merged = Object.assign({}, ...pendingDeltas.splice(0))
      L('socket: flush pending deltas', merged)
      try {
        const resp:any = await socket.value!.timeout(5000).emitWithAck('state', merged)
        if (!resp?.ok) pendingDeltas.unshift(merged)
      } catch { pendingDeltas.unshift(merged) }
    }
  })

  socket.value.on('connect_error', e => W('socket: error', e?.message))

  socket.value?.on('disconnect', () => { joinedRoomId.value = null })

  socket.value.on('force_logout', async () => {
    W('socket: force_logout')
    try { await onLeave() } finally {
      if ('localSignOut' in auth) await (auth as any).localSignOut()
      else await auth.logout()
    }
  })

  socket.value.on('state_changed', (p: any) => {
    L('socket: state_changed', p)
    applyPeerState(String(p.user_id), p)
  })
  
  socket.value.on('member_joined', (p: any) => {
    L('socket: member_joined', p)
    applyPeerState(String(p.user_id), p?.state || {})
  })
  
  socket.value.on('member_left', (p: any) => {
    const id = String(p.user_id)
    L('socket: member_left', { id })
    delete statusByUser[id]
    delete positionByUser[id]
  })
  
  socket.value.on('positions', (p: any) => {
    const ups = Array.isArray(p?.updates) ? p.updates : []
    for (const u of ups) {
      const id = String(u.user_id)
      const pos = Number(u.position)
      if (Number.isFinite(pos)) positionByUser[id] = pos
    }
    L('socket: positions', { count: ups.length })
  })
}

async function safeJoin() {
  if (!socket.value) connectSocket()
  if (joinedRoomId.value === rid && !joinInFlight.value) return { ok: true }
  if (joinInFlight.value) return joinInFlight.value
  if (!socket.value!.connected) {
    await new Promise<void>((res, rej) => {
      const t = setTimeout(() => rej(new Error('connect timeout')), 10000)
      socket.value!.once('connect', () => { clearTimeout(t); res() })
    })
  }
  joinInFlight.value = socket.value!.timeout(5000).emitWithAck('join', { room_id: rid, state: { ...local } })
  try {
    const ack = await joinInFlight.value
    if (ack?.ok) joinedRoomId.value = rid
    return ack
  } finally { joinInFlight.value = null }
}

function applyJoinAck(j: any) {
  Object.keys(positionByUser).forEach(k => delete (positionByUser as any)[k])
  Object.entries(j.positions || {}).forEach(([uid, pos]: any) => {
    const p = Number(pos)
    if (Number.isFinite(p)) positionByUser[String(uid)] = p
  })

  Object.keys(statusByUser).forEach(k => delete (statusByUser as any)[k])
  Object.entries(j.snapshot || {}).forEach(([uid, st]: any) => {
    statusByUser[uid] = {
      mic:        pick01(st.mic, 0),
      cam:        pick01(st.cam, 0),
      speakers:   pick01(st.speakers, 1),
      visibility: pick01(st.visibility, 1),
    }
  })

  if (j.self_pref) applySelfPref(j.self_pref)
}

const pendingDeltas: any[] = []
async function publishState(delta: Partial<{ mic: boolean; cam: boolean; speakers: boolean; visibility: boolean }>) {
  if (!socket.value || !socket.value.connected) {
    pendingDeltas.push(delta)
    L('queue delta (offline)', delta)
    return false
  }
  try {
    L('publish state', delta)
    const resp: any = await socket.value.timeout(5000).emitWithAck('state', delta)
    L('publish state ack', resp)
    return Boolean(resp?.ok)
  } catch (e) {
    W('publish state failed, queued', { delta, e })
    pendingDeltas.push(delta)
    return false
  }
}

const toggleFactory = (k: keyof typeof local, onEnable?: () => Promise<boolean | void>, onDisable?: () => Promise<void>) => async () => {
  if (pending[k]) return
  const want = !local[k]
  L('toggle click', { key: k, want })
  pending[k] = true
  try {
    if (want) {
      const okLocal = (await onEnable?.()) !== false
      L('toggle enable result', { key: k, okLocal })
      if (!okLocal) return
      local[k] = true
      if (k === 'speakers')   rtc.setAudioSubscriptionsForAll(true)
      if (k === 'visibility') rtc.setVideoSubscriptionsForAll(true)
      try { await publishState({ [k]: true } as any) } catch {}
    } else {
      await onDisable?.()
      local[k] = false
      if (k === 'speakers')   rtc.setAudioSubscriptionsForAll(false)
      if (k === 'visibility') rtc.setVideoSubscriptionsForAll(false)
      try { await publishState({ [k]: false } as any) } catch {}
    }
  } finally { pending[k] = false }
}

const toggleMic = toggleFactory('mic',
  async () => await rtc.enable('audioinput'),
  async () => { await rtc.disable('audioinput') }
)
const toggleCam = toggleFactory('cam',
  async () => await rtc.enable('videoinput'),
  async () => { await rtc.disable('videoinput') }
)
const toggleSpeakers  = toggleFactory('speakers',
  async () => {
    rtc.setAudioSubscriptionsForAll(true)
    return true
  },
  async () => rtc.setAudioSubscriptionsForAll(false)
)
const toggleVisibility = toggleFactory('visibility',
  async () => {
    rtc.setVideoSubscriptionsForAll(true)
    return true
  },
  async () => rtc.setVideoSubscriptionsForAll(false)
)

async function onLeave() {
  if (leaving.value) return
  leaving.value = true
  L('leave start')
  try {
    window.removeEventListener('pagehide', onPageHide)
    window.removeEventListener('beforeunload', onPageHide)
  } catch {}
  try {
    await rtc.disconnect()
    try {
      if (socket.value) {
        (socket.value.io.opts as any).reconnection = false
        socket.value.removeAllListeners?.()
        socket.value.close()
      }
    } catch {}
    socket.value = null
    roomId.value = null
    joinedRoomId.value = null
    await router.replace('/')
    L('leave done')
  } finally {
    leaving.value = false
  }
}
const onPageHide = () => {
  L('pagehide')
  void onLeave()
}

watch(() => auth.isAuthed, (ok) => {
  if (!ok) {
    W('auth lost')
    void onLeave()
  }
})
watch(() => rtc.remoteQuality.value, (nv, ov) => {
  L('quality store changed', { from: ov, to: nv, lk: 'VideoQuality.' + (nv === 'hd' ? 'High' : 'Low') })
})
watch(() => micOn.value,           v => L('local mic',        { on: v }))
watch(() => camOn.value,           v => L('local cam',        { on: v }))
watch(() => speakersOn.value,      v => L('local speakers',   { on: v }))
watch(() => visibilityOn.value,    v => L('local visibility', { on: v }))
watch(() => selectedMicId.value,   v => L('selected micId',   { id: v }))
watch(() => selectedCamId.value,   v => L('selected camId',   { id: v }))
watch(() => peerIds.value.slice(), v => L('peers list',       { ids: v }))

onMounted(async () => {
  L('mounted', { rid })
  try {
    if (!auth.ready) {
      try {
        await auth.init()
        L('auth.init done') } catch (e) { W('auth.init failed', e)
      }
    }
    const run = async () => {
      if (!rtc.permProbed.value && !micOn.value && !camOn.value) {
        L('probePermissions start')
        try {
          await rtc.probePermissions({ audio: true, video: true })
          L('probePermissions done') } catch (e) { W('probePermissions error', e)
        }
      }
    }
    if (document.visibilityState === 'visible') await run()
    else document.addEventListener('visibilitychange', async () => { if (document.visibilityState === 'visible') await run() }, { once: true })

    connectSocket()
    const j:any = await safeJoin()
    L('safeJoin ack', j)
    if (!j?.ok) {
      alert(j?.status === 404 ? 'Комната не найдена' : j?.status === 409 ? 'Комната заполнена' : 'Ошибка входа в комнату')
      await router.replace('/')
      return
    }

    await rtc.refreshDevices()
    L('devices refreshed', { mics: mics.value.length, cams: cams.value.length })

    applyJoinAck(j)

    rtc.initRoom({
      onMediaDevicesError: async (e: unknown) => {
        W('MediaDevicesError', e)
        if (!rtc.isBusyError(e)) return
        const msg = ((e as any)?.message || '') + ''
        const name = ((e as any)?.name || '') + ''
        const isVideo = /video|camera/i.test(msg) || /video/i.test(name)
        const isAudio = /audio|microphone/i.test(msg) || /audio/i.test(name)

        if (isVideo && camOn.value) {
          await rtc.fallback('videoinput')
          if (!selectedCamId.value) {
            camOn.value = false
            await publishState({ cam: false })
          }
        }
        if (isAudio && micOn.value) {
          await rtc.fallback('audioinput')
          if (!selectedMicId.value) {
            micOn.value = false
            await publishState({ mic: false })
          }
        }
      }
    })

    await rtc.connect(ws_url, j.token, { autoSubscribe: false })
    L('rtc.connect done', { localId: localId.value, peers: peerIds.value })

    rtc.setAudioSubscriptionsForAll(speakersOn.value)
    rtc.setVideoSubscriptionsForAll(visibilityOn.value)
    L('subscriptions set', { audio: speakersOn.value, video: visibilityOn.value })

    rtc.setRemoteQualityForAll(rtc.remoteQuality.value)
    L('initial quality applied', { to: rtc.remoteQuality.value })

    if (camOn.value) {
      const ok = await rtc.enable('videoinput')
      if (!ok) { W('camera auto-enable failed') } else { L('camera auto-enabled') }
    }
    if (micOn.value) {
      const ok = await rtc.enable('audioinput')
      if (!ok) { W('mic auto-enable failed') } else { L('mic auto-enabled') }
    }

    window.addEventListener('pagehide', onPageHide)
    window.addEventListener('beforeunload', onPageHide)
  } catch (e) {
    W('onMounted error', e)
    try { await rtc.disconnect() } catch {}
    alert('Ошибка входа в комнату')
    await router.replace('/')
  }
})

onBeforeUnmount(() => {
  L('beforeUnmount')
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
  background: $bg;
  aspect-ratio: 16 / 9;
  border: 2px solid transparent;
  box-shadow: inset 0 0 0 0 $color-primary;
  transition: border-color 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
  &.speaking {
    border-color: $color-primary;
    box-shadow: inset 0 0 0 6px $color-primary;
  }
}
video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  background: $black;
  filter: none !important;
  mix-blend-mode: normal !important;
  opacity: 1 !important;
}
.badges {
  position: absolute;
  left: 8px;
  top: 8px;
  display: flex;
  gap: 6px;
  z-index: 2;
  .badge {
    line-height: 1;
    padding: 4px 6px;
    border-radius: 8px;
    background: $black;
    border: 1px solid $fg;
    color: $fg;
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
    border: 1px solid $fg;
    cursor: pointer;
    background: $bg;
    color: $fg;
    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
    &.danger {
      background: $color-danger;
      color: $fg;
    }
  }
}
.perm-probe {
  margin: 0 12px 12px;
  display: flex;
  align-items: center;
  gap: 12px;
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
      border: 1px solid $fg;
      background: $bg;
      color: $fg;
    }
  }
}
</style>
