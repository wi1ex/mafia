<template>
  <section class="card">
    <div class="left" :class="{ 'left--top-banner': topBannerActive }">
      <header>
        <span class="left-title">Список комнат</span>
        <UiButton
          class="create-room-button"
          text="Создать комнату"
          :icon="iconAddPlus"
          icon-position="right"
          :disabled="!canCreateRooms || !auth.isAuthed || userStore.roomRestricted || verificationRestricted"
          @click="onOpenCreate"
        />
      </header>

      <Transition name="overlay">
        <RoomModal
          v-if="openCreate"
          @close="openCreate=false"
          @created="onCreated"
        />
      </Transition>

      <div v-if="sortedRooms.length === 0" class="muted-rooms">
        <img :src="iconNoRooms" alt="norooms" />
        <span>Пока нет комнат...</span>
      </div>

      <div v-else class="list">
        <div class="list-header">
          <span>Статус</span>
          <span>Название</span>
          <span>Владелец</span>
          <span class="text-center">Лимит</span>
        </div>

        <div class="list-body-shell">
          <ul class="list-body" ref="roomsList">
            <li class="item" v-for="r in sortedRooms" :key="r.id" :class="{ active: r.id === selectedId || r.id === pendingRoomId }" tabindex="0" @click="selectRoom(r.id)" >
              <div class="cell">
                <div class="status-room" :class="roomStatusClass(r)">
                  <UiIcon class="dot-img" :icon="iconDot" />
                  <span class="item-text">{{ roomStatusLabel(r)}}</span>
                </div>
              </div>
              <div class="cell">
                <UiIcon
                  :class="['lock-icon', r.privacy === 'private' ? 'lock-icon--private' : 'lock-icon--open']"
                  :icon="r.privacy === 'private' ? iconLockClose : iconLockOpen"
                  :label="r.privacy === 'private' ? 'Закрытая комната' : 'Открытая комната'"
                />
                <span class="item-text ellipsis margin">{{ r.title }}</span>
              </div>
              <div class="cell">
                <img class="user-avatar" v-minio-img="{key: r.creator_avatar_name ? `avatars/${r.creator_avatar_name}` : '', placeholder: iconDefaultAvatar, lazy: false}" alt="avatar" />
                <span class="item-text ellipsis">{{ r.creator_name }}</span>
              </div>
              <span class="text-center">{{ r.occupancy }}/{{ r.user_limit }}</span>
            </li>
          </ul>
          <UiScrollbar :target="roomsList" theme="dark" :inset-bottom="24" />
        </div>
      </div>
    </div>

    <div class="right-column">
      <aside class="right" :aria-live="selectedId ? 'polite' : 'off'" @pointerdown.self="selArmed = true"
             @pointerup.self="selArmed && clearSelection()" @pointerleave.self="selArmed = false" @pointercancel.self="selArmed = false">
        <Transition name="room-panel" mode="out-in">
          <div v-if="selectedId" key="info" class="room-info">
            <header>
              <span>{{ selectedRoom?.title }}</span>
              <div class="room-actions">
                <button v-if="canAdminSpectateRoom" :disabled="entering" @click="onAdminSpectateRoom" aria-label="Войти зрителем">
                  <UiIcon class="room-icon" :icon="iconVisOn" />
                </button>
                <button v-if="canCloseRooms" :disabled="adminKickBusy || selectedRoom?.in_game || selectedRoom?.entry_closed || selectedRoom?.occupancy === 0" @click="onAdminKickRoom" aria-label="Удалить комнату">
                  <UiIcon class="room-icon" :icon="iconDelete" />
                </button>
                <button @click="clearSelection" aria-label="Закрыть">
                  <UiIcon class="room-icon" :icon="iconClose" />
                </button>
              </div>
            </header>

            <div class="ri-info">
              <div class="ri-members" :class="{ solo: !canShowGameMeta }">
                <div class="ri-members-div">
                  <span class="ri-members-title">Участники:</span>
                  <span class="ri-members-count">{{ selectedRoom?.occupancy ?? 0 }}/{{ selectedRoom?.user_limit ?? 0 }}</span>
                </div>
                <div v-if="(info?.members?.length ?? 0) === 0" class="muted-members">
                  <img :src="iconNoMembers" alt="nomembers" />
                  <span>Пока никого нет...</span>
                </div>
                <ul v-else class="ri-users">
                  <li class="ri-user" v-for="m in sortedMembers" :key="m.id" :class="{ dead: m.role === 'player' && m.alive === false }">
                    <span v-if="m.role === 'head'" class="user-numb">Вед.</span>
                    <span v-else-if="m.role === 'player' && m.slot != null" class="user-numb">{{ formatSeatNumber(m.slot) }}.</span>
                    <button class="mini-profile-user-trigger" type="button" :disabled="!canOpenRoomInfoMiniProfileForUser(m)" @click="openMiniProfileFromRoomInfo(m)">
                      <img v-minio-img="{ key: m.avatar_name ? `avatars/${m.avatar_name}` : '', placeholder: iconDefaultAvatar, lazy: false }" alt="avatar" class="user-mini-avatar" />
                      <span class="mini-profile-name">{{ m.username || ('user' + m.id) }}</span>
                    </button>
                    <UiIcon v-if="m.screen" class="screen-icon" :icon="iconScreenOn" label="Стриминг" />
                  </li>
                </ul>
              </div>

              <div class="ri-meta-game" v-if="canShowGameMeta">
                <span class="ri-meta-title">Параметры игры:</span>
                <div class="ri-game-div">
                  <span class="ri-meta-text">Зрители</span>
                  <span ref="spectatorsWrapEl" class="spectators-wrap">
                    <button v-if="spectatorsTooltipEnabled" class="spectators-btn" :class="{ 'is-open': spectatorsTooltipVisible }" type="button" @click.stop="onSpectatorsToggle" aria-label="Показать зрителей">
                      <UiIcon class="spectators-icon" :icon="iconVisOn" />
                    </button>
                    <span class="ri-meta-value">{{ spectatorsLabel }}</span>
                    <div v-if="spectatorsTooltipVisible" class="spectators-tooltip">
                      <div v-if="spectatorsError">{{ spectatorsError }}</div>
                      <div v-else-if="spectators.length === 0">Нет зрителей</div>
                      <div v-else class="spectators-list">
                        <div v-for="s in spectators" :key="`spectator-${s.id}`" class="spectators-row">
                          <button class="mini-profile-user-trigger" type="button" :disabled="!canOpenRoomInfoMiniProfileForUser(s)" @click="openMiniProfileFromRoomInfo(s)">
                            <img v-minio-img="{ key: s.avatar_name ? `avatars/${s.avatar_name}` : '', placeholder: iconDefaultAvatarBlack, lazy: false }" alt="avatar" />
                            <span class="mini-profile-name">{{ s.username || ('user' + s.id) }}</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </span>
                </div>
                <div class="ri-game-div">
                  <span class="ri-meta-text">Режим</span>
                  <span class="ri-meta-value">{{ game.mode === 'normal' ? 'Обычный' : 'Рейтинг' }}</span>
                </div>
                <div class="ri-game-div">
                  <span class="ri-meta-text">Судья</span>
                  <span class="ri-meta-value">{{ game.format === 'hosted' ? 'Ведущий' : 'Без ведущего' }}</span>
                </div>
                <div class="ri-game-div">
                  <span class="ri-meta-text">Выставления</span>
                  <span class="ri-meta-value">{{ game.nominate_mode === 'head' ? 'От ведущего' : 'От игроков' }}</span>
                </div>
                <div class="ri-game-div">
                  <span class="ri-meta-text">Завещания</span>
                  <span class="ri-meta-value">{{ game.farewell_wills ? 'Вкл' : 'Откл' }}</span>
                </div>
                <div class="ri-game-div">
                  <span class="ri-meta-text">Подмигивать/Стучать</span>
                  <span class="ri-meta-value">{{ game.wink_knock ? 'Вкл' : 'Откл' }}</span>
                </div>
                <div class="ri-game-div">
                  <span class="ri-meta-text">Слом в нуле</span>
                  <span class="ri-meta-value">{{ game.break_at_zero ? 'Вкл' : 'Откл' }}</span>
                </div>
                <div class="ri-game-div">
                  <span class="ri-meta-text">Подъем в нуле</span>
                  <span class="ri-meta-value">{{ game.lift_at_zero ? 'Вкл' : 'Откл' }}</span>
                </div>
                <div class="ri-game-div">
                  <span class="ri-meta-text">Подъем 3х при 9х</span>
                  <span class="ri-meta-value">{{ game.lift_3x ? 'Вкл' : 'Откл' }}</span>
                </div>
                <div class="ri-game-div">
                  <span class="ri-meta-text">Музыка</span>
                  <span class="ri-meta-value">{{ game.music ? 'Вкл' : 'Откл' }}</span>
                </div>
              </div>
            </div>

            <div class="ri-actions">
              <UiButton v-if="ctaState==='enter'" class="ri-action" size="middle" text="Войти в комнату" :disabled="entering" @click="onEnter" />
              <UiButton v-else-if="ctaState==='full'" class="ri-action" size="middle" text="Комната заполнена" disabled />
              <UiButton v-else-if="ctaState==='apply'" class="ri-action" size="middle" text="Подать заявку" :disabled="applying" @click="onApply" />
              <UiButton v-else-if="ctaState==='pending'" class="ri-action" size="middle" text="Заявка отправлена" disabled />
              <UiButton v-else-if="ctaState==='watch'" class="ri-action" size="middle" text="Смотреть" :disabled="entering" @click="onEnter" />
              <UiButton v-else-if="ctaState==='spectators_full'" class="ri-action" size="middle" text="Лимит зрителей" disabled />
              <UiButton v-else-if="ctaState==='loading'" class="ri-action" size="middle" text="Загрузка..." disabled />
              <UiButton v-else-if="ctaState==='in_game'" class="ri-action" size="middle" text="Игра без зрителей" disabled />
              <UiButton v-else-if="ctaState==='blocked'" class="ri-action" size="middle" :text="blockedLabel" disabled />
              <UiButton v-else-if="ctaState==='login'" class="ri-action" size="middle" text="Авторизуйтесь, чтобы войти" disabled />
            </div>
          </div>

          <div v-else-if="pendingRoomId" key="pending" class="loading-overlay">Загрузка информации о комнате…</div>
          <Carousel v-else key="placeholder" />
        </Transition>
      </aside>
      <div class="right-extra right-extra--primary">
        <img class="background-image-6" :src="imageSlide6" alt="" aria-hidden="true" />
        <div class="right-extra-content">
          <div class="right-extra-copy-subscription">
            <span>Оформи подписку и получи</span>
            <span class="right-extra-copy-accent">бонусы!</span>
          </div>
          <button type="button" class="right-extra-btn" @click="openSubscriptionModal">
            <UiIcon class="btn-icon" :icon="iconArrowNext" />
          </button>
        </div>
      </div>

      <div class="right-extra right-extra--secondary">
        <img class="background-image-7" :src="imageSlide7" alt="" aria-hidden="true" />
        <div class="right-extra-content">
          <div class="right-extra-copy-connect">
            <span>Связаться с администрацией платформы</span>
          </div>
          <button type="button" class="right-extra-btn" @click="openContactModal">
            <UiIcon class="btn-icon" :icon="iconArrowNext" />
          </button>
        </div>
      </div>
    </div>
  </section>
  <MiniProfile
    v-model:open="miniProfileOpen"
    :user-id="miniProfileUserId"
    :initial-profile="miniProfileInitial"
    :show-stats-button="true"
  />
  <Subscription v-model:open="subscriptionModalOpen" @select="onSubscriptionPaymentSelect" />
  <Contact v-model:open="contactModalOpen" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Socket } from 'socket.io-client'
