проверь есть ли еще какие-либо потенциальные проблемы которые могут возникнуть при любых сценариях на сайте при использовании всего функционала сайта одновременно тысячей человек в онлайне?

header.vue:
<template>
  <header class="bar">
    <div class="brand" aria-label="Mafia">DECEIT • games</div>

    <div v-if="!auth.isAuthed && !auth.foreignActive" class="login-box">
      <div id="tg-login" />
    </div>
    <div v-else-if="!auth.isAuthed && auth.foreignActive" class="login-box note">
      <span>Вы уже авторизованы в соседней вкладке</span>
    </div>

    <div v-else class="user">
      <router-link to="/profile" class="profile-link" aria-label="Профиль">
        <img v-minio-img="{ key: user.user?.avatar_name ? `avatars/${user.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Аватар" class="avatar" />
        <span class="nick" aria-live="polite">{{ user.user?.username || 'User' }}</span>
      </router-link>
      <button class="btn" type="button" @click="logout">Выйти</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, nextTick, ref } from 'vue'
import { useAuthStore, useUserStore } from '@/store'

import defaultAvatar from "@/assets/svg/defaultAvatar.svg"

const auth = useAuthStore()
const user  = useUserStore()

const BOT = import.meta.env.VITE_TG_BOT_NAME as string | undefined
const SIZE: 'large' | 'medium' | 'small' = 'large'

declare global { interface Window { __tg_cb__?: (u:any) => void } }

async function logout() { try { await auth.logout() } catch {} }

function mountTGWidget() {
  if (!BOT) return
  const box = document.getElementById('tg-login')
  if (!box) return
  box.innerHTML = ''
  document.querySelector('script[data-tg-widget="1"]')?.remove()
  window.__tg_cb__ = async (u:any) => { await auth.signInWithTelegram(u) }

  const s = document.createElement('script')
  s.async = true
  s.src = 'https://telegram.org/js/telegram-widget.js?19'
  s.dataset.telegramLogin = BOT
  s.dataset.size = SIZE
  s.dataset.userpic = 'true'
  s.dataset.onauth = '__tg_cb__(user)'
  s.setAttribute('data-tg-widget', '1')
  box.appendChild(s)
}

watch([() => auth.isAuthed, () => auth.foreignActive], async () => {
  if (!auth.isAuthed && !auth.foreignActive) {
    await nextTick()
    mountTGWidget()
  } else {
    document.getElementById('tg-login')?.replaceChildren()
  }
}, { flush: 'post' })

onMounted(async () => {
  if (!auth.isAuthed && !auth.foreignActive) {
    await nextTick()
    mountTGWidget()
  }
})

onBeforeUnmount(() => {
  delete window.__tg_cb__
})
</script>

<style lang="scss" scoped>
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  .brand {
    color: $fg;
  }
  .note {
    color: $grey;
    max-width: 460px;
  }
  .user {
    display: flex;
    align-items: center;
    gap: 10px;
    .profile-link {
      display: flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
      .avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        object-fit: cover;
      }
      .nick {
        color: $fg;
      }
    }
    .btn {
      padding: 6px 10px;
      border-radius: 8px;
      cursor: pointer;
    }
  }
}
</style>




roomtile.vue:
<template>
  <div class="tile" :class="[{ speaking }, side && 'side']" tabindex="0">
    <video v-show="showVideo" :ref="videoRef" playsinline autoplay :muted="id === localId" />

    <div v-show="!showVideo" class="ava-wrap">
      <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" />
    </div>

    <div class="titlebar" :class="{ 'has-vol': openVol }">
      <div class="titlebar-div">
        <button :disabled="id===localId" :aria-disabled="id===localId" @click.stop="$emit('toggle-panel', id)" :aria-expanded="openPanel">
          <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" />
          <span>{{ userName(id) }}</span>
        </button>

        <div class="status">
          <img v-if="isBlocked(id,'mic') || !isOn(id,'mic')" :src="stateIcon('mic', id)" alt="mic" />
          <img v-if="isBlocked(id,'cam') || !isOn(id,'cam')" :src="stateIcon('cam', id)" alt="cam" />
          <img v-if="isBlocked(id,'speakers') || !isOn(id,'speakers')" :src="stateIcon('speakers', id)" alt="spk" />
          <img v-if="isBlocked(id,'visibility') || !isOn(id,'visibility')" :src="stateIcon('visibility', id)" alt="vis" />
        </div>
      </div>

      <div v-if="id !== localId" class="volume">
        <button v-if="!openVol" @click.stop="$emit('toggle-volume', id)" :disabled="!speakersOn || isBlocked(id,'speakers')" aria-label="volume">
          <img :src="volumeIcon" alt="vol" />
        </button>
        <div v-else class="vol-inline" @click.stop>
          <img :src="volumeIcon" alt="vol" />
          <input type="range" min="0" max="200" :disabled="!speakersOn || isBlocked(id,'speakers')" :value="vol ?? 100"
                 @input="$emit('vol-input', id, Number(($event.target as HTMLInputElement).value))" />
          <span>{{ vol ?? 100 }}%</span>
        </div>
      </div>
    </div>

    <div v-if="openPanel" class="tile-panel" @click.stop>
      <button class="panel-close" aria-label="Закрыть" @click.stop="$emit('toggle-panel', id)">
        <img :src="iconClose" alt="close" />
      </button>

      <div class="panel-user">
        <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" />
        <div class="panel-info">
          <span>{{ userName(id) }}</span>
          <span>*инф. о пользователе*</span>
        </div>
      </div>

      <div v-if="canModerate(id)" class="admin-row" aria-label="Блокировки">
        <button @click="$emit('block','mic',id)" aria-label="block mic">
          <img :src="stateIcon('mic', id)" alt="mic" />
        </button>
        <button @click="$emit('block','cam',id)" aria-label="block cam">
          <img :src="stateIcon('cam', id)" alt="cam" />
        </button>
        <button @click="$emit('block','speakers',id)" aria-label="block speakers">
          <img :src="stateIcon('speakers', id)" alt="spk" />
        </button>
        <button @click="$emit('block','visibility',id)" aria-label="block visibility">
          <img :src="stateIcon('visibility', id)" alt="vis" />
        </button>
        <button @click="$emit('block','screen',id)" aria-label="block screen">
          <img :src="stateIcon('screen', id)" alt="scr" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import iconClose from '@/assets/svg/close.svg'

type IconKind = 'mic' | 'cam' | 'speakers' | 'visibility' | 'screen'

const props = withDefaults(defineProps<{
  id: string
  localId: string
  speaking: boolean
  side?: boolean
  defaultAvatar: string
  volumeIcon: string
  videoRef: (el: HTMLVideoElement | null) => void
  openPanelFor: string
  openVolFor: string
  speakersOn: boolean
  vol?: number
  stateIcon: (k: IconKind, id: string) => string
  isOn: (id: string, k: IconKind) => boolean
  isBlocked: (id: string, k: IconKind) => boolean
  userName: (id: string) => string
  avatarKey: (id: string) => string
  canModerate: (id: string) => boolean
}>(), { side: false })

defineEmits<{
  (e: 'toggle-panel', id: string): void
  (e: 'toggle-volume', id: string): void
  (e: 'vol-input', id: string, v: number): void
  (e: 'block', key: 'mic'|'cam'|'speakers'|'visibility'|'screen', id: string): void
}>()

const openPanel = computed(() => props.openPanelFor === props.id)
const openVol = computed(() => props.openVolFor === props.id)
const showVideo = computed(() => props.isOn(props.id, 'cam') && !props.isBlocked(props.id, 'cam'))
</script>

<style scoped lang="scss">
.tile {
  position: relative;
  border-radius: 5px;
  border: 2px solid transparent;
  transition: border-color 0.25s ease-in-out;
  &.speaking {
    border-color: $green;
  }
  video {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 3px;
    background-color: $black;
  }
  .ava-wrap {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    inset: 0;
    background-color: $black;
    border-radius: 3px;
    z-index: 1;
    img {
      height: 40%;
      border-radius: 50%;
      user-select: none;
    }
  }
  .titlebar {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: space-between;
    left: 5px;
    right: 5px;
    top: 5px;
    gap: 5px;
    height: 40px;
    border-radius: 3px;
    background-color: rgba($black, 0.5);
    backdrop-filter: blur(5px);
    z-index: 5;
    &.has-vol {
      z-index: 10;
    }
    .titlebar-div {
      display: flex;
      align-items: center;
      min-width: 0;
      button {
        display: flex;
        align-items: center;
        padding: 0 5px;
        gap: 5px;
        min-width: 0;
        border: none;
        background: none;
        cursor: pointer;
        &:disabled {
          cursor: default;
        }
        img {
          width: 24px;
          height: 24px;
          border-radius: 50%;
          object-fit: cover;
        }
        span {
          color: $fg;
          font-size: 20px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }
      .status {
        display: flex;
        align-items: center;
        gap: 5px;
        img {
          width: 24px;
          height: 24px;
        }
      }
    }
    .volume {
      display: flex;
      position: relative;
      -webkit-overflow-scrolling: touch;
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        border: none;
        border-radius: 3px;
        background-color: rgba($dark, 0.5);
        cursor: pointer;
        img {
          width: 24px;
          height: 24px;
        }
      }
      .vol-inline {
        display: flex;
        position: absolute;
        flex-direction: column;
        align-items: center;
        justify-content: space-between;
        top: -20px;
        right: 0;
        padding: 8px 5px;
        width: 30px;
        height: 200px;
        border: none;
        border-radius: 3px;
        background-color: $dark;
        cursor: pointer;
        img {
          width: 24px;
          height: 24px;
        }
        input[type="range"] {
          width: 140px;
          height: 10px;
          accent-color: $fg;
          transform: rotate(270deg);
        }
        span {
          text-align: center;
          font-size: 12px;
        }
      }
    }
  }
  .tile-panel {
    display: flex;
    position: absolute;
    flex-direction: column;
    inset: 0;
    padding: 5px;
    gap: 10px;
    background-color: rgba($black, 0.8);
    backdrop-filter: blur(5px);
    z-index: 10;
    .panel-close {
      position: absolute;
      top: 5px;
      right: 5px;
      width: 40px;
      height: 40px;
      border: none;
      border-radius: 3px;
      background-color: $dark;
      cursor: pointer;
      img {
        width: 24px;
        height: 24px;
      }
    }
    .panel-user {
      display: flex;
      align-items: flex-start;
      gap: 5px;
      img {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        object-fit: cover;
      }
      .panel-info {
        display: flex;
        flex-direction: column;
        span {
          font-size: 12px;
          font-weight: 400;
        }
      }
    }
    .admin-row {
      display: flex;
      gap: 11px;
      button {
        border-radius: 3px;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 5px 7px;
        border: none;
        background-color: rgba($grey, 0.2);
        cursor: pointer;
        img {
          width: 24px;
          height: 24px;
        }
      }
    }
  }
}
.tile.side {
  aspect-ratio: 16 / 9;
}
</style>





home.vue:
<template>
  <section class="card card-grid">
    <div class="left">
      <h2 class="title">Комнаты</h2>
      <div v-if="sortedRooms.length === 0" class="muted">Пока пусто</div>
      <ul class="list" ref="listEl">
        <li class="item" v-for="r in sortedRooms" :key="r.id" :class="{ active: r.id === selectedId }" tabindex="0" @click="selectRoom(r.id)">
          <div class="item_main">
            <span class="item_title">#{{ r.id }} — {{ r.title }}</span>
            <span class="item_meta">({{ r.occupancy }}/{{ r.user_limit }}) • владелец: {{ r.creator_name }}</span>
          </div>
          <span class="chev">›</span>
        </li>
      </ul>

      <div v-if="auth.isAuthed" class="create">
        <h3 class="subtitle">Создать комнату</h3>
        <input v-model.trim="title" class="input" placeholder="Название" maxlength="64" />
        <input v-model.number="limit" class="input" type="number" min="2" max="12" placeholder="Лимит" />
        <button class="btn" :disabled="creating || !valid" @click="onCreate">
          {{ creating ? 'Создаю...' : 'Создать' }}
        </button>
      </div>
    </div>

    <aside class="right" aria-live="polite" ref="rightEl" @click.self="clearSelection">
      <div v-if="!selectedId" class="placeholder muted">Скоро здесь будет красиво</div>

      <div v-else class="room-info">
        <div class="ri-head">
          <h3 class="ri-title">#{{ selectedRoom?.id }} — {{ selectedRoom?.title || '...' }}</h3>
          <div class="ri-meta">
            <span>Участников: {{ selectedRoom?.occupancy ?? 0 }}/{{ selectedRoom?.user_limit ?? 0 }}</span>
            <span>Владелец: {{ selectedRoom?.creator_name || '—' }}</span>
          </div>
        </div>

        <div class="ri-members">
          <h4 class="ri-subtitle">В комнате</h4>
          <div v-if="loadingInfo" class="muted">Загрузка…</div>
          <div v-else-if="(info?.members?.length ?? 0) === 0" class="muted">Пока никого</div>
          <ul v-else class="ri-grid">
            <li class="ri-user" v-for="m in info!.members" :key="m.id">
              <img class="ri-ava" v-minio-img="{ key: m.avatar_name ? `avatars/${m.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
              <div class="ri-u-main">
                <div class="ri-u-name">{{ m.username || ('user' + m.id) }}</div>
              </div>
            </li>
          </ul>
        </div>

        <div class="ri-actions">
          <button v-if="auth.isAuthed && selectedRoom && !isFullRoom(selectedRoom)" class="btn enter" @click="goRoom(selectedRoom.id)">Войти</button>
          <div v-else-if="auth.isAuthed && selectedRoom && isFullRoom(selectedRoom)" class="muted">Комната заполнена</div>
          <div v-else class="muted">Авторизуйтесь, чтобы войти</div>
        </div>
      </div>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store'
