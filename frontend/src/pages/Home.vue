<template>
  <section class="card">
    <div class="left">
      <header>
        <div class="rooms-text">
          <span>Список комнат</span>
        </div>
        <button v-if="auth.isAuthed" @click="openCreate = true">Создать комнату</button>
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
          <span class="text-center">Лимит</span>
        </div>

        <ul class="list-body">
          <li class="item" v-for="r in sortedRooms" :key="r.id" :class="{ active: r.id === selectedId || r.id === pendingRoomId }" tabindex="0" @click="selectRoom(r.id)" >
            <span>{{ r.id }}</span>
            <div class="cell" :title="r.title">
              <img :src="r.privacy === 'private' ? iconLockClose : iconLockOpen" alt="lock" />
              <span>{{ r.title }}</span>
            </div>
            <div class="cell">
              <img class="user-avatar" v-minio-img="{key: r.creator_avatar_name ? `avatars/${r.creator_avatar_name}` : '', placeholder: defaultAvatar, lazy: false}" alt="" />
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
                  <span>Владелец</span>
                  <div class="owner">
                    <img v-minio-img="{ key: selectedRoom && selectedRoom.creator_avatar_name ? `avatars/${selectedRoom.creator_avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
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
                  <span>Режим</span>
                  <span>{{ game.mode === 'normal' ? 'Обычный' : 'Рейтинг' }}</span>
                </div>
                <div class="ri-game-div">
                  <span>Формат</span>
                  <span>{{ game.format === 'hosted' ? 'С ведущим' : 'Без ведущего' }}</span>
                </div>
                <div class="ri-game-div">
                  <span>Лимит зрителей</span>
                  <span>{{ game.spectators_limit }}</span>
                </div>
      <!--          <span>{{ gameOptions }}</span>-->
              </div>
            </div>

            <div class="ri-members">
              <span class="header-text">Участники ({{ selectedRoom?.occupancy ?? 0 }}/{{ selectedRoom?.user_limit ?? 0 }}):</span>
              <div v-if="(info?.members?.length ?? 0) === 0" class="muted">Пока никого</div>
              <ul v-else class="ri-users">
                <li class="ri-user" v-for="m in (info?.members || [])" :key="m.id">
                  <img v-minio-img="{ key: m.avatar_name ? `avatars/${m.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
                  <span>{{ m.username || ('user' + m.id) }}</span>
                  <img v-if="m.screen" :src="iconScreenOn" alt="streaming" />
                </li>
              </ul>
            </div>
          </div>

          <div class="ri-actions">
            <button v-if="ctaState==='enter'" :disabled="entering" @click="onEnter">{{ enterLabel }}</button>
            <button v-else-if="ctaState==='full'" disabled>Комната заполнена</button>
            <button v-else-if="ctaState==='apply'" @click="onApply">Подать заявку</button>
            <button v-else-if="ctaState==='pending'" disabled>Заявка отправлена</button>
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
import { api } from '@/services/axios'
import { useAuthStore } from '@/store'
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
}
type RoomInfoMember = {
  id: number
  username?: string
  avatar_name?: string | null
  screen?: boolean
}
type RoomMembers = {
  members: RoomInfoMember[]
}
type Game = {
  mode: 'normal' | 'rating'
  format: 'hosted' | 'nohost'
  spectators_limit: number
  vote_at_zero: boolean
  vote_three: boolean
  speech30_at_3_fouls: boolean
  extra30_at_2_fouls: boolean
}
type Access = 'approved'|'pending'|'none'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const roomsMap = reactive(new Map<number, Room>())
const sio = ref<Socket | null>(null)
const listEl = ref<HTMLElement | null>(null)
const rightEl = ref<HTMLElement | null>(null)
const suppressedAutoselect = ref(true)

const selArmed = ref(false)
const entering = ref(false)

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

const isOpen = computed(() => selectedRoom.value?.privacy === 'open')
const isFull = computed(() => selectedRoom.value ? isFullRoom(selectedRoom.value) : false)
const enterLabel = computed(() => entering.value ? 'Вхожу...' : 'Войти в комнату')
type Cta = 'login'|'enter'|'full'|'apply'|'pending'
const ctaState = computed<Cta>(() => {
  if (!auth.isAuthed || !selectedRoom.value) return 'login'
  if (isOpen.value) return isFull.value ? 'full' : 'enter'
  if (access.value === 'approved') return isFull.value ? 'full' : 'enter'
  if (access.value === 'none') return 'apply'
  return 'pending'
})

const game = computed(() => info.value?.game)
const gameOptions = computed(() => {
  const g = game.value
  if (!g) return ''
  const parts: string[] = []
  if (g.vote_at_zero) parts.push('Голосование в нуле')
  if (g.vote_three) parts.push('Подъём троих')
  if (g.speech30_at_3_fouls) parts.push('30с при 3 фолах')
  if (g.extra30_at_2_fouls) parts.push('+30с за 2 фола')
  return parts.join(', ')
})

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
  const id = selectedRoom.value?.id
  if (!id) return
  try {
    await api.post(`/rooms/${id}/apply`)
    access.value='pending'
  }
  catch (e: any) { alert('Ошибка отправки заявки') }
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
        padding: 0 20px;
        height: 40px;
        border-radius: 5px;
        background-color: $lead;
        box-shadow: 3px 3px 5px rgba($black, 0.25);
        span {
          height: 20px;
          font-size: 18px;
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
        grid-template-columns: 10% 45% 30% 15%;
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
          grid-template-columns: 10% 45% 30% 15%;
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
            img {
              width: 20px;
              height: 20px;
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
  transition: transform 0.15s ease-out, opacity 0.25s ease-out;
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
          scrollbar-width: none;
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
