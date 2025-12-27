<template>
  <section class="card">
    <div class="left">
      <header>
        <div class="rooms-text">
          <span>Список комнат</span>
        </div>
        <button @click="openCreate = true" :disabled="!settings.roomsCanCreate || !auth.isAuthed">Создать комнату</button>
      </header>

      <Transition name="overlay">
        <RoomModal
          v-if="openCreate"
          @close="openCreate=false"
          @created="onCreated"
        />
      </Transition>

      <div v-if="sortedRooms.length === 0" class="muted">Пока пусто</div>

      <div v-else class="list" ref="listEl">
        <div class="list-header">
          <span>№</span>
          <span>Название</span>
          <span>Владелец</span>
          <span class="text-center">Участники</span>
        </div>

        <ul class="list-body">
          <li class="item" v-for="r in sortedRooms" :key="r.id" :class="{ active: r.id === selectedId || r.id === pendingRoomId }" tabindex="0" @click="selectRoom(r.id)" >
            <span>{{ r.id }}</span>
            <div class="cell" :title="r.title">
              <img :src="r.privacy === 'private' ? iconLockClose : iconLockOpen" alt="lock" />
              <span class="status-room" :class="{ runned: r.in_game }">{{ r.in_game ? 'game' : 'lobby' }}</span>
              <span>{{ r.title }}</span>
            </div>
            <div class="cell">
              <img class="user-avatar" v-minio-img="{key: r.creator_avatar_name ? `avatars/${r.creator_avatar_name}` : '', placeholder: defaultAvatar, lazy: false}" alt="avatar" />
              <span class="user-name">{{ r.creator_name }}</span>
            </div>
            <span class="text-center">{{ r.occupancy }}/{{ r.user_limit }}</span>
          </li>
        </ul>
      </div>
    </div>

    <aside class="right" aria-live="polite" ref="rightEl" @pointerdown.self="selArmed = true"
           @pointerup.self="selArmed && clearSelection()" @pointerleave.self="selArmed = false" @pointercancel.self="selArmed = false">
      <Transition name="room-panel" mode="out-in">
        <div v-if="selectedId" key="info" class="room-info">
          <header>
            <span>{{ selectedRoom?.title }}</span>
            <button @click="clearSelection" aria-label="Закрыть">
              <img :src="iconClose" alt="close" />
            </button>
          </header>

          <div class="ri-info">
            <div class="ri-meta-game">
              <div class="ri-meta">
                <span class="header-text">Параметры комнаты:</span>
                <div class="ri-meta-div">
                  <span>Статус</span>
                  <span class="status-room" :class="{ runned: selectedRoom.in_game }">{{ selectedRoom.in_game ? 'game' : 'lobby' }}</span>
                </div>
                <div class="ri-meta-div">
                  <span>Владелец</span>
                  <div class="owner">
                    <img v-minio-img="{ key: selectedRoom && selectedRoom.creator_avatar_name ? `avatars/${selectedRoom.creator_avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                    <span class="owner-name">{{ selectedRoom?.creator_name }}</span>
                  </div>
                </div>
                <div class="ri-meta-div">
                  <span>Приватность</span>
                  <span>{{ isOpen ? 'Открытая' : 'Закрытая' }}</span>
                </div>
              </div>

              <div class="ri-game" v-if="game">
                <span class="header-text">Параметры игры:</span>
                <div class="ri-game-div">
                  <span>Зрители</span>
                  <span>?/{{ game.spectators_limit }}</span>
                </div>
                <div class="ri-game-div">
                  <span>Режим</span>
                  <span>{{ game.mode === 'normal' ? 'Обычный' : 'Рейтинг' }}</span>
                </div>
                <div class="ri-game-div">
                  <span>Формат</span>
                  <span>{{ game.format === 'hosted' ? 'С ведущим' : 'Без ведущего' }}</span>
                </div>
                <div class="ri-game-div">
                  <span>Слом в нуле</span>
                  <span>{{ game.break_at_zero ? 'Вкл' : 'Откл' }}</span>
                </div>
                <div class="ri-game-div">
                  <span>Подъем в нуле</span>
                  <span>{{ game.lift_at_zero ? 'Вкл' : 'Откл' }}</span>
                </div>
                <div class="ri-game-div">
                  <span>Подъем 3х при 9х</span>
                  <span>{{ game.lift_3x ? 'Вкл' : 'Откл' }}</span>
                </div>
              </div>
            </div>

            <div class="ri-members">
              <span class="header-text">Участники ({{ selectedRoom?.occupancy ?? 0 }}/{{ selectedRoom?.user_limit ?? 0 }}):</span>
              <div v-if="(info?.members?.length ?? 0) === 0" class="muted">Пока никого</div>
              <ul v-else class="ri-users">
                <li class="ri-user" v-for="m in sortedMembers" :key="m.id" :class="{ dead: m.role === 'player' && m.alive === false }">
                  <span v-if="m.role === 'head'" class="user-numb">В. </span>
                  <span v-else-if="m.role === 'player' && m.slot != null" class="user-numb">{{ m.slot }}. </span>
                  <img v-minio-img="{ key: m.avatar_name ? `avatars/${m.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                  <span>{{ m.username || ('user' + m.id) }}</span>
                  <img v-if="m.screen" :src="iconScreenOn" alt="streaming" />
                </li>
              </ul>
            </div>
          </div>

          <div class="ri-actions">
            <button v-if="ctaState==='enter'" :disabled="entering" @click="onEnter">Войти в комнату</button>
            <button v-else-if="ctaState==='full'" disabled>Комната заполнена</button>
            <button v-else-if="ctaState==='apply'" :disabled="applying" @click="onApply">Подать заявку</button>
            <button v-else-if="ctaState==='pending'" disabled>Заявка отправлена</button>
            <button v-else-if="ctaState==='watch'" :disabled="entering" @click="onEnter">Смотреть</button>
            <button v-else-if="ctaState==='spectators_full'" disabled>Лимит зрителей</button>
            <button v-else-if="ctaState==='in_game'" disabled>Идёт игра</button>
            <button v-else disabled>Авторизуйтесь, чтобы войти</button>
          </div>
        </div>

        <div v-else key="placeholder" class="loading-overlay">Выберите комнату для отображения информации</div>
      </Transition>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed, reactive, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Socket } from 'socket.io-client'