import { createPublicSocket } from '@/services/sio'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { api } from '@/services/axios'
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId } from '@/services/miniProfile'
import { roomGameDefault, type RoomGameParams } from '@/services/gameParams'
import { useAuthStore, useSettingsStore, useUserStore } from '@/store'
import Carousel from '@/components/Carousel.vue'
import RoomModal from '@/components/RoomModal.vue'
import MiniProfile from '@/components/MiniProfile.vue'
import Subscription from '@/components/Subscription.vue'
import Contact from '@/components/Contact.vue'
import UiIcon from '@/components/UiIcon.vue'
import UiButton from '@/components/UiButton.vue'
import UiScrollbar from '@/components/UiScrollbar.vue'

import iconDefaultAvatarBlack from '@/assets/svg/iconDefaultAvatarBlack.svg'
import iconDefaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconScreenOn from '@/assets/svg/iconScreenOn.svg'
import iconLockOpen from '@/assets/svg/iconLockOpen.svg'
import iconLockClose from '@/assets/svg/iconLockClose.svg'
import iconClose from '@/assets/svg/iconClose.svg'
import iconDelete from '@/assets/svg/iconDelete.svg'
import iconVisOn from '@/assets/svg/iconVisOn.svg'
import iconArrowNext from '@/assets/svg/iconArrowNext.svg'
import iconAddPlus from '@/assets/svg/iconAddPlus.svg'
import iconNoRooms from '@/assets/svg/iconNoRooms.svg'
import iconNoMembers from '@/assets/svg/iconNoMembers.svg'
import iconDot from '@/assets/svg/iconDot.svg'
import imageSlide6 from '@/assets/images/carousel-image6.png'
import imageSlide7 from '@/assets/images/carousel-image7.png'

