<template>
  <section class="room">
    <div v-if="!isTheater" class="grid" :style="gridStyle">
      <RoomTile
        v-for="id in sortedPeerIds"
        :key="id"
        :id="id"
        :local-id="localId"
        :speaking="rtc.isSpeaking(id)"
        :video-ref="stableVideoRef(id)"
        :fit-contain="fitContainInGrid"
        :default-avatar="defaultAvatar"
        :volume-icon="volumeIconForUser(id)"
        :state-icon="stateIcon"
        :is-on="isOn"
        :is-blocked="isBlocked"
        :user-name="userName"
        :avatar-key="avatarKey"
        :can-moderate="canModerate"
        :speakers-on="speakersOn"
        :open-panel-for="openPanelFor"
        :vol="volUi[id] ?? rtc.getUserVolume(id)"
        @toggle-panel="toggleTilePanel"
        @vol-input="onVol"
        @block="(key, uid) => toggleBlock(uid, key)"
        @kick="kickUser"
      />
    </div>

    <div v-else class="theater">
      <div class="stage">
        <video :ref="stableScreenRef(screenOwnerId)" playsinline autoplay />

        <div v-if="screenOwnerId !== localId && streamAudioKey" class="volume" @click.stop>
          <img :src="volumeIconForStream(streamAudioKey)" alt="vol" />
          <input type="range" min="0" max="200" :disabled="!speakersOn || isBlocked(screenOwnerId,'speakers')"
                 :value="streamVol" @input="onVol(streamAudioKey, Number(($event.target as HTMLInputElement).value))" />
          <span>{{ streamVol }}%</span>
        </div>
      </div>

      <div class="sidebar">
        <RoomTile
          v-for="id in sortedPeerIds"
          :key="id"
          :id="id"
          :local-id="localId"
          :side="true"
          :speaking="rtc.isSpeaking(id)"
          :video-ref="stableVideoRef(id)"
          :default-avatar="defaultAvatar"
          :volume-icon="volumeIconForUser(id)"
          :state-icon="stateIcon"
          :is-on="isOn"
          :is-blocked="isBlocked"
          :user-name="userName"
          :avatar-key="avatarKey"
          :can-moderate="canModerate"
          :speakers-on="speakersOn"
          :open-panel-for="openPanelFor"
          :vol="volUi[id] ?? rtc.getUserVolume(id)"
          @toggle-panel="toggleTilePanel"
          @vol-input="onVol"
          @block="(key, uid) => toggleBlock(uid, key)"
          @kick="kickUser"
        />
      </div>
    </div>

    <div class="panel">
      <button @click="onLeave" aria-label="Покинуть комнату">
        <img :src="iconLeaveRoom" alt="leave" />
      </button>

      <div v-if="showPermProbe" class="controls">
        <button class="probe" @click="rtc.probePermissions({ audio: true, video: true })">
          Разрешить доступ к камере и микрофону
        </button>
      </div>
      <div v-else class="controls">
        <button @click="toggleMic" :disabled="pending.mic || blockedSelf.mic" :aria-pressed="micOn">
          <img :src="stateIcon('mic', localId)" alt="mic" />
        </button>
        <button @click="toggleCam" :disabled="pending.cam || blockedSelf.cam" :aria-pressed="camOn">
          <img :src="stateIcon('cam', localId)" alt="cam" />
        </button>
        <button @click="toggleSpeakers" :disabled="pending.speakers || blockedSelf.speakers" :aria-pressed="speakersOn">
          <img :src="stateIcon('speakers', localId)" alt="speakers" />
        </button>
        <button @click="toggleVisibility" :disabled="pending.visibility || blockedSelf.visibility" :aria-pressed="visibilityOn">
          <img :src="stateIcon('visibility', localId)" alt="visibility" />
        </button>
        <button @click="toggleScreen" :disabled="pendingScreen || (!!screenOwnerId && screenOwnerId !== localId) || blockedSelf.screen" :aria-pressed="isMyScreen">
          <img :src="stateIcon('screen', localId)" alt="screen" />
        </button>
        <button @click="toggleQuality" :disabled="pendingQuality" aria-label="Качество видео">
          <img :src="videoQuality === 'hd' ? iconQualityHD : iconQualitySD" alt="quality" />
        </button>
      </div>

      <button @click.stop="toggleSettings" :aria-expanded="settingsOpen" aria-label="Настройки устройств">
        <img :src="iconSettings" alt="settings" />
      </button>

      <div v-show="settingsOpen" class="settings" aria-label="Настройки устройств" @click.stop>
        <label>
          <span>Микрофон</span>
          <select v-model="selectedMicId" @change="rtc.onDeviceChange('audioinput')" :disabled="mics.length === 0">
            <option v-for="d in mics" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Микрофон не обнаружен' }}</option>
          </select>
        </label>
        <label>
          <span>Камера</span>
          <select v-model="selectedCamId" @change="rtc.onDeviceChange('videoinput')" :disabled="cams.length === 0">
            <option v-for="d in cams" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Камера не обнаружена' }}</option>
          </select>
        </label>
      </div>
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
import RoomTile from '@/components/RoomTile.vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconQualitySD from '@/assets/svg/qualitySD.svg'
import iconQualityHD from '@/assets/svg/qualityHD.svg'
import iconLeaveRoom from '@/assets/svg/leaveRoom.svg'
import iconSettings from '@/assets/svg/settings.svg'
import iconVolumeMax from '@/assets/svg/volumeMax.svg'
import iconVolumeMid from '@/assets/svg/volumeMid.svg'
import iconVolumeLow from '@/assets/svg/volumeLow.svg'
import iconVolumeMute from '@/assets/svg/volumeMute.svg'
import iconMicOn from '@/assets/svg/micOn.svg'
import iconMicOff from '@/assets/svg/micOff.svg'
import iconMicBlocked from '@/assets/svg/micBlocked.svg'
import iconCamOn from '@/assets/svg/camOn.svg'
import iconCamOff from '@/assets/svg/camOff.svg'
import iconCamBlocked from '@/assets/svg/camBlocked.svg'
import iconSpkOn from '@/assets/svg/spkOn.svg'
import iconSpkOff from '@/assets/svg/spkOff.svg'
import iconSpkBlocked from '@/assets/svg/spkBlocked.svg'
import iconVisOn from '@/assets/svg/visOn.svg'
import iconVisOff from '@/assets/svg/visOff.svg'
import iconVisBlocked from '@/assets/svg/visBlocked.svg'
import iconScreenOn from '@/assets/svg/screenOn.svg'
import iconScreenOff from '@/assets/svg/screenOff.svg'
import iconScreenBlocked from '@/assets/svg/screenBlocked.svg'

