<template>
  <Transition name="panel" @after-leave="onAfterLeave">
    <div v-show="open" class="panel" ref="root" @click.stop>
      <header>
        <span class="title">Уведомления</span>
        <div class="buttons">
          <button v-if="notif.unread > 0" class="markall" @click="notif.markAll()">Прочитать все</button>
          <button class="close-btn" type="button" aria-label="Закрыть" @click="$emit('update:open', false)">
            <UiIcon class="close-icon" :icon="iconClose" />
          </button>
        </div>
      </header>

      <div class="list" ref="list">
        <article class="item" v-for="it in notif.items" :key="it.id" :data-id="it.id">
          <div class="item-header">
            <div class="item-title">
              <UiIcon class="bell-icon" :icon="iconNotifBell" />
              <span class="bell-title">{{ it.title }}</span>
            </div>
            <time class="bell-time">{{ formatNotifTimestamp(it.date) }}</time>
          </div>
          <div v-if="it.text" class="text">
            <template v-for="(block, blockIndex) in parseNotificationText(it.text)" :key="`${it.id}-${block.type}-${blockIndex}`">
              <p v-if="block.type === 'paragraph'" class="notification-text-paragraph">
                <template v-for="(line, lineIndex) in block.lines" :key="`${it.id}-${blockIndex}-${lineIndex}`">
                  {{ line }}<br v-if="lineIndex < block.lines.length - 1" />
                </template>
              </p>
              <ul v-else class="notification-text-list">
                <li v-for="(item, itemIndex) in block.items" :key="`${it.id}-${blockIndex}-${itemIndex}`">
                  {{ item }}
                </li>
              </ul>
            </template>
          </div>
        </article>
        <div v-if="notif.items.length === 0" class="empty">
          <img :src="iconNoNotifs" alt="nonotifs" />
          <span>Уведомлений пока нет...</span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { useNotifStore } from '@/store'
import { formatLocalDateTime } from '@/services/datetime'
import { parseNotificationText } from '@/services/notificationText'

import UiIcon from '@/components/UiIcon.vue'

import iconClose from '@/assets/svg/iconClose.svg'
import iconNotifBell from '@/assets/svg/iconNotifBell.svg'
import iconNoNotifs from '@/assets/svg/iconNoNotifs.svg'

const NOTIF_TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  hour: '2-digit',
  minute: '2-digit',
}

const NOTIF_DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}
const LOAD_MORE_SCROLL_OFFSET = 24
const VISIBLE_NOTIF_RATIO = 0.5
const VISIBLE_NOTIF_MAX_PX = 32

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

function isEnoughOfItemVisible(itemHeight: number, visibleHeight: number): boolean {
  if (visibleHeight <= 0) return false
  const requiredVisibleHeight = Math.min(itemHeight * VISIBLE_NOTIF_RATIO, VISIBLE_NOTIF_MAX_PX)
  return visibleHeight >= requiredVisibleHeight
}

function attachObserver() {
  if (!list.value) return
  try { obs?.disconnect() } catch {}
  obs = new IntersectionObserver((entries) => {
    const ids: number[] = []
    for (const e of entries) {
      if (!e.isIntersecting || !isEnoughOfItemVisible(e.boundingClientRect.height, e.intersectionRect.height)) continue
      const id = Number((e.target as HTMLElement).dataset.id)
      const it = notif.items.find(x => x.id === id)
      if (it && !it.read) ids.push(id)
    }
    if (ids.length) {
      void notif.markReadVisible(ids)
      flashJustRead(ids)
    }
  }, { root: list.value, threshold: 0 })
  queueMicrotask(() => list.value?.querySelectorAll('.item').forEach(el => obs?.observe(el)))
}

