<template>
  <div class="container">
    <div class="card">
      <h2 class="title">Комната #{{ rid }}</h2>

      <div class="grid">
        <div v-for="n in nodes" :key="n.key" class="tile" />
      </div>

      <button class="leave" @click="onLeave">Покинуть комнату</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRtcStore } from '@/store'

const route = useRoute()
const router = useRouter()
const rtc = useRtcStore()

const rid = Number(route.params.id)
const nodes = ref<{ key:string, el:HTMLElement }[]>([])

async function onLeave(){
  await rtc.leave()
  router.push('/')
}

function onAdd(e: Event){
  const ev = e as CustomEvent
  const el = ev.detail.el as HTMLMediaElement
  el.setAttribute('data-rtc-el','1')
  nodes.value.push({ key: crypto.randomUUID(), el })
  requestAnimationFrame(() => {
    const last = document.querySelector('.grid .tile:last-child') as HTMLElement | null
    if (last) last.appendChild(el)
  })
}

onMounted(async () => {
  document.addEventListener('rtc:add', onAdd as EventListener)
  await rtc.join(rid)
})

onBeforeUnmount(() => {
  document.removeEventListener('rtc:add', onAdd as EventListener)
  rtc.leave().catch(()=>{})
})
</script>

<style lang="scss" scoped>
.title{color:var(--fg)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px;margin-top:12px}
.tile{position:relative;border-radius:8px;overflow:hidden;background:#111827;min-height:160px}
.leave{margin-top:12px;padding:8px 12px;border-radius:8px;background:var(--color-danger);border:none;cursor:pointer}
video,audio{width:100%;height:100%}
</style>
