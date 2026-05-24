<template>
  <div class="overlay" @pointerdown.self="armed = true" @pointerup.self="armed && $emit('close')"
       @pointerleave.self="armed = false" @pointercancel.self="armed = false">
    <div class="modal">
      <header>
        <span>Создать комнату</span>
        <button @click="$emit('close')" aria-label="Закрыть">
          <img :src="iconClose" alt="close" />
        </button>
      </header>

      <div class="modal-div">
        <div class="params">
          <UiInput
            id="room-title"
            v-model.trim="title"
            :maxlength="TITLE_MAX"
            label="Название комнаты"
            autocomplete="off"
            :invalid="!title"
            :underline-style="titleUnderlineStyle"
            :aria-invalid="!title"
            aria-describedby="room-title-hint"
          >
            <template #meta>
              <span id="room-title-hint">{{ title.length }}/{{ TITLE_MAX }}</span>
            </template>
          </UiInput>

          <div class="range" :style="rangeStyle">
            <div class="range-label">
              <span class="limit-text">Лимит участников</span>
              <span class="limit-badge" aria-label="Лимит участников">{{ limit }}</span>
            </div>
            <UiSlider
              v-model="limit"
              :min="RANGE_MIN"
              :max="RANGE_MAX"
              :step="1"
              :dead-zone-until="DEAD_MIN"
              :dead-zone-value="DEAD_MIN"
              aria-label="Лимит участников"
            />
            <div class="range-marks" aria-hidden="true">
              <span v-if="limit === 2" class="range-mark" :style="rangeMarkStyle(2)">DUO HD</span>
              <span v-if="isMafiaRoom" class="range-mark" :style="rangeMarkStyle(gameLimitMin)">MAFIA</span>
            </div>
          </div>

          <UiSwitch
            v-model="isPrivate"
            :disabled="isPrivacyLocked"
            label="Приватность:"
            off-label="Открытая"
            on-label="Закрытая"
            aria-label="Приватность: открытая/закрытая"
          />
          <UiSwitch
            v-model="isAnonymous"
            :disabled="!canCreateHiddenRoom"
            :tooltip="!canCreateHiddenRoom ? hiddenRoomHint : undefined"
            tooltip-target="on"
            tooltip-placement="top-left"
            tooltip-bubble-width="320px"
            label="Анонимность:"
            off-label="Видимая"
            on-label="Скрытая"
            aria-label="Анонимность: видимая/скрытая"
          />
        </div>
      </div>

      <div class="create-room">
        <button :disabled="busy || !ok" @click="create">Создать</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import {
  normalizeRoomGameParams,
  roomGameDefault,
  type RoomGameParams,
} from '@/services/gameParams'
import { formatModerationAlert } from '@/services/moderation'
import { useUserStore, useSettingsStore } from '@/store'

import UiSlider from '@/components/UiSlider.vue'
import UiInput from '@/components/UiInput.vue'
import UiSwitch from '@/components/UiSwitch.vue'

import iconClose from '@/assets/svg/close.svg'

const user = useUserStore()
const settings = useSettingsStore()

const armed = ref(false)
const busy = ref(false)
let prevOverflow = ''

const RANGE_MIN = 0
const RANGE_MAX = 12
const DEAD_MIN = 2
const RANGE_THUMB_SIZE = 26
const TITLE_MAX = 32
const titlePct = computed(() => {
  const used = Math.min(TITLE_MAX, Math.max(0, title.value.length))
  return (used / TITLE_MAX) * 100
})
const titleUnderlineStyle = computed(() => ({ width: `${titlePct.value}%` }))

const gameLimitMin = computed(() => {
  const minReady = Number(settings.gameMinReadyPlayers)
  return Number.isFinite(minReady) && minReady > 0 ? minReady + 1 : 11
})
const rangeStyle = computed<Record<string, string>>(() => ({
  '--range-thumb-size': `${RANGE_THUMB_SIZE}px`,
  '--ui-slider-filled-thumb-size': `${RANGE_THUMB_SIZE}px`,
}))

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'created', room: any): void
}>()

const hasSubscription = computed(() => Boolean(user.subscriptionActive))
const canCreateHiddenRoom = hasSubscription
const canDisableSpectators = hasSubscription

const initialGame: RoomGameParams = (() => {
  try {
    const raw = localStorage.getItem('room:lastGame')
    if (!raw) return { ...roomGameDefault }
    return normalizeRoomGameParams(JSON.parse(raw), {
      allowDisableSpectators: canDisableSpectators.value,
    })
  } catch {
    return { ...roomGameDefault }
  }
})()
const game = ref<RoomGameParams>({ ...initialGame })

type RoomBasic = {
  title?: string
  user_limit?: number
  privacy?: 'open' | 'private'
  anonymity?: 'visible' | 'hidden'
}

