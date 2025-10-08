<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store'
import { useUserStore } from '@/store'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const user = useUserStore()

watch(auth.isAuthed, (ok) => {
  if (!ok && (route.meta as any)?.requiresAuth) router.replace('/')
})

onMounted(async () => {
  await auth.init()
  if (auth.isAuthed) { try { await user.fetchMe() } catch {} }
})
</script>
