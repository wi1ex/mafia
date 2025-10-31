<template>
  <div class="toasts" @transitionend="onTransEnd">
    <div v-for="t in items" :key="t.key" class="toast" :data-key="t.key" :class="{ closing: t._closing }">
      <div class="head">
        <strong class="title">{{ t.title }}</strong>
        <time class="date">{{ fmt(t.date) }}</time>
      </div>

      <div v-if="t.user" class="user">
        <img v-minio-img="{ key: t.user.avatar_name ? `avatars/${t.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
        <span class="user-name">
          {{ t.user.username || ('user' + t.user.id) }}
        </span>
      </div>

      <p class="text">{{ t.text }}</p>

      <div class="actions">
        <button v-if="t.action" @click="run(t)">
          {{ t.action.label }}
        </button>
        <button class="close" @click="closeManual(t)">
          <img :src="iconClose" alt="close" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useNotifStore } from '@/store/modules/notif'
import { api } from '@/services/axios'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconClose from '@/assets/svg/close.svg'

const router = useRouter()
const notif = useNotifStore()

type RouteAction = {
  kind: 'route'
  label: string
  to: string
}
type ApiAction = {
  kind: 'api'
  label: string
  url: string
  method?: 'get'|'post'|'delete'|'put'
  body?: any
}
type ToastAction = RouteAction | ApiAction
type ToastUser = {
  id: number
  username?: string
  avatar_name?: string|null
}

type ToastItem = {
  key: number
  noteId?: number
  title: string
  text: string
  date: number
  kind?: string
  action?: ToastAction
  ttl?: number
  user?: ToastUser
  room_id?: number
  _closing?: boolean
}

const items = ref<ToastItem[]>([])

function fmt(ts: number){ return new Date(ts).toLocaleString() }

async function close(t: ToastItem) {
  items.value = items.value.filter(x => x !== t)
}

async function closeManual(t: ToastItem){
  if (t.kind === 'app' && t.user?.id && t.room_id) {
    try {
      window.dispatchEvent(new CustomEvent('room-app-seen', { detail: { room_id: t.room_id, user_id: t.user.id } }))
    } catch {}
  }
  try { if (t.noteId) await notif.markReadVisible([t.noteId]) } catch {}
  t._closing = true
  setTimeout(() => { void close(t) }, 300)
}

async function run(t: ToastItem) {
  try {
    if (!t.action) return
    if (t.action.kind === 'route') {
      await router.push(t.action.to)
    } else {
      const m = (t.action.method || 'post').toLowerCase()
      await (api as any)[m](t.action.url, t.action.body)
      const rx = /\/rooms\/(\d+)\/requests\/(\d+)\/approve/
      const mm = rx.exec(t.action.url)
      if (mm) {
        window.dispatchEvent(new CustomEvent('auth-room_app_approved', {
          detail: { room_id: Number(mm[1]), user_id: Number(mm[2]) }
        }))
      }
    }
  } finally { await closeManual(t) }
}

function onTransEnd(e: TransitionEvent) {
  const el = e.target as HTMLElement
  if (!el.classList.contains('toast')) return
  const k = Number(el.dataset.key)
  const t = items.value.find(x => x.key === k)
  if (t && t._closing) { void close(t) }
}

onMounted(() => {
  window.addEventListener('toast', (e: any) => {
    const d = e?.detail || {}
    const key = Date.now() + Math.random()
    const t: ToastItem = {
      key,
      noteId: d.id,
      title: d.title || 'Уведомление',
      text: String(d.text || ''),
      date: d.date ? Number(new Date(d.date)) : Date.now(),
      kind: d.kind || 'info',
      action: d.action,
      ttl: Number.isFinite(d.ttl) ? d.ttl : (d.action ? 8000 : 5000),
      user: d.user,
      room_id: Number.isFinite(d.room_id) ? Number(d.room_id) : undefined,
    }
    items.value.push(t)
    window.setTimeout(() => {
      t._closing = true
      window.setTimeout(() => { void close(t) }, 600)
    }, t.ttl!)
  })
})
</script>

<style lang="scss" scoped>
.toasts {
  position: fixed;
  left: 10px;
  bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 2000;
}
.toast {
  min-width: 280px;
  max-width: 420px;
  background-color: #2a2a2a;
  color: #fff;
  border-radius: 6px;
  padding: 10px 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  opacity: 1;
  transform: translateY(0);
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
  will-change: opacity, transform;
  &.closing {
    opacity: 0;
    transform: translateY(8px);
    pointer-events: none;
  }
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}
.title {
  font-weight: 600;
}
.date {
  color: #bbb;
  font-size: 12px;
}
.user {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 0 4px;
}
.user img {
  width: 28px;
  height: 28px;
  border-radius: 50%;
}
.user-name {
  font-weight: 500;
}
.text {
  margin: 6px 0 8px;
}
.actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.actions > button {
  background-color: #444;
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
}
.actions > .close {
  background-color: #555;
}
</style>