type State01 = 0 | 1
type StatusState = { mic: State01; cam: State01; speakers: State01; visibility: State01 }
type BlockState = StatusState & { screen: State01 }
type IconKind = keyof StatusState | 'screen'

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
const statusByUser = reactive(new Map<string, StatusState>())
const positionByUser = reactive(new Map<string, number>())
const blockByUser  = reactive(new Map<string, BlockState>())
const rolesByUser = reactive(new Map<string, string>())
const nameByUser = reactive(new Map<string, string>())
const screenOwnerId = ref<string>('')
const openPanelFor = ref<string>('')
const pendingScreen = ref(false)
const settingsOpen = ref(false)
const isTheater = computed(() => !!screenOwnerId.value)
const isMyScreen = computed(() => screenOwnerId.value === localId.value)
const volUi = reactive<Record<string, number>>({})
const streamAudioKey = computed(() => screenOwnerId.value ? rtc.screenKey(screenOwnerId.value) : '')
const streamVol = computed(() => streamAudioKey.value ? (volUi[streamAudioKey.value] ?? rtc.getUserVolume(streamAudioKey.value)) : 100)
const leaving = ref(false)
const ws_url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
const pendingQuality = ref(false)
const videoQuality = computed(() => rtc.remoteQuality.value)
const fitContainInGrid = computed(() => !isTheater.value && sortedPeerIds.value.length < 3)

const rerr = (...a: any[]) => console.error('[ROOM]', ...a)

const avatarByUser = reactive(new Map<string, string | null>())
function avatarKey(id: string): string {
  const name = avatarByUser.get(id) || ''
  if (!name) return ''
  return name.startsWith('avatars/') ? name : `avatars/${name}`
}
function userName(id: string) {
  return nameByUser.get(id) || `user${id}`
}

