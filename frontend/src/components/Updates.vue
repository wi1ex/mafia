<template>
  <Transition name="panel" @after-leave="onAfterLeave">
    <div v-show="open" class="panel" ref="root" @click.stop>
      <header>
        <span>Обновления</span>
        <button @click="$emit('update:open', false)" aria-label="Закрыть">
          <img :src="iconClose" alt="close" />
        </button>
      </header>
      <div class="list">
        <article class="item" v-for="it in updates.items" :key="it.id">
          <div class="item-header">
            <span>v{{ it.version }}</span>
            <time>{{ formatLocalDateTime(it.date, DATE_ONLY) }}</time>
          </div>
          <p v-if="it.description" class="text">{{ it.description }}</p>
        </article>
        <p v-if="updates.items.length === 0" class="empty">Нет обновлений</p>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { useUpdatesStore } from '@/store'
import { formatLocalDateTime } from '@/services/datetime'

import iconClose from '@/assets/svg/close.svg'

const DATE_ONLY: Intl.DateTimeFormatOptions = { year: 'numeric', month: '2-digit', day: '2-digit' }

const props = defineProps<{
  open: boolean
  anchor?: HTMLElement | null
}>()
const emit = defineEmits<{
  'update:open': [boolean]
}>()

const updates = useUpdatesStore()
const root = ref<HTMLElement | null>(null)
let onDocDown: ((e: Event) => void) | null = null

function bindDoc() {
  if (onDocDown) return
  onDocDown = (e: Event) => {
    const t = e.target as Node | null
    if (!t) return
    if (root.value?.contains(t)) return
    if (props.anchor && props.anchor.contains(t)) return
    emit('update:open', false)
  }
  document.addEventListener('pointerdown', onDocDown, true)
}
function unbindDoc() {
  if (onDocDown) document.removeEventListener('pointerdown', onDocDown, true)
  onDocDown = null
}

function onAfterLeave() {
  unbindDoc()
}

async function markAllRead() {
  if (updates.unread <= 0) return
  await updates.markAll()
}

watch(() => props.open, async v => {
  if (v) {
    await nextTick()
    bindDoc()
    void markAllRead()
  } else {
    unbindDoc()
  }
})

onBeforeUnmount(() => {
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
      box-shadow: 0 3px 5px rgba($black, 0.25);
      .item-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin: 0;
        padding: 0;
        gap: 10px;
        width: 100%;
        span {
          margin: 0;
          font-size: 18px;
          font-weight: bold;
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

@media (max-width: 1280px) {
  .panel {
    max-height: calc(100dvh - 70px);
  }
}
</style>
