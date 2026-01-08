<template>
  <div class="overlay" @pointerdown.self="armed = true" @pointerup.self="armed && $emit('close')" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
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
              <div class="ui-input" :class="{ filled: !!title, invalid: !title }">
                <input id="room-title" v-model.trim="title" :maxlength="TITLE_MAX" placeholder=" " autocomplete="off" :aria-invalid="!title" aria-describedby="room-title-hint" />
                <label for="room-title">Название комнаты</label>
                <div class="underline"><span :style="titleUnderlineStyle"></span></div>
                <div class="meta"><span id="room-title-hint">{{ title.length }}/{{ TITLE_MAX }}</span></div>
              </div>

              <div class="range">
                <div class="range-label">
                  <span>Лимит участников: {{ limit }}/{{ RANGE_MAX }}</span>
                  <span v-if="limit === 2" class="limit-badge" aria-label="Высокое качество">HD</span>
                </div>
                <div class="range-wrap">
                  <div class="range-dead" :style="deadZoneStyle" @click="limit = DEAD_MIN"></div>
                  <div class="range-track" :style="rangeFillStyle" aria-hidden="true"></div>
                  <input class="range-native" type="range" :min="RANGE_MIN" :max="RANGE_MAX" step="1" v-model.number="limit" aria-label="Лимит участников" />
                </div>
              </div>

              <div class="switch">
                <span class="switch-label">Приватность:</span>
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
<!--              <div class="range is-disabled">-->
              <div class="range">
                <span>Лимит зрителей: {{ game.spectators_limit }}/{{ SPECT_MAX }}</span>
                <div class="range-wrap">
                  <div class="range-track" :style="rangeSpectFillStyle" aria-hidden="true"></div>
                  <input class="range-native" type="range" :min="SPECT_MIN" :max="SPECT_MAX" step="1" v-model.number="game.spectators_limit" aria-label="Лимит зрителей" />
                </div>
              </div>

              <div class="switch">
                <span class="switch-label">Режим:</span>
                <label>
                  <input type="checkbox" v-model="isRating" disabled aria-label="Режим: обычный/рейтинг" />
                  <div class="slider">
                    <span>Обычный</span>
                    <span>Рейтинг</span>
                  </div>
                </label>
              </div>

              <div class="switch">
                <span class="switch-label">Судья:</span>
                <label>
                  <input type="checkbox" v-model="isNoHost" disabled aria-label="Формат: с ведущим/без ведущего" />
                  <div class="slider">
                    <span>Ведущий</span>
                    <span>Авто</span>
                  </div>
                </label>
              </div>

              <div class="switch">
                <span class="switch-label">Слом в нуле:</span>
                <label>
                  <input type="checkbox" v-model="game.break_at_zero" aria-label="Слом в нуле" />
                  <div class="slider">
                    <span>Откл</span>
                    <span>Вкл</span>
                  </div>
                </label>
              </div>

              <div class="switch">
                <span class="switch-label">Подъем в нуле:</span>
                <label>
                  <input type="checkbox" v-model="game.lift_at_zero" aria-label="Подъем в нуле" />
                  <div class="slider">
                    <span>Откл</span>
                    <span>Вкл</span>
                  </div>
                </label>
              </div>

              <div class="switch">
                <span class="switch-label">Подъем 3х при 9х:</span>
                <label>
                  <input type="checkbox" v-model="game.lift_3x" aria-label="Подъем 3х" />
                  <div class="slider">
                    <span>Откл</span>
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
import { alertDialog } from '@/services/confirm'
import { useUserStore, useSettingsStore } from '@/store'

import iconClose from '@/assets/svg/close.svg'

const user = useUserStore()
const settings = useSettingsStore()

const armed = ref(false)
const busy = ref(false)
const tab = ref<'room'|'game'>('room')
const lastTab = ref<'room'|'game'>('room')
const tabTrans = computed(() => (lastTab.value === 'room' && tab.value === 'game') ? 'slide-left' : 'slide-right')
let prevOverflow = ''
let prevTab: 'room'|'game' = tab.value

const RANGE_MIN = 0
const RANGE_MAX = 12
const rangePct = computed(() => {
  const p = ((limit.value - RANGE_MIN) * 100) / (RANGE_MAX - RANGE_MIN)
  return Math.max(0, Math.min(100, p))
})
const rangeFillStyle = computed<Record<string, string>>(() => ({ '--fill': `${rangePct.value}%` }))

const DEAD_MIN = 2
const deadPct = computed(() => Math.max(0, Math.min(100, ((DEAD_MIN - RANGE_MIN) * 100) / (RANGE_MAX - RANGE_MIN))))
const deadZoneStyle = computed<Record<string, string>>(() => ({ '--dead': `${deadPct.value}%` }))