function memoRef<K, F extends (k:K) => any> (cache: Map<any, any>, factory: F) {
  return (k: K) => {
    const c = cache.get(k)
    if (c) return c
    const f = factory(k)
    cache.set(k,f)
    return f
  }
}
const videoRefMemo    = new Map<string, (el: HTMLVideoElement|null)=>void>()
const screenRefMemo   = new Map<string, (el: HTMLVideoElement|null)=>void>()
const stableVideoRef  = memoRef(videoRefMemo,  (id:string)=> rtc.videoRef(id))
const stableScreenRef = memoRef(screenRefMemo, (id:string)=> id? rtc.screenVideoRef(id) : () => {})

const STATE_ICONS = {
  mic:        { on: iconMicOn,    off: iconMicOff,    blk: iconMicBlocked },
  cam:        { on: iconCamOn,    off: iconCamOff,    blk: iconCamBlocked },
  speakers:   { on: iconSpkOn,    off: iconSpkOff,    blk: iconSpkBlocked },
  visibility: { on: iconVisOn,    off: iconVisOff,    blk: iconVisBlocked },
  screen:     { on: iconScreenOn, off: iconScreenOff, blk: iconScreenBlocked },
} as const
function stateIcon(kind: IconKind, id: string) {
  if (isBlocked(id, kind)) return STATE_ICONS[kind].blk
  return isOn(id, kind) ? STATE_ICONS[kind].on : STATE_ICONS[kind].off
}
const toggleTilePanel = (id: string) => {
  if (id === localId.value) return
  settingsOpen.value = false
  openPanelFor.value = openPanelFor.value === id ? '' : id
}
function toggleSettings() {
  const next = !settingsOpen.value
  settingsOpen.value = next
  if (next) {
    openPanelFor.value = ''
    void rtc.refreshDevices().catch(() => {})
  }
}
function volumeIcon(val: number, enabled: boolean) {
  if (!enabled) return iconVolumeMute
  const v = Math.round(val)
  return v < 1 ? iconVolumeMute : v < 25 ? iconVolumeLow : v < 100 ? iconVolumeMid : iconVolumeMax
}
function volumeIconForUser(id: string) {
  return volumeIcon(volUi[id] ?? rtc.getUserVolume(id), speakersOn.value && !isBlocked(id,'speakers'))
}
function volumeIconForStream(key: string) {
  if (!key) return iconVolumeMute
  return volumeIcon(volUi[key] ?? rtc.getUserVolume(key), speakersOn.value && !isBlocked(screenOwnerId.value,'speakers'))
}

type Ack = { ok: boolean; status?: number; [k: string]: any } | null
async function sendAck(event: string, payload: any, timeoutMs = 5000): Promise<Ack> {
  try {
    return await socket.value!.timeout(timeoutMs).emitWithAck(event, payload)
  } catch (e:any) {
    rerr('ack fail', { event, payload, name: e?.name, message: e?.message })
    return null
  }
}
function ensureOk(resp: Ack, msgByCode: Record<number, string>, netMsg: string): boolean {
  if (resp && resp.ok) return true
  const code = resp?.status
  alert((code && msgByCode[code]) || netMsg)
  return false
}

