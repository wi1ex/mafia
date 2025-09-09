<template>
  <header class="bar">
    <div class="brand">Mafia</div>
    <div v-if="!auth.isAuthed"><slot name="login" /></div>
    <div v-else class="user">
      <img v-if="auth.avatarUrl" :src="auth.avatarUrl" alt="" class="avatar" />
      <div v-else class="avatar placeholder" />
      <span class="nick">{{ auth.displayName }}</span>
      <button class="btn btn-ghost" @click="auth.logout()">Выйти</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/store'

const auth = useAuthStore()
</script>

<style lang="scss" scoped>
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
}
.brand {
  color: var(--bg);
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
  color: var(--bg);
}
.btn {
  padding: 6px 10px;
  border: 0;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity 0.25s;
}
.btn-ghost {
  background: #334155;
  color: #7795d2;
}
</style>
