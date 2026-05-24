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
        <div class="params">
          <UiSwitch
            v-model="spectatorsEnabled"
            :disabled="spectatorsToggleDisabled"
            :tooltip="spectatorsToggleTooltip"
            tooltip-target="off"
            tooltip-placement="bottom-right"
            label="Зрители:"
            off-label="Откл"
            on-label="Вкл"
            aria-label="Зрители: откл/вкл"
          />
          <UiSwitch
            v-model="isRating"
            label="Режим:"
            off-label="Обычный"
            on-label="Рейтинг"
            aria-label="Режим: обычный/рейтинг"
            :disabled="true"
          />
          <UiSwitch
            v-model="isNoHost"
            label="Ведущий:"
            off-label="Ведущий"
            on-label="Авто"
            aria-label="Ведущий: с ведущим/авто"
            :disabled="true"
          />
          <UiSwitch
            v-model="isPlayersNomination"
            label="Выставления:"
            off-label="Ведущий"
            on-label="Игрок"
            aria-label="Выставления"
            :disabled="gameParamsDisabled"
          />
          <UiSwitch
            v-model="game.farewell_wills"
            label="Завещания:"
            aria-label="Завещания"
            :disabled="gameParamsDisabled"
          />
          <UiSwitch
            v-model="game.wink_knock"
            label="Подмигивать/Стучать:"
            aria-label="Подмигивать/Стучать"
            :disabled="gameParamsDisabled"
          />
          <UiSwitch
            v-model="game.break_at_zero"
            label="Слом в нуле:"
            aria-label="Слом в нуле"
            :disabled="gameParamsDisabled"
          />
          <UiSwitch
            v-model="game.lift_at_zero"
            label="Подъём в нуле:"
            aria-label="Подъём в нуле"
            :disabled="gameParamsDisabled"
          />
          <UiSwitch
            v-model="game.lift_3x"
            label="Подъём 3х при 9х:"
            aria-label="Подъём 3х при 9х"
            :disabled="gameParamsDisabled"
          />
          <UiSwitch
            v-model="game.music"
            label="Музыка:"
            aria-label="Музыка"
            :disabled="gameParamsDisabled"
          />
        </div>
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
import UiSwitch from '@/components/UiSwitch.vue'
import {
  normalizeRoomGameParams,
  roomGameDefault,
  SPECTATORS_DISABLED_LIMIT,
  SPECTATORS_ENABLED_LIMIT,
  type RoomGameParams,
} from '@/services/gameParams'
import iconClose from '@/assets/svg/close.svg'

const props = defineProps<{
  open: boolean
  roomId: number | string
  canEdit: boolean
  externalGame?: RoomGameParams | null
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
const gameParamsDisabled = computed(() => busy.value || loading.value || !props.canEdit)
const spectatorsDisabledHint = 'Отключение зрителей доступно пользователям, поддержавшим платформу'

const isRating = computed<boolean>({
  get: () => game.value.mode === 'rating',
  set: v => { game.value.mode = v ? 'rating' : 'normal' },
})

const isNoHost = computed<boolean>({
  get: () => game.value.format === 'nohost',
  set: v => { game.value.format = v ? 'nohost' : 'hosted' },
})

const isPlayersNomination = computed<boolean>({
  get: () => game.value.nominate_mode === 'players',
  set: v => { game.value.nominate_mode = v ? 'players' : 'head' },
})

const spectatorsEnabled = computed<boolean>({
  get: () => game.value.spectators_limit >= SPECTATORS_ENABLED_LIMIT,
  set: (next) => {
    if (!next && !canDisableSpectators.value) return
    game.value.spectators_limit = next ? SPECTATORS_ENABLED_LIMIT : SPECTATORS_DISABLED_LIMIT
  },
})

const spectatorsToggleDisabled = computed(() => Boolean(gameParamsDisabled.value || !canDisableSpectators.value))
const spectatorsToggleTooltip = computed(() => {
  if (gameParamsDisabled.value || canDisableSpectators.value) return undefined
  return spectatorsDisabledHint
})

function normalizeLoadedGame(raw: unknown): RoomGameParams {
  return normalizeRoomGameParams(raw, {
    allowDisableSpectators: true,
  })
}

function normalizeSaveGame(raw: unknown): RoomGameParams {
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

function applyGame(next: RoomGameParams): void {
  game.value = { ...next }
  initialGame.value = { ...next }
}

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
    const next = data?.game ? normalizeLoadedGame(data.game) : { ...roomGameDefault }
    applyGame(next)
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
    const payload = normalizeSaveGame(game.value)
    await api.patch(`/rooms/${props.roomId}/game`, payload)
    saveLastGame(payload)
    applyGame(payload)
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

watch(() => props.externalGame, (next) => {
  if (!next) return
  applyGame(normalizeLoadedGame(next))
}, { deep: true })

watch([canDisableSpectators, () => props.canEdit], ([allowDisable, canEdit]) => {
  const normalizedGame = normalizeRoomGameParams(game.value, {
    allowDisableSpectators: !canEdit || allowDisable,
  })
  const normalizedInitial = initialGame.value
    ? normalizeRoomGameParams(initialGame.value, { allowDisableSpectators: !canEdit || allowDisable })
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
  .params {
    display: flex;
    flex-direction: column;
    padding: 10px;
    gap: 15px;
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

</style>
