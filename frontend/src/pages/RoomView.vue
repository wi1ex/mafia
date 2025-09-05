<template>
  <div class="container">
    <div class="card">
      <h2 class="title">Комната #{{ rid }}</h2>

      <div class="grid">
        <div v-for="m in room.members" :key="m.id" class="tile">
          <video :ref="setVideoRef(m.id)" autoplay playsinline></video>
          <div class="label">{{ m.name }}</div>
        </div>
      </div>

      <button class="leave" @click="onLeave">Покинуть комнату</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore, useRoomStore } from '@/store'

const route = useRoute(); const router = useRouter()
const rid = Number(route.params.id)
const auth = useAuthStore()
const room = useRoomStore()

function setVideoRef(pid:string){
  return (el: HTMLVideoElement | null) => { if (el) room.attachVideo(pid, el) }
}
async function onLeave(){ await room.leave(); router.replace('/') }

onMounted(async () => {
  if (!auth.isAuthed){ router.replace('/'); return }
  await room.connect(rid)
})
onBeforeUnmount(() => { room.leave() })
</script>

<style lang="scss" scoped>
.title{color:var(--fg)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px;margin-top:12px}
.tile{position:relative;border-radius:8px;overflow:hidden;background:#111827}
.label{position:absolute;left:8px;bottom:8px;background:rgba(0,0,0,.5);padding:2px 6px;border-radius:6px;color:#fff;font-size:12px}
.leave{margin-top:12px;padding:8px 12px;border-radius:8px;background:var(--color-danger);border:none;cursor:pointer}
</style>
