<template>
  <Transition name="panel">
    <div
      v-show="open"
      class="game-params-panel"
      :data-open="open ? 1 : 0"
      aria-label="Параметры игры"
      @click.stop
    >
      <header>
        <span>Параметры игры</span>
        <button @click="emitClose" aria-label="Закрыть">
          <img :src="iconClose" alt="close" />
        </button>
      </header>

      <div class="modal-div">
        <GameParamsForm
          v-model="game"
          :disabled="busy || loading || !canEdit"
          :can-disable-spectators="canDisableSpectators"
          spectators-disabled-hint="Отключение зрителей доступно пользователям, поддержавшим платформу"
        />
      </div>

      <div v-if="canEdit" class="save-game">
        <button :disabled="busy || loading || !isDirty" @click="save">Сохранить</button>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { useUserStore } from '@/store'
import GameParamsForm from '@/components/GameParamsForm.vue'
import {
  normalizeRoomGameParams,
  roomGameDefault,
  type RoomGameParams,
} from '@/services/gameParams'
import iconClose from '@/assets/svg/close.svg'

const props = defineProps<{
  open: boolean
  roomId: number | string
  canEdit: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'saved', game: RoomGameParams): void
}>()

const user = useUserStore()
const busy = ref(false)
const loading = ref(false)
const game = ref<RoomGameParams>({ ...roomGameDefault })
const initialGame = ref<RoomGameParams | null>(null)
const canDisableSpectators = computed(() => Boolean(user.subscriptionActive))

function normalizeGame(raw: unknown): RoomGameParams {
  return normalizeRoomGameParams(raw, {
    allowDisableSpectators: canDisableSpectators.value,
  })
}

function isSameGame(a: RoomGameParams, b: RoomGameParams) {
  return a.mode === b.mode &&
    a.format === b.format &&
    a.spectators_limit === b.spectators_limit &&
    a.nominate_mode === b.nominate_mode &&
    a.break_at_zero === b.break_at_zero &&
    a.lift_at_zero === b.lift_at_zero &&
    a.lift_3x === b.lift_3x &&
    a.wink_knock === b.wink_knock &&
    a.farewell_wills === b.farewell_wills &&
    a.music === b.music
}

const isDirty = computed(() => {
  if (!initialGame.value) return false
  return !isSameGame(initialGame.value, game.value)
})

function emitClose() {
  emit('update:open', false)
}

function saveLastGame(gameToStore: RoomGameParams) {
  try {
    localStorage.setItem('room:lastGame', JSON.stringify(gameToStore))
  } catch {}
}

async function loadGame() {
  if (!props.roomId) return
  loading.value = true
  try {
    const { data } = await api.get(`/rooms/${props.roomId}/info`)
    const next = data?.game ? normalizeGame(data.game) : { ...roomGameDefault }
    game.value = next
    initialGame.value = { ...next }
  } catch {
    void alertDialog('Не удалось загрузить параметры игры')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!props.canEdit || !isDirty.value || busy.value || loading.value) return
  busy.value = true
  try {
    const payload = normalizeGame(game.value)
    await api.patch(`/rooms/${props.roomId}/game`, payload)
    saveLastGame(payload)
    initialGame.value = { ...payload }
    game.value = { ...payload }
    emit('saved', payload)
    emitClose()
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 409 && d === 'game_in_progress') void alertDialog('Игра уже началась')
    else if (st === 403 && d === 'forbidden') void alertDialog('Нет доступа к настройкам игры')
    else if (st === 403 && d === 'subscription_required') void alertDialog('Отключение зрителей доступно только обладателям подписки')
    else if (st === 404 && d === 'room_not_found') void alertDialog('Комната не найдена')
    else if (st === 429 && d === 'rate_limited') void alertDialog('Слишком много запросов, попробуйте позже')
    else if (d && typeof d === 'object' && d.detail) void alertDialog(String(d.detail))
    else if (typeof d === 'string' && d) void alertDialog(d)
    else void alertDialog('Ошибка сохранения параметров игры')
  } finally {
    busy.value = false
  }
}

watch(() => props.open, (on) => {
  if (on) void loadGame()
}, { immediate: true })

watch(() => props.roomId, () => {
  if (props.open) void loadGame()
})

watch(canDisableSpectators, (allowDisable) => {
  const normalizedGame = normalizeRoomGameParams(game.value, {
    allowDisableSpectators: allowDisable,
  })
  const normalizedInitial = initialGame.value
    ? normalizeRoomGameParams(initialGame.value, { allowDisableSpectators: allowDisable })
    : null

  if (JSON.stringify(normalizedGame) !== JSON.stringify(game.value)) {
    game.value = normalizedGame
  }
  if (normalizedInitial && JSON.stringify(normalizedInitial) !== JSON.stringify(initialGame.value)) {
    initialGame.value = normalizedInitial
  }
}, { flush: 'sync' })
</script>

<style scoped lang="scss">
.game-params-panel {
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  bottom: 50px;
  width: 400px;
  max-height: 600px;
  border-radius: 5px;
  background-color: $dark;
  box-shadow: 3px 3px 5px rgba($black, 0.25);
  z-index: 25;
  &[data-open="0"] {
    pointer-events: none;
  }
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
    background-color: $dark;
    overflow-y: auto;
    scrollbar-width: none;
  }
  .save-game {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 0 10px;
    button {
      padding: 0;
      width: calc(100% - 20px);
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

.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}
.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(30px);
}

@media (max-width: 1280px) {
  .game-params-panel {
    bottom: 30px;
    max-height: calc(100dvh - 40px);
    header {
      padding: 5px;
      span {
        font-size: 14px;
      }
      button {
        width: 20px;
        height: 20px;
        img {
          width: 15px;
          height: 15px;
        }
      }
    }
    .save-game {
      button {
        height: 30px;
        font-size: 14px;
      }
    }
  }
}
</style>
