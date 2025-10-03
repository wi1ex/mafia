<template>
  <section class="card">
    <div class="grid" :style="gridStyle">
      <div v-for="id in sortedPeerIds" :key="id" class="tile" :class="{ speaking: rtc.isSpeaking(id) }">
        <video :ref="rtc.videoRef(id)" playsinline autoplay :muted="id === localId" />

        <div class="badges">
          <span class="badge">{{ emTri('mic', id) }}</span>
          <span class="badge">{{ emTri('cam', id) }}</span>
          <span class="badge">{{ emTri('speakers', id) }}</span>
          <span class="badge">{{ emTri('visibility', id) }}</span>
        </div>

        <div v-if="canModerate(id)" class="mod-controls" role="group" aria-label="Блокировки">
          <button class="mod" :class="{ on: isBlocked(id,'mic') }" @click="toggleBlock(id,'mic')">🎤⛔</button>
          <button class="mod" :class="{ on: isBlocked(id,'cam') }" @click="toggleBlock(id,'cam')">🎥⛔</button>
          <button class="mod" :class="{ on: isBlocked(id,'speakers') }" @click="toggleBlock(id,'speakers')">🔈⛔</button>
          <button class="mod" :class="{ on: isBlocked(id,'visibility') }" @click="toggleBlock(id,'visibility')">👁️⛔</button>
        </div>
      </div>
    </div>

    <div class="controls">
      <button class="ctrl" @click="toggleMic" :disabled="pending.mic || blockedSelf.mic">{{ micOn ? 'Микрофон ВКЛ' : 'Микрофон ВЫКЛ' }}</button>
      <button class="ctrl" @click="toggleCam" :disabled="pending.cam || blockedSelf.cam">{{ camOn ? 'Камера ВКЛ' : 'Камера ВЫКЛ' }}</button>
      <button class="ctrl" @click="toggleSpeakers" :disabled="pending.speakers || blockedSelf.speakers">{{ speakersOn ? 'Звук ВКЛ' : 'Звук ВЫКЛ' }}</button>
      <button class="ctrl" @click="toggleVisibility" :disabled="pending.visibility || blockedSelf.visibility">{{ visibilityOn ? 'Видео ВКЛ' : 'Видео ВЫКЛ' }}</button>
      <button class="ctrl" @click="toggleQuality" :disabled="pendingQuality">{{ videoQuality === 'hd' ? 'HD' : 'SD' }}</button>
      <button class="ctrl danger" @click="onLeave">Покинуть комнату</button>
    </div>

    <div v-if="showPermProbe" class="perm-probe">
      <button class="ctrl" @click="rtc.probePermissions({ audio: true, video: true })">
        Разрешить доступ к камере и микрофону
      </button>
    </div>

    <div class="devices">
      <label :class="{ disabled: !micOn || blockedSelf.mic }">
        {{ (!micOn || blockedSelf.mic) ? 'Включите микрофон, чтобы выбрать устройство' : 'Микрофон' }}
        <select v-model="selectedMicId" @change="rtc.onDeviceChange('audioinput')" :disabled="!micOn || blockedSelf.mic || mics.length === 0">
          <option v-for="d in mics" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Микрофон' }}</option>
        </select>
      </label>

      <label :class="{ disabled: !camOn || blockedSelf.cam }">
        {{ (!camOn || blockedSelf.cam) ? 'Включите камеру, чтобы выбрать устройство' : 'Камера' }}
        <select v-model="selectedCamId" @change="rtc.onDeviceChange('videoinput')" :disabled="!camOn || blockedSelf.cam || cams.length === 0">
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
const blockByUser = reactive<Record<string, UserState>>({})
const rolesByUser = reactive<Record<string, string>>({})
const leaving = ref(false)
const ws_url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
const pendingQuality = ref(false)
const videoQuality = computed(() => rtc.remoteQuality.value)

const BADGE_ON  = { mic:'🎤', cam:'🎥', speakers:'🔈', visibility:'👁️' } as const
const BADGE_OFF = { mic:'🔇', cam:'🚫', speakers:'🔇', visibility:'🙈' } as const
const BADGE_BLK = { mic:'⛔', cam:'⛔', speakers:'⛔', visibility:'⛔' } as const

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

function rol(id: string): string {
  return rolesByUser[id] || 'user'
}
const myRole = computed(() => rol(localId.value))
function isOn(id: string, kind: keyof UserState) {
  if (id === localId.value) {
    if (kind === 'mic') return micOn.value
    if (kind === 'cam') return camOn.value
    if (kind === 'speakers') return speakersOn.value
    return visibilityOn.value
  }
  const st = statusByUser[id]
  return st ? st[kind] === 1 : true
}
function isBlocked(id: string, kind: keyof UserState) {
  const st = blockByUser[id]
  return st ? st[kind] === 1 : false
}
function emTri(kind: keyof typeof BADGE_ON, id: string) {
  if (isBlocked(id, kind)) return BADGE_BLK[kind]
  return isOn(id, kind) ? BADGE_ON[kind] : BADGE_OFF[kind]
}

