<template>
  <header class="bar" role="banner">
    <div class="brand" aria-label="Mafia">Mafia</div>
    <div v-if="!auth.isAuthed"><slot name="login" /></div>
    <div v-else class="user">
      <img v-if="auth.avatarUrl" :src="auth.avatarUrl" alt="Аватар" class="avatar" loading="lazy" referrerpolicy="no-referrer" />
      <div v-else class="avatar placeholder" aria-hidden="true" />
      <span class="nick" aria-live="polite">{{ auth.displayName }}</span>
      <button class="btn btn-ghost" type="button" @click="logout">Выйти</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/store'

const auth = useAuthStore()

async function logout() {
  try {
    await auth.logout()
  } catch {}
}
</script>

<style lang="scss" scoped>
.bar { display:flex; justify-content:space-between; align-items:center; padding:12px 16px; }
.brand { color: var(--bg); font-weight:700; letter-spacing:.5px; }
.user { display:flex; align-items:center; gap:10px; }
.avatar { width:32px; height:32px; border-radius:50%; object-fit:cover; background:#0b0f14; }
.placeholder { background:#334155; }
.nick { color: var(--bg); }
.btn { padding:6px 10px; border:0; border-radius:8px; cursor:pointer; transition:opacity .2s ease; }
.btn-ghost { background:#334155; color:#7795d2; }
</style>