const initialBasic: RoomBasic = (() => {
  try {
    const raw = localStorage.getItem('room:lastRoom')
    return raw ? JSON.parse(raw) as RoomBasic : {}
  } catch {
    return {}
  }
})()
const hadStoredTitle = typeof initialBasic.title === 'string' && initialBasic.title.length > 0

const defaultTitle = () => {
  const name = (user.user?.username || '').trim()
  const id = user.user?.id
  const nick = name || (Number.isFinite(id) ? `user${id}` : 'user')
  return `Комната ${nick}`
}

const _title = ref((initialBasic.title || defaultTitle()).slice(0, TITLE_MAX))
const title = computed({
  get: () => _title.value,
  set: v => { _title.value = sanitizeTitle(v, TITLE_MAX) },
})

const initialLimit = (() => {
  const value = Number(initialBasic.user_limit)
  return Number.isFinite(value) ? clamp(value, 2, 12) : 11
})()
const limit = ref<number>(initialLimit)
const isMafiaRoom = computed(() => limit.value === gameLimitMin.value)
const hiddenRoomHint = 'Создание скрытых комнат доступно пользователям, поддержавшим платформу'

const privacy = ref<'open' | 'private'>(initialBasic.privacy === 'private' ? 'private' : 'open')
const initialAnonymity = initialBasic.anonymity === 'hidden' && canCreateHiddenRoom.value ? 'hidden' : 'visible'
const anonymity = ref<'visible' | 'hidden'>(initialAnonymity)
if (anonymity.value === 'hidden') privacy.value = 'private'

const ok = computed(() => title.value.length > 0 && limit.value >= 2 && limit.value <= 12)

const isPrivate = computed<boolean>({
  get: () => privacy.value === 'private',
  set: v => {
    if (!v && anonymity.value === 'hidden') {
      privacy.value = 'private'
      return
    }
    privacy.value = v ? 'private' : 'open'
  },
})

const isAnonymous = computed<boolean>({
  get: () => anonymity.value === 'hidden',
  set: v => {
    if (v && !canCreateHiddenRoom.value) return
    anonymity.value = v ? 'hidden' : 'visible'
  },
})

const isPrivacyLocked = computed(() => anonymity.value === 'hidden')

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

function rangeMarkStyle(value: number): Record<string, string> {
  const span = RANGE_MAX - RANGE_MIN
  const ratio = span > 0 ? (clamp(value, RANGE_MIN, RANGE_MAX) - RANGE_MIN) / span : 0
  const pct = Number((ratio * 100).toFixed(4))
  const thumbOffset = Number((RANGE_THUMB_SIZE * (0.5 - ratio)).toFixed(4))
  return { left: `calc(${pct}% + ${thumbOffset}px)` }
}

function normalizeGame(value: unknown): RoomGameParams {
  return normalizeRoomGameParams(value, {
    allowDisableSpectators: canDisableSpectators.value,
  })
}

function saveBasic() {
  try {
    const payload: RoomBasic = {
      title: title.value,
      user_limit: clamp(limit.value, 2, 12),
      privacy: privacy.value,
      anonymity: anonymity.value,
    }
    localStorage.setItem('room:lastRoom', JSON.stringify(payload))
  } catch {}
}

function saveGame() {
  try {
    localStorage.setItem('room:lastGame', JSON.stringify(normalizeGame(game.value)))
  } catch {}
}

async function create() {
  if (!ok.value || busy.value) return
  busy.value = true
  try {
    const normalizedGame = normalizeGame(game.value)
    game.value = normalizedGame
    const payload = {
      title: title.value,
      user_limit: limit.value,
      privacy: privacy.value,
      anonymity: anonymity.value,
      game: normalizedGame,
    }
    saveBasic()
    saveGame()
    const { data } = await api.post('/rooms', payload)
    emit('created', data)
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    const moderationText = formatModerationAlert(d)
    if (st === 403 && d === 'rooms_create_disabled') void alertDialog('Создание комнат временно недоступно')
    else if (st === 403 && d === 'user_timeout') void alertDialog('Вам выдан таймаут, создание комнаты недоступно')
    else if (st === 403 && d === 'user_banned') void alertDialog('Аккаунт забанен, создание комнаты недоступно')
    else if (st === 403 && d === 'not_verified') void alertDialog('Для создания комнаты требуется верификация')
    else if (st === 403 && d === 'subscription_required') void alertDialog('Скрытые комнаты и отключение зрителей доступны только обладателям подписки')
    else if (st === 409 && d === 'rooms_limit_global') void alertDialog('Достигнут общий лимит комнат')
    else if (st === 409 && d === 'rooms_limit_user') void alertDialog('Достигнут личный лимит комнат')
    else if (st === 422 && moderationText) void alertDialog({ title: 'Отказ в создании', text: moderationText })
    else if (st === 422 && d === 'title_empty') void alertDialog('Название не должно быть пустым')
    else if (d && typeof d === 'object' && d.detail) void alertDialog(String(d.detail))
    else if (typeof d === 'string' && d) void alertDialog(d)
    else void alertDialog('Ошибка создания комнаты')
  } finally {
    busy.value = false
  }
}