type Room = {
  id: number
  title: string
  user_limit: number
  privacy: 'open' | 'private'
  anonymity?: 'visible' | 'hidden'
  creator: number
  creator_name: string
  creator_avatar_name?: string | null
  created_at: string
  occupancy: number
  in_game?: boolean
  game_phase?: string
  entry_closed?: boolean
}
type RoomInfoMember = {
  id: number
  username?: string
  avatar_name?: string | null
  profile_role?: string | null
  screen?: boolean
  role?: 'head' | 'player' | 'observer'
  slot?: number | null
  alive?: boolean | null
}
type RoomMembers = {
  members: RoomInfoMember[]
  spectators_count?: number
}
type RoomSpectator = {
  id: number
  username?: string
  avatar_name?: string | null
  profile_role?: string | null
}
type HomeMiniProfileInitial = {
  id?: number | null
  username?: string | null
  avatar_name?: string | null
  role?: string | null
}
type Game = RoomGameParams
type Access = 'approved'|'pending'|'none'|'blacklisted'|'hidden'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const userStore = useUserStore()
const settings = useSettingsStore()
const isAdmin = computed(() => userStore.user?.role === 'admin')
const isModer = computed(() => userStore.user?.role === 'moder')
const canCloseRooms = computed(() => isAdmin.value || isModer.value)
const canBypassSpectatorsLimit = computed(() => isAdmin.value || isModer.value)
const canCreateRooms = computed(() => settings.roomsCanCreate || isAdmin.value)
const canEnterRooms = computed(() => settings.roomsCanEnter || isAdmin.value)
const canAdminSpectateRoom = computed(() => {
  const room = selectedRoom.value
  return isAdmin.value && !!room && !room.in_game && !room.entry_closed
})

const roomsMap = reactive(new Map<number, Room>())
const roomsList = ref<HTMLElement | null>(null)
const sio = ref<Socket | null>(null)
const suppressedAutoselect = ref(true)

const selArmed = ref(false)
const entering = ref(false)
const applying = ref(false)
const adminKickBusy = ref(false)

const infoTimers = new Map<number, number>()
const infoInFlight = new Set<number>()
const info = ref<(RoomMembers & { game?: Game }) | null>(null)
const spectators = ref<RoomSpectator[]>([])
const spectatorsLoading = ref(false)
const spectatorsError = ref('')
const spectatorsOpen = ref(false)
const spectatorsWrapEl = ref<HTMLElement | null>(null)
let spectatorsReqSeq = 0
const miniProfileOpen = ref(false)
const miniProfileUserId = ref<number | null>(null)
const miniProfileInitial = ref<HomeMiniProfileInitial | null>(null)
const subscriptionModalOpen = ref(false)
const contactModalOpen = ref(false)

const selectedId = ref<number | null>(null)
const pendingRoomId = ref<number | null>(null)
let selectReqSeq = 0

const openCreate = ref(false)
const access = ref<Access>('none')

const selectedRoom = computed(() => selectedId.value ? (roomsMap.get(selectedId.value) || null) : null)
const sortedRooms = computed(() => Array.from(roomsMap.values()).sort((a, b) => {
  const rank = (room: Room): number => {
    switch (roomStatusLabel(room)) {
      case 'GAME': return 0
      case 'DUO': return 1
      case 'HIDE': return 2
      case 'LOBBY': return 3
      default: return 4
    }
  }

  const aRank = rank(a)
  const bRank = rank(b)
  if (aRank !== bRank) return aRank - bRank
  return Date.parse(a.created_at) - Date.parse(b.created_at)
}))

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