const SPECT_MIN = 0
const SPECT_MAX = 10
const rangeSpectPct = computed(() => {
  const p = ((game.value.spectators_limit - SPECT_MIN) * 100) / (SPECT_MAX - SPECT_MIN)
  return Math.max(0, Math.min(100, p))
})
const rangeSpectFillStyle = computed<Record<string, string>>(() => ({ '--fill': `${rangeSpectPct.value}%` }))

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
const canOpenGameTab = computed(() => limit.value === gameLimitMin.value)
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
  break_at_zero: boolean
  lift_at_zero: boolean
  lift_3x: boolean
}
const gameDefault: Game = {
  mode: 'normal',
  format: 'hosted',
  spectators_limit: 10,
  break_at_zero: true,
  lift_at_zero: true,
  lift_3x: true,
}
const initialGame: Game = (() => {
  try {
    const raw = localStorage.getItem('room:lastGame')
    if (!raw) return gameDefault
    const parsed = JSON.parse(raw) as Partial<Game> & { lift_2x_at_zero?: boolean }
    const liftAtZero = typeof parsed.lift_at_zero === 'boolean'
      ? parsed.lift_at_zero
      : (typeof parsed.lift_2x_at_zero === 'boolean' ? parsed.lift_2x_at_zero : undefined)
    const merged: Game = { ...gameDefault, ...parsed }
    if (typeof liftAtZero === 'boolean') merged.lift_at_zero = liftAtZero
    return merged
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
  set: v => { _title.value = sanitizeTitle(v, TITLE_MAX) }
})

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
    if (st === 403 && d === 'rooms_create_disabled')   void alertDialog('Создание комнат временно недоступно')
    else if (st === 409 && d === 'rooms_limit_global') void alertDialog('Достигнут общий лимит комнат')
    else if (st === 409 && d === 'rooms_limit_user')   void alertDialog('Достигнут личный лимит комнат')
    else if (st === 422 && d === 'title_empty')        void alertDialog('Название не должно быть пустым')
    else if (d && typeof d === 'object' && d.detail)   void alertDialog(String(d.detail))
    else if (typeof d === 'string' && d)               void alertDialog(d)
    else                                               void alertDialog('Ошибка создания комнаты')
  } finally { busy.value = false }
}

function sanitizeTitle(s: string, max = 32): string {
  return (s ?? "")
    .normalize("NFKC")
    .replace(/[\u0000-\u001F\u007F]/g, "")
    .replace(/[\u200B-\u200F\u202A-\u202E\u2066-\u2069]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, max)
}

watch([title, limit, privacy], saveBasic, { flush: 'post' })

watch(tab, (cur) => {
  lastTab.value = prevTab
  prevTab = cur
})

watch([limit, gameLimitMin], ([v, min]) => {
  if (v < 2) limit.value = 2
  if (v < min && tab.value === 'game') tab.value = 'room'
}, { flush: 'sync' })

watch(() => user.user, () => { if (!hadStoredTitle && !_title.value) _title.value = defaultTitle() }, { flush: 'post' })

watch(() => JSON.stringify(game.value), (json) => {
  try { localStorage.setItem('room:lastGame', json) } catch {}
})

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
      .tab-viewport {
        position: relative;
        height: 265px;
        border-top: 3px solid $lead;
        border-left: 3px solid $lead;
        border-right: 3px solid $lead;
        overflow-y: auto;
        overflow-x: hidden;
        scrollbar-width: none;
      }
      .tabs {
        display: flex;
        align-items: flex-end;
        width: 100%;
        height: 40px;
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
        padding: 10px;
        gap: 15px;
        .ui-input {
          display: block;
          position: relative;
          width: 100%;
          box-shadow: 3px 3px 5px rgba($black, 0.25);
          input {
            width: calc(100% - 22px);
            padding: 20px 10px 5px;
            border: 1px solid $lead;
            border-radius: 5px 5px 0 0;
            background-color: $graphite;
            color: $fg;
            font-size: 16px;
            font-family: Manrope-Medium;
            line-height: 1;
            outline: none;
            transition: border-color 0.25s ease-in-out, background-color 0.25s ease-in-out;
          }
          input::placeholder {
            color: transparent;
          }
          label {
            position: absolute;
            top: 50%;
            left: 12px;
            color: $fg;
            transform: translateY(-50%);
            pointer-events: none;
            transition: all 0.25s ease-in-out;
          }
          .underline {
            position: absolute;
            left: 0;
            right: 0;
            bottom: -3px;
            height: 3px;
            border-radius: 0 0 3px 3px;
            overflow: hidden;
            span {
              position: absolute;
              left: 0;
              bottom: 0;
              height: 3px;
              width: 0;
              background-color: $fg;
              transition: width 0.25s ease-in-out;
            }
          }
          .underline::before {
            content: "";
            position: absolute;
            inset: 0;
            background-color: $lead;
            transition: background-color 0.25s ease-in-out;
          }
          .meta {
            position: absolute;
            top: 5px;
            right: 10px;
            pointer-events: none;
            span {
              font-size: 12px;
              color: $grey;
            }
          }
          &.invalid input {
            border-color: rgba($red, 0.75);
          }
          &.invalid label {
            color: $red;
          }
          &.invalid .underline::before {
            background-color: rgba($red, 0.75);
          }
        }
        .ui-input:focus-within label,
        .ui-input input:not(:placeholder-shown) + label,
        .ui-input.filled label {
          top: 5px;
          left: 10px;
          transform: none;
          font-size: 12px;
          color: $grey;
        }
        .range {
          display: flex;
          flex-direction: column;
          gap: 5px;
          .range-label {
            display: flex;
            align-items: center;
            justify-content: space-between;
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
          .range-wrap {
            position: relative;
            height: 20px;
            box-shadow: 3px 3px 5px rgba($black, 0.25);
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
          .switch-label {
            height: 18px;
          }
          label {
            position: relative;
            width: 170px;
            height: 25px;
            box-shadow: 3px 3px 5px rgba($black, 0.25);
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
                width: 100%;
                color: $fg;
                font-size: 14px;
                text-align: center;
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

.slide-left-enter-active,
.slide-left-leave-active,
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.25s ease-out, opacity 0.25s ease-out;
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

@media (max-width: 1280px) {
  .overlay {
    .modal {
      .modal-div {
        .tab-viewport {
          height: 155px;
          scrollbar-width: auto;
        }
        .params {
          gap: 10px;
        }
      }
    }
  }
}
</style>