const blockedSelf = computed<UserState>(() => {
  const s = blockByUser[localId.value]
  return {
    mic: (s?.mic ?? 0) as State01,
    cam: (s?.cam ?? 0) as State01,
    speakers: (s?.speakers ?? 0) as State01,
    visibility: (s?.visibility ?? 0) as State01,
  }
})

function canModerate(targetId: string): boolean {
  if (targetId === localId.value) return false
  const me = myRole.value
  const trg = rol(targetId)
  if (me === 'admin') return true
  return me === 'host' && trg !== 'admin'
}

function toggleQuality() {
  if (pendingQuality.value) return
  const next = videoQuality.value === 'hd' ? 'sd' : 'hd'
  pendingQuality.value = true
  try {
    rtc.setRemoteQualityForAll(next)
  } finally { pendingQuality.value = false }
}

async function toggleBlock(targetId: string, key: keyof UserState) {
  const want = !isBlocked(targetId, key)
  try {
    const resp:any = await socket.value!.timeout(5000).emitWithAck('moderate', {user_id: Number(targetId), blocks: { [key]: want } })
    if (!resp?.ok) alert(resp?.status === 403 ? 'Недостаточно прав' : resp?.status === 404 ? 'Пользователь не в комнате' : 'Ошибка модерации')
  } catch { alert('Сеть/таймаут при модерации') }
}

function applyPeerState(uid: string, patch: any) {
  const cur = statusByUser[uid] ?? { mic: 1, cam: 1, speakers: 1, visibility: 1 }
  statusByUser[uid] = {
    mic:        pick01(patch?.mic, cur.mic),
    cam:        pick01(patch?.cam, cur.cam),
    speakers:   pick01(patch?.speakers, cur.speakers),
    visibility: pick01(patch?.visibility, cur.visibility),
  }
}
function applyBlocks(uid: string, patch: any) {
  const cur = blockByUser[uid] ?? { mic: 0, cam: 0, speakers: 0, visibility: 0 }
  blockByUser[uid] = {
    mic:        pick01(patch?.mic, cur.mic),
    cam:        pick01(patch?.cam, cur.cam),
    speakers:   pick01(patch?.speakers, cur.speakers),
    visibility: pick01(patch?.visibility, cur.visibility),
  }
}
function applySelfPref(pref: any) {
  if (!isEmpty(pref?.mic))        local.mic        = norm01(pref.mic, local.mic ? 1 : 0) === 1
  if (!isEmpty(pref?.cam))        local.cam        = norm01(pref.cam, local.cam ? 1 : 0) === 1
  if (!isEmpty(pref?.speakers))   local.speakers   = norm01(pref.speakers, local.speakers ? 1 : 0) === 1
  if (!isEmpty(pref?.visibility)) local.visibility = norm01(pref.visibility, local.visibility ? 1 : 0) === 1
}

function connectSocket() {
  if (socket.value && (socket.value.connected || (socket.value as any).connecting)) return
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
    if (joinInFlight.value || joinedRoomId.value === rid) return
    try {
      const j:any = await safeJoin()
      if (j?.ok) applyJoinAck(j)
    } catch {}
    if (pendingDeltas.length) {
      const merged = Object.assign({}, ...pendingDeltas.splice(0))
      try {
        const resp:any = await socket.value!.timeout(5000).emitWithAck('state', merged)
        if (!resp?.ok) pendingDeltas.unshift(merged)
      } catch { pendingDeltas.unshift(merged) }
    }
  })

  socket.value?.on('disconnect', () => { joinedRoomId.value = null })

  socket.value.on('force_logout', async () => {
    try { await onLeave() } finally { await auth.localSignOut?.() }
  })

  socket.value.on('state_changed', (p: any) => {
    applyPeerState(String(p.user_id), p)
  })

  socket.value.on('member_joined', (p: any) => {
    const id = String(p.user_id)
    applyPeerState(id, p?.state || {})
    if (p?.role) rolesByUser[id] = String(p.role)
    if (p?.blocks) applyBlocks(id, p.blocks)
  })

  socket.value.on('member_left', (p: any) => {
    const id = String(p.user_id)
    delete statusByUser[id]
    delete positionByUser[id]
    delete blockByUser[id]
    delete rolesByUser[id]
  })

  socket.value.on('positions', (p: any) => {
    const ups = Array.isArray(p?.updates) ? p.updates : []
    for (const u of ups) {
      const id = String(u.user_id)
      const pos = Number(u.position)
      if (Number.isFinite(pos)) positionByUser[id] = pos
    }
  })

  socket.value.on('moderation', async (p: any) => {
    const uid = String(p?.user_id ?? '')
    const blocks = p?.blocks || {}
    if (!uid) return
    applyBlocks(uid, blocks)
    if (uid === localId.value) {
      if (blocks.cam === '1') {
        local.cam = false
        try { await rtc.disable('videoinput') } catch {}
      }
      if (blocks.mic === '1') {
        local.mic = false
        try { await rtc.disable('audioinput') } catch {}
      }
      if (blocks.speakers === '1') {
        local.speakers = false
        rtc.setAudioSubscriptionsForAll(false)
      }
      if (blocks.visibility === '1') {
        local.visibility = false
        rtc.setVideoSubscriptionsForAll(false)
      }
    }
  })
}