import { Socket } from 'socket.io-client'
import { api } from '@/services/axios'
import { createPublicSocket } from '@/services/sio'

import defaultAvatar from "@/assets/svg/defaultAvatar.svg"

type Room = {
  id: number
  title: string
  user_limit: number
  creator: number
  creator_name: string
  created_at: string
  occupancy: number
}
type RoomInfoMember = {
  id: number
  username?: string
  avatar_name?: string | null
}
type RoomMembers = { members: RoomInfoMember[] }

const router = useRouter()
const auth = useAuthStore()

const roomsMap = reactive(new Map<number, Room>())
const sio = ref<Socket | null>(null)
const listEl = ref<HTMLElement | null>(null)
const rightEl = ref<HTMLElement | null>(null)
const suppressedAutoselect = ref(true)

const title = ref('')
const limit = ref(12)
const creating = ref(false)

const infoTimers = new Map<number, number>()
const selectedId = ref<number | null>(null)
const info = ref<RoomMembers | null>(null)
const loadingInfo = ref(false)

const selectedRoom = computed(() => selectedId.value ? (roomsMap.get(selectedId.value) || null) : null)
const valid = computed(() => title.value.length > 0 && limit.value >= 2 && limit.value <= 12)
const sortedRooms = computed(() => Array.from(roomsMap.values()).sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)))

function isFullRoom(r: Room) { return r.occupancy >= r.user_limit }
function upsert(r: Room) { roomsMap.set(r.id, { ...(roomsMap.get(r.id) || {} as Room), ...r }) }
function remove(id: number) {
  roomsMap.delete(id)
  if (selectedId.value === id) {
    selectedId.value = null
    info.value = null
  }
}

async function fetchRoomInfo(id: number) {
  loadingInfo.value = true
  try {
    const { data } = await api.get<RoomMembers>(`/rooms/${id}/info`, { __skipAuth: true })
    info.value = data
  } catch {
    info.value = null
  } finally {
    loadingInfo.value = false
  }
}

function selectRoom(id: number) {
  if (selectedId.value === id) return
  suppressedAutoselect.value = false
  const prevId = selectedId.value
  selectedId.value = id
  if (prevId != null) {
    const t = infoTimers.get(prevId)
    if (t) {
      try { clearTimeout(t) } catch {}
      infoTimers.delete(prevId)
    }
  }
  void fetchRoomInfo(id)
}

function clearSelection() {
  if (selectedId.value == null) return
  const prevId = selectedId.value
  selectedId.value = null
  info.value = null
  suppressedAutoselect.value = true
  const t = infoTimers.get(prevId)
  if (t) {
    try { clearTimeout(t) } catch {}
    infoTimers.delete(prevId)
  }
}

function onGlobalPointerDown(e: PointerEvent) {
  const target = e.target as Node | null
  if ( (target && listEl.value && listEl.value.contains(target)) || (target && rightEl.value && rightEl.value.contains(target)) ) return
  clearSelection()
}

function goRoom(id: number) { router.push(`/room/${id}`) }

async function syncRoomsSnapshot() {
  if (!sio.value) return
  try {
    const resp: any = await sio.value.timeout(1500).emitWithAck('rooms_list')
    if (!resp?.ok || !Array.isArray(resp.rooms)) return
    const nextIds = new Set<number>()
    for (const r of resp.rooms as Room[]) {
      nextIds.add(r.id)
      upsert(r)
    }
    for (const id of Array.from(roomsMap.keys())) if (!nextIds.has(id)) roomsMap.delete(id)
  } catch {}
}

function startWS() {
  if (sio.value && (sio.value.connected || (sio.value as any).connecting)) return
  sio.value = createPublicSocket('/rooms', {
    path: '/ws/socket.io',
    transports: ['websocket'],
    autoConnect: true,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 500,
    reconnectionDelayMax: 5000,
  })

  sio.value.on('connect', syncRoomsSnapshot)

  sio.value.on('rooms_upsert', (r: Room) => {
   upsert(r)
   if (!selectedId.value && !suppressedAutoselect.value) selectRoom(r.id)
  })

  sio.value.on('rooms_remove', (p: { id: number }) => remove(p.id))

  sio.value.on('rooms_occupancy', async (p: { id: number; occupancy: number }) => {
    const cur = roomsMap.get(p.id)
    if (cur) roomsMap.set(p.id, { ...cur, occupancy: p.occupancy })
    if (selectedId.value === p.id) {
      const prev = infoTimers.get(p.id)
      if (prev) window.clearTimeout(prev)
      const roomId = p.id
      const t = window.setTimeout(() => {
        if (selectedId.value !== roomId) return
        void fetchRoomInfo(roomId)
        infoTimers.delete(roomId)
      }, 500)
      infoTimers.set(p.id, t)
    }
  })
}

function stopWS() {
  try { sio.value?.off?.() } catch {}
  try { sio.value?.close?.() } catch {}
  sio.value = null
}

async function createRoom(title: string, user_limit: number) {
  const { data } = await api.post<Room>('/rooms', { title, user_limit })
  upsert(data)
  return data
}
async function onCreate() {
  if (!valid.value || creating.value) return
  creating.value = true
  try {
    const r = await createRoom(title.value, limit.value)
    await router.push(`/room/${r.id}`)
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 409 && d === 'rooms_limit_global')      alert('Достигнут общий лимит активных комнат (100). Попробуйте позже.')
    else if (st === 409 && d === 'rooms_limit_user')   alert('У вас уже 3 активные комнаты. Закройте одну и попробуйте снова.')
    else if (st === 422 && (d === 'title_empty'))      alert('Название не должно быть пустым')
    else if (typeof d === 'string' && d)               alert(d)
    else if (d && typeof d === 'object' && d.detail)   alert(String(d.detail))
    else                                               alert('Ошибка создания комнаты')
  } finally { creating.value = false }
}

onMounted(() => {
  startWS()
  document.addEventListener('pointerdown', onGlobalPointerDown, { capture: true })
})

onBeforeUnmount(() => {
  infoTimers.forEach((t) => { try { clearTimeout(t) } catch {} })
  infoTimers.clear()
  stopWS()
  try { document.removeEventListener('pointerdown', onGlobalPointerDown, { capture: true } as any) } catch {}
})
</script>

<style lang="scss" scoped>
.card {
  &.card-grid {
    display: grid;
    grid-template-columns: 1fr 420px;
    gap: 16px;
    padding: 12px 16px;
  }
  .left {
    .title {
      color: $fg;
    }
  }
  .muted {
    color: $grey;
  }
  .list {
    margin: 8px 0 0;
    padding: 0;
    list-style: none;
  }
  .item {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    margin: 6px 0;
    border: 1px solid transparent;
    border-radius: 10px;
    cursor: pointer;
    color: $fg;
    background: transparent;
    transition: border-color 0.15s ease-in-out, background 0.15s ease-in-out;
    &.active {
      border-color: $blue;
      background: rgba(14, 165, 233, 0.07);
    }
    .item_main {
      display: flex;
      align-items: baseline;
      gap: 6px;
      .item_title {
        font-weight: 600;
      }
      .item_meta {
        margin-left: 6px;
        color: $grey;
      }
    }
    .chev {
      opacity: 0.6;
    }
  }
  .create {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 16px;
  }
  .input {
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid $fg;
    color: $fg;
    background: $bg;
  }
  .btn {
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    background: $green;
    color: $bg;
    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }
  .right {
    position: sticky;
    top: 12px;
    align-self: start;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
  }
  .placeholder {
    padding: 8px 4px;
  }
  .room-info {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px;
    .ri-head {
      .ri-title {
        margin: 0;
        color: $fg;
      }
      .ri-meta {
        display: flex;
        gap: 10px;
        color: $grey;
      }
    }
    .ri-members {
      .ri-subtitle {
        margin: 6px 0;
        color: $fg;
      }
      .ri-grid {
        list-style: none;
        margin: 8px 0 0;
        padding: 0;
        display: grid;
        grid-template-columns: 1fr;
        gap: 8px;
        max-height: 420px;
        overflow: auto;
        .ri-user {
          display: flex;
          gap: 10px;
          align-items: center;
          .ri-ava {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            object-fit: cover;
            background: $black;
          }
          .ri-u-main {
            .ri-u-name {
              font-weight: 600;
            }
          }
        }
      }
    }
    .ri-actions {
      .enter {
        width: 100%;
      }
    }
  }
}
</style>





profile.vue:
<template>
  <section class="profile card">
    <div class="page-actions">
      <router-link class="btn" :to="{ name: 'home' }" aria-label="На главную">На главную</router-link>
    </div>

    <nav class="tabs" aria-label="Профиль">
      <button class="tab active" aria-selected="true">Личные данные</button>
      <button class="tab" disabled>Статистика</button>
      <button class="tab" disabled>История игр</button>
    </nav>

    <div class="grid">
      <div class="block">
        <h3 class="title">Аватар</h3>
        <div class="avatar-row">
          <img class="avatar" v-minio-img="{ key: me.avatar_name ? `avatars/${me.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Текущий аватар" />
          <div class="actions">
            <input ref="fileEl" type="file" accept="image/jpeg,image/png" @change="onPick" hidden />
            <button class="btn primary" @click="fileEl?.click()" :disabled="busyAva">Изменить аватар</button>
            <button class="btn danger" v-if="me.avatar_name" @click="onDeleteAvatar" :disabled="busyAva">Удалить</button>
            <div class="hint">JPG/PNG, до 5 МБ</div>
          </div>
        </div>
      </div>

      <div class="block">
        <h3 class="title">Никнейм</h3>
        <div class="nick-row">
          <input class="input" v-model.trim="nick" maxlength="32" :disabled="busyNick" placeholder="Никнейм" />
          <button class="btn" @click="saveNick" :disabled="busyNick || nick === me.username || !validNick">{{ busyNick ? '...' : 'Сохранить' }}</button>
        </div>
        <div class="hint">
          2–32 символа: латиница, кириллица, цифры, <code>._-</code> (не начинается с <code>user</code>).
        </div>
      </div>

      <div v-if="crop.show" ref="modalEl" class="modal" @keydown.esc="cancelCrop" tabindex="0" aria-modal="true" aria-label="Кадрирование аватара" >
        <div class="modal-body">
          <canvas ref="canvasEl" @mousedown="dragStart" @mousemove="dragMove" @mouseup="dragStop" @mouseleave="dragStop" @wheel.passive="onWheel" />
          <input class="range" type="range" aria-label="Масштаб" :min="crop.min" :max="crop.max" step="0.01" :value="crop.scale" @input="onRange" />
          <div class="modal-actions">
            <button class="btn danger" @click="cancelCrop">Отменить</button>
            <button class="btn" @click="applyCrop" :disabled="busyAva">Загрузить</button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { api } from '@/services/axios'
import { useUserStore } from '@/store'
import defaultAvatar from '@/assets/svg/defaultAvatar.svg'

const userStore = useUserStore()
const me = reactive({ id: 0, username: '', avatar_name: null as string | null, role: '' })
const fileEl = ref<HTMLInputElement | null>(null)
const modalEl = ref<HTMLDivElement | null>(null)

const nick = ref('')
const busyNick = ref(false)
const validNick = computed(() => /^[a-zA-Zа-яА-Я0-9._-]{2,32}$/.test(nick.value) && !/^user/i.test(nick.value))

async function loadMe() {
  const { data } = await api.get('/users/profile_info')
  me.id = data.id
  me.username = data.username || ''
  me.avatar_name = data.avatar_name
  me.role = data.role
  nick.value = me.username
  try { await userStore.fetchMe?.() } catch {}
}