import { createPublicSocket } from '@/services/sio'
import { alertDialog } from '@/services/confirm'
import { api } from '@/services/axios'
import { useAuthStore, useUserStore, useSettingsStore } from '@/store'
import RoomModal from '@/components/RoomModal.vue'

import defaultAvatar from "@/assets/svg/defaultAvatar.svg"
import iconScreenOn from '@/assets/svg/screenOn.svg'
import iconLockOpen from '@/assets/svg/lockOpen.svg'
import iconLockClose from '@/assets/svg/lockClose.svg'
import iconClose from '@/assets/svg/close.svg'

type Room = {
  id: number
  title: string
  user_limit: number
  privacy: 'open' | 'private'
  creator: number
  creator_name: string
  creator_avatar_name?: string | null
  created_at: string
  occupancy: number
  in_game?: boolean
  game_phase?: string
}
type RoomInfoMember = {
  id: number
  username?: string
  avatar_name?: string | null
  screen?: boolean
  role?: 'head' | 'player' | 'observer'
  slot?: number | null
  alive?: boolean | null
}
type RoomMembers = {
  members: RoomInfoMember[]
  spectators_count?: number
}
type Game = {
  mode: 'normal' | 'rating'
  format: 'hosted' | 'nohost'
  spectators_limit: number
  break_at_zero: boolean
  lift_at_zero: boolean
  lift_3x: boolean
}
type Access = 'approved'|'pending'|'none'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const userStore = useUserStore()
const settings = useSettingsStore()

const roomsMap = reactive(new Map<number, Room>())
const sio = ref<Socket | null>(null)
const listEl = ref<HTMLElement | null>(null)
const rightEl = ref<HTMLElement | null>(null)
const suppressedAutoselect = ref(true)

const selArmed = ref(false)
const entering = ref(false)
const applying = ref(false)

const infoTimers = new Map<number, number>()
const infoInFlight = new Set<number>()
const info = ref<(RoomMembers & { game?: Game }) | null>(null)

const selectedId = ref<number | null>(null)
const pendingRoomId = ref<number | null>(null)
let selectReqSeq = 0

const openCreate = ref(false)
const access = ref<Access>('none')

