<template>
  <div class="overlay" @pointerdown.self="armed = true" @pointerup.self="armed && $emit('close')"
       @pointerleave.self="armed = false" @pointercancel.self="armed = false">
    <div class="modal">
      <header>
        <div class="header-div">
          <span class="header-title">Создать комнату</span>
        </div>
        <button type="button" @click.stop="$emit('close')" aria-label="Закрыть">
          <UiIcon class="close-icon" :icon="iconClose" />
        </button>
      </header>

      <div class="modal-div">
        <UiInput
          id="room-title"
          v-model.trim="title"
          :maxlength="TITLE_MAX"
          mode="light"
          label="Название комнаты"
          autocomplete="off"
          :invalid="titleInvalid"
          :aria-invalid="titleInvalid"
          aria-describedby="room-title-hint"
        >
          <template #meta>
            <span id="room-title-hint">{{ title.length }}/{{ TITLE_MAX }}</span>
          </template>
        </UiInput>

        <UiTripleSwitch
          v-model="limit"
          label="Лимит участников"
          theme="light"
          :width="274"
          :options="roomLimitOptions"
          aria-label="Лимит участников: 2, 11 или 20"
        />

        <UiSwitch
          v-model="isPrivate"
          theme="light"
          :width="274"
          :disabled="isPrivacyLocked"
          label="Приватность"
          off-label="Открытая"
          on-label="Закрытая"
          aria-label="Приватность: открытая/закрытая"
        />
        <UiSwitch
          v-model="isAnonymous"
          theme="light"
          :width="274"
          :disabled="!canCreateHiddenRoom"
          :tooltip="!canCreateHiddenRoom ? hiddenRoomHint : undefined"
          tooltip-target="on"
          tooltip-placement="top-left"
          tooltip-bubble-width="320px"
          label="Анонимность"
          off-label="Видимая"
          on-label="Скрытая"
          aria-label="Анонимность: видимая/скрытая"
        />
      </div>

      <UiButton
        class="create-room"
        width="100%"
        text="Создать комнату"
        :disabled="busy || !ok"
        @click="create"
      />
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
import { useUserStore } from '@/store'

import UiInput from '@/components/UiInput.vue'
import UiSwitch from '@/components/UiSwitch.vue'
import UiTripleSwitch from '@/components/UiTripleSwitch.vue'
import UiButton from '@/components/UiButton.vue'
import UiIcon from '@/components/UiIcon.vue'

import iconClose from '@/assets/svg/iconClose.svg'

const user = useUserStore()

const armed = ref(false)
const busy = ref(false)
let prevOverflow = ''

const TITLE_MAX = 32
type RoomLimit = 2 | 11 | 20
const roomLimitOptions = [
  { value: 2, label: '2' },
  { value: 11, label: '11' },
  { value: 20, label: '20' },
] as const

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
const titleInvalid = computed(() => title.value.length > TITLE_MAX)

const initialLimit = (() => {
  return normalizeRoomLimit(initialBasic.user_limit)
})()
const limit = ref<RoomLimit>(initialLimit)
const hiddenRoomHint = 'Создание скрытых комнат доступно только при наличии подписки'

const privacy = ref<'open' | 'private'>(initialBasic.privacy === 'private' ? 'private' : 'open')
const initialAnonymity = initialBasic.anonymity === 'hidden' && canCreateHiddenRoom.value ? 'hidden' : 'visible'
const anonymity = ref<'visible' | 'hidden'>(initialAnonymity)
if (anonymity.value === 'hidden') privacy.value = 'private'

const ok = computed(() => title.value.length > 0)

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

function normalizeRoomLimit(value: unknown): RoomLimit {
  const parsed = Number(value)
  if (parsed === 2 || parsed === 11 || parsed === 20) return parsed
  return 11
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
      user_limit: limit.value,
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
    else if (st === 403 && d === 'subscription_required') void alertDialog('Скрытые комнаты доступны только обладателям подписки')
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
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($neutral-800, 0.2);
  backdrop-filter: blur(12px);
  z-index: 1000;
  .modal {
    display: flex;
    flex-direction: column;
    padding: 24px;
    gap: 32px;
    width: 606px;
    border-radius: 24px;
    background-color: $neutral-100;
    box-shadow: 0 2px 16px 0 rgba($neutral-black, 0.20);
    transform: translateY(0);
    transition: transform 0.25s ease-in-out;
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      .header-div {
        display: flex;
        flex-direction: column;
        gap: 8px;
        .header-title {
          color: $neutral-black;
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
      }
      button {
        padding: 0;
        width: 24px;
        height: 24px;
        border: none;
        background: none;
        cursor: pointer;
        .close-icon {
          --ui-icon-width: 24px;
          --ui-icon-height: 24px;
          --ui-icon-color: #{$neutral-black};
        }
        &:not(:disabled):hover,
        &:not(:disabled):focus-visible,
        &:not(:disabled):active {
          .close-icon {
            --ui-icon-color: #{$green-500};
          }
        }
      }
    }
    .modal-div {
      display: flex;
      flex-direction: column;
      gap: 24px;
      background-color: $neutral-100;
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
