<template>
  <Transition name="panel">
    <div v-show="open" class="game-params-panel" :data-open="open ? 1 : 0" aria-label="Параметры игры" @click.stop>
      <header>
        <span class="title">Параметры игры</span>
        <button class="close-btn" type="button" aria-label="Закрыть" @click="emitClose">
          <UiIcon class="close-icon" :icon="iconClose" />
        </button>
      </header>

      <div class="modal-shell">
        <div ref="paramsScroll" class="modal-div">
          <div class="params">
            <UiSwitch
              v-model="isRating"
              label="Режим:"
              theme="light"
              size="low"
              :width="256"
              off-label="Обычный"
              on-label="Рейтинг"
              aria-label="Режим"
              :disabled="gameParamsDisabled"
            />
<!--              :disabled="true"-->
            <UiSwitch
              v-model="spectatorsEnabled"
              :disabled="modeDependentParamsDisabled"
              label="Зрители:"
              theme="light"
              size="low"
              :width="256"
              off-label="Откл"
              on-label="Вкл"
              aria-label="Зрители: откл/вкл"
            />
            <UiSwitch
              v-model="isPlayersNomination"
              label="Выставления:"
              theme="light"
              size="low"
              :width="256"
              off-label="Ведущий"
              on-label="Игрок"
              aria-label="Выставления"
              :disabled="modeDependentParamsDisabled"
            />
            <UiSwitch
              v-model="game.tech_fouls"
              label="Тех. фолы:"
              theme="light"
              size="low"
              :width="256"
              aria-label="Тех. фолы"
              :disabled="modeDependentParamsDisabled"
            />
            <UiSwitch
              v-model="game.farewell_wills"
              label="Завещания:"
              theme="light"
              size="low"
              :width="256"
              aria-label="Завещания"
              :disabled="modeDependentParamsDisabled"
            />
            <UiSwitch
              v-model="game.wink_knock"
              label="Подмигивать/Стучать:"
              theme="light"
              size="low"
              :width="256"
              aria-label="Подмигивать/Стучать"
              :disabled="modeDependentParamsDisabled"
            />
            <UiSwitch
              v-model="game.break_at_zero"
              label="Слом в нуле:"
              theme="light"
              size="low"
              :width="256"
              aria-label="Слом в нуле"
              :disabled="modeDependentParamsDisabled"
            />
            <UiSwitch
              v-model="game.lift_at_zero"
              label="Подъем в нуле:"
              theme="light"
              size="low"
              :width="256"
              aria-label="Подъем в нуле"
              :disabled="modeDependentParamsDisabled"
            />
            <UiSwitch
              v-model="game.lift_3x"
              label="Подъем 3х при 9х:"
              theme="light"
              size="low"
              :width="256"
              aria-label="Подъем 3х при 9х"
              :disabled="modeDependentParamsDisabled"
            />
            <UiSwitch
              v-model="game.first_shot_check"
              label="Проверка 1го отстрела:"
              theme="light"
              size="low"
              :width="256"
              aria-label="Проверка 1го отстрела"
              :disabled="modeDependentParamsDisabled"
            />
            <UiSwitch
              v-model="game.music"
              label="Музыка:"
              theme="light"
              size="low"
              :width="256"
              aria-label="Музыка"
              :disabled="modeDependentParamsDisabled"
            />
          </div>
        </div>
        <UiScrollbar :target="paramsScroll" :active="open" theme="light" :inset-bottom="8" right="-16px" />
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import {
  normalizeRoomGameParams,
  roomGameDefault,
  SPECTATORS_DISABLED_LIMIT,
  SPECTATORS_ENABLED_LIMIT,
  type RoomGameParams,
} from '@/services/gameParams'

import UiSwitch from '@/components/UiSwitch.vue'
import UiScrollbar from '@/components/UiScrollbar.vue'
import UiIcon from '@/components/UiIcon.vue'

import iconClose from '@/assets/svg/iconClose.svg'

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

const busy = ref(false)
const loading = ref(false)
const paramsScroll = ref<HTMLElement | null>(null)
const game = ref<RoomGameParams>({ ...roomGameDefault })
const initialGame = ref<RoomGameParams | null>(null)
const gameParamsDisabled = computed(() => busy.value || loading.value || !props.canEdit)

const isRating = computed<boolean>({
  get: () => game.value.mode === 'rating',
  set: v => {
    game.value = normalizeGame({ ...game.value, mode: v ? 'rating' : 'normal' })
  },
})

const modeDependentParamsDisabled = computed(() => gameParamsDisabled.value || isRating.value)

const isPlayersNomination = computed<boolean>({
  get: () => game.value.nominate_mode === 'players',
  set: v => { game.value.nominate_mode = v ? 'players' : 'head' },
})

const spectatorsEnabled = computed<boolean>({
  get: () => game.value.spectators_limit >= SPECTATORS_ENABLED_LIMIT,
  set: (next) => {
    game.value.spectators_limit = next ? SPECTATORS_ENABLED_LIMIT : SPECTATORS_DISABLED_LIMIT
  },
})

function normalizeGame(raw: unknown): RoomGameParams {
  return normalizeRoomGameParams(raw)
}

function isSameGame(a: RoomGameParams, b: RoomGameParams) {
  return a.mode === b.mode &&
    a.spectators_limit === b.spectators_limit &&
    a.nominate_mode === b.nominate_mode &&
    a.tech_fouls === b.tech_fouls &&
    a.break_at_zero === b.break_at_zero &&
    a.lift_at_zero === b.lift_at_zero &&
    a.lift_3x === b.lift_3x &&
    a.first_shot_check === b.first_shot_check &&
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
    const next = data?.game ? normalizeGame(data.game) : { ...roomGameDefault }
    applyGame(next)
  } catch {
    void alertDialog('Не удалось загрузить параметры игры')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!props.roomId || !props.canEdit || !isDirty.value || busy.value || loading.value) return
  busy.value = true
  try {
    const payload = normalizeGame(game.value)
    await api.patch(`/rooms/${props.roomId}/game`, payload)
    saveLastGame(payload)
    applyGame(payload)
    emit('saved', payload)
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 409 && d === 'game_in_progress') void alertDialog('Игра уже началась')
    else if (st === 403 && d === 'forbidden') void alertDialog('Нет доступа к настройкам игры')
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
  applyGame(normalizeGame(next))
}, { deep: true })

watch(game, () => {
  if (!props.open) return
  void save()
}, { deep: true })

</script>

<style scoped lang="scss">
.game-params-panel {
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  bottom: 48px;
  padding: 16px 24px;
  width: 462px;
  max-height: 400px;
  border-radius: 24px;
  background-color: $neutral-100;
  box-shadow: 0 0 16px 0 rgba($neutral-black, 0.16);
  z-index: 25;
  &[data-open="0"] {
    pointer-events: none;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 4px 16px;
    .title {
      color: $neutral-black;
      font-family: Hauora-Bold;
      font-size: 18px;
      line-height: 20px;
      letter-spacing: -0.36px;
    }
    .close-btn {
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
  .modal-shell {
    display: flex;
    position: relative;
    min-height: 0;
    .modal-div {
      display: flex;
      flex: 1 1 auto;
      flex-direction: column;
      min-height: 0;
      overflow-y: auto;
      scrollbar-width: none;
      .params {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      &::-webkit-scrollbar {
        display: none;
        width: 0;
        height: 0;
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
