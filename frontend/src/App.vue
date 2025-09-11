<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/store'

const auth = useAuthStore()

onMounted(() => {
  auth.init()
})
</script>