const selectedRoom = computed(() => selectedId.value ? (roomsMap.get(selectedId.value) || null) : null)
const sortedRooms = computed(() => Array.from(roomsMap.values()).sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)))

const sortedMembers = computed<RoomInfoMember[]>(() => {
  const members = info.value?.members || []
  const inGame = !!selectedRoom.value?.in_game
  if (!inGame) return [...members]

  return [...members].sort((a, b) => {
    const ra = a.role === 'head' ? 0 : a.role === 'player' ? 1 : 2
    const rb = b.role === 'head' ? 0 : b.role === 'player' ? 1 : 2
    if (ra !== rb) return ra - rb
    if (a.role === 'player' && b.role === 'player') {
      const sa = a.slot ?? 999
      const sb = b.slot ?? 999
      if (sa !== sb) return sa - sb
    }
    const na = a.username || ''
    const nb = b.username || ''
    return na.localeCompare(nb)
  })
})

const isOpen = computed(() => selectedRoom.value?.privacy === 'open')
const isFull = computed(() => selectedRoom.value ? isFullRoom(selectedRoom.value) : false)
const currentUserId = computed(() => userStore.user?.id ?? null)
const isGameParticipant = computed(() => {
  const room = selectedRoom.value
  const uid = currentUserId.value
  const members = info.value?.members ?? []
  if (!room || !room.in_game || !uid) return false
  return members.some(m => m.id === uid && (m.role === 'head' || m.role === 'player'))
})

type Cta = 'login' | 'enter' | 'full' | 'apply' | 'pending' | 'in_game' | 'watch' | 'spectators_full'
const ctaState = computed<Cta>(() => {
  const room = selectedRoom.value
  if (!auth.isAuthed || !room) return 'login'
  if (room.in_game) {
    if (room.privacy === 'private' && access.value !== 'approved') return 'in_game'
    if (isGameParticipant.value) return 'enter'
    const limit = info.value?.game?.spectators_limit ?? 0
    const count = info.value?.spectators_count ?? 0
    if (limit <= 0) return 'in_game'
    return count < limit ? 'watch' : 'spectators_full'
  }
  if (room.privacy === 'open' || access.value === 'approved') return isFull.value ? 'full' : 'enter'
  if (access.value === 'none') return 'apply'
  return 'pending'
})
const game = computed(() => info.value?.game)

function isFullRoom(r: Room) { return r.occupancy >= r.user_limit }

function upsert(r: Room) {
  const cur = roomsMap.get(r.id)
  roomsMap.set(r.id, cur ? { ...cur, ...r } : r)
}

function remove(id: number) {
  roomsMap.delete(id)
  if (selectedId.value === id) {
    selectedId.value = null
    info.value = null
    suppressedAutoselect.value = true
    const t = infoTimers.get(id)
    if (t) {
      try { clearTimeout(t) } catch {}
      infoTimers.delete(id)
    }
  }
}

async function onCreated(room: any) {
  openCreate.value = false
  await router.push(`/room/${room.id}`)
}

async function fetchAccess(id: number) {
  if (!auth.isAuthed) {
    access.value = 'none'
    return
  }
  try {
    const { data } = await api.get(`/rooms/${id}/access`)
    access.value = data.access
  } catch { access.value = 'none' }
}

async function onApply() {
  const roomId = selectedRoom.value?.id
  if (!roomId || applying.value) return
  applying.value = true
  try {
    await api.post(`/rooms/${roomId}/apply`)
    access.value = 'pending'
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (detail === 'room_not_found') {
      void alertDialog('Комната не найдена')
      clearSelection()
    } else if (detail === 'not_private') {
      access.value = 'approved'
      void alertDialog('Комната открыта, можно зайти без заявки')
    } else {
      void alertDialog('Ошибка при отправке заявки')
    }
  } finally { applying.value = false }
}

async function fetchRoomInfo(id: number, opts?: { silent?: boolean }): Promise<(RoomMembers & { game?: Game }) | null> {
  if (infoInFlight.has(id)) return null
  infoInFlight.add(id)
  try {
    const { data } = await api.get<RoomMembers & { game?: Game }>(`/rooms/${id}/info`, { __skipAuth: true },)
    if (!opts?.silent && selectedId.value === id) info.value = data
    return data
  } catch {
    if (!opts?.silent && selectedId.value === id) info.value = null
    return null
  } finally { infoInFlight.delete(id) }
}