const showPermProbe = computed(() => (!rtc.hasAudioInput.value && !rtc.hasVideoInput.value) || !rtc.permProbed.value)
const sortedPeerIds = computed(() => {
  return [...peerIds.value].sort((a, b) => {
    const pa = positionByUser.get(a) ?? Number.POSITIVE_INFINITY
    const pb = positionByUser.get(b) ?? Number.POSITIVE_INFINITY
    return pa !== pb ? pa - pb : String(a).localeCompare(String(b))
  })
})
const gridStyle = computed(() => {
  const count = sortedPeerIds.value.length
  const cols = count <= 2 ? 2 : count <= 6 ? 3 : 4
  const rows = count <= 2 ? 1 : count <= 6 ? 2 : 3
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

function onVol(id: string, v: number) {
  volUi[id] = v
  rtc.setUserVolume(id, v)
  void rtc.resumeAudio()
}
function onDocClick() {
  openPanelFor.value = ''
  settingsOpen.value = false
  void rtc.resumeAudio()
}

function rol(id: string): string { return rolesByUser.get(id) || 'user' }
const myRole = computed(() => rol(localId.value))
function isOn(id: string, kind: IconKind) {
  if (kind === 'screen') return id === screenOwnerId.value
  if (id === localId.value) {
    if (kind === 'mic') return micOn.value
    if (kind === 'cam') return camOn.value
    if (kind === 'speakers') return speakersOn.value
    return visibilityOn.value
  }
  const st = statusByUser.get(id)
  return st ? st[kind] === 1 : true
}
function isBlocked(id: string, kind: IconKind) {
  const st = blockByUser.get(id)
  return st ? st[kind] === 1 : false
}
const blockedSelf = computed<BlockState>(() => {
  const s = blockByUser.get(localId.value)
  return {
    mic: s?.mic ?? 0,
    cam: s?.cam ?? 0,
    speakers: s?.speakers ?? 0,
    visibility: s?.visibility ?? 0,
    screen: s?.screen ?? 0,
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

async function toggleBlock(targetId: string, key: keyof BlockState) {
  const want = !isBlocked(targetId, key)
  const resp = await sendAck('moderate', { user_id: Number(targetId), blocks: { [key]: want } })
  if (!ensureOk(resp, { 403: 'Недостаточно прав', 404: 'Пользователь не в комнате' }, 'Сеть/таймаут при модерации')) return
}

async function kickUser(targetId: string) {
  if (!canModerate(targetId)) return
  if (!confirm('Удалить пользователя из комнаты?')) return
  const resp = await sendAck('kick', { user_id: Number(targetId) })
  if (!ensureOk(resp, { 403: 'Недостаточно прав', 404: 'Пользователь не в комнате' }, 'Сеть/таймаут при удалении')) return
}

function applyPeerState(uid: string, patch: any) {
  const cur = statusByUser.get(uid) ?? { mic: 1, cam: 1, speakers: 1, visibility: 1 }
  statusByUser.set(uid, {
    mic:        pick01(patch?.mic, cur.mic),
    cam:        pick01(patch?.cam, cur.cam),
    speakers:   pick01(patch?.speakers, cur.speakers),
    visibility: pick01(patch?.visibility, cur.visibility),
  })
}
function applyBlocks(uid: string, patch: any) {
  const cur = blockByUser.get(uid) ?? { mic: 0, cam: 0, speakers: 0, visibility: 0, screen: 0 }
  blockByUser.set(uid, {
    mic:        pick01(patch?.mic, cur.mic),
    cam:        pick01(patch?.cam, cur.cam),
    speakers:   pick01(patch?.speakers, cur.speakers),
    visibility: pick01(patch?.visibility, cur.visibility),
    screen:     pick01(patch?.screen, cur.screen),
  })
}
function applySelfPref(pref: any) {
  if (!isEmpty(pref?.mic)) local.mic = norm01(pref.mic, local.mic ? 1 : 0) === 1
  if (!isEmpty(pref?.cam)) local.cam = norm01(pref.cam, local.cam ? 1 : 0) === 1
  if (!isEmpty(pref?.speakers)) local.speakers = norm01(pref.speakers, local.speakers ? 1 : 0) === 1
  if (!isEmpty(pref?.visibility)) local.visibility = norm01(pref.visibility, local.visibility ? 1 : 0) === 1
}

function purgePeerUI(id: string) {
  statusByUser.delete(id)
  positionByUser.delete(id)
  blockByUser.delete(id)
  rolesByUser.delete(id)
  nameByUser.delete(id)
  avatarByUser.delete(id)
  videoRefMemo.delete(id)
  screenRefMemo.delete(id)
  if (openPanelFor.value === id || openPanelFor.value === rtc.screenKey(id)) openPanelFor.value = ''
  delete volUi[id]
  delete volUi[rtc.screenKey(id)]
  if (screenOwnerId.value === id) screenOwnerId.value = ''
}

function connectSocket() {
  if (socket.value && socket.value.connected) return
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
      const resp = await sendAck('state', merged)
      if (!resp?.ok) pendingDeltas.unshift(merged)
    }
  })

  socket.value?.on('disconnect', () => {
    joinedRoomId.value = null
    openPanelFor.value = ''
  })

  socket.value.on('force_logout', async () => {
    try { await onLeave() } finally { await auth.localSignOut?.() }
  })

  socket.value.on('state_changed', (p: any) => {
    applyPeerState(String(p.user_id), p)
  })

  socket.value.on('member_joined', (p: any) => {
    const id = String(p.user_id)
    applyPeerState(id, p?.state || {})
    if (p?.role) rolesByUser.set(id, String(p.role))
    if (p?.blocks) applyBlocks(id, p.blocks)
    const av = p?.avatar_name
    if (typeof av === 'string' && av.trim() !== '') avatarByUser.set(id, av)
    const un = p?.username
    if (typeof un === 'string' && un.trim() !== '') nameByUser.set(id, String(un))
  })

  socket.value.on('member_left', (p: any) => {
    const id = String(p.user_id)
    purgePeerUI(id)
  })

  socket.value.on('positions', (p: any) => {
    const ups = Array.isArray(p?.updates) ? p.updates : []
    for (const u of ups) {
      const id = String(u.user_id)
      const pos = Number(u.position)
      if (Number.isFinite(pos)) positionByUser.set(id, pos)
    }
  })

  socket.value.on('moderation', async (p: any) => {
    const uid = String(p?.user_id ?? '')
    const blocks = (p?.blocks ?? {}) as Record<string, any>
    applyBlocks(uid, blocks)
    if (uid === String(localId.value)) {
      if ('cam' in blocks && norm01(blocks.cam, 0) === 1) {
        local.cam = false
        try { await rtc.disable('videoinput') } catch {}
      }
      if ('mic' in blocks && norm01(blocks.mic, 0) === 1) {
        local.mic = false
        try { await rtc.disable('audioinput') } catch {}
      }
      if ('speakers' in blocks && norm01(blocks.speakers, 0) === 1) {
        local.speakers = false
        rtc.setAudioSubscriptionsForAll(false)
      }
      if ('visibility' in blocks && norm01(blocks.visibility, 0) === 1) {
        local.visibility = false
        rtc.setVideoSubscriptionsForAll(false)
      }
      if ('screen' in blocks && norm01(blocks.screen, 0) === 1) {
        if (screenOwnerId.value === localId.value) { try { await rtc.stopScreenShare() } catch {} }
        screenOwnerId.value = ''
      }
    }
  })

  socket.value.on('force_leave', async (_p:any) => {
    try { await onLeave() } catch {}
  })

  socket.value.on('screen_owner', (p: any) => {
    const prev = screenOwnerId.value
    screenOwnerId.value = p?.user_id ? String(p.user_id) : ''
    if (openPanelFor.value === rtc.screenKey(prev)) openPanelFor.value = ''
    if (prev) delete volUi[rtc.screenKey(prev)]
  })
}

async function safeJoin() {
  if (!socket.value) connectSocket()
  if (socket.value?.connected && joinedRoomId.value === rid && !joinInFlight.value) return { ok: true }
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
  joinInFlight.value = sendAck('join', { room_id: rid, state: { ...local } })
  try {
    const ack = await joinInFlight.value
    if (ack?.ok) joinedRoomId.value = rid
    return ack
  } finally { joinInFlight.value = null }
}

function applyJoinAck(j: any) {
  positionByUser.clear()
  for (const [uid, pos] of Object.entries(j.positions || {})) {
    const p = Number(pos)
    if (Number.isFinite(p)) positionByUser.set(String(uid), p)
  }

  statusByUser.clear()
  for (const [uid, st] of Object.entries(j.snapshot || {})) {
    statusByUser.set(String(uid), {
      mic:        pick01(st.mic, 0),
      cam:        pick01(st.cam, 0),
      speakers:   pick01(st.speakers, 1),
      visibility: pick01(st.visibility, 1),
    })
  }

  blockByUser.clear()
  for (const [uid, bl] of Object.entries(j.blocked || {})) {
    blockByUser.set(String(uid), {
      mic:        pick01(bl.mic, 0),
      cam:        pick01(bl.cam, 0),
      speakers:   pick01(bl.speakers, 0),
      visibility: pick01(bl.visibility, 0),
      screen:     pick01(bl.screen, 0),
    })
  }

  rolesByUser.clear()
  for (const [uid, r] of Object.entries(j.roles || {})) {
    rolesByUser.set(String(uid), String(r || 'user'))
  }

  const prof = j.profiles || {}
  for (const [uid, m] of Object.entries(prof)) {
    const id = String(uid)
    const mm = m as any
    if (typeof mm?.avatar_name === 'string' && mm.avatar_name.trim() !== '') avatarByUser.set(id, mm.avatar_name)
    if (typeof mm?.username === 'string' && mm.username.trim() !== '') nameByUser.set(id, String(mm.username))
  }

  if (j.self_pref) applySelfPref(j.self_pref)

  screenOwnerId.value = j.screen_owner ? String(j.screen_owner) : ''
  const keepKey = screenOwnerId.value ? rtc.screenKey(screenOwnerId.value) : ''
  for (const k in volUi) {
    const isUserId = statusByUser.has(k)
    const isKeep = keepKey && k === keepKey
    if (!isUserId && !isKeep) delete volUi[k]
  }
}

const pendingDeltas: any[] = []
async function publishState(delta: Partial<{ mic: boolean; cam: boolean; speakers: boolean; visibility: boolean }>) {
  if (!socket.value || !socket.value.connected) {
    pendingDeltas.push(delta)
    return false
  }
  const resp = await sendAck('state', delta)
  if (resp?.ok) return true
  pendingDeltas.push(delta)
  return false
}

const toggleFactory = (k: keyof typeof local, onEnable?: () => Promise<boolean | void>, onDisable?: () => Promise<void>) => async () => {
  if (pending[k]) return
  if (blockedSelf.value[k]) return
  try {
    pending[k] = true
    const want = !local[k]
    if (want) {
      const okLocal = (await onEnable?.()) !== false
      if (!okLocal) return
      local[k] = true
      try { await publishState({ [k]: true } as any) } catch {}
    } else {
      await onDisable?.()
      local[k] = false
      try { await publishState({ [k]: false } as any) } catch {}
    }
  } finally { pending[k] = false }
}

const toggleMic = toggleFactory('mic',
  async () => await rtc.enable('audioinput'),
  async () => await rtc.disable('audioinput'),
)
const toggleCam = toggleFactory('cam',
  async () => await rtc.enable('videoinput'),
  async () => await rtc.disable('videoinput'),
)
const toggleSpeakers = toggleFactory('speakers',
  async () => {
    rtc.setAudioSubscriptionsForAll(true)
    return true
  },
  async () => rtc.setAudioSubscriptionsForAll(false),
)
const toggleVisibility = toggleFactory('visibility',
  async () => {
    rtc.setVideoSubscriptionsForAll(true)
    return true
  },
  async () => rtc.setVideoSubscriptionsForAll(false),
)

const toggleScreen = async () => {
  if (pendingScreen.value) return
  pendingScreen.value = true
  try {
    if (!isMyScreen.value) {
      const resp = await sendAck('screen', { on: true })
      if (!resp || !resp.ok) {
        if (resp?.status === 409 && resp?.owner) screenOwnerId.value = String(resp.owner)
        else if (resp?.status === 403 && resp?.error === 'blocked') alert('Стрим запрещён администратором')
        else alert('Не удалось начать трансляцию')
        return
      }
      screenOwnerId.value = localId.value
      const ok = await rtc.startScreenShare({ audio: true })
      if (!ok) {
        await sendAck('screen', { on: false })
        screenOwnerId.value = ''
        alert('Ошибка публикации видеопотока или доступ отклонён')
      }
    } else await rtc.stopScreenShare()
  } finally { pendingScreen.value = false }
}

async function onLeave() {
  if (leaving.value) return
  leaving.value = true
  try {
    document.removeEventListener('click', onDocClick)
    window.removeEventListener('pagehide', onPageHide)
    window.removeEventListener('beforeunload', onPageHide)
  } catch {}
  try {
    const s = socket.value
    socket.value = null
    if (s) {
      try { (s.io.opts as any).reconnection = false } catch {}
      try { s.removeAllListeners?.() } catch {}
      try { s.close() } catch {}
    }
    const disc = rtc.disconnect().catch(() => {})
    await router.replace('/')
    await disc
    roomId.value = null
    joinedRoomId.value = null
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
      onScreenShareEnded: async () => {
        if (isMyScreen.value) {
          screenOwnerId.value = ''
          try { await sendAck('screen', { on: false }) } catch {}
        }
      },
    })

    await rtc.connect(ws_url, j.token, { autoSubscribe: false })
    rtc.setAudioSubscriptionsForAll(local.speakers)
    rtc.setVideoSubscriptionsForAll(local.visibility)

    if (camOn.value && !blockedSelf.value.cam) {
      const ok = await rtc.enable('videoinput')
      if (!ok) {
        camOn.value = false
        void publishState({ cam: false })
      }
    }
    if (micOn.value && !blockedSelf.value.mic) {
      const ok = await rtc.enable('audioinput')
      if (!ok) {
        micOn.value = false
        void publishState({ mic: false })
      }
    }

    document.addEventListener('click', onDocClick)
    window.addEventListener('pagehide', onPageHide)
    window.addEventListener('beforeunload', onPageHide)
  } catch {
    rerr('room onMounted fatal')
    try { await rtc.disconnect() } catch {}
    alert('Ошибка входа в комнату')
    await router.replace('/')
  }
})

