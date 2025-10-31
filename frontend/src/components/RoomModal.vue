<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="actions">
        <button @click="$emit('close')">
          <img :src="iconClose" alt="close" />
        </button>
      </div>
      <h3>Новая комната</h3>
      <input v-model.trim="title" placeholder="Название" maxlength="32" />
      <label>Лимит: {{ limit }}</label>
      <input type="range" min="2" max="12" step="1" v-model.number="limit" />
      <div class="privacy">
        <label><input type="radio" value="open" v-model="privacy" /> Открытая</label>
        <label><input type="radio" value="private" v-model="privacy" /> Закрытая</label>
      </div>
      <div class="actions">
        <button :disabled="busy || !ok" @click="create">Создать</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '@/services/axios'
import { useUserStore } from '@/store'

import iconClose from '@/assets/svg/close.svg'

const user = useUserStore()

const busy = ref(false)
const emit = defineEmits<{ (e: 'close'): void; (e: 'created', room: any): void }>()

const defaultTitle = () => {
  const name = (user.user?.username || '').trim()
  const id = user.user?.id
  const nick = name || (Number.isFinite(id) ? `user${id}` : 'user')
  return `Комната ${nick}`
}
const title = ref(defaultTitle())

const initLimit = (() => {
  const v = Number(localStorage.getItem('room:lastLimit'))
  return Number.isFinite(v) ? clamp(v,2,12) : 12
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
    const { data } = await api.post('/rooms', { title: title.value, user_limit: limit.value, privacy: privacy.value })
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

onMounted(() => {
  if (!title.value) title.value = defaultTitle()
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
  padding: 16px;
  border-radius: 8px;
  min-width: 320px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.privacy {
  display: flex;
  gap: 12px;
}

.overlay-enter-active,
.overlay-leave-active {
  transition: opacity 0.18s ease;
}
.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}
.modal {
  transform: translateY(8px);
  transition: transform 0.18s ease;
}
.overlay-enter-from .modal,
.overlay-leave-to .modal {
  transform: translateY(16px);
}
</style>
