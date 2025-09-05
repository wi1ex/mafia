<template>
  <header class="bar">
    <div class="brand">Mafia</div>
    <div v-if="!auth.isAuthed"><slot name="login"></slot></div>
    <div v-else class="user">
      <img v-if="auth.avatarUrl" :src="auth.avatarUrl" alt="" class="avatar" />
      <div v-else class="avatar placeholder"></div>
      <span class="nick">{{ auth.displayName }}</span>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/store'
const auth = useAuthStore()
</script>

<style lang="scss" scoped>
.bar{display:flex;justify-content:space-between;align-items:center;padding:12px 16px}
.brand{color:var(--fg);font-weight:600}
.user{display:flex;align-items:center;gap:8px}
.avatar{width:32px;height:32px;border-radius:50%}
.placeholder{background:#334155}
.nick{color:var(--fg)}
</style>
