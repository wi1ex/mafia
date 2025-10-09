<template>
  <Header v-if="!isRoom" />
  <router-view />
</template>

<script setup lang="ts">
import { onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store'
import { useUserStore } from '@/store'
import Header from '@/components/Header.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const user = useUserStore()

const isRoom = computed(() => route.name === 'room')

watch(auth.isAuthed, (ok) => {
  if (!ok && (route.meta as any)?.requiresAuth) router.replace('/')
})

onMounted(async () => {
  await auth.init()
  if (auth.isAuthed) { try { await user.fetchMe() } catch {} }
})
</script>