const isFull = computed(() => selectedRoom.value ? isFullRoom(selectedRoom.value) : false)
const currentUserId = computed(() => normalizeMiniProfileUserId(userStore.user?.id))
const verificationRestricted = computed(() => auth.isAuthed && settings.verificationRestrictions && !userStore.telegramVerified)
const canOpenRoomInfoMiniProfile = computed(() => {
  if (!auth.ready || !settings.ready || !auth.isAuthed) return false
  if (!userStore.user) return false
  if (userStore.banActive) return false
  return !(settings.verificationRestrictions && !userStore.telegramVerified)
})
const topBannerActive = computed(() => {
  const verificationBanner = auth.ready
    && settings.ready
    && settings.verificationRestrictions
    && auth.isAuthed
    && Boolean(userStore.user)
    && !userStore.telegramVerified
  const text = String(settings.adminBannerText || '').trim()
  const adminBanner = settings.ready && Boolean(text && text !== '0')
  const sanctionBanner = auth.isAuthed && (userStore.banActive || userStore.timeoutActive || userStore.suspendActive)
  return verificationBanner || adminBanner || sanctionBanner
})
const blockedLabel = computed(() => {
  if (access.value === 'blacklisted') return 'Вход запрещен: Вы находитесь в ЧС'
  if (access.value === 'hidden') return 'Вход только по приглашению'
  if (selectedRoom.value?.entry_closed) return 'Вход в комнату закрыт'
  if (!canEnterRooms.value) return 'Вход в комнаты отключен'
  if (userStore.banActive) return 'Вход запрещен: аккаунт забанен'
  if (userStore.timeoutActive) return 'Вход запрещен: активный таймаут'
  if (verificationRestricted.value) return 'Вход запрещен: нет верификации'
  return 'Вход запрещен'
})
const isGameParticipant = computed(() => {
  const room = selectedRoom.value
  const uid = currentUserId.value
  const members = info.value?.members ?? []
  if (!room || !room.in_game || !uid) return false
  return members.some(m => m.id === uid && (m.role === 'head' || m.role === 'player'))
})

type Cta = 'none' | 'login' | 'enter' | 'full' | 'apply' | 'pending' | 'in_game' | 'watch' | 'spectators_full' | 'blocked' | 'loading'
const ctaState = computed<Cta>(() => {
  const room = selectedRoom.value
  if (!room) return 'none'
  if (room?.entry_closed) return 'blocked'
  if (room && !canEnterRooms.value) return 'blocked'
  if (room && (userStore.roomRestricted || verificationRestricted.value)) return 'blocked'
  if (!auth.isAuthed) return 'login'
  if (access.value === 'blacklisted') return 'blocked'
  if (access.value === 'hidden') return 'blocked'
  if (room.in_game) {
    if (isGameParticipant.value) return 'enter'
    if (canBypassSpectatorsLimit.value) return 'watch'
    if (!info.value?.game) return 'loading'
    const limit = info.value.game.spectators_limit
    const count = info.value?.spectators_count ?? 0
    if (limit <= 0) return 'in_game'
    return count < limit ? 'watch' : 'spectators_full'
  }
  if (room.privacy === 'open' || access.value === 'approved') return isFull.value ? 'full' : 'enter'
  if (access.value === 'none') return 'apply'
  if (access.value === 'pending') return 'pending'
  return 'none'
})
const hasGame = computed(() => Boolean(info.value?.game))
const game = computed<Game>(() => info.value?.game ?? roomGameDefault)
const gameLimitMin = computed(() => {
  const minReady = Number(settings.gameMinReadyPlayers)
  return Number.isFinite(minReady) && minReady > 0 ? minReady + 1 : 11
})
const canShowGameMeta = computed(() => {
  const room = selectedRoom.value
  if (!room) return false
  if (room.in_game) return hasGame.value
  const limit = Number(room.user_limit)
  return Number.isFinite(limit) && limit === gameLimitMin.value && hasGame.value
})
const spectatorsLabel = computed(() => {
  const limit = game.value.spectators_limit
  if (limit <= 0) return 'Без зрителей'
  if (selectedRoom.value?.in_game) {
    const count = info.value?.spectators_count ?? 0
    return `${count}/${limit}`
  }
  return `до ${limit}`
})
const spectatorsTooltipEnabled = computed(() => {
  const limit = game.value.spectators_limit
  if (settings.verificationRestrictions && !userStore.telegramVerified) return false
  return auth.isAuthed && !!selectedRoom.value?.in_game && limit > 0
})
const spectatorsTooltipVisible = computed(() => spectatorsOpen.value && spectatorsTooltipEnabled.value)

function roomStatusLabel(room: Room): string {
  if (room.anonymity === 'hidden') return 'HIDE'
  if (room.in_game) return 'GAME'
  const limit = Number(room.user_limit)
  if (limit === 2) return 'DUO'
  return 'LOBBY'
}

function roomStatusClass(room: Room): Record<string, boolean> {
  const label = roomStatusLabel(room)
  return {
    hide: label === 'HIDE',
    runned: label === 'GAME',
    duo: label === 'DUO',
  }
}

function isFullRoom(r: Room) { return r.occupancy >= r.user_limit }

function formatSeatNumber(slot: number | null | undefined): string {
  if (slot == null) return ''
  const n = Number(slot)
  if (!Number.isFinite(n)) return String(slot)
  return String(Math.trunc(n)).padStart(2, '0')
}

