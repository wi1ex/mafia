<template>
  <Header>
    <template #login>
      <TelegramLogin />
    </template>
  </Header>
  <section class="card">
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
      <input v-model.trim="title" class="input" placeholder="Название" />
      <input v-model.number="limit" class="input" type="number" min="2" max="20" placeholder="Лимит" />
      <button class="btn btn-primary" :disabled="creating || !valid" @click="onCreate">
        {{ creating ? 'Создаю…' : 'Создать' }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from 'vue'
import Header from '@/components/Header.vue'
import TelegramLogin from '@/components/TelegramLogin.vue'
import { useRouter } from 'vue-router'
import { useAuthStore, useRoomsStore } from '@/store'

const router = useRouter()
const auth = useAuthStore()
const roomsStore = useRoomsStore()

const title = ref('')
const limit = ref(12)
const creating = ref(false)
const valid = computed(() => (title.value || '').length > 0 && limit.value >= 2 && limit.value <= 20)

async function onCreate() {
  if (!valid.value || creating.value) return
  creating.value = true
  try {
    const r = await roomsStore.createRoom(title.value, limit.value)
    await router.push(`/room/${r.id}`)
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  roomsStore.startWS()
})

onBeforeUnmount(()=> {
  roomsStore.stopWS()
})
</script>

<style lang="scss" scoped>
.card {
  .title {
    color: var(--fg);
    margin: 0 0 8px;
  }
  .subtitle {
    color: var(--fg);
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
    color: var(--fg);
    &__title {
      font-weight: 500;
    }
    &__meta {
      color: var(--muted);
    }
  }
  .link {
    margin-left: auto;
    text-decoration: underline;
    color: var(--fg);
    &.disabled {
      opacity: 0.5;
      cursor: not-allowed;
      pointer-events: none;
    }
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
  }
  .btn-primary {
    background: var(--color-primary);
    color: #06110b;
  }
}
</style>
