<template>
  <section class="card">
    <div class="panel">
      <div class="controls">
        <button class="ctrl" @click="toggleMic" :disabled="pending.mic || blockedSelf.mic">{{ micOn ? 'Микрофон ВКЛ' : 'Микрофон ВЫКЛ' }}</button>
        <button class="ctrl" @click="toggleCam" :disabled="pending.cam || blockedSelf.cam">{{ camOn ? 'Камера ВКЛ' : 'Камера ВЫКЛ' }}</button>
        <button class="ctrl" @click="toggleSpeakers" :disabled="pending.speakers || blockedSelf.speakers">{{ speakersOn ? 'Звук ВКЛ' : 'Звук ВЫКЛ' }}</button>
        <button class="ctrl" @click="toggleVisibility" :disabled="pending.visibility || blockedSelf.visibility">{{ visibilityOn ? 'Видео ВКЛ' : 'Видео ВЫКЛ' }}</button>
        <button class="ctrl" @click="toggleScreen" :disabled="pendingScreen || (!!screenOwnerId && screenOwnerId !== localId) || blockedSelf.screen">{{ isMyScreen ? 'Стрим ВКЛ' : 'Стрим ВЫКЛ' }}</button>
        <button class="ctrl" @click="toggleQuality" :disabled="pendingQuality">{{ videoQuality === 'hd' ? 'Качество HD' : 'Качество SD' }}</button>
        <button class="ctrl danger" @click="onLeave">Покинуть комнату</button>
      </div>

      <div class="devices">
        <select v-model="selectedMicId" @change="rtc.onDeviceChange('audioinput')" :disabled="!micOn || blockedSelf.mic || mics.length === 0">
          <option v-for="d in mics" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Микрофон' }}</option>
        </select>
        <select v-model="selectedCamId" @change="rtc.onDeviceChange('videoinput')" :disabled="!camOn || blockedSelf.cam || cams.length === 0">
          <option v-for="d in cams" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Камера' }}</option>
        </select>
      </div>
    </div>

    <div v-if="!isTheater" class="grid" :style="gridStyle">
      <div v-for="id in sortedPeerIds" :key="id" class="tile" :class="{ speaking: rtc.isSpeaking(id) }">
        <video :ref="rtc.videoRef(id)" playsinline autoplay :muted="id === localId" v-show="isOn(id,'cam') && !isBlocked(id,'cam')" />

        <div v-show="!isOn(id,'cam') || isBlocked(id,'cam')" class="ava-wrap">
          <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" class="ava-circle" />
        </div>

        <div class="vol-wrap" v-if="streamAudioKey">
          <button v-if="openVolumeFor !== streamAudioKey" class="vol-btn" @click.stop="toggleVolPopover(streamAudioKey)" :aria-expanded="openVolumeFor===streamAudioKey">🔊</button>
          <div class="vol-pop" :class="{ show: openVolumeFor === streamAudioKey }" @click.stop>
            <input class="vol-range" type="range" min="0" max="200" :disabled="!speakersOn || isBlocked(screenOwnerId,'speakers')" v-model.number="volUi[streamAudioKey]" @input="onVol(streamAudioKey, volUi[streamAudioKey])" />
            <span class="vol-val">{{ volUi[streamAudioKey] ?? 100 }}%</span>
          </div>
        </div>

        <div class="badges">
          <span class="badge">{{ emTri('mic', id) }}</span>
          <span class="badge">{{ emTri('cam', id) }}</span>
          <span class="badge">{{ emTri('speakers', id) }}</span>
          <span class="badge">{{ emTri('visibility', id) }}</span>
          <span class="badge">{{ emTri('screen', id) }}</span>
        </div>

        <div v-if="canModerate(id)" class="mod-controls" role="group" aria-label="Блокировки">
          <button class="mod" :class="{ on: isBlocked(id,'mic') }" @click="toggleBlock(id,'mic')">🎤⛔</button>
          <button class="mod" :class="{ on: isBlocked(id,'cam') }" @click="toggleBlock(id,'cam')">🎥⛔</button>
          <button class="mod" :class="{ on: isBlocked(id,'speakers') }" @click="toggleBlock(id,'speakers')">🔈⛔</button>
          <button class="mod" :class="{ on: isBlocked(id,'visibility') }" @click="toggleBlock(id,'visibility')">👁️⛔</button>
          <button class="mod" :class="{ on: isBlocked(id,'screen') }" @click="toggleBlock(id,'screen')">🖥️⛔</button>
        </div>
      </div>
    </div>

    <div v-else class="theater">
      <div class="stage">
        <video :ref="rtc.screenVideoRef(screenOwnerId)" playsinline autoplay />
        <div class="vol-wrap" v-if="streamAudioKey">
          <button v-if="openVolumeFor !== streamAudioKey" class="vol-btn" @click.stop="toggleVolPopover(streamAudioKey)">🔊</button>
          <div class="vol-pop" :class="{ show: openVolumeFor === streamAudioKey }" @click.stop>
            <input class="vol-range" type="range" min="0" max="200" :disabled="!speakersOn" v-model.number="volUi[streamAudioKey]" @input="onVol(streamAudioKey, volUi[streamAudioKey])" />
            <span class="vol-val">{{ volUi[streamAudioKey] ?? 100 }}%</span>
          </div>
        </div>
      </div>

      <div class="sidebar">
        <div v-for="id in sortedPeerIds" :key="id" class="tile side" :class="{ speaking: rtc.isSpeaking(id) }">
          <video :ref="rtc.videoRef(id)" playsinline autoplay :muted="id === localId" v-show="isOn(id,'cam') && !isBlocked(id,'cam')" />

          <div v-show="!isOn(id,'cam') || isBlocked(id,'cam')" class="ava-wrap">
            <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" class="ava-circle" />
          </div>

          <div class="vol-wrap" v-if="id !== localId">
            <button v-if="openVolumeFor !== id" class="vol-btn" @click.stop="toggleVolPopover(id)" :aria-expanded="openVolumeFor===id">🔊</button>
            <div class="vol-pop" :class="{ show: openVolumeFor === id }" @click.stop>
              <input class="vol-range" type="range" min="0" max="200" :disabled="!speakersOn || isBlocked(id,'speakers')" v-model.number="volUi[id]" @input="onVol(id, volUi[id])" />
              <span class="vol-val">{{ volUi[id] ?? 100 }}%</span>
            </div>
          </div>

          <div class="badges">
            <span class="badge">{{ emTri('mic', id) }}</span>
            <span class="badge">{{ emTri('cam', id) }}</span>
            <span class="badge">{{ emTri('speakers', id) }}</span>
            <span class="badge">{{ emTri('visibility', id) }}</span>
            <span class="badge">{{ emTri('screen', id) }}</span>
          </div>

          <div v-if="canModerate(id)" class="mod-controls" role="group" aria-label="Блокировки">
            <button class="mod" :class="{ on: isBlocked(id,'mic') }" @click="toggleBlock(id,'mic')">🎤⛔</button>
            <button class="mod" :class="{ on: isBlocked(id,'cam') }" @click="toggleBlock(id,'cam')">🎥⛔</button>
            <button class="mod" :class="{ on: isBlocked(id,'speakers') }" @click="toggleBlock(id,'speakers')">🔈⛔</button>
            <button class="mod" :class="{ on: isBlocked(id,'visibility') }" @click="toggleBlock(id,'visibility')">👁️⛔</button>
            <button class="mod" :class="{ on: isBlocked(id,'screen') }" @click="toggleBlock(id,'screen')">🖥️⛔</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showPermProbe" class="perm-probe">
      <button class="ctrl" @click="rtc.probePermissions({ audio: true, video: true })">
        Разрешить доступ к камере и микрофону
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Socket } from 'socket.io-client'
import { useAuthStore } from '@/store'
import { useRTC } from '@/services/rtc'
import { createAuthedSocket } from '@/services/sio'
import { api } from '@/services/axios'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'

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
const screenOwnerId = ref<string>('')
const pendingScreen = ref(false)
const isTheater = computed(() => !!screenOwnerId.value)
const isMyScreen = computed(() => screenOwnerId.value === localId.value)
const streamAudioKey = computed(() => screenOwnerId.value ? `${screenOwnerId.value}#s` : '')
const leaving = ref(false)
const ws_url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
const pendingQuality = ref(false)
const videoQuality = computed(() => rtc.remoteQuality.value)
const openVolumeFor = ref<string>('')
const volUi = reactive<Record<string, number>>({})