function canOpenRoomInfoMiniProfileForUser(user: { id?: number | null; profile_role?: string | null }): boolean {
  if (!canOpenRoomInfoMiniProfile.value) return false
  return canOpenMiniProfileTarget({
    targetId: user.id,
    viewerId: currentUserId.value,
    viewerRole: userStore.user?.role,
    targetRole: user.profile_role,
  })
}

function openMiniProfileFromRoomInfo(user: { id: number; username?: string | null; avatar_name?: string | null; profile_role?: string | null }): void {
  const uid = Number(user.id || 0)
  if (!canOpenRoomInfoMiniProfileForUser(user)) return
  miniProfileUserId.value = uid
  miniProfileInitial.value = {
    id: uid,
    username: user.username || null,
    avatar_name: user.avatar_name || null,
    role: user.profile_role || null,
  }
  spectatorsOpen.value = false
  miniProfileOpen.value = true
}

function openSubscriptionModal() {
  subscriptionModalOpen.value = true
}

function openContactModal() {
  contactModalOpen.value = true
}

function onSubscriptionPaymentSelect(site: { id: string; name: string; url: string }) {
  if (!auth.isAuthed) return
  if (site.id === 'lava') return
  void api.post('/users/support_link_click', {
    source: 'home_right_extra_primary',
    site_id: site.id,
    site_name: site.name,
    url: site.url,
  }).catch(() => {})
}

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

async function loadSpectators(roomId: number, reqId: number) {
  spectatorsLoading.value = true
  spectatorsError.value = ''
  try {
    const resp = await api.get(`/rooms/${roomId}/spectators`)
    if (reqId !== spectatorsReqSeq) return
    if (selectedId.value !== roomId) return
    spectators.value = Array.isArray(resp.data?.spectators) ? resp.data.spectators : []
  } catch (err) {
    if (reqId !== spectatorsReqSeq) return
    if (selectedId.value !== roomId) return
    spectators.value = []
    spectatorsError.value = 'Не удалось загрузить'
  } finally {
    if (reqId === spectatorsReqSeq) spectatorsLoading.value = false
  }
  if (reqId !== spectatorsReqSeq) return
  if (!spectatorsTooltipEnabled.value) return
  if (selectedId.value !== roomId) return
  spectatorsOpen.value = true
}

function onSpectatorsToggle() {
  if (!spectatorsTooltipEnabled.value) return
  if (spectatorsOpen.value) {
    spectatorsOpen.value = false
    return
  }
  if (spectatorsLoading.value) return
  const roomId = selectedId.value
  if (!roomId) return
  const reqId = ++spectatorsReqSeq
  void loadSpectators(roomId, reqId)
}

async function onCreated(room: any) {
  openCreate.value = false
  await router.push(`/room/${room.id}`)
}