async function saveNick() {
  if (!validNick.value || busyNick.value || nick.value === me.username) return
  busyNick.value = true
  try {
    const { data } = await api.patch('/users/username', { username: nick.value })
    me.username = data.username
    try { await userStore.fetchMe?.() } catch {}
  } catch (e: any) {
    const st = e?.response?.status
    const d  = e?.response?.data?.detail
    if (st === 409 && d === 'username_taken') alert('Ник уже занят')
    else if (st === 422 && d === 'reserved_prefix') alert('Ник не должен начинаться с "user"')
    else alert('Не удалось сохранить ник')
  } finally { busyNick.value = false }
}

type Crop = {
  show: boolean
  img?: HTMLImageElement
  scale: number
  min: number
  max: number
  x: number
  y: number
  dragging: boolean
  sx: number
  sy: number
  type: 'image/jpeg'|'image/png'
}
const crop = reactive<Crop>({ show: false, scale: 1, min: 0.5, max: 3, x: 0, y: 0, dragging: false, sx: 0, sy: 0, type: 'image/jpeg' })
const canvasEl = ref<HTMLCanvasElement | null>(null)
const busyAva = ref(false)

function clamp(v:number, lo:number, hi:number) { return Math.min(hi, Math.max(lo, v)) }
function fitContain(imgW: number, imgH: number, boxW: number, boxH: number) {
  return Math.min(boxW / imgW, boxH / imgH)
}
function scaleTo(next: number) {
  if (!crop.img || !canvasEl.value) return
  const c = canvasEl.value!
  const Cx = c.width / 2, Cy = c.height / 2
  const u = (Cx - crop.x) / crop.scale
  const v = (Cy - crop.y) / crop.scale
  crop.scale = next
  crop.x = Cx - u * next
  crop.y = Cy - v * next
  clampPosition()
  redraw()
}

async function onPick(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  ;(e.target as HTMLInputElement).value = ''
  if (!f) return
  if (!['image/jpeg', 'image/png'].includes(f.type)) {
    alert('Только JPG/PNG')
    return
  }
  if (f.size > 5 * 1024 * 1024) {
    alert('Файл больше 5 МБ')
    return
  }

  const url = URL.createObjectURL(f)
  const img = new Image()
  img.onload = async () => {
    URL.revokeObjectURL(url)
    crop.img = img
    crop.type = (f.type === 'image/png' ? 'image/png' : 'image/jpeg')
    crop.show = true
    await nextTick()
    modalEl.value?.focus()
    document.body.style.overflow = 'hidden'
    const canvas = canvasEl.value!
    const dpr = Math.max(1, window.devicePixelRatio || 1)
    const S = 240
    canvas.width = S * dpr
    canvas.height = S * dpr
    canvas.style.width = S + 'px'
    canvas.style.height = S + 'px'
    const s = fitContain(img.width, img.height, canvas.width, canvas.height)
    crop.min = s
    crop.max = s * 3
    crop.scale = s
    crop.x = (canvas.width - img.width * s) / 2
    crop.y = (canvas.height - img.height * s) / 2
    clampPosition()
    requestAnimationFrame(redraw)
  }
  img.onerror = () => {
    URL.revokeObjectURL(url)
    alert('Не удалось открыть изображение')
  }
  img.src = url
}

function redraw() {
  const c = canvasEl.value
  const img = crop.img
  if (!c || !img) return
  const ctx = c.getContext('2d')!
  ctx.clearRect(0,0,c.width,c.height)
  ctx.fillStyle = '#000'
  ctx.fillRect(0,0,c.width,c.height)
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high' as any
  ctx.drawImage(img, crop.x, crop.y, img.width * crop.scale, img.height * crop.scale)
}
function onRange(e: Event) {
  const next = clamp(Number((e.target as HTMLInputElement).value), crop.min, crop.max)
  scaleTo(next)
}
function clampPosition() {
  const c = canvasEl.value!, img = crop.img!
  const w = img.width * crop.scale, h = img.height * crop.scale
  crop.x = w <= c.width  ? (c.width - w)/2  : Math.min(0, Math.max(c.width - w, crop.x))
  crop.y = h <= c.height ? (c.height - h)/2 : Math.min(0, Math.max(c.height - h, crop.y))
}
function dragStart(ev: MouseEvent) {
  crop.dragging = true
  crop.sx = ev.clientX - crop.x
  crop.sy = ev.clientY - crop.y
}
function dragMove(ev: MouseEvent) {
  if (!crop.dragging) return
  crop.x = ev.clientX - crop.sx
  crop.y = ev.clientY - crop.sy
  clampPosition()
  redraw()
}
function dragStop() {
  crop.dragging = false
}
function onWheel(ev: WheelEvent) {
  const dir = ev.deltaY > 0 ? -1 : 1
  const next = Math.min(crop.max, Math.max(crop.min, crop.scale * (1 + dir * 0.04)))
  if (next === crop.scale) return
  scaleTo(next)
}

function cancelCrop() {
  crop.show = false
  crop.img = undefined
  document.body.style.overflow = ''
}

async function applyCrop() {
  if (!canvasEl.value) return
  busyAva.value = true
  try {
    const OUT = 512
    const dpr = 1
    const src = canvasEl.value
    const tmp = document.createElement('canvas')
    tmp.width = OUT * dpr
    tmp.height = OUT * dpr
    const tctx = tmp.getContext('2d')!
    const img = crop.img!
    tctx.imageSmoothingEnabled = true
    tctx.imageSmoothingQuality = 'high' as any
    const k = (tmp.width / src.width)
    tctx.drawImage(img, crop.x * k, crop.y * k, img.width * crop.scale * k, img.height * crop.scale * k)
    const blob: Blob = await new Promise((res, rej) => tmp.toBlob(b => b ? res(b) : rej(new Error('toBlob')), crop.type === 'image/png' ? 'image/png' : 'image/jpeg', 0.92))
    if (blob.size > 5 * 1024 * 1024) {
      alert('Получившийся файл больше 5 МБ')
      return
    }
    const fd = new FormData()
    fd.append('file', new File([blob], crop.type === 'image/png' ? 'avatar.png' : 'avatar.jpg', { type: crop.type }))
    const { data } = await api.post('/users/avatar', fd)
    me.avatar_name = data.avatar_name || null
    try { await userStore.fetchMe?.() } catch {}
    cancelCrop()
  } catch (e: any) {
    const st = e?.response?.status
    const d  = e?.response?.data?.detail
    if (st === 415 || d === 'unsupported_media_type') alert('Только JPG/PNG')
    else if (st === 413) alert('Файл больше 5 МБ')
    else alert('Не удалось загрузить аватар')
  } finally { busyAva.value = false }
}

async function onDeleteAvatar() {
  if (!confirm('Удалить аватар?')) return
  busyAva.value = true
  try {
    await api.delete('/users/avatar')
    me.avatar_name = null
    try { await userStore.fetchMe?.() } catch {}
  } catch { alert('Не удалось удалить аватар') } finally { busyAva.value = false }
}

onMounted(() => {
  loadMe().catch(() => {})
})

onBeforeUnmount(() => {
  document.body.style.overflow = ''
})
</script>

