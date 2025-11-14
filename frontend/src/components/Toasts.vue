<template>
  <div class="toasts" @transitionend="onTransEnd">
    <div v-for="t in items" :key="t.key" class="toast" :data-key="t.key" :class="{ closing: t._closing }">
      <header>
        <span>{{ t.title }}</span>
        <button @click="closeManual(t)">
          <img :src="iconClose" alt="close" />
        </button>
      </header>

      <div class="user">
        <img v-if="t.kind === 'app' && t.user" v-minio-img="{ key: t.user.avatar_name ? `avatars/${t.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
        <span v-if="t.kind === 'app' && t.user">{{ t.user.username || ('user' + t.user.id) }}</span>
        <p v-if="t.kind !== 'app' && t.text">{{ t.text }}</p>
        <button v-if="(t.kind === 'app' || t.kind === 'approve') && t.action" @click="run(t)">{{ t.action.label }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
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

function onApproved(e: any) {
  const p = e?.detail || {}
  const rid = Number(p.room_id)
  const uid = Number(p.user_id)
  if (!Number.isFinite(rid) || !Number.isFinite(uid)) return
  const targets = items.value.filter(t => t.kind === 'app' && t.room_id === rid && t.user?.id === uid)
  for (const t of targets) {
    t._closing = true
    setTimeout(() => { void close(t) }, 300)
  }
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
  window.addEventListener('auth-room_app_approved', onApproved)
})

onBeforeUnmount(() => {
  window.removeEventListener('auth-room_app_approved', onApproved)
})
</script>

<style scoped lang="scss">
.toasts {
  display: flex;
  position: fixed;
  flex-direction: column;
  left: 10px;
  bottom: 10px;
  gap: 10px;
  z-index: 2000;
  .toast {
    display: flex;
    flex-direction: column;
    width: 400px;
    border-radius: 5px;
    background-color: $dark;
    opacity: 1;
    transform: translateY(0);
    transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
    will-change: opacity, transform;
    &.closing {
      opacity: 0;
      transform: translateY(30px);
      pointer-events: none;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 5px 10px;
      border-radius: 5px;
      background-color: $graphite;
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
    .user {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 15px 10px;
      gap: 5px;
      border-radius: 5px;
      img {
        width: 30px;
        height: 30px;
        border-radius: 50%;
      }
      span {
        flex: 1;
        height: 18px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      p {
        margin: 0;
      }
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 10px;
        height: 30px;
        border: none;
        border-radius: 5px;
        background-color: $green;
        color: $bg;
        font-size: 14px;
        font-family: Manrope-Medium;
        line-height: 1;
        cursor: pointer;
      }
    }
  }
}
</style>