async function selectRoom(id: number) {
  if (selectedId.value === id) return
  suppressedAutoselect.value = false
  access.value = 'none'
  const prevId = selectedId.value
  if (prevId != null) {
    const t = infoTimers.get(prevId)
    if (t) {
      try { clearTimeout(t) } catch {}
      infoTimers.delete(prevId)
    }
  }
  const reqId = ++selectReqSeq
  pendingRoomId.value = id
  const data = await fetchRoomInfo(id, { silent: true })
  if (reqId !== selectReqSeq) return
  pendingRoomId.value = null
  if (!data) return
  selectedId.value = id
  info.value = data
}

function clearSelection() {
  if (selectedId.value == null && pendingRoomId.value == null) return
  const prevId = selectedId.value ?? pendingRoomId.value
  selectedId.value = null
  pendingRoomId.value = null
  info.value = null
  suppressedAutoselect.value = true
  selectReqSeq++
  if (prevId != null) {
    const t = infoTimers.get(prevId)
    if (t) {
      try { clearTimeout(t) } catch {}
      infoTimers.delete(prevId)
    }
  }
}

function scheduleInfoRefresh(id: number, delay: number) {
  const prev = infoTimers.get(id)
  if (prev) {
    try { clearTimeout(prev) } catch {}
  }
  const t = window.setTimeout(() => {
    if (selectedId.value === id) void fetchRoomInfo(id)
    infoTimers.delete(id)
  }, delay)
  infoTimers.set(id, t)
}

function onGlobalPointerDown(e: PointerEvent) {
  const target = e.target as Node | null
  if ( (target && listEl.value && listEl.value.contains(target)) || (target && rightEl.value && rightEl.value.contains(target)) ) return
  clearSelection()
}

async function onEnter() {
  const id = selectedRoom?.value?.id
  if (!id || entering.value) return
  entering.value = true
  try { await router.push(`/room/${id}`) }
  finally { entering.value = false }
}

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
    transports: ['websocket','polling'],
    upgrade: true,
    autoConnect: true,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 200,
    reconnectionDelayMax: 2000,
  })

  sio.value.on('connect', syncRoomsSnapshot)

  sio.value.on('settings_update', () => {
    void settings.fetchPublic()
  })

  sio.value.on('rooms_upsert', (r: Room) => {
    upsert(r)
    if (!selectedId.value && !suppressedAutoselect.value) selectRoom(r.id)
  })

  sio.value.on('rooms_remove', (p: { id: number }) => remove(p.id))

  sio.value.on('rooms_occupancy', async (p: { id: number; occupancy: number }) => {
    const cur = roomsMap.get(p.id)
    if (cur) roomsMap.set(p.id, { ...cur, occupancy: p.occupancy })
    if (selectedId.value === p.id) scheduleInfoRefresh(p.id, 300)
  })

  sio.value.on('rooms_stream', (p: { id: number; owner: number | null }) => {
    if (selectedId.value === p.id) scheduleInfoRefresh(p.id, 300)
  })
}

function stopWS() {
  try { sio.value?.off?.() } catch {}
  try { sio.value?.close?.() } catch {}
  sio.value = null
}

function onAuthNotify(e: any) {
  const d = e?.detail
  if (!d) return
  if (d.kind === 'approve') {
    const rid = Number(d.room_id)
    if (selectedId.value && rid === selectedId.value) {
      access.value = 'approved'
      void fetchRoomInfo(rid)
    }
  }
}

watch([selectedId, () => auth.isAuthed], ([id, ok]) => {
  if (ok && id) void fetchAccess(id as number)
})

watch(() => route.query.focus, (v) => {
  const id = Number(v)
  if (Number.isFinite(id)) selectRoom(id)
})

onMounted(() => {
  startWS()
  document.addEventListener('pointerdown', onGlobalPointerDown, { capture: true })
  const f = Number(route.query.focus)
  if (Number.isFinite(f)) selectRoom(f)
  window.addEventListener('auth-notify', onAuthNotify)
})

onBeforeUnmount(() => {
  infoTimers.forEach((t) => { try { clearTimeout(t) } catch {} })
  infoTimers.clear()
  stopWS()
  try { document.removeEventListener('pointerdown', onGlobalPointerDown, { capture: true } as any) } catch {}
  try { window.removeEventListener('auth-notify', onAuthNotify) } catch {}
})
</script>

