<template>
  <Transition name="panel" @after-leave="onAfterLeave">
    <div v-show="open" class="panel" ref="root" @click.stop>
      <header>
        <span>Уведомления</span>
        <button v-if="notif.unread > 0" class="markall" @click="notif.markAll()">Отметить всё прочитанным</button>
        <button @click="$emit('update:open', false)" aria-label="Закрыть">
          <img :src="iconClose" alt="close" />
        </button>
      </header>

      <div class="list" ref="list">
        <article v-for="it in notif.items" :key="it.id" class="item" :data-id="it.id" :class="{ unread: !it.read }">
          <div class="head">
            <strong class="title">{{ it.title }}</strong>
            <time class="date">{{ new Date(it.date).toLocaleString() }}</time>
          </div>
          <div v-if="it.user" class="user">
            <img v-minio-img="{ key: it.user.avatar_name ? `avatars/${it.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
            <span class="user-name">{{ it.user.username || ('user' + it.user.id) }}</span>
          </div>
          <p v-if="it.text" class="text">{{ it.text }}</p>
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
import defaultAvatar from '@/assets/svg/defaultAvatar.svg'

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
  top: 50px;
  width: 360px;
  max-height: 420px;
  overflow: auto;
  scrollbar-width: none;
  background-color: $lead;
  border-radius: 5px;
  z-index: 100;
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px;
    border-radius: 5px;
    background-color: $graphite;
    span {
      font-size: 18px;
      font-weight: bold;
    }
    button {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 30px;
      height: 30px;
      border: none;
      background: none;
      cursor: pointer;
      img {
        width: 25px;
        height: 25px;
      }
    }
  }
  .list {
    margin: 10px;
    .item {
      padding: 10px 0;
      border-top: 1px solid $grey;
      .head {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 10px;
        .title {
          font-weight: 600;
        }
        .date  {
          color: #bbb;
          font-size: 12px;
        }
      }
      .user {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 5px 0;
        img {
          width: 28px;
          height: 28px;
          border-radius: 50%;
        }
        .user-name {
          font-weight: 500;
        }
      }
      .text {
        margin: 5px 0 0;
      }
    }
    .item.unread .title {
      font-weight: 700;
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