<style lang="scss" scoped>
.profile {
  &.card {
    padding: 12px 16px;
  }
  .btn {
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    background: $green;
    color: $bg;
    border: 1px solid $green;
    &.primary {
      background: $blue;
      border-color: $blue;
    }
    &.danger {
      background: $red;
      border-color: $red;
      color: $fg;
    }
    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }
  .hint {
    margin-top: 4px;
    color: $grey;
    font-size: 12px;
  }
  .page-actions {
    display: flex;
    justify-content: flex-start;
    margin-bottom: 24px;
    .btn {
      text-decoration: none;
    }
  }
  .tabs {
    display: flex;
    gap: 12px;
    margin-bottom: 12px;
    .tab {
      padding: 8px 12px;
      border-radius: 8px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      background: $bg;
      color: $fg;
      &.active {
        border-color: $blue;
        background: rgba(14, 165, 233, 0.07);
      }
      &:disabled {
        opacity: 0.6;
        cursor: not-allowed;
      }
    }
  }
  .grid {
    display: grid;
    gap: 12px;
    grid-template-columns: 1fr 1fr;
  }
  .block {
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    padding: 12px;
    .title {
      margin: 0 0 10px;
      color: $fg;
    }
    .avatar-row {
      display: flex;
      gap: 12px;
      align-items: center;
      .avatar {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        object-fit: cover;
        background: $black;
      }
      .actions {
        display: flex;
        gap: 12px;
        align-items: flex-end;
      }
    }
    .nick-row {
      display: flex;
      gap: 12px;
      align-items: center;
      .input {
        padding: 8px 10px;
        border-radius: 8px;
        border: 1px solid $fg;
        color: $fg;
        background: $bg;
        min-width: 240px;
      }
    }
  }
  .modal {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(2px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
    overscroll-behavior: contain;
    .modal-body {
      background: $bg;
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 12px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      canvas {
        background: $black;
        border-radius: 8px;
        width: 240px;
        height: 240px;
      }
      .range {
        width: 100%;
        accent-color: $fg;
      }
      .modal-actions {
        display: flex;
        gap: 12px;
        justify-content: space-between;
      }
    }
  }
}
</style>







room.vue:
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
        :open-vol-for="openVolFor"
        :vol="volUi[id] ?? rtc.getUserVolume(id)"
        @toggle-panel="toggleTilePanel"
        @toggle-volume="toggleVolume"
        @vol-input="onVol"
        @block="(key, uid) => toggleBlock(uid, key)"
      />
    </div>

    <div v-else class="theater">
      <div class="stage">
        <video :ref="stableScreenRef(screenOwnerId)" playsinline autoplay />
        <div v-if="screenOwnerId !== localId" class="volume">
          <button v-if="openVolFor !== streamAudioKey" @click.stop="toggleVolume(streamAudioKey)"
                  :disabled="!speakersOn || isBlocked(screenOwnerId,'speakers')" aria-label="volume">
            <img :src="volumeIconForStream(streamAudioKey)" alt="vol" />
          </button>
          <div v-else class="vol-inline" @click.stop>
            <img :src="volumeIconForStream(streamAudioKey)" alt="vol" />
            <input type="range" min="0" max="200" :disabled="!speakersOn || isBlocked(screenOwnerId,'speakers')"
                   v-model.number="volUi[streamAudioKey]" @input="onVol(streamAudioKey, volUi[streamAudioKey])" />
            <span>{{ volUi[streamAudioKey] ?? 100 }}%</span>
          </div>
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
          :open-vol-for="openVolFor"
          :vol="volUi[id] ?? rtc.getUserVolume(id)"
          @toggle-panel="toggleTilePanel"
          @toggle-volume="toggleVolume"
          @vol-input="onVol"
          @block="(key, uid) => toggleBlock(uid, key)"
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

      <button ref="settingsBtnRef" @click.stop="toggleSettings" :aria-expanded="settingsOpen" aria-label="Настройки устройств">
        <img :src="iconSettings" alt="settings" />
      </button>

      <div v-show="settingsOpen" class="settings" aria-label="Настройки устройств" @click.stop>
        <label class="sel">
          <span>Микрофон</span>
          <select v-model="selectedMicId" @change="rtc.onDeviceChange('audioinput')" :disabled="mics.length === 0">
            <option v-for="d in mics" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Микрофон' }}</option>
          </select>
        </label>
        <label class="sel">
          <span>Камера</span>
          <select v-model="selectedCamId" @change="rtc.onDeviceChange('videoinput')" :disabled="cams.length === 0">
            <option v-for="d in cams" :key="d.deviceId" :value="d.deviceId">{{ d.label || 'Камера' }}</option>
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
const openVolFor = ref<string>('')
const pendingScreen = ref(false)
const settingsOpen = ref(false)
const settingsBtnRef = ref<HTMLButtonElement | null>(null)
const isTheater = computed(() => !!screenOwnerId.value)
const isMyScreen = computed(() => screenOwnerId.value === localId.value)
const streamAudioKey = computed(() => screenOwnerId.value ? rtc.screenKey(screenOwnerId.value) : '')
const leaving = ref(false)
const ws_url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
const pendingQuality = ref(false)
const videoQuality = computed(() => rtc.remoteQuality.value)
const volUi = reactive<Record<string, number>>({})

const avatarByUser = reactive(new Map<string, string | null>())
function avatarKey(id: string): string {
  const name = avatarByUser.get(id)
  return name ? `avatars/${name}` : ''
}
function userName(id: string) {
  return nameByUser.get(id) || `user-${id}`
}

const videoRefMemo = new Map<string, (el: HTMLVideoElement | null) => void>()
function stableVideoRef(id: string) {
  const cached = videoRefMemo.get(id)
  if (cached) return cached
  const fn = rtc.videoRef(id)
  videoRefMemo.set(id, fn)
  return fn
}
const screenRefMemo = new Map<string, (el: HTMLVideoElement | null) => void>()
function stableScreenRef(uid: string) {
  const cached = screenRefMemo.get(uid)
  if (cached) return cached
  const fn = rtc.screenVideoRef(uid)
  screenRefMemo.set(uid, fn)
  return fn
}

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
async function toggleTilePanel(id: string) {
  if (id === localId.value) return
  settingsOpen.value = false
  if (openPanelFor.value === id) {
    openPanelFor.value = ''
    return
  }
  openPanelFor.value = id
  openVolFor.value = ''
}
function toggleVolume(id: string) {
  if (id === localId.value) return
  settingsOpen.value = false
  if (openVolFor.value === id) {
    openVolFor.value = ''
    return
  }
  openVolFor.value = id
  openPanelFor.value = ''
  void rtc.resumeAudio()
  volUi[id] = rtc.getUserVolume(id)
}
function toggleSettings() {
  const next = !settingsOpen.value
  settingsOpen.value = next
  if (next) {
    openPanelFor.value = ''
    openVolFor.value = ''
    void rtc.refreshDevices().catch(() => {})
  }
}
function volumeIconForStream(key: string): string {
  if (!key) return iconVolumeMute
  if (!speakersOn.value || isBlocked(screenOwnerId.value, 'speakers')) return iconVolumeMute
  const raw = Math.round(volUi[key] ?? rtc.getUserVolume(key))
  if (raw < 1) return iconVolumeMute
  if (raw < 25) return iconVolumeLow
  if (raw < 100) return iconVolumeMid
  return iconVolumeMax
}
function volumeIconForUser(id: string): string {
  if (!speakersOn.value || isBlocked(id, 'speakers')) return iconVolumeMute
  const raw = Math.round(volUi[id] ?? rtc.getUserVolume(id))
  if (raw < 1) return iconVolumeMute
  if (raw < 25) return iconVolumeLow
  if (raw < 100) return iconVolumeMid
  return iconVolumeMax
}

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
}
function onDocClick() {
  openPanelFor.value = ''
  openVolFor.value = ''
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
      try {
        const resp:any = await socket.value!.timeout(5000).emitWithAck('state', merged)
        if (!resp?.ok) pendingDeltas.unshift(merged)
      } catch { pendingDeltas.unshift(merged) }
    }
  })

  socket.value?.on('disconnect', () => {
    joinedRoomId.value = null
    openPanelFor.value = ''
    openVolFor.value = ''
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
    if (p?.avatar_name !== undefined) avatarByUser.set(id, p.avatar_name || null)
    if (p?.username) nameByUser.set(id, p.username)
  })

  socket.value.on('member_left', (p: any) => {
    const id = String(p.user_id)
    statusByUser.delete(id)
    positionByUser.delete(id)
    blockByUser.delete(id)
    rolesByUser.delete(id)
    if (openPanelFor.value === id || openPanelFor.value === rtc.screenKey(id)) openPanelFor.value = ''
    if (openVolFor.value === id || openVolFor.value === rtc.screenKey(id)) openVolFor.value = ''
    delete volUi[id]
    delete volUi[rtc.screenKey(id)]
    avatarByUser.delete(id)
    videoRefMemo.delete(id)
    screenRefMemo.delete(id)
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
    const prev = screenOwnerId.value
    screenOwnerId.value = p?.user_id ? String(p.user_id) : ''
    if (openPanelFor.value === rtc.screenKey(prev)) openPanelFor.value = ''
    if (openVolFor.value === rtc.screenKey(prev)) openVolFor.value = ''
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

  const prof = j.profiles || {}
  for (const [uid, m] of Object.entries(prof)) {
    const id = String(uid)
    const mm = m as any
    if (mm?.avatar_name !== undefined) avatarByUser.set(id, mm.avatar_name || null)
    if (mm?.username) nameByUser.set(id, mm.username)
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
      const resp: any = await socket.value!.timeout(5000).emitWithAck('screen', { on: true })
      if (!resp?.ok) {
        if (resp?.status === 409 && resp?.owner) screenOwnerId.value = String(resp.owner)
        else if (resp?.status === 403 && resp?.error === 'blocked') alert('Стрим запрещён администратором')
        else alert('Не удалось начать трансляцию')
        return
      }
      screenOwnerId.value = localId.value
      const ok = await rtc.startScreenShare({ audio: true })
      if (!ok) {
        await socket.value!.timeout(5000).emitWithAck('screen', { on: false }).catch(() => {})
        screenOwnerId.value = ''
        alert('Ошибка публикации видеопотока или доступ отклонён')
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
.room {
  display: flex;
  flex-direction: column;
  padding: 10px;
  gap: 10px;
  overflow: hidden;
  .grid {
    display: grid;
    width: calc(100vw - 20px);
    height: calc(100vh - 80px);
    gap: 10px;
  }
  .theater {
    display: grid;
    grid-template-columns: 1fr 250px;
    width: calc(100vw - 20px);
    height: calc(100vh - 80px);
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
        top: 5px;
        right: 5px;
        -webkit-overflow-scrolling: touch;
        button {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 40px;
          height: 40px;
          border: none;
          border-radius: 5px;
          background-color: $dark;
          cursor: pointer;
          img {
            width: 24px;
            height: 24px;
          }
        }
        .vol-inline {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: space-between;
          padding: 8px 5px;
          width: 30px;
          height: 200px;
          border: none;
          border-radius: 5px;
          background-color: $dark;
          cursor: pointer;
          img {
            width: 24px;
            height: 24px;
          }
          input[type="range"] {
            width: 140px;
            height: 10px;
            accent-color: $fg;
            transform: rotate(270deg);
          }
          span {
            text-align: center;
            font-size: 12px;
          }
        }
      }
    }
    .sidebar {
      display: flex;
      flex-direction: column;
      width: 250px;
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
      width: 75px;
      height: 50px;
      border: none;
      border-radius: 5px;
      background-color: $dark;
      cursor: pointer;
      &:disabled {
        cursor: not-allowed;
      }
      img {
        width: 32px;
        height: 32px;
      }
    }
    .probe {
      width: fit-content;
      color: $fg;
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
      gap: 10px;
      min-width: 250px;
      border-radius: 5px;
      background-color: $dark;
      z-index: 20;
      .sel {
        display: flex;
        flex-direction: column;
        gap: 5px;
        color: $fg;
        select {
          padding: 5px;
          border-radius: 5px;
          background-color: $bg;
          color: $fg;
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






router index.ts:
import { createRouter, createWebHistory, type RouteRecordRaw, type RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/store'

const BASE_TITLE = 'Deceit'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/pages/Home.vue'),
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/pages/Profile.vue'),
    meta: { requiresAuth: true, title: 'Профиль' },
  },
  {
    path: '/room/:id(\\d+)',
    name: 'room',
    component: () => import('@/pages/Room.vue'),
    meta: { requiresAuth: true, title: 'Комната' },
  },
  { path: '/:pathMatch(.*)*', redirect: { name: 'home' } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

function setTitle(to: RouteLocationNormalized): void {
  const t = (to.meta?.title as string | undefined) ?? ''
  const id = to.name === 'room' ? String(to.params.id ?? '') : ''
  document.title = t ? `${t}${id ? ` #${id}` : ''}` : BASE_TITLE
}

router.beforeEach(async (to) => {
  if (!to.meta?.requiresAuth) return true

  const auth = useAuthStore()
  if (!auth.ready) await auth.init()
  if (!auth.isAuthed) return { name: 'home' }

  if (to.name === 'room') {
    const id = Number(to.params.id)
    if (!Number.isFinite(id) || id <= 0) return { name: 'home' }
  }
  return true
})

router.afterEach((to) => setTitle(to))

router.onError((err) => {
  const msg = String(err?.message || '')
  if (/Loading chunk \d+ failed|ChunkLoadError|Failed to fetch dynamically imported module/.test(msg)) {
    location.reload()
    return
  }
  router.replace({ name: 'home' }).catch(() => {})
})

export default router





axios.ts:
import axios,{
  AxiosError, AxiosHeaders, AxiosResponse, InternalAxiosRequestConfig,
} from 'axios'

declare module 'axios' {
  export interface InternalAxiosRequestConfig<D = unknown> {
    __retry401?: boolean
    __skipAuth?: boolean
  }
}

export const api = axios.create({
  baseURL: '/api',
  timeout: 15_000,
  withCredentials: true,
  headers: { Accept: 'application/json','X-Requested-With': 'XMLHttpRequest' }
})

let accessToken = ''
let isRefreshing = false
let pendingWaiters: Array<(t: string | null) => void> = []

type RefreshResult = { token: string | null; data?: any }
let refreshInFlight: Promise<RefreshResult> | null = null

const tokenRefreshedListeners: Array<(t: string) => void> = []
const authExpiredListeners: Array<() => void> = []

function notifyTokenRefreshed(tok: string) { for (const cb of [...tokenRefreshedListeners]) { try { cb(tok) } catch {} } }
function notifyAuthExpired() { for (const cb of [...authExpiredListeners]) { try { cb() } catch {} } }

export function addTokenRefreshedListener(cb: (t: string) => void) { tokenRefreshedListeners.push(cb) }
export function removeTokenRefreshedListener(cb: (t: string) => void) {
  const i = tokenRefreshedListeners.indexOf(cb)
  if (i >= 0) tokenRefreshedListeners.splice(i, 1)
}
export function addAuthExpiredListener(cb: () => void) { authExpiredListeners.push(cb) }
export function removeAuthExpiredListener(cb: () => void) {
  const i = authExpiredListeners.indexOf(cb)
  if (i >= 0) authExpiredListeners.splice(i, 1)
}
export async function refreshAccessToken(notifyOnFail = false): Promise<string | null> {
  const { token } = await startRefresh()
  if (!token && notifyOnFail) notifyAuthExpired()
  return token
}
export async function refreshAccessTokenFull(notifyOnFail = false): Promise<any | null> {
  const { token, data } = await startRefresh()
  if (!token && notifyOnFail) notifyAuthExpired()
  return token ? data : null
}
export function getAccessToken(): string { return accessToken }

export class AuthExpiredError extends Error { constructor() { super('auth_expired') } }
export function setAuthHeader(tok: string): void { accessToken = tok }

function setReqAuthHeader(cfg: InternalAxiosRequestConfig, tok: string): void {
  cfg.headers = AxiosHeaders.from(cfg.headers || {})
  cfg.headers.set('Authorization', `Bearer ${tok}`)
}

async function doRefreshWithTimeout(): Promise<RefreshResult> {
  const ctrl = new AbortController()
  let tid: ReturnType<typeof setTimeout>
  const refreshPromise = (async () => {
    try {
      const headers = AxiosHeaders.from({ Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' })
      const { data } = await api.post('/auth/refresh', undefined, { signal: ctrl.signal, headers, __skipAuth: true })
      const tok = (data?.access_token as string | undefined) ?? null
      setAuthHeader(tok ?? '')
      if (tok) notifyTokenRefreshed(tok)
      return { token: tok, data }
    } catch {
      setAuthHeader('')
      return { token: null }
    } finally { clearTimeout(tid) }
  })()
  const timeoutPromise = new Promise<string | null>((resolve) => {
    tid = setTimeout(() => {
      try { ctrl.abort() } catch {}
      resolve(null)
    }, 10_000)
  })
  const res = await Promise.race([refreshPromise, timeoutPromise])
  return (res && typeof res === 'object' && 'token' in res) ? res as RefreshResult : { token: res as string | null }
}
async function startRefresh(): Promise<RefreshResult> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const out = await doRefreshWithTimeout()
      refreshInFlight = null
      return out
    })()
  }
  return refreshInFlight
}

api.interceptors.request.use((cfg: InternalAxiosRequestConfig) => {
  if (accessToken && !cfg.__skipAuth) setReqAuthHeader(cfg, accessToken)
  return cfg
})

const AUTH_PATHS = ['/auth/refresh', '/auth/telegram', '/auth/logout'] as const
const isAuthEndpoint = (url: string) => AUTH_PATHS.some(p => url.includes(p))
const isRefreshWorthyStatus = (st?: number) => st === 401 || st === 419 || st === 440

api.interceptors.response.use(
  (res: AxiosResponse) => res,
  async (error: AxiosError) => {
    const status = error.response?.status
    const cfg = (error.config || {}) as InternalAxiosRequestConfig
    const url = cfg.url || ''
    if (!isRefreshWorthyStatus(status) || cfg.__retry401 || isAuthEndpoint(url)) return Promise.reject(error)
    cfg.__retry401 = true

    if (!isRefreshing) {
      isRefreshing = true
      try {
        const { token: tok } = await startRefresh()
        pendingWaiters.forEach(cb => cb(tok))
        pendingWaiters = []
        if (!tok) {
          notifyAuthExpired()
          return Promise.reject(new AuthExpiredError())
        }
        setReqAuthHeader(cfg, tok)
        return api(cfg)
      } finally { isRefreshing = false }
    }

    if (pendingWaiters.length > 200) {
      pendingWaiters = []
      return Promise.reject(new Error('refresh_queue_overflow'))
    }
    return new Promise((resolve, reject) => {
      pendingWaiters.push((tok) => {
        if (!tok) {
          notifyAuthExpired()
          return reject(new AuthExpiredError())
        }
        setReqAuthHeader(cfg, tok)
        resolve(api(cfg))
      })
    })
  }
)





mediaCache.ts:
import { api } from '@/services/axios'

type Stored = {
  key: string
  version: number
  blob: Blob
  ctype?: string
}
const DB_NAME = 'media-cache'
const DB_VER = 1
const STORE = 'objects'
const urlMap = new Map<string, string>()
const urlOrder: string[] = []
const URL_MAX = 300

function rememberURL(key: string, url: string) {
  urlMap.set(key, url)
  const idx = urlOrder.indexOf(key)
  if (idx !== -1) urlOrder.splice(idx, 1)
  urlOrder.push(key)
  while (urlOrder.length > URL_MAX) {
    const oldKey = urlOrder.shift()
    if (!oldKey) continue
    const u = urlMap.get(oldKey)
    if (u) {
      try { URL.revokeObjectURL(u) } catch {}
      urlMap.delete(oldKey)
    }
  }
}

export function clearObjectURL(key: string) {
  const u = urlMap.get(key)
  if (u) {
    try { URL.revokeObjectURL(u) } catch {}
    urlMap.delete(key)
  }
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VER)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        const st = db.createObjectStore(STORE, { keyPath: 'key' })
        st.createIndex('version', 'version', { unique: false })
      }
    }
    req.onerror = () => reject(req.error)
    req.onsuccess = () => resolve(req.result)
  })
}

async function withStore<T>(mode: IDBTransactionMode, fn: (st: IDBObjectStore) => Promise<T>): Promise<T> {
  const db = await openDB()
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(STORE, mode)
    const st = tx.objectStore(STORE)
    tx.oncomplete = () => resolve(res!)
    tx.onerror = () => reject(tx.error)
    let res: T
    ;(async () => { try { res = await fn(st) } catch (e) { reject(e) } })()
  })
}

