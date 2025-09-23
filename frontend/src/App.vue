<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

watch(auth.isAuthed, (ok) => {
  if (!ok && (route.meta as any)?.requiresAuth) router.replace('/')
})

onMounted(() => {
  await auth.init()
  if (auth.isAuthed) { try { await auth.fetchMe() } catch {} }
})
</script>