function markVisibleNow() {
  if (!list.value) return
  const box = list.value.getBoundingClientRect()
  const ids: number[] = []
  list.value.querySelectorAll<HTMLElement>('.item').forEach(el => {
    const r = el.getBoundingClientRect()
    const visible = Math.max(0, Math.min(box.bottom, r.bottom) - Math.max(box.top, r.top))
    if (isEnoughOfItemVisible(r.height, visible)) {
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

function maybeLoadMore() {
  if (!list.value || notif.loadingInitial || notif.loadingMore || !notif.hasMore) return
  const remaining = list.value.scrollHeight - list.value.scrollTop - list.value.clientHeight
  if (remaining <= LOAD_MORE_SCROLL_OFFSET) void onLoadMore()
}

function bindScroll() {
  if (!list.value || onScroll) return
  onScroll = () => {
    markVisibleNow()
    maybeLoadMore()
  }
  list.value.addEventListener('scroll', onScroll, { passive: true })
}
function unbindScroll() {
  if (list.value && onScroll) list.value.removeEventListener('scroll', onScroll)
  onScroll = null
}
function bindResize() {
  if (ro || !list.value) return
  ro = new ResizeObserver(() => {
    markVisibleNow()
    maybeLoadMore()
  })
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

function isLocalToday(dt: Date): boolean {
  const now = new Date()
  return (
    dt.getFullYear() === now.getFullYear()
    && dt.getMonth() === now.getMonth()
    && dt.getDate() === now.getDate()
  )
}

function formatNotifTimestamp(value?: string | number | Date | null): string {
  if (!value) return '-'
  const dt = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(dt.getTime())) return '-'
  return formatLocalDateTime(dt, isLocalToday(dt) ? NOTIF_TIME_OPTIONS : NOTIF_DATE_OPTIONS)
}

async function onLoadMore() {
  if (notif.loadingInitial || notif.loadingMore || !notif.hasMore) return
  await notif.loadMore()
}

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
  maybeLoadMore()
})

watch(() => props.open, async v => {
  if (v) {
    await nextTick()
    bindDoc()
    if (list.value) list.value.scrollTop = 0
    attachObserver()
    markVisibleNow()
    bindScroll()
    bindResize()
    maybeLoadMore()
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
  top: 72px;
  padding: 16px;
  width: 448px;
  min-height: 408px;
  max-height: 608px;
  border-radius: 24px;
  background-color: $neutral-100;
  box-shadow: 0 0 16px 0 rgba($neutral-black, 0.16);
  z-index: 100;
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 8px 16px;
    .title {
      color: $neutral-black;
      font-family: Hauora-Bold;
      font-size: 18px;
      line-height: 20px;
      letter-spacing: -0.36px;
    }
    .buttons {
      display: flex;
      gap: 24px;
      .markall {
        padding: 0;
        border: none;
        background: none;
        color: $neutral-700;
        font-family: Hauora-Regular;
        font-size: 14px;
        line-height: 14px;
        letter-spacing: -0.28px;
        text-decoration-line: underline;
        text-decoration-color: $neutral-700;
        text-decoration-thickness: 1px;
        text-underline-offset: 3px;
        cursor: pointer;
        transition: color 0.25s ease-in-out, text-decoration-color 0.25s ease-in-out;
        &:hover,
        &:focus-visible,
        &:active {
          color: $neutral-black;
          text-decoration-color: $neutral-black;
        }
      }
      .close-btn {
        padding: 0;
        width: 24px;
        height: 24px;
        border: none;
        background: none;
        cursor: pointer;
        .close-icon {
          --ui-icon-width: 24px;
          --ui-icon-height: 24px;
          --ui-icon-color: #{$neutral-black};
        }
        &:hover,
        &:focus-visible,
        &:active {
          .close-icon {
            --ui-icon-color: #{$green-500};
          }
        }
      }
    }
  }
  .list {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    scrollbar-width: none;
    .item {
      display: flex;
      flex-direction: column;
      padding: 16px 8px;
      gap: 8px;
      .item-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 16px;
        width: 100%;
        .item-title {
          display: flex;
          gap: 8px;
          .bell-icon {
            --ui-icon-width: 20px;
            --ui-icon-height: 20px;
            --ui-icon-color: #{$neutral-400};
          }
          .bell-title {
            max-width: 280px;
            color: $neutral-black;
            font-family: Hauora-Bold;
            font-size: 16px;
            line-height: 18px;
            letter-spacing: -0.32px;
          }
        }
        .bell-time {
          color: $neutral-500;
          font-family: Hauora-Regular;
          font-size: 14px;
          line-height: 14px;
          letter-spacing: -0.28px;
        }
      }
      .text {
        margin-left: 28px;
        width: calc(100% - 28px);
        color: $neutral-900;
        font-family: Hauora-Regular;
        font-size: 16px;
        line-height: 22px;
        letter-spacing: -0.32px;
        overflow-wrap: anywhere;
        word-break: break-word;
        .notification-text-paragraph,
        .notification-text-list {
          margin: 0;
        }
        .notification-text-paragraph + .notification-text-paragraph,
        .notification-text-paragraph + .notification-text-list,
        .notification-text-list + .notification-text-paragraph,
        .notification-text-list + .notification-text-list {
          margin-top: 8px;
        }
        .notification-text-list {
          padding-left: 20px;
          li + li {
            margin-top: 4px;
          }
        }
      }
    }
    .item.just-read .item-header .item-title .bell-icon {
      --ui-icon-color: #{$red-600};
    }

    .item.just-read.fade-just-read .item-header .item-title .bell-icon {
      --ui-icon-color: #{$neutral-400};
      transition: background-color 1s ease-in-out;
    }
    .empty {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 10px;
      width: 100%;
      height: 100%;
      img {
        width: 95px;
        height: 100px;
      }
      span {
        color: $neutral-500;
        font-family: Hauora-Regular;
        font-size: 14px;
        line-height: 14px;
        letter-spacing: -0.28px;
      }
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