const avatarByUser = reactive(new Map<string, string | null>())
function avatarKey(id: string): string {
  const name = avatarByUser.get(id)
  return name ? `avatars/${name}` : ''
}
let avatarsTimer: number | null = null
function scheduleFetchAvatars() {
  if (avatarsTimer) clearTimeout(avatarsTimer)
  avatarsTimer = window.setTimeout(() => {
    avatarsTimer = null
    void fetchAvatars()
  }, 300)
}
async function fetchAvatars() {
  try {
    const { data } = await api.get<{ members: { id: number; avatar_name?: string|null }[] }>(
      `/rooms/${rid}/info`, { __skipAuth: true }
    )
    avatarByUser.clear()
    for (const m of (data?.members || [])) avatarByUser.set(String(m.id), m.avatar_name ?? null)
  } catch {}
}

const BADGE_ON = { mic:'🎤', cam:'🎥', speakers:'🔈', visibility:'👁️', screen:'🖥️' } as const
const BADGE_OFF = { mic:'🚫', cam:'🚫', speakers:'🚫', visibility:'🚫', screen:'🚫' } as const
const BADGE_BLK = { mic:'⛔', cam:'⛔', speakers:'⛔', visibility:'⛔', screen:'⛔' } as const

const showPermProbe = computed(() => !rtc.permProbed.value && !micOn.value && !camOn.value)
const sortedPeerIds = computed(() => {
  return [...peerIds.value].sort((a, b) => {
    const pa = positionByUser.get(a) ?? Number.POSITIVE_INFINITY
    const pb = positionByUser.get(b) ?? Number.POSITIVE_INFINITY
    return pa !== pb ? pa - pb : String(a).localeCompare(String(b))
  })
})
const gridStyle = computed(() => {
  const count = sortedPeerIds.value.length
  const cols = count <= 6 ? 3 : 4
  const rows = count <= 6 ? 2 : 3
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
}
async function toggleVolPopover(id: string) {
  await rtc.resumeAudio()
  volUi[id] = rtc.getUserVolume(id)
  openVolumeFor.value = openVolumeFor.value === id ? '' : id
}
function onDocClick() {
  openVolumeFor.value = ''
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
function emTri(kind: IconKind, id: string) {
  if (isBlocked(id, kind)) return BADGE_BLK[kind]
  return isOn(id, kind) ? BADGE_ON[kind] : BADGE_OFF[kind]
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
  try {
    const resp:any = await socket.value!.timeout(5000).emitWithAck('moderate', {user_id: Number(targetId), blocks: { [key]: want } })
    if (!resp?.ok) alert(resp?.status === 403 ? 'Недостаточно прав' : resp?.status === 404 ? 'Пользователь не в комнате' : 'Ошибка модерации')
  } catch { alert('Сеть/таймаут при модерации') }
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
    if (p?.role) rolesByUser.set(id, String(p.role))
    if (p?.blocks) applyBlocks(id, p.blocks)
    scheduleFetchAvatars()
  })

  socket.value.on('member_left', (p: any) => {
    const id = String(p.user_id)
    statusByUser.delete(id)
    positionByUser.delete(id)
    blockByUser.delete(id)
    rolesByUser.delete(id)
    if (openVolumeFor.value === id) openVolumeFor.value = ''
    delete volUi[id]
    avatarByUser.delete(id)
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

  socket.value.on('screen_owner', (p: any) => {
    screenOwnerId.value = p?.user_id ? String(p.user_id) : ''
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

  for (const k in volUi) {
    if (!statusByUser.has(k)) delete volUi[k]
  }

  if (j.self_pref) applySelfPref(j.self_pref)

  screenOwnerId.value = j.screen_owner ? String(j.screen_owner) : ''
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
const toggleSpeakers = toggleFactory('speakers',
  async () => {
    rtc.setAudioSubscriptionsForAll(true)
    await rtc.resumeAudio()
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

const toggleScreen = async () => {
  if (pendingScreen.value) return
  pendingScreen.value = true
  try {
    if (!isMyScreen.value) {
      const resp:any = await socket.value!.timeout(5000).emitWithAck('screen', { on: true })
      if (!resp?.ok) {
        if (resp?.status === 409 && resp?.owner) screenOwnerId.value = String(resp.owner)
        else if (resp?.status === 403 && resp?.error === 'blocked') alert('Стрим запрещён администратором')
        else alert('Не удалось начать трансляцию')
        return
      }
      screenOwnerId.value = localId.value
      const got = await rtc.prepareScreenShare({ audio: true })
      if (!got) {
        await socket.value!.timeout(5000).emitWithAck('screen', { on: false }).catch(() => {})
        screenOwnerId.value = ''
        alert('Браузер отклонил доступ к экрану')
        return
      }
      const pubOk = await rtc.publishPreparedScreen()
      if (!pubOk) {
        await socket.value!.timeout(5000).emitWithAck('screen', { on: false }).catch(() => {})
        screenOwnerId.value = ''
        alert('Ошибка публикации видеопотока')
        return
      }
    } else {
      await rtc.stopScreenShare()
      await socket.value!.timeout(5000).emitWithAck('screen', { on: false }).catch(() => {})
      screenOwnerId.value = ''
    }
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
    if (avatarsTimer) {
      try { clearTimeout(avatarsTimer) } catch {}
      avatarsTimer = null
    }
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
    scheduleFetchAvatars()

    rtc.initRoom({
      onMediaDevicesError: async (_e) => {},
      onScreenShareEnded: async () => {
        if (isMyScreen.value) {
          screenOwnerId.value = ''
          try { await socket.value!.timeout(5000).emitWithAck('screen', { on: false }) } catch {}
        }
      }
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
    try { await rtc.disconnect() } catch {}
    alert('Ошибка входа в комнату')
    await router.replace('/')
  }
})

onBeforeUnmount(() => { void onLeave() })
</script>

<style lang="scss" scoped>
.card {
  display: flex;
  .panel {
    display: flex;
    flex-direction: column;
    background-color: $black;
    .controls {
      margin: 12px;
      display: flex;
      flex-direction: column;
      width: 74px;
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
    .devices {
      margin: 12px;
      display: flex;
      flex-direction: column;
      width: 74px;
      gap: 12px;
      select {
        padding: 6px 8px;
        border-radius: 8px;
        border: 1px solid $fg;
        background: $bg;
        color: $fg;
      }
    }
  }
  .theater {
    display: grid;
    grid-template-columns: 1fr 320px;
    width: calc(100vw - 98px);
    height: 100vh;
    .stage {
      position: relative;
      border-radius: 12px;
      overflow: hidden;
      background: $black;
      video {
        width: 100%;
        height: 100%;
        object-fit: contain;
        background: $black;
      }
      .vol-wrap {
        position: absolute;
        top: 8px;
        right: 8px;
        z-index: 4;
      }
    }
    .sidebar {
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 12px;
      overflow-y: auto;
      .tile.side {
        min-height: 0;
      }
    }
  }
  .grid {
    display: grid;
    gap: 12px;
    margin: 12px;
    width: calc(100vw - 98px);
    height: 100vh;
  }
  .tile {
    min-height: 0;
    min-width: 0;
    position: relative;
    border-radius: 12px;
    border: 2px solid transparent;
    transition: border-color 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
    &.speaking {
      border-color: $color-primary;
      box-shadow: inset 0 0 0 6px $color-primary;
    }
    video {
      width: 100%;
      height: 100%;
      display: block;
      object-fit: cover;
      border-radius: 12px;
      background: $black;
    }
    .ava-wrap {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: $black;
      border-radius: 12px;
      z-index: 1;
    }
    .ava-circle {
      height: 40%;
      border-radius: 50%;
      object-fit: cover;
      background: $black;
      user-select: none;
      pointer-events: none;
    }
    .vol-wrap {
      position: absolute;
      top: 8px;
      right: 8px;
      z-index: 4;
      display: flex;
      align-items: center;
      gap: 6px;
      .vol-btn {
        padding: 4px 6px;
        border-radius: 8px;
        border: 1px solid $fg;
        background: $black;
        color: $fg;
        cursor: pointer;
        opacity: 0.9;
      }
      .vol-btn:hover {
        opacity: 1
      }
      .vol-pop {
        display: none;
        flex-direction: column;
        align-items: center;
        height: 160px;
        width: 40px;
        gap: 8px;
        background: $black;
        border: 1px solid $fg;
        border-radius: 8px;
        padding: 6px 8px;
        &.show {
          display: flex;
        }
        .vol-range {
          position: absolute;
          top: 90px;
          transform: rotate(-90deg);
          accent-color: $fg;
        }
        .vol-val {
          font-variant-numeric: tabular-nums;
        }
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
        line-height: 1;
        padding: 4px 6px;
        border-radius: 8px;
        background: $black;
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
        border: none;
        background: $black;
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
  .perm-probe {
    margin: 0 12px 12px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
}
</style>
