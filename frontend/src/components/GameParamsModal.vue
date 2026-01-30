<template>
  <Transition name="panel">
    <div v-show="open" class="game-params-panel" aria-label="Параметры игры" @click.stop>
      <header>
        <span>Параметры игры</span>
        <button @click="emitClose" aria-label="Закрыть">
          <img :src="iconClose" alt="close" />
        </button>
      </header>

      <div class="modal-div">
        <GameParamsForm v-model="game" :disabled="busy || loading" />
      </div>

      <div class="save-game">
        <button :disabled="busy || loading" @click="save">Сохранить</button>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import GameParamsForm from '@/components/GameParamsForm.vue'
import iconClose from '@/assets/svg/close.svg'

const props = defineProps<{
  open: boolean
  roomId: number | string
}>()

type Game = {
  mode: 'normal' | 'rating'
  format: 'hosted' | 'nohost'
  spectators_limit: number
  nominate_mode: 'head' | 'players'
  break_at_zero: boolean
  lift_at_zero: boolean
  lift_3x: boolean
  wink_knock: boolean
  farewell_wills: boolean
  music: boolean
}

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'saved', game: Game): void
}>()

const gameDefault: Game = {
  mode: 'normal',
  format: 'hosted',
  spectators_limit: 10,
  nominate_mode: 'players',
  break_at_zero: true,
  lift_at_zero: true,
  lift_3x: true,
  wink_knock: true,
  farewell_wills: true,
  music: true,
}

const SPECT_MIN = 0
const SPECT_MAX = 10

const busy = ref(false)
const loading = ref(false)
const game = ref<Game>({ ...gameDefault })

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

function normalizeGame(raw: any): Game {
  const merged: Game = { ...gameDefault }
  if (!raw || typeof raw !== 'object') return merged
  if (raw.mode === 'normal' || raw.mode === 'rating') merged.mode = raw.mode
  if (raw.format === 'hosted' || raw.format === 'nohost') merged.format = raw.format
  if (raw.nominate_mode === 'head' || raw.nominate_mode === 'players') merged.nominate_mode = raw.nominate_mode
  const spect = Number(raw.spectators_limit)
  if (Number.isFinite(spect)) merged.spectators_limit = clamp(spect, SPECT_MIN, SPECT_MAX)
  if (typeof raw.break_at_zero === 'boolean') merged.break_at_zero = raw.break_at_zero
  if (typeof raw.lift_at_zero === 'boolean') merged.lift_at_zero = raw.lift_at_zero
  if (typeof raw.lift_3x === 'boolean') merged.lift_3x = raw.lift_3x
  if (typeof raw.wink_knock === 'boolean') merged.wink_knock = raw.wink_knock
  if (typeof raw.farewell_wills === 'boolean') merged.farewell_wills = raw.farewell_wills
  if (typeof raw.music === 'boolean') merged.music = raw.music
  return merged
}

function emitClose() {
  emit('update:open', false)
}

async function loadGame() {
  if (!props.roomId) return
  loading.value = true
  try {
    const { data } = await api.get(`/rooms/${props.roomId}/info`)
    if (data?.game) {
      game.value = normalizeGame(data.game)
    } else {
      game.value = { ...gameDefault }
    }
  } catch {
    void alertDialog('Не удалось загрузить параметры игры')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (busy.value || loading.value) return
  busy.value = true
  try {
    const payload = { ...game.value }
    await api.patch(`/rooms/${props.roomId}/game`, payload)
    emit('saved', payload)
    emitClose()
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
  overflow: hidden;
  z-index: 25;
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
    padding: 10px;
    background-color: $dark;
    overflow-y: auto;
    scrollbar-width: none;
  }
  .save-game {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 0 20px;
    button {
      padding: 0;
      width: calc(100% - 40px);
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
    .modal-div {
      padding: 10px 10px 0;
    }
  }
}
</style>
