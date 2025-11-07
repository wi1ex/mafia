<template>
  <div class="toasts" @transitionend="onTransEnd">
    <div v-for="t in items" :key="t.key" class="toast" :data-key="t.key" :class="{ closing: t._closing }">
      <div class="head">
        <strong class="title">{{ t.title }}</strong>
      </div>

      <div v-if="t.kind === 'app' && t.user" class="user">
        <img v-minio-img="{ key: t.user.avatar_name ? `avatars/${t.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
        <span class="user-name">
          {{ t.user.username || ('user' + t.user.id) }}
        </span>
      </div>

      <p v-if="t.kind !== 'app' && t.text" class="text">{{ t.text }}</p>

      <div class="actions">
        <button v-if="(t.kind === 'app' || t.kind === 'approve') && t.action" @click="run(t)">
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
import { useNotifStore } from '@/store'
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
  title: string
  text?: string
  date: number
  kind?: string
  action?: ToastAction
  ttl?: number
  user?: ToastUser
  room_id?: number
  _closing?: boolean
  read?: boolean
  id?: number
}

const items = ref<ToastItem[]>([])

async function close(t: ToastItem) {
  items.value = items.value.filter(x => x !== t)
}

async function closeManual(t: ToastItem){
  if (t.kind === 'app' && t.user?.id && t.room_id) {
    try {
      window.dispatchEvent(new CustomEvent('room-app-seen', { detail: { room_id: t.room_id, user_id: t.user.id } }))
    } catch {}
  }
  try { if (t.id && t.kind !== 'app') await notif.markReadVisible([t.id]) } catch {}
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
      id: d.id,
      title: d.title ?? 'Уведомление',
      text: d.text ? String(d.text) : undefined,
      date: d.date ? Number(new Date(d.date)) : Date.now(),
      kind: d.kind || 'info',
      action: d.action,
      ttl: Number.isFinite(d.ttl_ms) ? d.ttl_ms : (d.action ? 10000 : 5000),
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

<style scoped lang="scss">
.toasts {
  position: fixed;
  left: 10px;
  bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 2000;
}
.toast {
  min-width: 280px;
  max-width: 420px;
  background-color: #2a2a2a;
  color: #fff;
  border-radius: 5px;
  padding: 10px;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.5);
  opacity: 1;
  transform: translateY(0);
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
  will-change: opacity, transform;
  &.closing {
    opacity: 0;
    transform: translateY(10px);
    pointer-events: none;
  }
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 5px;
}
.title {
  font-weight: 600;
}
.user {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 5px 0 5px;
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
  margin: 5px 0 10px;
}
.actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
.actions > button {
  background-color: #444;
  color: $fg;
  font-size: 14px;
  font-family: Manrope-Medium;
  line-height: 1;
  border: none;
  border-radius: 5px;
  padding: 5px 10px;
  cursor: pointer;
}
.actions > .close {
  background-color: #555;
}
</style>