function sanitizeTitle(s: string, max = 32): string {
  return (s ?? '')
    .normalize('NFKC')
    .replace(/[\u0000-\u001F\u007F]/g, '')
    .replace(/[\u200B-\u200F\u202A-\u202E\u2066-\u2069]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, max)
}

watch([title, limit, privacy, anonymity], saveBasic, { flush: 'post' })

watch(limit, (value) => {
  if (value < 2) limit.value = 2
}, { flush: 'sync' })

watch(anonymity, (next) => {
  if (next === 'hidden' && privacy.value !== 'private') privacy.value = 'private'
}, { flush: 'sync' })

watch(canCreateHiddenRoom, (canCreate) => {
  if (!canCreate && anonymity.value === 'hidden') anonymity.value = 'visible'
}, { flush: 'sync' })

watch(canDisableSpectators, (allowDisable) => {
  const normalizedGame = normalizeRoomGameParams(game.value, {
    allowDisableSpectators: allowDisable,
  })
  if (JSON.stringify(normalizedGame) !== JSON.stringify(game.value)) {
    game.value = normalizedGame
  }
  saveGame()
}, { flush: 'sync' })

watch(() => user.user, () => {
  if (!hadStoredTitle && !_title.value) _title.value = defaultTitle()
}, { flush: 'post' })

onMounted(() => {
  if (!hadStoredTitle && !_title.value) _title.value = defaultTitle()
  prevOverflow = document.documentElement.style.overflow
  document.documentElement.style.overflow = 'hidden'
})

onBeforeUnmount(() => {
  document.documentElement.style.overflow = prevOverflow
})
</script>

<style scoped lang="scss">
.overlay {
  position: fixed;
  display: flex;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($black, 0.25);
  backdrop-filter: blur(5px);
  z-index: 1000;
  .modal {
    display: flex;
    flex-direction: column;
    width: 600px;
    border-radius: 5px;
    background-color: $dark;
    transform: translateY(0);
    transition: transform 0.25s ease-in-out;
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 5px 10px;
      border-radius: 5px;
      background-color: $graphite;
      box-shadow: 0 3px 5px rgba($black, 0.25);
      span {
        font-size: 18px;
        font-weight: bold;
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
    .modal-div {
      display: flex;
      flex-direction: column;
      padding: 10px 10px 0;
      background-color: $grey;
      .params {
        display: flex;
        flex-direction: column;
        gap: 10px;
        border-bottom: none;
        .range {
          display: flex;
          flex-direction: column;
          gap: 4px;
          .range-label {
            display: flex;
            align-items: center;
            justify-content: space-between;
            .limit-text {
              color: $bg;
              font-size: 12px;
              font-weight: bold;
              letter-spacing: 1px;
            }
            .limit-badge {
              padding: 2px 5px 2px 7px;
              border-radius: 5px;
              background-color: $red;
              color: $fg;
              font-size: 12px;
              font-weight: bold;
              letter-spacing: 1px;
            }
          }
          .range-marks {
            position: relative;
            height: 40px;
            pointer-events: none;
            .range-mark {
              display: inline-flex;
              position: absolute;
              align-items: center;
              justify-content: center;
              top: 7px;
              height: 32px;
              padding: 0 8px;
              border-radius: 12px;
              background-color: $black;
              color: $neutral-white;
              font-family: Hauora-Regular;
              font-size: 16px;
              line-height: 16px;
              letter-spacing: -0.3px;
              white-space: nowrap;
              transform: translateX(-50%);
              isolation: isolate;
            }
            .range-mark::before {
              content: "";
              position: absolute;
              top: -5px;
              left: 50%;
              width: 10px;
              height: 10px;
              border-radius: 3px 0 0;
              background-color: inherit;
              transform: translateX(-50%) scaleX(0.7) rotate(45deg);
              transform-origin: center;
              z-index: -1;
            }
          }
        }
      }
    }
    .create-room {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 10px 0 0;
      button {
        padding: 0;
        width: 100%;
        height: 40px;
        border: none;
        border-radius: 5px;
        background-color: $fg;
        color: $bg;
        font-size: 18px;
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
  }
}

.overlay-enter-active,
.overlay-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}
.overlay-enter-from .modal,
.overlay-leave-to .modal {
  transform: translateY(-30px);
}

</style>
