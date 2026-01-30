<template>
  <div class="overlay" @pointerdown.self="armed = true" @pointerup.self="armed && emitClose()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
    <div class="modal" role="dialog" aria-modal="true" aria-label="Параметры игры">
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
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import GameParamsForm from '@/components/GameParamsForm.vue'
import iconClose from '@/assets/svg/close.svg'

const props = defineProps<{
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
  (e: 'close'): void
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

const armed = ref(false)
const busy = ref(false)
const loading = ref(false)
const game = ref<Game>({ ...gameDefault })
let prevOverflow = ''


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
  emit('close')
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

onMounted(() => {
  prevOverflow = document.documentElement.style.overflow
  document.documentElement.style.overflow = 'hidden'
  void loadGame()
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
  background-color: rgba($black, 0.75);
  z-index: 1000;
  .modal {
    display: flex;
    flex-direction: column;
    width: 400px;
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
      background-color: $dark;
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
        border-radius: 0 0 5px 5px;
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

@media (max-width: 1280px) {
  .overlay {
    .modal {
      .modal-div {
        padding: 10px 10px 0;
      }
    }
  }
}
</style>