onBeforeUnmount(() => { void onLeave() })
</script>

<style lang="scss" scoped>
.room {
  display: flex;
  position: relative;
  flex-direction: column;
  padding: 10px;
  gap: 10px;
  overflow: hidden;
  .grid {
    display: grid;
    width: calc(100vw - 20px);
    height: calc(100dvh - 70px);
    gap: 10px;
  }
  .theater {
    display: grid;
    grid-template-columns: 1fr 284px;
    width: calc(100vw - 20px);
    height: calc(100dvh - 70px);
    gap: 10px;
    .stage {
      position: relative;
      border: 5px solid $dark;
      border-radius: 5px;
      overflow: hidden;
      video {
        width: 100%;
        height: 100%;
        object-fit: contain;
        background-color: $black;
      }
      .volume {
        display: flex;
        position: absolute;
        align-items: center;
        justify-content: space-between;
        top: 5px;
        left: 5px;
        padding: 5px;
        gap: 5px;
        width: min-content;
        height: 20px;
        border-radius: 5px;
        background-color: $dark;
        -webkit-overflow-scrolling: touch;
        img {
          width: 20px;
          height: 20px;
        }
        input[type="range"] {
          width: 160px;
          height: 10px;
          accent-color: $fg;
          cursor: pointer;
        }
        span {
          min-width: 32px;
          text-align: center;
          font-size: 12px;
        }
      }
    }
    .sidebar {
      display: flex;
      flex-direction: column;
      width: 284px;
      gap: 10px;
      overflow-y: auto;
      scrollbar-width: none;
      -ms-overflow-style: none;
    }
    .sidebar::-webkit-scrollbar {
      width: 0;
      height: 0;
    }
  }
  .panel {
    display: flex;
    position: relative;
    align-items: center;
    justify-content: space-between;
    width: calc(100vw - 20px);
    height: 50px;
    button {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 60px;
      height: 40px;
      border: none;
      border-radius: 5px;
      background-color: $dark;
      cursor: pointer;
      &:disabled {
        cursor: not-allowed;
      }
      img {
        width: 30px;
        height: 30px;
      }
    }
    .probe {
      width: fit-content;
      color: $fg;
      font-size: 16px;
      font-family: Manrope-Medium;
      line-height: 1;
    }
    .controls {
      display: flex;
      gap: 10px;
    }
    .settings {
      display: flex;
      position: absolute;
      flex-direction: column;
      right: 0;
      bottom: 60px;
      padding: 10px;
      gap: 20px;
      min-width: 250px;
      border-radius: 5px;
      background-color: $dark;
      z-index: 20;
      label {
        display: flex;
        flex-direction: column;
        gap: 5px;
        span {
          color: $fg;
        }
        select {
          padding: 5px;
          border-radius: 5px;
          background-color: $bg;
          color: $fg;
          font-size: 14px;
          font-family: Manrope-Medium;
          line-height: 1;
          &:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
        }
      }
    }
  }
}
</style>