async function get(key: string): Promise<Stored | undefined> {
  return withStore('readonly', st => new Promise((resolve, reject) => {
    const req = st.get(key)
    req.onsuccess = () => resolve(req.result as Stored | undefined)
    req.onerror = () => reject(req.error)
  }))
}

async function put(val: Stored): Promise<void> {
  await withStore('readwrite', st => new Promise<void>((resolve, reject) => {
    const req = st.put(val)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  }))
}

export function parseAvatarVersion(name: string): number {
  const m = name.match(/^\d+-([0-9]{9,})\.[a-z0-9]+$/i)
  return m ? Number(m[1]) : 0
}

export async function presign(key: string): Promise<string> {
  const { data } = await api.get('/media/presign', { params: { key }, __skipAuth: true })
  return String(data?.url || '')
}

export async function fetchBlobByPresign(key: string): Promise<Blob> {
  const url = await presign(key)
  const resp = await fetch(url, { credentials: 'omit', cache: 'no-store' })
  if (!resp.ok) throw new Error('fetch_failed')
  return await resp.blob()
}

export async function getImageURL(key: string, version: number, loader?: (key: string)=>Promise<Blob>): Promise<string> {
  const u = urlMap.get(key)
  if (u) return u

  try {
    const cur = await get(key)
    if (cur && cur.version === version) {
      const cached = URL.createObjectURL(cur.blob)
      rememberURL(key, cached)
      return cached
    }
  } catch {}

  const load = loader || fetchBlobByPresign
  const blob = await load(key)
  try { await put({ key, version, blob, ctype: blob.type }) } catch {}
  const url = URL.createObjectURL(blob)
  rememberURL(key, url)
  return url
}




minioImg.ts:
import type { Directive, DirectiveBinding } from 'vue'
import { getImageURL, parseAvatarVersion, clearObjectURL } from '@/services/mediaCache'

type MinioVal = | string | {
  key: string
  version?: number
  placeholder?: string
  fallback?: string
  lazy?: boolean
}

type ElEx = HTMLImageElement & { __m_req?: number; __m_obs?: IntersectionObserver | null }

function norm(v: unknown): { key: string; version?: number; placeholder?: string; fallback?: string; lazy: boolean } {
  if (typeof v === 'string') return { key: v, lazy: true }
  const o = (v ?? {}) as any
  return {
    key: String(o.key || ''),
    version: typeof o.version === 'number' ? o.version : undefined,
    placeholder: typeof o.placeholder === 'string' ? o.placeholder : undefined,
    fallback: typeof o.fallback === 'string' ? o.fallback : undefined,
    lazy: o.lazy !== false,
  }
}

async function loadInto(el: ElEx, val: MinioVal) {
  const { key, version, placeholder, fallback } = norm(val)
  const myReq = (el.__m_req = (el.__m_req || 0) + 1)

  if (!key) {
    if (placeholder) el.src = placeholder
    return
  }

  if (placeholder && !el.src) el.src = placeholder

  const v = typeof version === 'number' ? version : parseAvatarVersion(key.split('/').pop() || '')

  try {
    const url = await getImageURL(key, v)
    if (el.__m_req === myReq) el.src = url
  } catch {
    if (fallback && el.__m_req === myReq) el.src = fallback
  }
}

function mount(el: ElEx, binding: DirectiveBinding<MinioVal>) {
  el.setAttribute('referrerpolicy', 'no-referrer')

  const { lazy } = norm(binding.value)
  el.loading = lazy ? 'lazy' : 'eager'

  const run = () => loadInto(el, binding.value)

  if (lazy && 'IntersectionObserver' in window) {
    const obs = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) {
        try { obs.disconnect() } catch {}
        el.__m_obs = null
        run()
      }
    }, { rootMargin: '200px' })
    el.__m_obs = obs
    obs.observe(el)
  } else {
    run()
  }
}

function update(el: ElEx, binding: DirectiveBinding<MinioVal>) {
  const cur = norm(binding.value)
  const prev = binding.oldValue ? norm(binding.oldValue as any) : null
  if (prev && cur.key === prev.key && cur.version === prev.version) return
  loadInto(el, binding.value)
}

function unmount(el: ElEx, binding: DirectiveBinding<MinioVal>) {
  try { el.__m_obs?.disconnect() } catch {}
  el.__m_obs = null
  el.__m_req = 0
  const { key } = (binding.value ?? {}) as any
  if (key) clearObjectURL(key)
}

const minioImg: Directive<ElEx, MinioVal> = { mounted: mount, updated: update, unmounted: unmount }
export default minioImg





rtc.ts:
import { ref, type Ref } from 'vue'
import {
  LocalTrackPublication,
  RemoteParticipant,
  RemoteTrack,
  RemoteTrackPublication,
  Room as LkRoom,
  RoomEvent,
  Track,
  VideoPresets,
  ScreenSharePresets,
  VideoQuality,
  createLocalScreenTracks,
  type LocalTrack,
  setLogLevel,
  LogLevel,
} from 'livekit-client'

setLogLevel(LogLevel.error)

export type DeviceKind = 'audioinput' | 'videoinput'
export type VQ = 'sd' | 'hd'
const LS = { mic: 'audioDeviceId', cam: 'videoDeviceId', vq: 'videoQuality', perm: 'mediaPermProbed' }
const saveLS = (k: string, v: string) => { try { localStorage.setItem(k, v) } catch {} }
const loadLS = (k: string) => { try { return localStorage.getItem(k) } catch { return null } }

export type UseRTC = {
  lk: Ref<LkRoom | null>
  localId: Ref<string>
  peerIds: Ref<string[]>
  mics: Ref<MediaDeviceInfo[]>
  cams: Ref<MediaDeviceInfo[]>
  LS: typeof LS
  saveLS: (k: string, v: string) => void
  loadLS: (k: string) => string | null
  selectedMicId: Ref<string>
  selectedCamId: Ref<string>
  remoteQuality: Ref<VQ>
  videoRef: (id: string) => (el: HTMLVideoElement | null) => void
  screenVideoRef: (id: string) => (el: HTMLVideoElement | null) => void
  prepareScreenShare: (opts?: { audio?: boolean }) => Promise<boolean>
  publishPreparedScreen: () => Promise<boolean>
  cancelPreparedScreen: () => Promise<void>
  stopScreenShare: () => Promise<void>
  screenKey: (id: string) => string
  isScreenKey: (key: string) => boolean
  startScreenShare: (opts?: { audio?: boolean }) => Promise<boolean>
  initRoom: (opts?: {
    onMediaDevicesError?: (e: unknown) => void
    onScreenShareEnded?: () => void | Promise<void>
    publishDefaults?: ConstructorParameters<typeof LkRoom>[0]['publishDefaults']
    audioCaptureDefaults?: ConstructorParameters<typeof LkRoom>[0]['audioCaptureDefaults']
    videoCaptureDefaults?: ConstructorParameters<typeof LkRoom>[0]['videoCaptureDefaults']
  }) => LkRoom
  connect: (wsUrl: string, token: string, opts?: {
    autoSubscribe?: boolean
    maxRetries?: number
    peerConnectionTimeout?: number
    websocketTimeout?: number
  }) => Promise<void>
  disconnect: () => Promise<void>
  setAudioSubscriptionsForAll: (on: boolean) => void
  setVideoSubscriptionsForAll: (on: boolean) => void
  setRemoteQualityForAll: (q: VQ) => void
  refreshDevices: () => Promise<void>
  isBusyError: (e: unknown) => boolean
  fallback: (kind: DeviceKind) => Promise<void>
  onDeviceChange: (kind: DeviceKind) => Promise<void>
  enable: (kind: DeviceKind) => Promise<boolean>
  permProbed: Ref<boolean>
  probePermissions: (opts?: { audio?: boolean; video?: boolean | MediaTrackConstraints }) => Promise<boolean>
  clearProbeFlag: () => void
  hasAudioInput: Ref<boolean>
  hasVideoInput: Ref<boolean>
  disable: (kind: DeviceKind) => Promise<void>
  isSpeaking: (id: string) => boolean
  setUserVolume: (id: string, v: number) => void
  getUserVolume: (id: string) => number
  resumeAudio: () => Promise<void>
}

