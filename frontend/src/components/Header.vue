<template>
  <header class="bar">
    <div class="brand">Mafia</div>
    <div v-if="!isAuthed"><slot name="login" /></div>
    <div v-else class="user">
      <img v-if="avatarUrl" :src="avatarUrl" alt="" class="avatar" />
      <div v-else class="avatar placeholder" />
      <span class="nick">{{ displayName }}</span>
      <button class="btn btn-ghost" @click="auth.logout()">Выйти</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/store'

const auth = useAuthStore()

const isAuthed = computed(() => !!auth.accessToken)
const displayName = computed(() => auth.me?.username || 'User')
const avatarUrl = computed(() => auth.me?.photo_url || null)
</script>

<style lang="scss" scoped>
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
}
.brand {
  color: var(--fg);
  font-weight: 700;
  letter-spacing: 0.5px;
}
.user {
  display: flex;
  align-items: center;
  gap: 10px;
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
}
.placeholder {
  background: #334155;
}
.nick {
  color: var(--fg);
}
.btn {
  padding: 6px 10px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-ghost {
  background: #334155;
  color: #e5e7eb;
}
</style>
