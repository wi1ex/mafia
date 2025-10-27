<template>
  <div class="bell" ref="root">
    <button @click="toggle" aria-label="Уведомления">
      🔔 <span v-if="n.unread>0" class="cnt">{{ n.unread }}</span>
    </button>
    <div v-if="open" class="panel" ref="panel">
      <div class="head">
        <span>Уведомления</span>
        <button @click="n.markAll()">Отметить всё прочитанным</button>
      </div>
      <div class="list" ref="list">
        <article v-for="it in n.items" :key="it.id" class="item" :data-id="it.id" :class="{ unread: !it.read }">
          <p>{{ it.text }}</p>
          <time>{{ new Date(it.created_at).toLocaleString() }}</time>
        </article>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useNotifStore } from '@/store/modules/notif'

const n = useNotifStore()

let obs: IntersectionObserver | null = null
let onScrollBound: ((e: Event)=>void) | null = null
const open = ref(false)
const list = ref<HTMLElement|null>(null)
const panel = ref<HTMLElement|null>(null)
const root = ref<HTMLElement|null>(null)

function toggle() { open.value = !open.value }

function attachObserver() {
  if (!list.value) return
  if (obs) { try { obs.disconnect() } catch {} }
  obs = new IntersectionObserver((entries) => {
    const ids: number[] = []
    entries.forEach(e => {
      if (!e.isIntersecting) return
      if (e.intersectionRatio < 0.5) return
      const id = Number((e.target as HTMLElement).dataset.id)
      const it = n.items.find(x => x.id === id)
      if (it && !it.read) ids.push(id)
    })
    if (ids.length) void n.markReadVisible(ids)
  }, { root: list.value, threshold: 0.5 })
  queueMicrotask(() => {
    list.value?.querySelectorAll('.item').forEach(el => obs?.observe(el))
  })
}
function markVisibleNow() {
  if (!list.value) return
  const rootBox = list.value.getBoundingClientRect()
  const ids: number[] = []
  list.value.querySelectorAll<HTMLElement>('.item').forEach(el => {
    const r = el.getBoundingClientRect()
    const visible = Math.max(0, Math.min(rootBox.bottom, r.bottom) - Math.max(rootBox.top, r.top))
    const ratio = visible / Math.max(1, r.height)
    if (ratio >= 0.5) {
      const id = Number(el.dataset.id)
      const it = n.items.find(x => x.id === id)
      if (it && !it.read) ids.push(id)
    }
  })
  if (ids.length) void n.markReadVisible(ids)
}
function bindScroll() {
  if (!list.value) return
  if (onScrollBound) return
  onScrollBound = () => markVisibleNow()
  list.value.addEventListener('scroll', onScrollBound, { passive: true })
}
function unbindScroll() {
  if (!list.value || !onScrollBound) return
  try { list.value.removeEventListener('scroll', onScrollBound) } catch {}
  onScrollBound = null
}
function onDocClick(e: Event) {
  const t = e.target as Node | null
  if (!t) return
  if (!root.value?.contains(t)) open.value = false
}

watch(open, (v) => {
  try { document.removeEventListener('pointerdown', onDocClick, { capture: true } as any) } catch {}
  if (v) document.addEventListener('pointerdown', onDocClick, { capture: true })
})

watch(() => n.items.length, () => {
  if (!open.value) return
  attachObserver()
  markVisibleNow()
})

watch(open, (v) => {
  if (v) {
    attachObserver()
    markVisibleNow()
    bindScroll()
  } else {
    try { obs?.disconnect() } catch {}
    unbindScroll()
  }
})

onMounted(async () => {
  n.ensureWS()
  await n.fetchAll()
  if (open.value) {
    attachObserver()
    markVisibleNow()
    bindScroll()
  }
})

onBeforeUnmount(() => {
  try { obs?.disconnect() } catch {}
  unbindScroll()
})
</script>

<style scoped>
.bell {
  position: relative;
}
.cnt {
  background: #e33;
  color: #fff;
  border-radius: 10px;
  padding: 0 6px;
  margin-left: 4px;
  font-size: 12px;
}
.panel {
  position: absolute;
  right: 0;
  top: 44px;
  width: 360px;
  max-height: 420px;
  overflow: auto;
  background: #1e1e1e;
  border-radius: 8px;
  padding: 8px;
  z-index: 100;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.item {
  padding: 8px;
  border-bottom: 1px solid #333;
}
.item.unread p {
  font-weight: 600;
}
</style>
