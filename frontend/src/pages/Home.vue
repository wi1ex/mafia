<template>
  <Header><template #login><TelegramLogin /></template></Header>
  <div class="container">
    <div class="card">
      <h2 class="title">Комнаты</h2>
      <div v-if="roomsStore.rooms.length===0" class="muted">Пока пусто</div>
      <ul class="list">
        <li v-for="r in roomsStore.rooms" :key="r.id" class="item">
          <span class="item__title">#{{ r.id }} — {{ r.title }}</span>
          <span class="item__meta">({{ r.occupancy }}/{{ r.user_limit }})</span>
          <router-link v-if="auth.isAuthed" :to="`/room/${r.id}`" class="link">Открыть</router-link>
          <div v-else class="link disabled">Войдите, чтобы открыть</div>
        </li>
      </ul>
      <div v-if="auth.isAuthed" class="create">
        <h3 class="subtitle">Создать комнату</h3>
        <input v-model="title" class="input" placeholder="Название" />
        <input v-model.number="limit" class="input" type="number" min="2" max="32" placeholder="Лимит" />
        <button class="btn btn-primary" @click="onCreate">Создать</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import Header from '@/components/Header.vue'
import TelegramLogin from '@/components/TelegramLogin.vue'
import { useRouter } from 'vue-router'
import { useAuthStore, useRoomsStore } from '@/store'

const router = useRouter()
const auth = useAuthStore()
const roomsStore = useRoomsStore()

const title = ref('')
const limit = ref(8)

async function onCreate() {
  const r = await roomsStore.createRoom(title.value||'Комната', limit.value)
  await router.push(`/room/${r.id}`)
}

onMounted(async () => {
  await roomsStore.fetchRooms()
  roomsStore.startWS()
})

onBeforeUnmount(()=> {
  roomsStore.stopWS()
})
</script>

<style lang="scss" scoped>
.title {
  color: var(--bg);
  margin: 0 0 8px;
}
.subtitle {
  color: var(--bg);
  margin: 12px 0 6px;
  font-size: 16px;
}
.muted {
  color: var(--muted);
}
.list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
  color: var(--bg);
}
.item__title {
  font-weight: 500;
}
.item__meta {
  color: var(--muted);
}
.link {
  margin-left: auto;
  text-decoration: underline;
}
.link.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}
.create {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.input {
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid #334155;
  color: #e5e7eb;
  background: #0b0f14;
}
.btn {
  padding: 8px 12px;
  border-radius: 8px;
  border: 0;
  cursor: pointer;
  transition: transform 0.25s;
}
.btn-primary {
  background: var(--color-primary);
  color: #06110b;
}
</style>