export function useRTC(): UseRTC {
  const lk = ref<LkRoom | null>(null)
  const localId = ref('')
  const peerIds = ref<string[]>([])
  const videoEls = new Map<string, HTMLVideoElement>()
  const audioEls = new Map<string, HTMLAudioElement>()
  const screenVideoEls = new Map<string, HTMLVideoElement>()
  const videoRefFns = new Map<string, (el: HTMLVideoElement|null) => void>()
  const screenRefFns = new Map<string, (el: HTMLVideoElement|null) => void>()
  const mics = ref<MediaDeviceInfo[]>([])
  const cams = ref<MediaDeviceInfo[]>([])
  const selectedMicId = ref<string>('')
  const selectedCamId = ref<string>('')
  const wantAudio = ref(true)
  const wantVideo = ref(true)
  const permProbed = ref<boolean>(loadLS(LS.perm) === '1')
  const hasAudioInput = ref(false)
  const hasVideoInput = ref(false)
  const activeSpeakers = ref<Set<string>>(new Set())
  const audibleIds = ref<Set<string>>(new Set())

  const screenKey = (id: string) => `${id}#s`
  const isScreenKey = (key: string) => key.endsWith('#s')
  const isSub = (pub: RemoteTrackPublication) => pub.isSubscribed
  const lowVideoQuality = VideoPresets.h180
  const highVideoQuality = VideoPresets.h540
  const highScreenQuality = ScreenSharePresets.h720fps30

  type SrcWrap = { node: MediaStreamAudioSourceNode; stream: MediaStream }
  const gainNodes = new Map<string, GainNode>()
  const msrcNodes = new Map<string, SrcWrap>()
  const volumePrefs = new Map<string, number>()
  const VOL_LS = (id: string) => `vol:${id}`
  const lsWriteTimers = new Map<string, number>()
  let audioCtx: AudioContext | null = null
  let waState: 0 | 1 | -1 = 0
  const getCtx = () => (audioCtx ??= new (window.AudioContext || (window as any).webkitAudioContext)())
  function webAudioAvailable(): boolean {
    if (waState === -1) return false
    try {
      getCtx()
      waState = 1
      return true
    } catch {
      waState = -1
      return false
    }
  }

  function getSavedVol(id: string): number {
    try {
      const v = localStorage.getItem(VOL_LS(id))
      if (!v) return 100
      const n = +v
      return Number.isFinite(n) ? Math.min(200, Math.max(0, n)) : 100
    } catch { return 100 }
  }

  function setSavedVol(id: string, v: number) {
    const vv = Math.min(200, Math.max(0, Math.round(v)))
    volumePrefs.set(id, vv)
    const prev = lsWriteTimers.get(id)
    if (prev) window.clearTimeout(prev)
    const t = window.setTimeout(() => {
      try { localStorage.setItem(VOL_LS(id), String(vv)) } catch {}
      lsWriteTimers.delete(id)
    }, 500)
    lsWriteTimers.set(id, t)
  }

  function ensureGainFor(id: string, el: HTMLAudioElement): GainNode {
    const ctx = getCtx()
    let g = gainNodes.get(id)
    if (!g) {
      g = ctx.createGain()
      gainNodes.set(id, g)
      g.connect(ctx.destination)
    }
    const stream = el.srcObject as MediaStream | null
    if (stream) {
      const wrap = msrcNodes.get(id)
      if (!wrap || wrap.stream !== stream) {
        try { wrap?.node.disconnect() } catch {}
        const src = new MediaStreamAudioSourceNode(ctx, { mediaStream: stream })
        src.connect(g)
        msrcNodes.set(id, { node: src, stream })
      }
    }
    el.muted = true
    el.volume = 0
    return g
  }

  function applyVolume(id: string, v?: number) {
    const a = audioEls.get(id)
    if (!a) return
    const want = v ?? volumePrefs.get(id) ?? getSavedVol(id)

    if (webAudioAvailable()) {
      try {
        const ctx = getCtx()
        const g = ensureGainFor(id, a)
        const gain = Math.max(0, want / 100)
        const now = ctx.currentTime || 0
        try { g.gain.cancelScheduledValues(now) } catch {}
        g.gain.setTargetAtTime(gain, now, 0.01)
        a.muted = true
        a.volume = 0
        return
      } catch {
        waState = -1
      }
    }
    destroyAudioGraph(id)
    a.muted = false
    a.volume = Math.min(1, Math.max(0, (want || 100) / 100))
  }

  function setUserVolume(id: string, v: number) {
    const vv = Math.min(200, Math.max(0, Math.round(v)))
    const cur = volumePrefs.get(id) ?? getSavedVol(id)
    if (cur === vv) return
    setSavedVol(id, vv)
    applyVolume(id, vv)
  }
  function getUserVolume(id: string): number {
    let v = volumePrefs.get(id)
    if (v == null) {
      v = getSavedVol(id)
      volumePrefs.set(id, v)
    }
    return v
  }
  let resumeBusy = false
  async function resumeAudio() {
    if (resumeBusy) return
    resumeBusy = true
    try {
      if (audioCtx && audioCtx.state !== 'running') { await audioCtx.resume() }
      const plays = []
      for (const a of audioEls.values()) plays.push(a.play().catch(() => {}))
      await Promise.allSettled(plays)
    } finally {
      queueMicrotask(() => { resumeBusy = false })
    }
  }

  const isSpeaking = (id: string) => {
    if (id === localId.value) return activeSpeakers.value.has(id)
    return activeSpeakers.value.has(id) && audibleIds.value.has(id)
  }

  function refreshAudibleIds() {
    const room = lk.value
    const s = new Set<string>()
    if (!room || !wantAudio.value) {
      audibleIds.value = s
      return
    }
    room.remoteParticipants.forEach(p => {
      const has = p.getTrackPublications().some(pub => pub.kind === Track.Kind.Audio && isSub(pub))
      if (has) s.add(String(p.identity))
    })
    audibleIds.value = s
  }

  const getByIdentity = (room: LkRoom, id: string) => room.getParticipantByIdentity?.(id) ?? room.remoteParticipants.get(id)

  function setPermFlag(v: boolean) {
    try {
      permProbed.value = v
      if (v) localStorage.setItem(LS.perm, '1')
      else localStorage.removeItem(LS.perm)
    } catch {}
  }

  async function probePermissions(opts?: { audio?: boolean; video?: boolean | MediaTrackConstraints }): Promise<boolean> {
    const audio = opts?.audio ?? true
    const video = opts?.video ?? true
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio, video })
      stream.getTracks().forEach(t => { try { t.stop() } catch {} })
      await refreshDevices()
      setPermFlag(true)
      return true
    } catch {
      setPermFlag(false)
      return false
    }
  }

  function clearProbeFlag() { setPermFlag(false) }

  async function disable(kind: DeviceKind) {
    try {
      if (kind === 'audioinput') await lk.value?.localParticipant.setMicrophoneEnabled(false)
      else await lk.value?.localParticipant.setCameraEnabled(false)
    } catch {}
  }

  async function startScreenShare(opts?: { audio?: boolean }): Promise<boolean> {
    const got = await prepareScreenShare(opts)
    if (!got) return false
    const ok = await publishPreparedScreen()
    if (!ok) {
      try { await cancelPreparedScreen() } catch {}
      return false
    }
    return true
  }
  function setScreenVideoRef(id: string, el: HTMLVideoElement | null) {
    const prev = screenVideoEls.get(id)
    if (!el) {
      if (prev) { try { prev.srcObject = null } catch {} }
      screenVideoEls.delete(id)
      return
    }
    el.autoplay = true
    el.playsInline = true
    el.muted = id === localId.value
    screenVideoEls.set(id, el)
    const room = lk.value
    if (!room) return
    const p = getByIdentity(room, id) ?? room.localParticipant
    p?.getTrackPublications()?.forEach(pub => {
      if (pub.kind === Track.Kind.Video && (pub as RemoteTrackPublication).source === Track.Source.ScreenShare && pub.track) {
        try { pub.track.attach(el) } catch {}
      }
    })
  }
  const screenVideoRef = (id: string) => {
    let fn = screenRefFns.get(id)
    if (!fn) {
      fn = (el) => setScreenVideoRef(id, el)
      screenRefFns.set(id, fn)
    }
    return fn
  }

  let preparedScreen: LocalTrack[] | null = null
  async function prepareScreenShare(opts?: { audio?: boolean }): Promise<boolean> {
    try {
      preparedScreen = await createLocalScreenTracks({
        audio: opts?.audio ?? true,
        resolution: highScreenQuality.resolution,
      })
      preparedScreen.forEach(t => {
        const onEnded = async () => {
          try { await lk.value?.localParticipant.unpublishTrack(t) } catch {}
        }
        t.mediaStreamTrack.addEventListener('ended', onEnded, { once: true })
      })
      return true
    } catch {
      try {
        preparedScreen = await createLocalScreenTracks({
          audio: false,
          resolution: highScreenQuality.resolution,
        })
        return true
      } catch { return false }
    }
  }
  async function publishPreparedScreen(): Promise<boolean> {
    if (!lk.value || !preparedScreen?.length) return false
    const video = preparedScreen.find(t => t.kind === Track.Kind.Video)
    const audio = preparedScreen.find(t => t.kind === Track.Kind.Audio)
    try {
      if (video) {
        await lk.value.localParticipant.publishTrack(video, {
          source: Track.Source.ScreenShare,
          simulcast: false,
          videoEncoding: highScreenQuality.encoding,
        })
      }
    } catch {
      try { preparedScreen.forEach(t => t.stop()) } catch {}
      preparedScreen = null
      return false
    }
    if (audio) {
      try {
        await lk.value.localParticipant.publishTrack(audio, {
          source: Track.Source.ScreenShareAudio,
        })
      } catch {
        try { audio.stop() } catch {}
      }
    }
    preparedScreen = null
    return true
  }
  async function cancelPreparedScreen() {
    try { preparedScreen?.forEach(t => t.stop()) } catch {}
    preparedScreen = null
  }

  async function stopScreenShare() {
    try { await lk.value?.localParticipant.setScreenShareEnabled(false) } catch {}
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
    pubs?.forEach(pub => {
      const rp = pub as RemoteTrackPublication
      if (pub.kind === Track.Kind.Video && rp.source === Track.Source.Camera && pub.track) {
        try { pub.track.attach(el) } catch {}
      }
    })
  }
  const videoRef = (id: string) => {
    let fn = videoRefFns.get(id)
    if (!fn) {
      fn = (el) => setVideoRef(id, el)
      videoRefFns.set(id, fn)
    }
    return fn
  }

  function destroyAudioGraph(id: string) {
    const w = msrcNodes.get(id)
    try { w?.node.disconnect() } catch {}
    msrcNodes.delete(id)
    try { gainNodes.get(id)?.disconnect() } catch {}
    gainNodes.delete(id)
  }

  function ensureAudioEl(id: string): HTMLAudioElement {
    let a = audioEls.get(id)
    if (!a) {
      a = new Audio()
      a.autoplay = true
      a.playsInline = true
      a.muted = true
      a.style.display = 'none'
      audioEls.set(id, a)
      document.body.appendChild(a)
      applyVolume(id)
    }
    return a
  }

  async function onDeviceChange(kind: DeviceKind) {
    const id = kind === 'audioinput' ? selectedMicId.value : selectedCamId.value
    if (!id) return
    saveLS(kind === 'audioinput' ? LS.mic : LS.cam, id)
    const room = lk.value
    if (!room) return
    const pubs = room.localParticipant.getTrackPublications()
    const enabled = pubs.some(pub => kind === 'audioinput'
      ? pub.kind === Track.Kind.Audio && (pub as any).source === Track.Source.Microphone && !!pub.track
      : pub.kind === Track.Kind.Video && (pub as any).source === Track.Source.Camera && !!pub.track
    )
    if (!enabled) return
    try { await room.switchActiveDevice(kind, id) } catch {}
  }

  const isBusyError = (e: unknown) => {
    const name = ((e as any)?.name || '') + ''
    const msg  = ((e as any)?.message || '') + ''
    return name === 'NotReadableError' || /Could not start .* source/i.test(msg)
  }

  async function fallback(kind: DeviceKind): Promise<void> {
    await refreshDevices()
    const list = kind === 'audioinput' ? mics.value : cams.value
    const setEnabled = (on: boolean) =>
      kind === 'audioinput'
        ? lk.value?.localParticipant.setMicrophoneEnabled(on)
        : lk.value?.localParticipant.setCameraEnabled(on)
    if (list.length === 0) {
      try { await setEnabled(false) } catch {}
      if (kind === 'audioinput') {
        selectedMicId.value = ''
        saveLS(LS.mic, '')
      } else {
        selectedCamId.value = ''
        saveLS(LS.cam, '')
      }
      return
    }
    const id = list[0].deviceId
    try { await lk.value?.switchActiveDevice(kind, id) } catch {}
    if (kind === 'audioinput') {
      selectedMicId.value = id
      saveLS(LS.mic, id)
    } else {
      selectedCamId.value = id
      saveLS(LS.cam, id)
    }
  }

  async function refreshDevices() {
    try {
      const list = await navigator.mediaDevices.enumerateDevices()
      mics.value = list.filter(d => d.kind === 'audioinput')
      cams.value = list.filter(d => d.kind === 'videoinput')
      if (mics.value.length === 0 && cams.value.length === 0) { permProbed.value = false }
      hasAudioInput.value = mics.value.length > 0
      hasVideoInput.value = cams.value.length > 0
      if (!mics.value.find(d => d.deviceId === selectedMicId.value)) {
        const fromLS = loadLS(LS.mic)
        selectedMicId.value = (fromLS && mics.value.find(d => d.deviceId === fromLS)) ? fromLS : (mics.value[0]?.deviceId || '')
      }
      if (!cams.value.find(d => d.deviceId === selectedCamId.value)) {
        const fromLS = loadLS(LS.cam)
        selectedCamId.value = (fromLS && cams.value.find(d => d.deviceId === fromLS)) ? fromLS : (cams.value[0]?.deviceId || '')
      }
    } catch {}
  }

  async function enable(kind: DeviceKind): Promise<boolean> {
    const room = lk.value
    if (!room) return false
    if ((kind === 'audioinput' ? mics.value.length : cams.value.length) === 0) {
      try {
        const perms = kind === 'audioinput' ? { audio: true, video: false } : { audio: false, video: true }
        await navigator.mediaDevices.getUserMedia(perms)
        await refreshDevices()
        if ((kind === 'audioinput' ? mics.value.length : cams.value.length) === 0) {
          permProbed.value = false
          return false
        }
        permProbed.value = true
      } catch {
        permProbed.value = false
        return false
      }
    }
    let id = kind === 'audioinput' ? selectedMicId.value : selectedCamId.value
    if (!id) {
      await fallback(kind)
      id = kind === 'audioinput' ? selectedMicId.value : selectedCamId.value
      if (!id) return false
    }
    try {
      if (kind === 'audioinput') {
        await room.localParticipant.setMicrophoneEnabled(true, { deviceId: { exact: id } } as any)
      } else {
        await room.localParticipant.setCameraEnabled(true, { deviceId: { exact: id }, resolution: highVideoQuality.resolution } as any)
      }
      return true
    } catch {
      await fallback(kind)
      const nextId = kind === 'audioinput' ? selectedMicId.value : selectedCamId.value
      if (!nextId) return false
      try {
        if (kind === 'audioinput') {
          await room.localParticipant.setMicrophoneEnabled(true, { deviceId: { exact: nextId } } as any)
        } else {
          await room.localParticipant.setCameraEnabled(true, { deviceId: { exact: nextId }, resolution: highVideoQuality.resolution } as any)
        }
        return true
      } catch { return false }
    }
  }

  function setSubscriptions(kind: Track.Kind, on: boolean) {
    const room = lk.value
    if (!room) return
    room.remoteParticipants.forEach(p => {
      p.getTrackPublications().forEach(pub => {
        if (pub.kind === kind) { try { pub.setSubscribed(on) } catch {} }
      })
    })
  }
  const setAudioSubscriptionsForAll = (on: boolean) => {
    wantAudio.value = on
    setSubscriptions(Track.Kind.Audio, on)
    if (!on) audibleIds.value = new Set()
    else {
      refreshAudibleIds()
      void resumeAudio()
    }
  }
  const setVideoSubscriptionsForAll = (on: boolean) => {
    wantVideo.value = on
    setSubscriptions(Track.Kind.Video, on)
  }
  function applyVideoQuality(pub: RemoteTrackPublication) {
    if (pub.kind !== Track.Kind.Video || !pub.isSubscribed) return
    try {
      pub.setVideoQuality(remoteQuality.value === 'hd' ? VideoQuality.HIGH : VideoQuality.LOW)
    } catch {}
  }
  const applySubsFor = (p: RemoteParticipant) => {
    p.getTrackPublications().forEach(pub => {
      if (pub.kind === Track.Kind.Audio) {
        try { pub.setSubscribed(wantAudio.value) } catch {}
        return
      }
      if (pub.kind === Track.Kind.Video) {
        try {
          pub.setSubscribed(wantVideo.value)
          if (wantVideo.value) applyVideoQuality(pub as RemoteTrackPublication)
        } catch {}
      }
    })
  }

  const remoteQuality = ref<VQ>((loadLS(LS.vq) as VQ) === 'sd' ? 'sd' : 'hd')

  function setRemoteQualityForAll(q: VQ) {
    const changed = remoteQuality.value !== q
    if (changed) {
      remoteQuality.value = q
      saveLS(LS.vq, q)
    }
    const room = lk.value
    if (!room) return
    room.remoteParticipants.forEach(p => {
      p.getTrackPublications().forEach(pub => {
        if (pub.kind === Track.Kind.Video && pub.isSubscribed) applyVideoQuality(pub as RemoteTrackPublication)
      })
    })
  }

  function cleanupMedia() {
    activeSpeakers.value = new Set()
    audibleIds.value = new Set()
    videoEls.forEach(el => { try { el.srcObject = null } catch {} })
    videoEls.clear()
    audioEls.forEach(a => {
      try { a.srcObject = null } catch {}
      try { a.remove() } catch {}
    })
    audioEls.clear()
    screenVideoEls.forEach(el => { try { el.srcObject = null } catch {} })
    screenVideoEls.clear()
    videoRefFns.clear()
    screenRefFns.clear()
    try {
      gainNodes.forEach(g => g.disconnect())
      gainNodes.clear()
    } catch {}
    try {
      msrcNodes.forEach(w => { try { w.node.disconnect() } catch {} })
      msrcNodes.clear()
    } catch {}
    try { audioCtx?.close() } catch {}
    audioCtx = null
    volumePrefs.clear()
    lsWriteTimers.forEach((t) => { try { window.clearTimeout(t) } catch {} })
    lsWriteTimers.clear()
    waState = 0
    peerIds.value = []
    localId.value = ''
    try { preparedScreen?.forEach(t => t.stop()) } catch {}
    preparedScreen = null
  }

  let optsRoom: Parameters<typeof initRoom>[0] | undefined
  function initRoom(opts?: {
    onMediaDevicesError?: (e: unknown) => void
    onScreenShareEnded?: () => void | Promise<void>
    publishDefaults?: ConstructorParameters<typeof LkRoom>[0]['publishDefaults']
    audioCaptureDefaults?: ConstructorParameters<typeof LkRoom>[0]['audioCaptureDefaults']
    videoCaptureDefaults?: ConstructorParameters<typeof LkRoom>[0]['videoCaptureDefaults']
  }): LkRoom {
    optsRoom = opts
    if (lk.value) return lk.value
    const room = new LkRoom({
      dynacast: true,
      publishDefaults: {
        videoCodec: 'vp8',
        red: true,
        dtx: true,
        simulcast: true,
        videoSimulcastLayers: [lowVideoQuality, highVideoQuality],
        screenShareEncoding: highScreenQuality.encoding,
        screenShareSimulcastLayers: undefined,
        ...(opts?.publishDefaults || {})
      },
      audioCaptureDefaults: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        ...(opts?.audioCaptureDefaults || {})
      },
      videoCaptureDefaults: {
        resolution: highVideoQuality.resolution,
        ...(opts?.videoCaptureDefaults || {})
      },
    })
    lk.value = room

    room.on(RoomEvent.Disconnected, cleanupMedia)

    room.on(RoomEvent.LocalTrackPublished, (pub: LocalTrackPublication) => {
      if (pub.kind === Track.Kind.Video && pub.source === Track.Source.ScreenShare) {
        const el = screenVideoEls.get(localId.value)
        if (el && pub.track) { try { pub.track.attach(el) } catch {} }
      }
      if (pub.kind === Track.Kind.Video && pub.source === Track.Source.Camera) {
        const el = videoEls.get(localId.value)
        if (el && pub.track) { try { pub.track.attach(el) } catch {} }
      }
    })

    room.on(RoomEvent.LocalTrackUnpublished, (pub: LocalTrackPublication) => {
      if (pub.kind === Track.Kind.Video && pub.source === Track.Source.ScreenShare) {
        const el = screenVideoEls.get(localId.value)
        if (el && pub.track) { try { pub.track.detach(el) } catch {} }
        try { opts?.onScreenShareEnded?.() } catch {}
      }
      if (pub.kind === Track.Kind.Video && pub.source === Track.Source.Camera) {
        const el = videoEls.get(localId.value)
        if (el && pub.track) { try { pub.track.detach(el) } catch {} }
      }
    })

    room.on(RoomEvent.TrackSubscribed, (t: RemoteTrack, pub, part) => {
      const id = String(part.identity)
      if (t.kind === Track.Kind.Video) {
        if ((pub as RemoteTrackPublication).source === Track.Source.ScreenShare) {
          const el = screenVideoEls.get(id)
          if (el) { try { t.attach(el) } catch {} }
          return
        }
        const el = videoEls.get(id)
        if (el) { try { t.attach(el) } catch {} }
        applyVideoQuality(pub as RemoteTrackPublication)
      } else if (t.kind === Track.Kind.Audio) {
        const isScreenA = (pub as RemoteTrackPublication).source === Track.Source.ScreenShareAudio
        const aid = isScreenA ? screenKey(id) : id
        const a = ensureAudioEl(aid)
        try { t.attach(a) } catch {}
        try { applyVolume(aid) } catch {}
        try { void resumeAudio() } catch {}
        try { void a.play() } catch {}
      }
    })

    room.on(RoomEvent.TrackUnsubscribed, (t: RemoteTrack, pub, part) => {
      const id = String(part.identity)
      if (t.kind === Track.Kind.Video) {
        const isScreenV = (pub as RemoteTrackPublication).source === Track.Source.ScreenShare
        const el = isScreenV ? screenVideoEls.get(id) : videoEls.get(id)
        if (el) { try { t.detach(el) } catch {} }
      } else if (t.kind === Track.Kind.Audio) {
        const isScreenA = (pub as RemoteTrackPublication).source === Track.Source.ScreenShareAudio
        const aid = isScreenA ? screenKey(id) : id
        const a = audioEls.get(aid)
        if (a) {
          try { t.detach(a) } catch {}
          a.muted = true
          a.volume = 0
        }
        destroyAudioGraph(aid)
        const tm = lsWriteTimers.get(aid)
        if (tm) {
          try { clearTimeout(tm) } catch {}
          lsWriteTimers.delete(aid)
        }
      }
    })

    room.on(RoomEvent.TrackPublished, (_pub, part) => applySubsFor(part as RemoteParticipant))

    room.on(RoomEvent.ParticipantConnected, (p: RemoteParticipant) => {
      const id = String(p.identity)
      if (!peerIds.value.includes(id)) { peerIds.value = [...peerIds.value, id] }
      applySubsFor(p)
      refreshAudibleIds()
      void resumeAudio()
    })

    room.on(RoomEvent.ParticipantDisconnected, (p) => {
      const id = String(p.identity)
      peerIds.value = peerIds.value.filter(x => x !== id)
      const a = audioEls.get(id)
      if (a) {
        try { a.srcObject = null } catch {}
        try { a.remove() } catch {}
        audioEls.delete(id)
      }
      const tm = lsWriteTimers.get(id)
      if (tm) { try {
        clearTimeout(tm) } catch {}
        lsWriteTimers.delete(id)
      }
      destroyAudioGraph(id)
      volumePrefs.delete(id)
      const sid = screenKey(id)
      const sa = audioEls.get(sid)
      if (sa) {
        try { sa.srcObject = null } catch {}
        try { sa.remove() } catch {}
        audioEls.delete(sid)
      }
      const tms = lsWriteTimers.get(sid)
      if (tms) {
        try { clearTimeout(tms) } catch {}
        lsWriteTimers.delete(sid) }
      destroyAudioGraph(sid)
      volumePrefs.delete(sid)
      const v = videoEls.get(id)
      if (v) {
        try { v.srcObject = null } catch {}
        videoEls.delete(id)
      }
      const s1 = new Set(audibleIds.value)
      s1.delete(id)
      audibleIds.value = s1
      const s2 = new Set(activeSpeakers.value)
      s2.delete(id)
      activeSpeakers.value = s2
      const sv = screenVideoEls.get(id)
      if (sv) {
        try { sv.srcObject = null } catch {}
        screenVideoEls.delete(id)
      }
      videoRefFns.delete(id)
      screenRefFns.delete(id)
    })

    room.on(RoomEvent.TrackSubscriptionStatusChanged, (pub, _status, _part) => {
      if (pub.kind === Track.Kind.Video && isSub(pub)) {
        applyVideoQuality(pub as RemoteTrackPublication)
      }
      if (pub.kind === Track.Kind.Audio && _part) {
        const id = String(_part.identity)
        const s = new Set(audibleIds.value)
        if (isSub(pub)) s.add(id)
        else s.delete(id)
        audibleIds.value = s
      }
    })

    room.on(RoomEvent.MediaDevicesError, (e: any) => { opts?.onMediaDevicesError?.(e) })

    room.on(RoomEvent.MediaDevicesChanged, refreshDevices)

    room.on(RoomEvent.ActiveSpeakersChanged, (parts) => {
      activeSpeakers.value = new Set(parts.map(p => String(p.identity)))
    })

    return room
  }

  async function connect(wsUrl: string, token: string, opts?: {
    autoSubscribe?: boolean
    maxRetries?: number
    peerConnectionTimeout?: number
    websocketTimeout?: number
  }) {
    const room = lk.value ?? initRoom()
    await room.connect(wsUrl, token, {
      autoSubscribe: opts?.autoSubscribe ?? false,
      maxRetries: opts?.maxRetries ?? 2,
      peerConnectionTimeout: opts?.peerConnectionTimeout ?? 20_000,
      websocketTimeout: opts?.websocketTimeout ?? 10_000,
    })

    localId.value = String(room.localParticipant.identity)
    const ids: string[] = [localId.value]
    room.remoteParticipants.forEach(p => ids.push(String(p.identity)))
    peerIds.value = [...new Set(ids)]

    room.remoteParticipants.forEach(p => applySubsFor(p))
    if (wantAudio.value) { void resumeAudio() }

    await refreshDevices()
    refreshAudibleIds()
  }

  async function disconnect() {
    try {
      const pubs = lk.value?.localParticipant.getTrackPublications() ?? []
      for (const p of pubs) { try { p.track?.stop() } catch {} }
    } catch {}
    try { await lk.value?.localParticipant.setMicrophoneEnabled(false) } catch {}
    try { await lk.value?.localParticipant.setCameraEnabled(false) } catch {}
    try { await lk.value?.disconnect() } catch {}
    try { lk.value?.removeAllListeners?.() } catch {}
    cleanupMedia()
    lk.value = null
  }

  return {
    lk,
    localId,
    peerIds,
    mics,
    cams,
    LS,
    remoteQuality,
    selectedMicId,
    selectedCamId,
    permProbed,
    hasAudioInput,
    hasVideoInput,

    videoRef,
    initRoom,
    connect,
    disconnect,
    setAudioSubscriptionsForAll,
    setVideoSubscriptionsForAll,
    saveLS,
    loadLS,
    refreshDevices,
    isBusyError,
    fallback,
    onDeviceChange,
    enable,
    probePermissions,
    clearProbeFlag,
    disable,
    setRemoteQualityForAll,
    isSpeaking,
    setUserVolume,
    getUserVolume,
    resumeAudio,
    screenVideoRef,
    prepareScreenShare,
    publishPreparedScreen,
    cancelPreparedScreen,
    stopScreenShare,
    screenKey,
    isScreenKey,
    startScreenShare,
  }
}





