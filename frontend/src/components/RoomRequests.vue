<template>
  <div v-if="open" class="apps-overlay" @click.self="$emit('update:open', false)">
    <div class="apps-panel">
      <header><span>Заявки</span><button @click="$emit('update:open', false)">✕</button></header>
      <ul v-if="apps.length" class="apps-list">
        <li v-for="u in apps" :key="u.id">
          <img v-minio-img="{ key: u.avatar_name ? `avatars/${u.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
          <span>{{ u.username || ('user' + u.id) }}</span>
          <button @click="approve(u.id)">Разрешить вход</button>
        </li>
      </ul>
      <p v-else>Нет заявок</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '@/services/axios'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'

const props = defineProps<{
  open: boolean
  roomId: number
}>()
defineEmits<{
  'update:open': [boolean]
}>()
const apps = ref<{id: number; username?: string; avatar_name?: string|null}[]>([])

async function load() {
  try {
    const { data } = await api.get(`/rooms/${props.roomId}/requests`)
    apps.value = data
  }
  catch { apps.value = [] }
}

async function approve(uid: number) {
  try {
    await api.post(`/rooms/${props.roomId}/requests/${uid}/approve`)
    apps.value = apps.value.filter(x=>x.id!==uid)
  }
  catch { alert('Ошибка') }
}

function onInvite(e: any) {
  const p = e?.detail
  if (Number(p?.room_id) !== props.roomId) return
  const u = p?.user
  if (!u?.id) return
  if (!apps.value.some(x => x.id === u.id)) apps.value.push({ id: u.id, username: u.username, avatar_name: u.avatar_name })
}

watch(() => props.open, on => {
  if (on) void load()
  else apps.value = []
})

onMounted(() => window.addEventListener('auth-room_invite', onInvite))

onBeforeUnmount(() => window.removeEventListener('auth-room_invite', onInvite))
</script>

<style scoped lang="scss">
.apps-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3000;
  .apps-panel {
    min-width: 300px;
    max-width: 420px;
    max-height: 60vh;
    overflow: auto;
    background: #1e1e1e;
    border-radius: 8px;
    padding: 10px;
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }
    .apps-list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
      li {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      img {
        width: 24px;
        height: 24px;
        border-radius: 50%;
      }
      button {
        margin-left: auto;
      }
    }
  }
}
</style>
