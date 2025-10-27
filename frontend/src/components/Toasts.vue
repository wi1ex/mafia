<template>
  <div class="toasts">
    <div v-for="t in items" :key="t.key" class="toast">
      <span>{{ t.text }}</span>
      <button v-if="t.action" @click="run(t)"> {{ t.action.label }} </button>
      <button @click="close(t)">✕</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useNotifStore } from '@/store/modules/notif'

type T = { key: number; text: string; action?: {label: string; run: () => void}; noteId?: number }

const items = ref<T[]>([])
const n = useNotifStore()

async function close(t: T) {
  items.value = items.value.filter(x => x !== t)
  if (t.noteId) {
    try { await n.markReadVisible([t.noteId]) } catch {}
  }
}

function run(t:T) { try{ t.action?.run() } finally { close(t) } }

onMounted(() => {
  window.addEventListener('toast', (e: any)=>{
    const d = e.detail || {}
    const key = Date.now() + Math.random()
    const t: T = { key, text: d.text, noteId: d.id, action: d.action }
    items.value.push(t)
    setTimeout(() => {
      items.value = items.value.filter(x => x !== t)
    }, 5000)
  })
})
</script>

<style scoped>
.toasts {
  position: fixed;
  right: 10px;
  bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 2000;
}
.toast {
  display: flex;
  gap: 8px;
  align-items: center;
  background: #2a2a2a;
  color: #fff;
  border-radius: 6px;
  padding: 10px 12px;
}
.toast button {
  background: #444;
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
}
</style>