session.ts:
type ForeignActiveCb = (on: boolean) => void
type InconsistencyCb = () => void

const TAB_ID = Math.random().toString(36).slice(2)

let bc: BroadcastChannel | null = null
let hbTimer: number | null = null
let consistencyTimer: number | null = null
let storageListenerBound = false
let inited = false

let currentSid = ''
let foreignActive = false

const foreignActiveSubs = new Set<ForeignActiveCb>()
const inconsistencySubs = new Set<InconsistencyCb>()

const read = {
  sid(): string { try { return localStorage.getItem('auth:sid') || '' } catch { return '' } },
  owner(): string { try { return localStorage.getItem('auth:owner') || '' } catch { return '' } },
  hb(): { id: string; ts: number } | null {
    try {
      const v = localStorage.getItem('auth:owner_hb')
      return v ? JSON.parse(v) : null
    } catch { return null }
  },
}

function writeSidMarker(sid: string) { try { localStorage.setItem('auth:sid', sid || '') } catch {} }
function beat() { try { localStorage.setItem('auth:owner_hb', JSON.stringify({ id: TAB_ID, ts: Date.now() })) } catch {} }
function ownerAlive(): boolean {
  const owner = read.owner()
  const hb = read.hb()
  if (!owner || !hb) return false
  return hb.id === owner && (Date.now() - hb.ts) < 15_000
}
function becomeOwner() {
  try {
    localStorage.setItem('auth:owner', TAB_ID)
    beat()
    if (hbTimer) clearInterval(hbTimer)
    hbTimer = window.setInterval(beat, 4000)
    window.addEventListener('beforeunload', () => { releaseOwnership(currentSid) }, { once: true })
  } catch {}
}
function releaseOwnership(prevSid?: string) {
  try {
    const owner = read.owner()
    if (owner === TAB_ID) {
      localStorage.removeItem('auth:owner')
      localStorage.removeItem('auth:owner_hb')
      if (prevSid && read.sid() === prevSid) writeSidMarker('')
    }
  } catch {}
}
function broadcastSession(sid: string) {
  const payload = { sid }
  try { bc?.postMessage(payload) } catch {}
  try { localStorage.setItem('auth:msg', JSON.stringify({ ...payload, ts: Date.now(), rnd: Math.random() })) } catch {}
}
function setForeignActive(on: boolean) {
  if (foreignActive !== on) {
    foreignActive = on
    foreignActiveSubs.forEach(cb => { try { cb(on) } catch {} })
  }
}

