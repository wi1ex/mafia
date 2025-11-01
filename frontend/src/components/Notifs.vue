<template>
  <Transition name="panel" @after-leave="onAfterLeave">
    <div v-show="open" class="panel" ref="root" @click.stop>
      <div class="head">
        <span>Уведомления</span>
        <div class="actions">
          <button v-if="notif.unread > 0" class="markall" @click="notif.markAll()">Отметить всё прочитанным</button>
          <button class="close" @click="$emit('update:open', false)" aria-label="Закрыть">
            <img :src="iconClose" alt="close" />
          </button>
        </div>
      </div>

      <div class="list" ref="list">
        <article v-for="it in notif.items" :key="it.id" class="item" :data-id="it.id" :class="{ unread: !it.read }">
          <p>{{ it.text }}</p>
          <time>{{ new Date(it.created_at).toLocaleString() }}</time>
        </article>
        <p v-if="notif.items.length === 0" class="empty">Нет уведомлений</p>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { useNotifStore } from '@/store'

import iconClose from '@/assets/svg/close.svg'

const props = defineProps<{
  open: boolean
  anchor?: HTMLElement | null
}>()
const emit = defineEmits<{
  'update:open': [boolean]
}>()

const notif = useNotifStore()

const root = ref<HTMLElement | null>(null)
const list = ref<HTMLElement | null>(null)
let obs: IntersectionObserver | null = null
let ro: ResizeObserver | null = null
let onScroll: ((e: Event) => void) | null = null
let onDocDown: ((e: Event) => void) | null = null

function attachObserver() {
  if (!list.value || !root.value) return
  try { obs?.disconnect() } catch {}
  obs = new IntersectionObserver((entries) => {
    const ids: number[] = []
    for (const e of entries) {
      if (!e.isIntersecting || e.intersectionRatio < 0.5) continue
      const id = Number((e.target as HTMLElement).dataset.id)
      const it = notif.items.find(x => x.id === id)
      if (it && !it.read) ids.push(id)
    }
    if (ids.length) void notif.markReadVisible(ids)
  }, { root: root.value, threshold: 0.5 })
  queueMicrotask(() => list.value?.querySelectorAll('.item').forEach(el => obs?.observe(el)))
}

function markVisibleNow() {
  if (!list.value || !root.value) return
  const box = root.value.getBoundingClientRect()
  const ids: number[] = []
  list.value.querySelectorAll<HTMLElement>('.item').forEach(el => {
    const r = el.getBoundingClientRect()
    const visible = Math.max(0, Math.min(box.bottom, r.bottom) - Math.max(box.top, r.top))
    const ratio = visible / Math.max(1, r.height)
    if (ratio >= 0.5) {
      const id = Number(el.dataset.id)
      const it = notif.items.find(x => x.id === id)
      if (it && !it.read) ids.push(id)
    }
  })
  if (ids.length) void notif.markReadVisible(ids)
}

function bindScroll() {
  if (!root.value || onScroll) return
  onScroll = () => markVisibleNow()
  root.value.addEventListener('scroll', onScroll, { passive: true })
}
function unbindScroll() {
  if (root.value && onScroll) root.value.removeEventListener('scroll', onScroll)
  onScroll = null
}
function bindResize() {
  if (ro || !root.value) return
  ro = new ResizeObserver(() => markVisibleNow())
  ro.observe(root.value)
}
function unbindResize() {
  try { ro?.disconnect() } catch {}
  ro = null
}

function bindDoc() {
  if (onDocDown) return
  onDocDown = (e: Event) => {
    const t = e.target as Node | null
    if (!t) return
    if (root.value?.contains(t)) return
    if (props.anchor && props.anchor.contains(t)) return
    emitClose()
  }
  document.addEventListener('pointerdown', onDocDown, true)
}
function unbindDoc() {
  if (onDocDown) document.removeEventListener('pointerdown', onDocDown, true)
  onDocDown = null
}

function emitClose() { emit('update:open', false) }

function onAfterLeave() {
  try { obs?.disconnect() } catch {}
  unbindScroll()
  unbindResize()
  unbindDoc()
}

watch(() => notif.items.length, async () => {
  if (!props.open) return
  await nextTick()
  attachObserver()
  markVisibleNow()
})

watch(() => props.open, async v => {
  if (v) {
    await nextTick()
    bindDoc()
    attachObserver()
    markVisibleNow()
    bindScroll()
    bindResize()
  } else {
    try { obs?.disconnect() } catch {}
    unbindScroll()
    unbindResize()
    unbindDoc()
  }
})

onBeforeUnmount(() => {
  try { obs?.disconnect() } catch {}
  unbindScroll()
  unbindResize()
  unbindDoc()
})
</script>

<style scoped lang="scss">
.panel {
  position: absolute;
  right: 0;
  top: 44px;
  width: 360px;
  max-height: 420px;
  overflow: auto;
  background-color: #1e1e1e;
  border-radius: 10px;
  padding: 10px;
  z-index: 100;
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 5px;
    span {
      color: $fg;
      font-weight: bold;
    }
    .actions {
      display: inline-flex;
      gap: 5px;
      align-items: center;
      .markall {
        background: none;
        border: none;
        color: $fg;
        cursor: pointer;
        font-size: 12px;
      }
      .close {
        background: none;
        border: none;
        width: 24px;
        height: 24px;
        padding: 0;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        img {
          width: 18px;
          height: 18px;
        }
      }
    }
  }
  .list {
    .item {
      padding: 10px;
      border-bottom: 1px solid #333;
    }
    .item.unread p {
      font-weight: 600;
    }
    .empty {
      color: $grey;
      text-align: center;
      margin: 0;
      padding: 15px 0;
    }
  }
}

.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}
.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>
