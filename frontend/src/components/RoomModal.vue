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
        <div class="tabs">
          <button :class="{active: tab === 'room'}" @click="openTab('room')">Комната</button>
          <button :class="{active: tab === 'game'}" @click="openTab('game')" :disabled="!canOpenGameTab" :aria-disabled="!canOpenGameTab">Игра</button>
        </div>

        <div class="tab-viewport">
          <Transition :name="tabTrans" mode="out-in">
            <div v-if="tab === 'room'" key="room" class="params">
              <div class="roomname">
                <span>Название комнаты:</span>
                <input v-model.trim="title" placeholder="Название" maxlength="32" />
              </div>

              <div class="range">
                <span>Лимит: {{ limit }}/12</span>
                <div class="range-wrap">
                  <div class="range-dead" :style="deadZoneStyle" aria-hidden="true"></div>
                  <div class="range-track" :style="rangeFillStyle" aria-hidden="true"></div>
                  <input class="range-native" type="range" min="0" max="12" step="1" v-model.number="limit" aria-label="Лимит участников" />
                </div>
              </div>

              <div class="switch">
                <span>Приватность:</span>
                <label>
                  <input type="checkbox" v-model="isPrivate" aria-label="Приватность: открытая/закрытая" />
                  <div class="slider">
                    <span>Открытая</span>
                    <span>Закрытая</span>
                  </div>
                </label>
              </div>
            </div>

            <div v-else key="game" class="params">
              <div class="switch">
                <span>Режим:</span>
                <label>
                  <input type="checkbox" v-model="isRating" disabled aria-label="Режим: обычный/рейтинг" />
                  <div class="slider">
                    <span>Обычный</span>
                    <span>Рейтинг</span>
                  </div>
                </label>
              </div>
              <div class="switch">
                <span>Судья:</span>
                <label>
                  <input type="checkbox" v-model="isNoHost" disabled aria-label="Формат: с ведущим/без ведущего" />
                  <div class="slider">
                    <span>Ведущий</span>
                    <span>Автомат</span>
                  </div>
                </label>
              </div>

              <div class="range is-disabled">
                <span>Лимит зрителей: {{ game.spectators_limit }}/10</span>
                <div class="range-wrap">
                  <div class="range-track" :style="rangeSpectFillStyle" aria-hidden="true"></div>
                  <input class="range-native" type="range" min="0" max="10" step="1" v-model.number="game.spectators_limit" disabled aria-label="Лимит зрителей" />
                </div>
              </div>

              <div class="switch">
                <span>Слом в нуле:</span>
                <label>
                  <input type="checkbox" v-model="game.vote_at_zero" disabled aria-label="Слом в нуле" />
                  <div class="slider">
                    <span>Выкл</span>
                    <span>Вкл</span>
                  </div>
                </label>
              </div>
              <div class="switch">
                <span>Подъём троих:</span>
                <label>
                  <input type="checkbox" v-model="game.vote_three" disabled aria-label="Подъём троих" />
                  <div class="slider">
                    <span>Выкл</span>
                    <span>Вкл</span>
                  </div>
                </label>
              </div>
              <div class="switch">
                <span>30с речи при 3 фолах:</span>
                <label>
                  <input type="checkbox" v-model="game.speech30_at_3_fouls" disabled aria-label="30с речи при 3 фолах" />
                  <div class="slider">
                    <span>Выкл</span>
                    <span>Вкл</span>
                  </div>
                </label>
              </div>
              <div class="switch">
                <span>За 2 фола +30с к речи:</span>
                <label>
                  <input type="checkbox" v-model="game.extra30_at_2_fouls" disabled aria-label="За 2 фола +30с к речи" />
                  <div class="slider">
                    <span>Выкл</span>
                    <span>Вкл</span>
                  </div>
                </label>
              </div>
            </div>
          </Transition>
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
import { useUserStore } from '@/store'

import iconClose from '@/assets/svg/close.svg'

const user = useUserStore()

let prevOverflow = ''
const armed = ref(false)
const busy = ref(false)
const tab = ref<'room'|'game'>('room')
const lastTab = ref<'room'|'game'>('room')
const tabTrans = computed(() =>
  (lastTab.value === 'room' && tab.value === 'game') ? 'slide-left' : 'slide-right'
)

const RANGE_MIN = 0
const RANGE_MAX = 12
const rangePct = computed(() => {
  const p = ((limit.value - RANGE_MIN) * 100) / (RANGE_MAX - RANGE_MIN)
  return Math.max(0, Math.min(100, p))
})
const rangeFillStyle = computed(() => ({ '--fill': `${rangePct.value}%` }))

const DEAD_MIN = 2
const deadPct = computed(() => Math.max(0, Math.min(100, ((DEAD_MIN - RANGE_MIN) * 100) / (RANGE_MAX - RANGE_MIN))))
const deadZoneStyle = computed(() => ({ '--dead': `${deadPct.value}%` }))