async function checkConsistency(): Promise<void> {
  const globalSid = read.sid()
  const cur = currentSid || ''

  if (!cur && globalSid) {
    if (!ownerAlive()) {
      releaseOwnership(globalSid)
      try { writeSidMarker('') } catch {}
      setForeignActive(false)
    } else {
      setForeignActive(true)
    }
    return
  }
  if (cur && !globalSid) {
    setForeignActive(false)
    inconsistencySubs.forEach(cb => { try { cb() } catch {} })
    return
  }
  if (cur && globalSid && cur !== globalSid) {
    setForeignActive(false)
    inconsistencySubs.forEach(cb => { try { cb() } catch {} })
    return
  }
  setForeignActive(false)
}

let storageHandler: ((e: StorageEvent)=>void) | null = null
let focusHandler: (()=>void) | null = null
let visHandler: (()=>void) | null = null

function bindListenersOnce() {
  if (storageListenerBound) return
  storageListenerBound = true

  if ('BroadcastChannel' in window) {
    try {
      bc = new BroadcastChannel('auth')
      bc.onmessage = () => { void checkConsistency() }
    } catch {}
  }

  storageHandler = (e) => {
    if (e.key === 'auth:msg' && e.newValue) { void checkConsistency() }
  }
  focusHandler = () => { void checkConsistency() }
  visHandler = () => { if (!document.hidden) void checkConsistency() }

  window.addEventListener('storage', storageHandler)
  window.addEventListener('focus', focusHandler)
  document.addEventListener('visibilitychange', visHandler)

  consistencyTimer = window.setInterval(() => { void checkConsistency() }, 5000)
}

export function initSessionBus(): void {
  if (inited) return
  inited = true
  bindListenersOnce()
  void checkConsistency()
}

export function stopSessionBus(): void {
  try { bc?.close() } catch {}
  bc = null
  if (hbTimer) {
    clearInterval(hbTimer)
    hbTimer = null
  }
  if (consistencyTimer) {
    clearInterval(consistencyTimer)
    consistencyTimer = null
  }
  if (storageHandler) {
    window.removeEventListener('storage', storageHandler)
    storageHandler = null
  }
  if (focusHandler) {
    window.removeEventListener('focus', focusHandler)
    focusHandler = null
  }
  if (visHandler) {
    document.removeEventListener('visibilitychange', visHandler)
    visHandler = null
  }
  storageListenerBound = false
  inited = false
  foreignActiveSubs.clear()
  inconsistencySubs.clear()
}

export function setSid(sid: string): void {
  currentSid = sid || ''
  writeSidMarker(currentSid)
  if (!read.owner() || !ownerAlive()) becomeOwner()
  broadcastSession(currentSid)
}

export function clearSid(prevSid?: string): void {
  const prev = prevSid ?? currentSid
  currentSid = ''
  writeSidMarker('')
  releaseOwnership(prev)
  broadcastSession('')
}

export function isForeignActive(): boolean { return foreignActive }

export async function checkConsistencyNow(): Promise<boolean> {
  await checkConsistency()
  return foreignActive
}

export function onForeignActive(cb: ForeignActiveCb): () => void {
  foreignActiveSubs.add(cb)
  return () => { foreignActiveSubs.delete(cb) }
}
export function onInconsistency(cb: InconsistencyCb): () => void {
  inconsistencySubs.add(cb)
  return () => { inconsistencySubs.delete(cb) }
}





sio.ts:
import { io, Socket } from 'socket.io-client'
import {
  getAccessToken,
  refreshAccessToken,
  addTokenRefreshedListener,
  removeTokenRefreshedListener,
  addAuthExpiredListener,
  removeAuthExpiredListener,
} from '@/services/axios'

type IoOpts = Parameters<typeof io>[1]

function wireAuthedSocket(s: Socket) {
  let triedRefreshOnThisCycle = false

  const applyAuth = () => {
    const tok = getAccessToken()
    ;(s as any).auth = { token: tok }
    ;(s.io.opts as any).auth = { token: tok }
  }

  s.on('connect_error', async () => {
    if (triedRefreshOnThisCycle) return
    triedRefreshOnThisCycle = true
    const tok = await refreshAccessToken(false)
    if (tok) {
      applyAuth()
      try { s.io.reconnect() } catch {}
    } else {
      try { (s.io.opts as any).reconnection = false } catch {}
      try { s.close() } catch {}
    }
  })

  s.on('connect', () => { triedRefreshOnThisCycle = false })

  s.io.on('reconnect_attempt', applyAuth)

  const onRefreshed = (_: string) => applyAuth()
  const onExpired = () => {
    try { (s.io.opts as any).reconnection = false } catch {}
    try { s.close() } catch {}
  }
  addTokenRefreshedListener(onRefreshed)
  addAuthExpiredListener(onExpired)

  const off = () => {
    removeTokenRefreshedListener(onRefreshed)
    removeAuthExpiredListener(onExpired)
    try { s.io.off?.('reconnect_attempt', applyAuth as any) } catch {}
  }

  s.on('disconnect', off)

  s.on('close', off)

  return s
}

export function createAuthedSocket(namespace: string, opts?: IoOpts): Socket {
  const s = io(namespace, { ...opts, auth: { token: getAccessToken() } })
  return wireAuthedSocket(s)
}

export function createPublicSocket(namespace: string, opts?: IoOpts): Socket {
  return io(namespace, { ...opts, auth: undefined })
}

let authSocket: Socket | null = null

export function startAuthSocket(opts?: { onForceLogout?: () => void }): Socket {
  if (authSocket) return authSocket
  authSocket = createAuthedSocket('/auth', {
    path: '/ws/socket.io',
    transports: ['websocket'],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 500,
    reconnectionDelayMax: 5000,
  })
  if (opts?.onForceLogout) authSocket.on('force_logout', opts.onForceLogout)
  return authSocket
}

export function stopAuthSocket(): void {
  try { authSocket?.off?.() } catch {}
  try { authSocket?.close?.() } catch {}
  authSocket = null
}




store auth.ts:
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { startAuthSocket, stopAuthSocket } from '@/services/sio'
import {
  api,
  setAuthHeader,
  addAuthExpiredListener,
  refreshAccessTokenFull,
} from '@/services/axios'
import {
  initSessionBus,
  setSid,
  clearSid,
  isForeignActive,
  onForeignActive,
  onInconsistency,
  checkConsistencyNow,
  stopSessionBus,
} from '@/services/session'

export interface TgUser {
  id: number
  username?: string
  photo_url?: string
  auth_date?: number
  hash?: string
}

export const useAuthStore = defineStore('auth', () => {
  const sessionId = ref<string>('')
  const ready = ref(false)
  const foreign = ref(false)

  const isAuthed = computed(() => Boolean(sessionId.value))

  let busInited = false
  let unsubFA: (() => void) | null = null
  let unsubINC: (() => void) | null = null

  function bindBus() {
    if (busInited) return
    initSessionBus()
    unsubFA = onForeignActive((on) => { foreign.value = on })
    unsubINC = onInconsistency(async () => { await localSignOut() })
    busInited = true
  }
  function unbindBus() {
    unsubFA?.()
    unsubINC?.()
    unsubFA = unsubINC = null
  }

  async function applySession(data: { access_token?: string; sid?: string }, { connect = true } = {}) {
    sessionId.value = data.sid || ''
    setAuthHeader(data.access_token || '')
    bindBus()
    setSid(sessionId.value)
    if (connect) startAuthSocket({ onForceLogout: () => { void localSignOut() } })
    ready.value = true
  }

  async function clearSession() {
    const prev = sessionId.value
    sessionId.value = ''
    setAuthHeader('')
    stopAuthSocket()
    clearSid(prev)
    unbindBus()
    stopSessionBus()
    foreign.value = isForeignActive()
    ready.value = true
    try {
      const { useUserStore } = await import('@/store/modules/user')
      useUserStore().clear()
    } catch {}
  }

  async function localSignOut(): Promise<void> { await clearSession() }

  async function init(): Promise<void> {
    if (ready.value) return
    bindBus()
    addAuthExpiredListener(() => { void localSignOut() })

    await checkConsistencyNow()
    if (isForeignActive()) {
      foreign.value = true
      ready.value = true
      return
    }
    try {
      const data = await refreshAccessTokenFull(false)
      if (!data) {
        await clearSession()
        return
      }
      await applySession(data)
    } catch {
      await clearSession()
    }
  }

  async function signInWithTelegram(tg: TgUser): Promise<void> {
    const { data } = await api.post('/auth/telegram', tg)
    await applySession(data)
    const { useUserStore } = await import('@/store/modules/user')
    await useUserStore().fetchMe()
  }

  async function logout(): Promise<void> {
    try { await api.post('/auth/logout', undefined, { __skipAuth: true }) } catch {}
    finally { await clearSession() }
  }

  return {
    sessionId,
    ready,
    isAuthed,
    foreignActive: foreign,

    init,
    signInWithTelegram,
    logout,
    localSignOut,
  }
})




store user.ts:
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

export interface UserProfile {
  id: number
  username?: string
  avatar_name?: string | null
  role: string
}

export const useUserStore = defineStore('user', () => {
  const user = ref<UserProfile | null>(null)

  async function fetchMe(): Promise<void> {
    const { data } = await api.get<UserProfile>('/users/profile_info')
    user.value = data
  }

  function clear(): void {
    user.value = null
  }

  return {
    user,
    fetchMe,
    clear,
  }
})




app.vue:
<template>
  <Header v-if="!isRoom" />
  <router-view />
</template>

<script setup lang="ts">
import { onMounted, watchEffect, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store'
import { useUserStore } from '@/store'
import Header from '@/components/Header.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const user = useUserStore()

const isRoom = computed(() => route.name === 'room')

watchEffect(() => {
  if (route.meta?.requiresAuth && !auth.isAuthed) {
    router.replace({ name: 'home' }).catch(() => {})
  }
})

onMounted(async () => {
  await auth.init()
  if (auth.isAuthed) { try { await user.fetchMe() } catch {} }
})
</script>





main.ts:
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import minioImg from './services/minioImg'
import './styles/main.scss'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.directive('minio-img', minioImg)

app.mount('#app')
