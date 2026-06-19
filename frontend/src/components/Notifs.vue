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
            <time class="bell-time">{{ formatLocalDateTime(it.date, NOTIF_DATE_OPTIONS) }}</time>
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
        <button v-if="notif.hasMore" class="load-more" type="button" :disabled="notif.loadingInitial || notif.loadingMore" @click="onLoadMore">
          {{ notif.loadingMore ? 'Загружаем...' : 'Загрузить ещё' }}
        </button>
        <p v-if="notif.items.length === 0" class="empty">Нет уведомлений</p>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { useNotifStore } from '@/store'
import { formatLocalDateTime } from '@/services/datetime'
import { parseNotificationText } from '@/services/notificationText'

import iconClose from '@/assets/svg/iconClose.svg'
import UiIcon from '@/components/UiIcon.vue'
import iconNotifBell from '@/assets/svg/iconNotifBell.svg'

const NOTIF_DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
}

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
    padding: 10px;
    gap: 10px;
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
      box-shadow: 0 3px 5px rgba($black, 0.25);
      .item-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        width: 100%;
        .item-title {
          display: flex;
          .bell-icon {
            --ui-icon-width: 20px;
            --ui-icon-height: 20px;
            --ui-icon-color: #{$neutral-400};
          }
          .bell-title {
            margin: 0;
            max-width: 240px;
            font-size: 18px;
            font-weight: bold;
          }
        }
        .bell-time {
          margin-top: 3px;
          color: $grey;
          font-size: 12px;
        }
      }
      .text {
        margin: 0;
        width: 100%;
        color: $fg;
        line-height: 1.35;
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
    .item.just-read .bell-icon {
      --ui-icon-color: #{$red-600};
    }

    .item.just-read.fade-just-read .bell-icon {
      --ui-icon-color: #{$neutral-400};
    }
    .load-more {
      margin-top: 5px;
      padding: 10px;
      width: 100%;
      border: none;
      border-radius: 5px;
      background-color: $lead;
      color: $fg;
      font-size: 14px;
      font-family: Manrope-Medium;
      line-height: 1;
      cursor: pointer;
      transition: background-color 0.25s ease-in-out, opacity 0.25s ease-in-out;
      &:hover:enabled {
        background-color: $dark;
      }
      &:disabled {
        opacity: 0.5;
        cursor: default;
      }
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