const SPECT_MIN = 0
const SPECT_MAX = 10
const rangeSpectPct = computed(() => {
  const p = ((game.value.spectators_limit - SPECT_MIN) * 100) / (SPECT_MAX - SPECT_MIN)
  return Math.max(0, Math.min(100, p))
})
const rangeSpectFillStyle = computed(() => ({ '--fill': `${rangeSpectPct.value}%` }))

const GAME_LIMIT_MIN = 10
const canOpenGameTab = computed(() => limit.value >= GAME_LIMIT_MIN)
function openTab(t: 'room' | 'game') {
  if (t === 'game' && !canOpenGameTab.value) return
  tab.value = t
}

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'created', room: any): void
}>()

type Game = {
  mode: 'normal' | 'rating'
  format: 'hosted' | 'nohost'
  spectators_limit: number
  vote_at_zero: boolean
  vote_three: boolean
  speech30_at_3_fouls: boolean
  extra30_at_2_fouls: boolean
}
const gameDefault: Game = {
  mode: 'normal',
  format: 'hosted',
  spectators_limit: 0,
  vote_at_zero: true,
  vote_three: true,
  speech30_at_3_fouls: true,
  extra30_at_2_fouls: true,
}
const initialGame: Game = (() => {
  try {
    const raw = localStorage.getItem('room:lastGame')
    if (!raw) return gameDefault
    const parsed = JSON.parse(raw)
    return { ...gameDefault, ...parsed }
  } catch { return gameDefault }
})()
const game = ref<Game>(initialGame)

type RoomBasic = {
  title?: string
  user_limit?: number
  privacy?: 'open'|'private'
}
const initialBasic: RoomBasic = (() => {
  try {
    const raw = localStorage.getItem('room:lastRoom')
    return raw ? JSON.parse(raw) as RoomBasic : {}
  } catch { return {} }
})()

const defaultTitle = () => {
  const name = (user.user?.username || '').trim()
  const id = user.user?.id
  const nick = name || (Number.isFinite(id) ? `user${id}` : 'user')
  return `Комната ${nick}`
}
const title = ref((initialBasic.title || defaultTitle()).slice(0, 32))

const initialLimit = (() => {
  const v = Number(initialBasic.user_limit)
  return Number.isFinite(v) ? clamp(v, 2, 12) : 11
})()
const limit = ref<number>(initialLimit)

const privacy = ref<'open'|'private'>(initialBasic.privacy === 'private' ? 'private' : 'open')

const ok = computed(() => title.value.length > 0 && limit.value >= 2 && limit.value <= 12)

const isPrivate = computed<boolean>({
  get: () => privacy.value === 'private',
  set: v => { privacy.value = v ? 'private' : 'open' }
})
const isRating = computed<boolean>({
  get: () => game.value.mode === 'rating',
  set: v => { game.value.mode = v ? 'rating' : 'normal' }
})
const isNoHost = computed<boolean>({
  get: () => game.value.format === 'nohost',
  set: v => { game.value.format = v ? 'nohost' : 'hosted' }
})

function clamp(n: number, min: number, max: number) { return Math.max(min, Math.min(max, n)) }

function saveBasic() {
  try {
    const payload: RoomBasic = {
      title: title.value,
      user_limit: clamp(limit.value, 2, 12),
      privacy: privacy.value,
    }
    localStorage.setItem('room:lastRoom', JSON.stringify(payload))
  } catch {}
}

async function create() {
  if (!ok.value || busy.value) return
  busy.value = true
  try {
    const payload = {
      title: title.value,
      user_limit: limit.value,
      privacy: privacy.value,
      game: { ...game.value },
    }
    saveBasic()
    const { data } = await api.post('/rooms', payload)
    emit('created', data)
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 409 && d === 'rooms_limit_global')      alert('Достигнут общий лимит активных комнат (100). Попробуйте позже.')
    else if (st === 409 && d === 'rooms_limit_user')   alert('У вас уже 3 активные комнаты. Закройте одну и попробуйте снова.')
    else if (st === 422 && d === 'title_empty')        alert('Название не должно быть пустым')
    else if (d && typeof d === 'object' && d.detail)   alert(String(d.detail))
    else if (typeof d === 'string' && d)               alert(d)
    else                                               alert('Ошибка создания комнаты')
  } finally { busy.value = false }
}

watch(() => user.user, () => { if (!title.value) title.value = defaultTitle() })

watch([title, limit, privacy], () => { saveBasic() })

watch(tab, (next, prev) => { lastTab.value = (prev ?? 'room') as 'room'|'game' })

watch(limit, (v) => { if (v < GAME_LIMIT_MIN && tab.value === 'game') tab.value = 'room' })

watch(limit, (v) => { if (v < 2) limit.value = 2 }, { flush: 'sync' })

watch(game, (v) => { try { localStorage.setItem('room:lastGame', JSON.stringify(v)) } catch {} }, { deep: true })

