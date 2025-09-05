<template>
  <HeaderBar>
    <template #login><TelegramLogin /></template>
  </HeaderBar>

  <div class="container">
    <div class="card">
      <h2 class="title">Комнаты</h2>

      <div v-if="rooms.rooms.length===0" class="muted">Пока пусто</div>
      <ul>
        <li v-for="r in rooms.rooms" :key="r.id" class="item">
          #{{ r.id }} — {{ r.title }} ({{ r.occupancy }}/{{ r.user_limit }})
          <router-link :to="`/room/${r.id}`" class="link">Открыть</router-link>
        </li>
      </ul>

      <div v-if="auth.isAuthed" class="create">
        <h3 class="title">Создать комнату</h3>
        <input v-model="title" placeholder="Название"/>
        <input v-model.number="limit" type="number" min="2" max="32" placeholder="Лимит"/>
        <button @click="onCreate">Создать</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import HeaderBar from '@/components/HeaderBar.vue'
import TelegramLogin from '@/components/TelegramLogin.vue'
import { useRouter } from 'vue-router'
import { useAuthStore, useRoomsStore } from '@/store'

const auth = useAuthStore()
const rooms = useRoomsStore()
const router = useRouter()
const title = ref(''); const limit = ref(8)

async function onCreate(){
  const room = await rooms.createRoom(title.value || 'Комната', limit.value)
  router.push(`/room/${room.id}`)
}

onMounted(async () => { await rooms.fetchRooms(); rooms.startSSE() })
onBeforeUnmount(() => rooms.stopSSE())
</script>

<style lang="scss" scoped>
.title{color:var(--fg)}
.muted{color:var(--muted)}
.item{margin:8px 0;color:var(--fg)}
.link{margin-left:8px}
.create{margin-top:16px;display:flex;align-items:center;gap:8px}
input{padding:8px;border-radius:8px;border:1px solid #334155;color:#e5e7eb;background:#0b0f14}
button{padding:8px 12px;border-radius:8px;background:var(--color-primary);border:none;cursor:pointer}
</style>
