<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal">
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
        <button @click="$emit('close')">Отмена</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { api } from '@/services/axios'

const emit = defineEmits<{ (e:'close'): void; (e:'created', room:any): void }>()
const title = ref('')
const limit = ref(12)
const privacy = ref<'open'|'private'>('open')
const busy = ref(false)

const ok = computed(() => title.value.length > 0 && limit.value >= 2 && limit.value <= 12)

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
    else if (st === 422 && (d === 'title_empty'))      alert('Название не должно быть пустым')
    else if (typeof d === 'string' && d)               alert(d)
    else if (d && typeof d === 'object' && d.detail)   alert(String(d.detail))
    else                                               alert('Ошибка создания комнаты')
  } finally { busy.value = false }
}
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal {
  background: #1e1e1e;
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
</style>
