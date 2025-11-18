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
        <article class="item" v-for="it in notif.items" :key="it.id" :data-id="it.id">
          <div class="item-header">
            <span>{{ it.title }}</span>
            <time>{{ new Date(it.date).toLocaleString() }}</time>
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
  if (!list.value) return
  try { obs?.disconnect() } catch {}
  obs = new IntersectionObserver((entries) => {
    const ids: number[] = []
    for (const e of entries) {
      if (!e.isIntersecting || e.intersectionRatio < 0.5) continue
      const id = Number((e.target as HTMLElement).dataset.id)
      const it = notif.items.find(x => x.id === id)
      if (it && !it.read) ids.push(id)
    }
    if (ids.length) {
      void notif.markReadVisible(ids)
      flashJustRead(ids)
    }
  }, { root: list.value, threshold: 0.5 })
  queueMicrotask(() => list.value?.querySelectorAll('.item').forEach(el => obs?.observe(el)))
}

function markVisibleNow() {
  if (!list.value) return
  const box = list.value.getBoundingClientRect()
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
  if (ids.length) {
    void notif.markReadVisible(ids)
    flashJustRead(ids)
  }
}

function bindScroll() {
  if (!list.value || onScroll) return
  onScroll = () => markVisibleNow()
  list.value.addEventListener('scroll', onScroll, { passive: true })
}
function unbindScroll() {
  if (list.value && onScroll) list.value.removeEventListener('scroll', onScroll)
  onScroll = null
}
function bindResize() {
  if (ro || !list.value) return
  ro = new ResizeObserver(() => markVisibleNow())
  ro.observe(list.value)
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

function flashJustRead(ids: number[]) {
  if (!list.value) return
  ids.forEach((id) => {
    const el = list.value!.querySelector<HTMLElement>(`.item[data-id="${id}"]`)
    if (!el) return
    el.classList.remove('just-read', 'fade-just-read')
    void el.offsetWidth
    el.classList.add('just-read')
    window.setTimeout(() => {
      el.classList.add('fade-just-read')
      window.setTimeout(() => {
        el.classList.remove('just-read', 'fade-just-read')
      }, 1000)
    }, 2000)
  })
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
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  top: 50px;
  width: 400px;
  min-height: 200px;
  max-height: 400px;
  border-radius: 5px;
  background-color: $graphite;
  box-shadow: 3px 3px 5px rgba($black, 0.25);
  z-index: 100;
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 10px;
    border-radius: 5px;
    background-color: $lead;
    box-shadow: 0 3px 5px rgba($black, 0.25);
    span {
      font-size: 18px;
      font-weight: bold;
    }
    button {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 25px;
      height: 30px;
      border: none;
      background: none;
      cursor: pointer;
      img {
        width: 25px;
        height: 25px;
      }
    }
    .markall {
      padding: 0 10px;
      width: fit-content;
      height: 25px;
      border-radius: 5px;
      background-color: $fg;
      color: $bg;
      font-size: 12px;
      font-family: Manrope-Medium;
      line-height: 1;
    }
  }
  .list {
    display: flex;
    flex-direction: column;
    margin: 10px;
    padding: 0;
    gap: 10px;
    border-radius: 5px;
    overflow-y: auto;
    scrollbar-width: none;
    .item {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 10px;
      gap: 15px;
      border-radius: 5px;
      background-color: $lead;
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      .item-header {
        display: flex;
        justify-content: space-between;
        margin: 0;
        padding: 0;
        gap: 10px;
        width: 100%;
        span {
          margin: 0;
          font-size: 16px;
        }
        time {
          color: $grey;
          font-size: 12px;
        }
      }
      .text {
        margin: 0;
        width: 100%;
        color: $fg;
      }
    }
    .item.just-read {
      background-color: rgba($red, 0.25);
    }
    .item.just-read.fade-just-read {
      background-color: $lead;
      transition: background-color 1s ease-in-out;
    }
    .empty {
      color: $grey;
      text-align: center;
      margin: 55px;
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
  transform: translateY(-30px);
}
</style>