<style scoped lang="scss">
.card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 600px;
  align-items: flex-start;
  padding: 0 10px;
  gap: 10px;
  overflow: auto;
  scrollbar-width: none;
  .left {
    display: flex;
    flex-direction: column;
    border-radius: 5px;
    background-color: $dark;
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 40px;
      border-radius: 5px;
      background-color: $graphite;
      box-shadow: 0 3px 5px rgba($black, 0.25);
      .rooms-text {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 10px;
        height: 40px;
        border-radius: 5px;
        span {
          height: 22px;
          font-size: 20px;
          font-weight: bold;
        }
      }
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 20px;
        height: 40px;
        border: none;
        border-radius: 5px;
        background-color: $fg;
        color: $bg;
        font-size: 16px;
        font-family: Manrope-Medium;
        line-height: 1;
        cursor: pointer;
        transition: opacity 0.25s ease-in-out, background-color 0.25s ease-in-out;
        &:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        &:hover {
          background-color: $white;
        }
      }
    }
    .muted {
      padding: 20px 10px;
      color: $ashy;
    }
    .list {
      display: flex;
      flex-direction: column;
      padding: 10px;
      gap: 10px;
      .text-center {
        text-align: center;
      }
      .list-header {
        display: grid;
        grid-template-columns: 10% 50% 25% 15%;
        padding: 10px;
        border-radius: 5px;
        background-color: $lead;
        box-shadow: 3px 3px 5px rgba($black, 0.25);
        span {
          color: $fg;
          letter-spacing: 2px;
        }
      }
      .list-body {
        display: flex;
        flex-direction: column;
        margin: 0;
        padding: 0;
        gap: 10px;
        list-style: none;
        .item {
          display: grid;
          grid-template-columns: 10% 50% 25% 15%;
          align-items: center;
          padding: 10px;
          border: 1px solid transparent;
          border-radius: 5px;
          background-color: $graphite;
          box-shadow: 3px 3px 5px rgba($black, 0.25);
          cursor: pointer;
          transition: border-color 0.25s ease-in-out, background-color 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
          &.active {
            border-color: $grey;
            background-color: $lead;
            box-shadow: none;
          }
          &:hover {
            background-color: $lead;
          }
          img {
            width: 20px;
            height: 20px;
          }
          span {
            color: $ashy;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          .cell {
            display: flex;
            align-items: center;
            gap: 5px;
            .status-room {
              padding: 3px 0;
              width: 45px;
              border-radius: 5px;
              background-color: $fg;
              color: $bg;
              font-size: 12px;
              text-align: center;
              &.runned {
                background-color: $green;
              }
            }
            .user-avatar {
              border-radius: 50%;
              object-fit: cover;
            }
            .user-name {
              height: 18px;
            }
          }
        }
      }
    }
  }
  .right {
    display: flex;
    position: sticky;
    top: 0;
    width: 600px;
    min-width: 600px;
    max-width: 600px;
    min-height: 480px;
    height: 480px;
    max-height: 480px;
    flex-direction: column;
    border-radius: 5px;
    background-color: $dark;
    overflow: hidden;
    .loading-overlay {
      margin: auto;
      text-align: center;
      color: $ashy;
    }
    .room-info {
      display: flex;
      position: relative;
      flex-direction: column;
      width: 100%;
      height: 100%;
      header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 5px 10px;
        border-radius: 5px;
        background-color: $graphite;
        box-shadow: 0 3px 5px rgba($black, 0.25);
        span {
          max-width: 550px;
          height: 20px;
          font-size: 18px;
          font-weight: bold;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        button {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          width: 25px;
          height: 30px;
          border: none;
          background: none;
          cursor: pointer;
          img {
            width: 25px;
            height: 25px;
          }
        }
      }
      .ri-info {
        display: flex;
        padding: 10px;
        gap: 10px;
        .ri-meta-game {
          display: flex;
          flex-direction: column;
          gap: 10px;
          width: calc(60% - 15px);
          .ri-meta {
            display: flex;
            flex-direction: column;
            padding: 10px;
            gap: 5px;
            border-radius: 5px;
            background-color: $graphite;
            box-shadow: 3px 3px 5px rgba($black, 0.25);
            .ri-meta-div {
              display: flex;
              align-items: center;
              justify-content: space-between;
              span {
                height: 16px;
                font-size: 14px;
                color: $ashy;
              }
              .status-room {
                padding: 3px 0;
                width: 50px;
                border-radius: 5px;
                background-color: $fg;
                color: $bg;
                font-size: 14px;
                text-align: center;
                &.runned {
                  background-color: $green;
                }
              }
              .owner {
                display: inline-flex;
                align-items: center;
                gap: 5px;
                img {
                  width: 20px;
                  height: 20px;
                  border-radius: 50%;
                  object-fit: cover;
                }
                .owner-name {
                  max-width: 130px;
                  white-space: nowrap;
                  overflow: hidden;
                  text-overflow: ellipsis;
                }
              }
            }
          }
          .ri-game {
            display: flex;
            flex-direction: column;
            padding: 10px;
            gap: 5px;
            border-radius: 5px;
            background-color: $graphite;
            box-shadow: 3px 3px 5px rgba($black, 0.25);
            .ri-game-div {
              display: flex;
              align-items: center;
              justify-content: space-between;
              span {
                height: 16px;
                font-size: 14px;
                color: $ashy;
              }
            }
          }
        }
        .ri-members {
          display: flex;
          flex-direction: column;
          padding: 10px;
          gap: 5px;
          width: calc(40% - 15px);
          border-radius: 5px;
          background-color: $graphite;
          box-shadow: 3px 3px 5px rgba($black, 0.25);
          .muted {
            height: 16px;
            font-size: 14px;
            color: $ashy;
          }
          .ri-users {
            display: flex;
            flex-direction: column;
            margin: 0;
            padding: 0;
            gap: 5px;
            list-style: none;
            .ri-user {
              display: flex;
              align-items: center;
              gap: 5px;
              width: 100%;
              height: 20px;
              img {
                width: 20px;
                height: 20px;
                border-radius: 50%;
                object-fit: cover;
              }
              span {
                max-width: 167px;
                height: 16px;
                font-size: 14px;
                color: $ashy;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
              }
              .user-numb {
                font-variant-numeric: tabular-nums;
              }
              &.dead {
                opacity: 0.5;
              }
            }
          }
        }
        .header-text {
          margin-bottom: 10px;
        }
      }
      .ri-actions {
        display: flex;
        position: absolute;
        align-items: center;
        justify-content: center;
        bottom: 20px;
        width: 100%;
        button {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0 20px;
          height: 40px;
          border: none;
          border-radius: 5px;
          background-color: $fg;
          color: $bg;
          font-size: 16px;
          font-family: Manrope-Medium;
          line-height: 1;
          cursor: pointer;
          transition: opacity 0.25s ease-in-out;
          &:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
        }
      }
    }
  }
}