onMounted(() => {
  if (!title.value) title.value = defaultTitle()
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
      padding: 10px;
      border-radius: 5px;
      background-color: $graphite;
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
      padding: 20px;
      gap: 20px;
      border-radius: 5px;
      background-color: $dark;
      .tab-viewport {
        position: relative;
        max-height: 133px;
        overflow-y: auto;
        overflow-x: hidden;
        scrollbar-width: thin;
      }
      .tabs {
        display: flex;
        align-items: flex-end;
        width: 100%;
        height: 40px;
        border-bottom: 3px solid $grey;
        border-radius: 0 0 3px 3px;
        button {
          width: 50%;
          height: 30px;
          border: none;
          border-radius: 5px 5px 0 0;
          background-color: $graphite;
          color: $fg;
          font-size: 16px;
          font-family: Manrope-Medium;
          line-height: 1;
          cursor: pointer;
          transition: height 0.25s ease-in-out, background-color 0.25s ease-in-out;
          &.active {
            height: 40px;
            background-color: $lead;
          }
          &:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
        }
      }
      .params {
        display: flex;
        flex-direction: column;
        gap: 10px;
        .roomname {
          display: flex;
          flex-direction: column;
          gap: 5px;
        }
        .range {
          display: flex;
          flex-direction: column;
          gap: 5px;
          .range-wrap {
            position: relative;
            height: 20px;
          }
          .range-dead {
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: var(--dead);
            border-radius: 5px;
            z-index: 3;
            pointer-events: auto;
            cursor: pointer;
          }
          .range-track {
            position: absolute;
            inset: 0;
            border-radius: 5px;
            border: 1px solid $lead;
            background-color: $graphite;
            overflow: hidden;
          }
          .range-track::after {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: var(--fill);
            background-color: $fg;
            border-radius: inherit;
            transition: width 0.25s ease-in-out;
            will-change: width;
          }
          .range-native {
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            margin: 0;
            padding: 0;
            background: none;
            cursor: pointer;
            z-index: 2;
            -webkit-appearance: none;
            appearance: none;
          }
          .range-native::-webkit-slider-runnable-track {
            background: transparent;
            height: 100%;
          }
          .range-native::-moz-range-track {
            background: transparent;
            height: 100%;
          }
          .range-native::-ms-track {
            background: transparent;
            color: transparent;
            border: none;
            height: 100%;
          }
          .range-native::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 1px;
            height: 100%;
            background: transparent;
            border: none;
          }
          .range-native::-moz-range-thumb {
            width: 1px;
            height: 100%;
            background: transparent;
            border: none;
          }
          .range-native:focus-visible {
            outline: 2px solid $lead;
            outline-offset: 2px;
          }
          .range-native:disabled {
            cursor: not-allowed;
          }
          .range.is-disabled {
            opacity: 0.5;
          }
          .range.is-disabled .range-native {
            cursor: not-allowed;
          }
        }
        .switch {
          display: flex;
          align-items: center;
          justify-content: space-between;
          label {
            position: relative;
            width: 170px;
            height: 25px;
            input {
              position: absolute;
              opacity: 0;
              width: 0;
              height: 0;
            }
            .slider {
              display: flex;
              align-items: center;
              justify-content: space-around;
              position: absolute;
              inset: 0;
              cursor: pointer;
              border: 1px solid $lead;
              border-radius: 5px;
              background-color: $graphite;
              span {
                position: relative;
                font-size: 14px;
                color: $fg;
                transition: color 0.25s ease-in-out;
              }
            }
            .slider:before {
              content: "";
              position: absolute;
              top: 0;
              left: 0;
              width: 83px;
              height: 23px;
              background-color: $fg;
              border-radius: 5px;
              transition: transform 0.25s ease-in-out;
            }
            input:checked + .slider:before {
              transform: translateX(85px);
            }
            input:not(:checked) + .slider span:first-child,
            input:checked + .slider span:last-child {
              color: $bg;
            }
            input:disabled + .slider {
              opacity: 0.5;
              cursor: not-allowed;
            }
          }
        }
      }
    }
    .create-room {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px 0;
      button {
        width: 50%;
        height: 40px;
        border: none;
        border-radius: 5px;
        background-color: $fg;
        color: $bg;
        font-size: 16px;
        font-family: Manrope-Medium;
        line-height: 1;
        cursor: pointer;
        &:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      }
    }
  }
}

.slide-left-enter-active,
.slide-left-leave-active,
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.25s ease-in-out, opacity 0.25s ease-in-out;
}
.slide-left-enter-from {
  transform: translateX(60px);
  opacity: 0;
}
.slide-left-leave-to {
  transform: translateX(-60px);
  opacity: 0;
}
.slide-right-enter-from {
  transform: translateX(-60px);
  opacity: 0;
}
.slide-right-leave-to {
  transform: translateX(60px);
  opacity: 0;
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
