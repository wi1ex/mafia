<template>
  <div class="overlay" @pointerdown.self="armed = true" @pointerup.self="armed && $emit('close')"
       @pointerleave.self="armed = false" @pointercancel.self="armed = false">
    <div class="modal">
      <div class="actions">
        <button @click="$emit('close')">
          <img :src="iconClose" alt="close" />
        </button>
      </div>
      <h3>Новая комната</h3>

      <div class="tabs">
        <button :class="{active: tab==='room'}" @click="tab='room'">Комната</button>
        <button :class="{active: tab==='game'}" @click="tab='game'">Игра</button>
      </div>

      <template v-if="tab==='room'">
        <input v-model.trim="title" placeholder="Название" maxlength="32" />
        <label>Лимит: {{ limit }}</label>
        <input type="range" min="2" max="12" step="1" v-model.number="limit" />
        <div class="privacy">
          <label><input type="radio" value="open" v-model="privacy" /> Открытая</label>
          <label><input type="radio" value="private" v-model="privacy" /> Закрытая</label>
        </div>
      </template>

      <template v-else>
        <div class="field">
          <label>Режим</label>
          <div class="row">
            <label><input type="radio" value="normal" v-model="game.mode" /> Обычный</label>
            <label><input type="radio" value="rating" v-model="game.mode" disabled /> Рейтинг (скоро)</label>
          </div>
        </div>
        <div class="field">
          <label>Формат</label>
          <div class="row">
            <label><input type="radio" value="hosted" v-model="game.format" /> С ведущим</label>
            <label><input type="radio" value="nohost" v-model="game.format" disabled /> Без ведущего (скоро)</label>
          </div>
        </div>
        <div class="field">
          <label>Лимит зрителей: {{ game.spectators_limit }}</label>
          <input type="range" min="0" max="10" step="1" v-model.number="game.spectators_limit" disabled />
        </div>
        <div class="field">
          <label>Доп. параметры</label>
          <div class="col">
            <label><input type="checkbox" v-model="game.vote_at_zero" disabled /> Голосование в нуле</label>
            <label><input type="checkbox" v-model="game.vote_three" disabled /> Голосование за подъём троих</label>
            <label><input type="checkbox" v-model="game.speech30_at_3_fouls" disabled /> Речь 30с при трёх фолах</label>
            <label><input type="checkbox" v-model="game.extra30_at_2_fouls" disabled /> +30с к речи за 2 фола</label>
          </div>
        </div>
      </template>
      
      <div class="actions">
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

const defaultTitle = () => {
  const name = (user.user?.username || '').trim()
  const id = user.user?.id
  const nick = name || (Number.isFinite(id) ? `user${id}` : 'user')
  return `Комната ${nick}`
}
const title = ref(defaultTitle())

const initLimit = (() => {
  const v = Number(localStorage.getItem('room:lastLimit'))
  return Number.isFinite(v) ? clamp(v,2,12) : 11
})()
const limit = ref<number>(initLimit)

const initPrivacy = (() => {
  const v = (localStorage.getItem('room:lastPrivacy') || '').trim()
  return v === 'private' ? 'private' : 'open'
})()
const privacy = ref<'open'|'private'>(initPrivacy)

const ok = computed(() => title.value.length > 0 && limit.value >= 2 && limit.value <= 12)

function clamp(n: number, min: number, max: number) { return Math.max(min, Math.min(max, n)) }

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

watch(limit, v => { try { localStorage.setItem('room:lastLimit', String(clamp(v,2,12))) } catch {} })

watch(privacy, v => { try { localStorage.setItem('room:lastPrivacy', v) } catch {} })

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
  inset: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal {
  background-color: #1e1e1e;
  padding: 15px;
  border-radius: 5px;
  min-width: 320px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
.privacy {
  display: flex;
  gap: 10px;
}

.overlay-enter-active,
.overlay-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}
.modal {
  transform: translateY(10px);
  transition: transform 0.25s ease-in-out;
}
.overlay-enter-from .modal,
.overlay-leave-to .modal {
  transform: translateY(15px);
}
.tabs {
  display: flex;
  gap: 10px;
  margin: 5px 0 10px;
  button {
    padding: 5px 10px;
    border: none;
    border-radius: 5px;
    background-color: #2a2a2a;
    color: #ddd;
    cursor: pointer;
    &.active {
      background-color: #3a3a3a;
    }
  }
}
.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.col {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
</style>