async function safeJoin() {
  if (!socket.value) connectSocket()
  if (joinedRoomId.value === rid && !joinInFlight.value) return { ok: true }
  if (joinInFlight.value) return joinInFlight.value
  if (!socket.value!.connected) {
    await new Promise<void>((res, rej) => {
      const t = setTimeout(() => rej(new Error('connect timeout')), 10000)
      socket.value!.once('connect', () => {
        clearTimeout(t)
        res()
      })
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

  Object.keys(blockByUser).forEach(k => delete (blockByUser as any)[k])
  Object.entries(j.blocked || {}).forEach(([uid, bl]: any) => {
    blockByUser[uid] = {
      mic:        pick01(bl.mic, 0),
      cam:        pick01(bl.cam, 0),
      speakers:   pick01(bl.speakers, 0),
      visibility: pick01(bl.visibility, 0),
    }
  })

  Object.keys(rolesByUser).forEach(k => delete (rolesByUser as any)[k])
  Object.entries(j.roles || {}).forEach(([uid, r]: any) => { rolesByUser[uid] = String(r || 'user') })

  if (j.self_pref) applySelfPref(j.self_pref)
}

const pendingDeltas: any[] = []
async function publishState(delta: Partial<{ mic: boolean; cam: boolean; speakers: boolean; visibility: boolean }>) {
  if (!socket.value || !socket.value.connected) {
    pendingDeltas.push(delta)
    return false
  }
  try {
    const resp: any = await socket.value.timeout(5000).emitWithAck('state', delta)
    return Boolean(resp?.ok)
  } catch {
    pendingDeltas.push(delta)
    return false
  }
}

const toggleFactory = (k: keyof typeof local, onEnable?: () => Promise<boolean | void>, onDisable?: () => Promise<void>) => async () => {
  if (pending[k]) return
  if (blockedSelf.value[k]) return
  const want = !local[k]
  pending[k] = true
  try {
    if (want) {
      const okLocal = (await onEnable?.()) !== false
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
  } finally {
    leaving.value = false
  }
}
const onPageHide = () => { void onLeave() }

watch(() => auth.isAuthed, (ok) => { if (!ok) { void onLeave() } })

onMounted(async () => {
  try {
    if (!auth.ready) { try { await auth.init() } catch {} }
    connectSocket()
    const j:any = await safeJoin()
    if (!j?.ok) {
      alert(j?.status === 404 ? 'Комната не найдена' : j?.status === 409 ? 'Комната заполнена' : 'Ошибка входа в комнату')
      await router.replace('/')
      return
    }

    await rtc.refreshDevices()
    applyJoinAck(j)

    rtc.initRoom({
      onMediaDevicesError: async (_e) => {}
    })

    await rtc.connect(ws_url, j.token, { autoSubscribe: false })
    rtc.setAudioSubscriptionsForAll(local.speakers)
    rtc.setVideoSubscriptionsForAll(local.visibility)

    if (camOn.value && !blockedSelf.value.cam) { await rtc.enable('videoinput').catch(()=>{}) }
    if (micOn.value && !blockedSelf.value.mic) { await rtc.enable('audioinput').catch(()=>{}) }

    window.addEventListener('pagehide', onPageHide)
    window.addEventListener('beforeunload', onPageHide)
  } catch {
    try { await rtc.disconnect() } catch {}
    alert('Ошибка входа в комнату')
    await router.replace('/')
  }
})

onBeforeUnmount(() => { void onLeave() })
</script>

<style lang="scss" scoped>
.card {
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
    video {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      display: block;
      object-fit: cover;
      background: $black;
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
      }
    }
    .mod-controls {
      position: absolute;
      left: 8px;
      bottom: 8px;
      display: flex;
      gap: 6px;
      z-index: 3;
      .mod {
        padding: 4px 6px;
        border-radius: 8px;
        border: 1px solid $fg;
        background: $black;
        color: $fg;
        cursor: pointer;
        opacity: 0.85;
        &.on {
          background: $color-danger;
          color: $fg;
          border-color: $color-danger;
        }
      }
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
      &.disabled {
        opacity: 0.7;
      }
      select {
        padding: 6px 8px;
        border-radius: 8px;
        border: 1px solid $fg;
        background: $bg;
        color: $fg;
      }
    }
  }
}
</style>