.room-panel-enter-active,
.room-panel-leave-active {
  transition: transform 0.15s ease-out, opacity 0.15s ease-out;
}
.room-panel-enter-from,
.room-panel-leave-to {
  opacity: 0;
}
.room-panel-enter-to,
.room-panel-leave-from {
  opacity: 1;
}
.room-info.room-panel-enter-from,
.room-info.room-panel-leave-to {
  transform: translateX(100%);
}
.room-info.room-panel-enter-to,
.room-info.room-panel-leave-from {
  transform: translateX(0);
}

@media (max-width: 1280px) {
  .card {
    grid-template-columns: minmax(0, 1fr) 300px;
    .right {
      width: 300px;
      min-width: 300px;
      max-width: 300px;
      min-height: 240px;
      height: 240px;
      max-height: 240px;
      .room-info {
        header span {
          max-width: 250px;
        }
        .ri-info {
          flex-direction: column;
          padding: 10px 10px 5px;
          max-height: 130px;
          overflow: auto;
          .ri-meta-game {
            width: 100%;
            .ri-meta .ri-meta-div .owner .owner-name {
              max-width: 100px;
            }
          }
          .ri-members {
            width: calc(100% - 20px);
            .ri-users .ri-user span {
              max-width: 210px;
            }
          }
        }
        .ri-actions {
          position: static;
          margin-top: 5px;
        }
      }
    }
  }
}

</style>