async function onOpenCreate() {
  if (!canCreateRooms.value || !auth.isAuthed || userStore.roomRestricted) return
  if (verificationRestricted.value) return
  openCreate.value = true
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
    if (detail === 'room_owner_blacklisted_requester') {
      access.value = 'blacklisted'
      void alertDialog('Заявка отменена: Вы находитесь в ЧС у владельца комнаты')
      return
    }
    if (detail === 'hidden_room') {
      access.value = 'hidden'
      void alertDialog('Заявка отменена: скрытая комната доступна только по приглашению')
      return
    }
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

async function onAdminKickRoom() {
  const room = selectedRoom.value
  if (!room || adminKickBusy.value || !canCloseRooms.value) return
  if (room.in_game) {
    void alertDialog('Нельзя удалить комнату во время игры')
    return
  }
  const ok = await confirmDialog({
    title: 'Удалить комнату',
    text: `Вы уверены, что хотите кикнуть всех из «${room.title}» и закрыть вход?`,
    confirmText: 'Подтвердить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  adminKickBusy.value = true
  try {
    const closeUrl = isModer.value ? `/moderation/rooms/${room.id}/close` : `/admin/rooms/${room.id}/close`
    await api.post(closeUrl)
    const cur = roomsMap.get(room.id)
    if (cur) roomsMap.set(room.id, { ...cur, entry_closed: true })
    void alertDialog('Комната закрыта, она будет удалена после освобождения.')
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (detail === 'room_in_game') {
      void alertDialog('Нельзя удалить комнату во время игры')
    } else if (detail === 'room_not_found') {
      void alertDialog('Комната не найдена')
      clearSelection()
    } else {
      void alertDialog('Не удалось удалить комнату')
    }
  } finally { adminKickBusy.value = false }
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
  if (target instanceof Element && target.closest('.user-mini-profile-overlay, .avatar-lightbox-overlay')) return
  if (spectatorsOpen.value) {
    const wrap = spectatorsWrapEl.value
    if (!wrap || (target && !wrap.contains(target))) {
      spectatorsOpen.value = false
      return
    }
  }
  if (target instanceof Element) {
    if (target.closest('.item.active')) return
    if (target.closest('.room-info')) return
  }
  clearSelection()
}

async function onEnter() {
  const id = selectedRoom?.value?.id
  if (!id || entering.value) return
  entering.value = true
  try { await router.push(`/room/${id}`) }
  finally { entering.value = false }
}

async function onAdminSpectateRoom() {
  const id = selectedRoom?.value?.id
  if (!id || entering.value || !canAdminSpectateRoom.value) return
  entering.value = true
  try {
    await router.push({ path: `/room/${id}`, query: { spectator: 'admin' } })
  } finally {
    entering.value = false
  }
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

  sio.value.on('settings_update', (payload: unknown) => {
    if (settings.applyPublicPayload(payload)) return
    void settings.fetchPublic()
  })

  sio.value.on('rooms_upsert', (r: Room) => {
    upsert(r)
    if (selectedId.value === r.id) scheduleInfoRefresh(r.id, 150)
    if (!selectedId.value && !suppressedAutoselect.value) selectRoom(r.id)
  })

  sio.value.on('rooms_remove', (p: { id: number }) => remove(p.id))

  sio.value.on('rooms_refresh', () => {
    void syncRoomsSnapshot()
  })

  sio.value.on('rooms_occupancy', async (p: { id: number; occupancy: number }) => {
    const cur = roomsMap.get(p.id)
    if (cur) roomsMap.set(p.id, { ...cur, occupancy: p.occupancy })
    if (selectedId.value === p.id) scheduleInfoRefresh(p.id, 300)
  })

  sio.value.on('rooms_spectators', (p: { id: number; spectators_count: number }) => {
    if (selectedId.value !== p.id) return
    const prevCount = info.value?.spectators_count
    if (info.value) {
      info.value = { ...info.value, spectators_count: p.spectators_count }
    } else {
      scheduleInfoRefresh(p.id, 300)
    }
    if (spectatorsTooltipVisible.value && prevCount !== p.spectators_count) {
      const reqId = ++spectatorsReqSeq
      void loadSpectators(p.id, reqId)
    }
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
    void syncRoomsSnapshot()
    if (selectedId.value && rid === selectedId.value) {
      access.value = 'approved'
      void fetchRoomInfo(rid)
    }
  }
}

function onAppRevoked(e: any) {
  const p = e?.detail
  const rid = Number(p?.room_id)
  if (!Number.isFinite(rid)) return
  void syncRoomsSnapshot()
  if (selectedId.value && rid === selectedId.value) {
    access.value = p?.source === 'blacklist' ? 'blacklisted' : 'none'
  }
}

watch([selectedId, () => auth.isAuthed], ([id, ok]) => {
  if (ok && id) void fetchAccess(id as number)
})

watch(selectedId, () => {
  spectatorsOpen.value = false
  spectators.value = []
  spectatorsLoading.value = false
  spectatorsError.value = ''
})

watch(() => selectedRoom.value?.in_game, (inGame) => {
  if (!inGame) {
    spectatorsOpen.value = false
    spectators.value = []
    spectatorsLoading.value = false
    spectatorsError.value = ''
    const rid = selectedId.value
    if (auth.isAuthed && rid) void fetchAccess(rid)
  }
})

watch(() => auth.isAuthed, (ok, prev) => {
  if (!ok) {
    spectatorsOpen.value = false
    spectators.value = []
    spectatorsLoading.value = false
    spectatorsError.value = ''
  }
  if (ok !== prev) {
    stopWS()
    startWS()
    return
  }
  if (sio.value?.connected) void syncRoomsSnapshot()
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
  window.addEventListener('auth-room_app_revoked', onAppRevoked)
})

onBeforeUnmount(() => {
  infoTimers.forEach((t) => { try { clearTimeout(t) } catch {} })
  infoTimers.clear()
  stopWS()
  try { document.removeEventListener('pointerdown', onGlobalPointerDown, { capture: true } as any) } catch {}
  try { window.removeEventListener('auth-notify', onAuthNotify) } catch {}
  try { window.removeEventListener('auth-room_app_revoked', onAppRevoked) } catch {}
})
</script>

<style scoped lang="scss">
.card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 607px;
  align-items: flex-start;
  margin: 0 40px 10px;
  gap: 10px;
  height: 100%;
  overflow: hidden;
  .left {
    display: flex;
    flex-direction: column;
    height: calc(100dvh - 94px);
    border-radius: 24px;
    background-color: $soft-purple-900;
    &.left--top-banner {
      height: calc(100dvh - 134px);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 24px 24px 16px;
      .left-title {
        color: $neutral-white;
        font-family: Involve-Medium;
        font-size: 24px;
        line-height: 26px;
        letter-spacing: -0.48px;
      }
    }
    .muted-rooms {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 10px;
      width: 100%;
      height: 100%;
      img {
        width: 220px;
        height: 250px;
      }
      span {
        color: $neutral-300;
        font-family: Hauora-Regular;
        font-size: 16px;
        line-height: 22px;
        letter-spacing: -0.32px;
      }
    }
    .list {
      display: flex;
      flex-direction: column;
      padding: 16px 24px 0;
      gap: 16px;
      height: calc(100% - 120px);
      .text-center {
        text-align: center;
      }
      .list-header {
        display: grid;
        grid-template-columns: 10% 50% 30% 10%;
        padding: 0 16px;
        span {
          color: $neutral-300;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 100%;
          letter-spacing: -0.32px;
        }
      }
      .list-body-shell {
        position: relative;
        flex: 1 1 auto;
        min-height: 0;
        margin-right: -18px;
      }
      .list-body {
        display: flex;
        flex-direction: column;
        box-sizing: border-box;
        height: 100%;
        margin: 0;
        padding: 0 18px 24px 0;
        gap: 10px;
        list-style: none;
        overflow-y: auto;
        overflow-x: hidden;
        scrollbar-width: none;
        -ms-overflow-style: none;
        &::-webkit-scrollbar {
          display: none;
          width: 0;
          height: 0;
        }
        .item {
          display: grid;
          position: relative;
          grid-template-columns: 10% 50% 30% 10%;
          align-items: center;
          padding: 16px;
          min-height: 30px;
          border-radius: 20px;
          border: 1px solid transparent;
          background-color: $soft-purple-800;
          overflow: hidden;
          cursor: pointer;
          transition: border-color 0.25s ease-in-out;
          &.active {
            border-color: $green-700;
          }
          &::after {
            content: '';
            position: absolute;
            inset: 0;
            border-radius: inherit;
            background: linear-gradient(261deg, $green-700 0%, $soft-purple-800 100%);
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.25s ease-in-out;
            z-index: 0;
          }
          > * {
            position: relative;
            z-index: 1;
          }
          &:not(:disabled):hover,
          &:not(:disabled):focus-visible,
          &:not(:disabled):active,
          &:not(:disabled).active {
            &::after {
              opacity: 1;
            }
          }
          .cell {
            display: flex;
            align-items: center;
            gap: 8px;
            .item-text {
              color: $neutral-white;
              font-family: Hauora-Regular;
              font-size: 16px;
              line-height: 16px;
              letter-spacing: -0.32px;
              &.ellipsis {
                line-height: 20px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
              }
              &.margin {
                margin-right: 24px;
              }
            }
            .status-room {
              display: flex;
              align-items: center;
              padding: 8px;
              gap: 8px;
              min-width: 59px;
              border-radius: 12px;
              background-color: $neutral-500;
              &.duo {
                background-color: $blue-500;
              }
              &.runned {
                background-color: $green-700;
              }
              &.hide {
                background-color: $neutral-black;
              }
              .dot-img {
                --ui-icon-width: 4px;
                --ui-icon-height: 4px;
                --ui-icon-color: #{$neutral-white};
              }
            }
            img {
              width: 24px;
              height: 24px;
            }
            .lock-icon {
              --ui-icon-width: 24px;
              --ui-icon-height: 24px;
              &--private {
                --ui-icon-color: #{$red-500};
              }
              &--open {
                --ui-icon-color: #{$green-500};
              }
            }
            .user-avatar {
              border-radius: 50%;
              aspect-ratio: 1;
              object-fit: cover;
            }
          }
        }
      }
    }
  }
  .right-column {
    display: flex;
    position: sticky;
    top: 0;
    width: 607px;
    min-width: 607px;
    max-width: 607px;
    height: 100%;
    min-height: 0;
    flex-direction: column;
    gap: 10px;
    .right {
      flex: 0 0 auto;
      display: flex;
      flex-direction: column;
      width: 100%;
      min-width: 0;
      max-width: none;
      height: 510px;
      border-radius: 24px;
      overflow: hidden;
      .loading-overlay {
        margin: auto;
        text-align: center;
        color: $neutral-300;
      }
      .room-info {
        display: flex;
        position: relative;
        flex-direction: column;
        padding: 24px;
        gap: 16px;
        width: calc(100% - 48px);
        height: calc(100% - 48px);
        background-color: $soft-purple-900;
        header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          span {
            max-width: 495px;
            color: $neutral-white;
            font-family: Involve-Medium;
            font-size: 24px;
            line-height: 28px;
            letter-spacing: -0.48px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          .room-actions {
            display: inline-flex;
            align-items: center;
            gap: 12px;
            button {
              display: flex;
              align-items: center;
              justify-content: center;
              padding: 0;
              width: 24px;
              height: 24px;
              border: none;
              background: none;
              cursor: pointer;
              .room-icon {
                --ui-icon-width: 24px;
                --ui-icon-height: 24px;
                --ui-icon-color: #{$neutral-white};
              }
              &:disabled {
                cursor: not-allowed;
                .room-icon {
                  --ui-icon-color: #{$neutral-500};
                }
              }
              &:not(:disabled):hover,
              &:not(:disabled):focus-visible,
              &:not(:disabled):active {
                .room-icon {
                  --ui-icon-color: #{$green-500};
                }
              }
            }
          }
        }
        .ri-info {
          display: flex;
          gap: 10px;
          width: 100%;
          height: 100%;
          .mini-profile-user-trigger {
            display: inline-flex;
            align-items: center;
            flex: 0 1 auto;
            min-width: 0;
            gap: 4px;
            padding: 0;
            border: none;
            background: none;
            color: inherit;
            font: inherit;
            text-align: left;
            cursor: pointer;
            &:disabled {
              cursor: default;
            }
          }
          .ri-members {
            display: flex;
            flex-direction: column;
            padding: 12px;
            gap: 8px;
            width: calc(50% - 24px);
            border-radius: 20px;
            background-color: $soft-purple-800;
            &.solo {
              width: calc(100% - 24px);
            }
            .ri-members-div {
              display: flex;
              align-items: center;
              justify-content: space-between;
              .ri-members-title {
                color: $neutral-white;
                font-family: Involve-Medium;
                font-size: 16px;
                line-height: 22px;
                letter-spacing: -0.28px;
              }
              .ri-members-count {
                padding: 4px 8px;
                border-radius: 999px;
                background-color: $neutral-500;
                color: $neutral-white;
                font-family: Hauora-Regular;
                font-size: 14px;
                line-height: 14px;
                letter-spacing: -0.28px;
              }
            }
            .muted-members {
              display: flex;
              flex-direction: column;
              align-items: center;
              justify-content: center;
              gap: 10px;
              width: 100%;
              height: 100%;
              img {
                width: 110px;
                height: 100px;
              }
              span {
                color: $neutral-300;
                font-family: Hauora-Regular;
                font-size: 14px;
                line-height: 14px;
                letter-spacing: -0.28px;
              }
            }
            .ri-users {
              display: flex;
              flex-direction: column;
              margin: 0;
              padding: 0;
              gap: 4px;
              list-style: none;
              .ri-user {
                display: flex;
                align-items: center;
                gap: 8px;
                width: 100%;
                &.dead {
                  opacity: 0.4;
                }
                .user-numb {
                  min-width: 27px;
                  color: $neutral-300;
                  font-family: Hauora-Regular;
                  font-size: 14px;
                  line-height: 14px;
                  letter-spacing: -0.28px;
                  font-variant-numeric: tabular-nums;
                }
                img {
                  width: 20px;
                  height: 20px;
                }
                .screen-icon {
                  --ui-icon-width: 20px;
                  --ui-icon-height: 20px;
                  --ui-icon-color: #{$neutral-white};
                }
                .user-mini-avatar {
                  border-radius: 50%;
                  object-fit: cover;
                }
                .mini-profile-name {
                  min-width: 0;
                  max-width: 190px;
                  color: $neutral-white;
                  font-family: Hauora-Regular;
                  font-size: 14px;
                  line-height: 16px;
                  letter-spacing: -0.28px;
                  text-overflow: ellipsis;
                  white-space: nowrap;
                  overflow: hidden;
                }
              }
            }
          }
          .ri-meta-game {
            display: flex;
            flex-direction: column;
            padding: 12px;
            gap: 3px;
            width: calc(50% - 24px);
            border-radius: 20px;
            background-color: $soft-purple-800;
            .ri-meta-title {
              margin-bottom: 4px;
              color: $neutral-white;
              font-family: Involve-Medium;
              font-size: 16px;
              line-height: 22px;
              letter-spacing: -0.28px;
            }
            .ri-game-div {
              display: flex;
              align-items: center;
              justify-content: space-between;
              .ri-meta-text,
              .ri-meta-value {
                font-family: Hauora-Regular;
                font-size: 14px;
                line-height: 20px;
                letter-spacing: -0.28px;
              }
              .ri-meta-text {
                color: $neutral-300;
              }
              .ri-meta-value {
                color: $neutral-white;
              }
              .spectators-wrap {
                display: flex;
                position: relative;
                align-items: center;
                gap: 8px;
                cursor: default;
                .spectators-btn {
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  width: 20px;
                  height: 20px;
                  padding: 0;
                  border: none;
                  background: none;
                  cursor: pointer;
                  .spectators-icon {
                    --ui-icon-width: 20px;
                    --ui-icon-height: 20px;
                    --ui-icon-color: #{$neutral-white};
                  }
                  &:not(:disabled):hover,
                  &:not(:disabled):focus-visible,
                  &:not(:disabled):active,
                  &.is-open {
                    .spectators-icon {
                      --ui-icon-color: #{$green-500};
                    }
                  }
                }
                .spectators-tooltip {
                  display: flex;
                  position: absolute;
                  flex-direction: column;
                  top: calc(100% + 4px);
                  right: 0;
                  padding: 16px;
                  width: 200px;
                  border: 1px solid $neutral-200;
                  border-radius: 20px;
                  background-color: $neutral-100;
                  box-shadow: 0 2px 16px rgba($neutral-black, 0.20);
                  z-index: 5;
                  pointer-events: auto;
                  .spectators-list {
                    display: flex;
                    flex-direction: column;
                    gap: 4px;
                    .spectators-row {
                      display: flex;
                      align-items: center;
                      gap: 4px;
                      .mini-profile-name {
                        min-width: 0;
                        max-width: 175px;
                        color: $neutral-black;
                        font-family: Hauora-Regular;
                        font-size: 14px;
                        line-height: 16px;
                        letter-spacing: -0.28px;
                        text-overflow: ellipsis;
                        white-space: nowrap;
                        overflow: hidden;
                      }
                      img {
                        width: 20px;
                        height: 20px;
                        border-radius: 50%;
                        object-fit: cover;
                      }
                    }
                  }
                }
              }
            }
          }
        }
        .ri-actions {
          display: inline-grid;
          .ri-action {
            margin-top: 8px;
            width: 100%;
          }
        }
      }
    }
    .right-extra {
      display: flex;
      position: relative;
      flex: 1 1 auto;
      padding: 24px;
      border-radius: 24px;
      .right-extra-content {
        display: flex;
        flex-direction: column;
        align-self: center;
        align-items: flex-start;
        gap: 16px;
        max-width: calc(100% - 48px);
        z-index: 1;
        .right-extra-copy-subscription {
          width: 220px;
          color: $neutral-white;
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
          .right-extra-copy-accent {
            margin-left: 6px;
            color: $green-500;
          }
        }
        .right-extra-copy-connect {
          color: $neutral-white;
          font-family: Hauora-Bold;
          font-size: 16px;
          line-height: 18px;
          letter-spacing: -0.32px;
        }
        .right-extra-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          width: 40px;
          height: 40px;
          border-radius: 12px;
          border: 1px solid $green-200;
          background: none;
          cursor: pointer;
          transition: border-color 0.25s ease-in-out;
          .btn-icon {
            --ui-icon-width: 20px;
            --ui-icon-height: 20px;
            --ui-icon-color: #{$neutral-white};
          }
          &:not(:disabled):hover,
          &:not(:disabled):focus-visible,
          &:not(:disabled):active,
          &.is-open {
            border-color: $green-500;
            .btn-icon {
              --ui-icon-color: #{$green-500};
            }
          }
        }
      }
      &--primary {
        min-height: 110px;
        height: 110px;
        max-height: 310px;
        .background-image-6 {
          position: absolute;
          left: 0;
          top: 0;
          width: 100%;
          height: 100%;
          border-radius: inherit;
          object-fit: cover;
        }
      }
      &--secondary {
        min-height: 80px;
        height: 80px;
        max-height: 160px;
        .background-image-7 {
          position: absolute;
          left: 0;
          top: 0;
          width: 100%;
          height: 100%;
          border-radius: inherit;
          object-fit: cover;
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

</style>
