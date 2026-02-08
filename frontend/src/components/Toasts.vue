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
        <img v-if="t.user" v-minio-img="{ key: t.user.avatar_name ? `avatars/${t.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
        <div class="meta">
          <span v-if="t.user">{{ t.user.username || ('user' + t.user.id) }}</span>
          <p v-if="t.text">{{ t.text }}</p>
        </div>
        <div v-if="t.actions && t.actions.length" class="actions">
          <button v-for="a in t.actions" :key="a.label" :class="['action', a.style]" @click="runAction(t, a)">{{ a.label }}</button>
        </div>
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
  style?: 'primary' | 'danger' | 'neutral'
}
type ApiAction = {
  kind: 'api'
  label: string
  url: string
  method?: 'get'|'post'|'delete'|'put'
  body?: any
  style?: 'primary' | 'danger' | 'neutral'
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
  actions?: ToastAction[]
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

async function runAction(t: ToastItem, action: ToastAction) {
  try {
    if (!action) return
    if (action.kind === 'route') {
      await router.push(action.to)
    } else {
      const m = (action.method || 'post').toLowerCase()
      await (api as any)[m](action.url, action.body)
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
    setTimeout(() => { void close(t) }, 250)
  }
}

onMounted(() => {
  window.addEventListener('toast', (e: any) => {
    const d = e?.detail || {}
    const key = Date.now() + Math.random()
    const actions = Array.isArray(d.actions) ? d.actions : (d.action ? [d.action] : undefined)
    const t: ToastItem = {
      key,
      id: d.id,
      title: d.title ?? 'Уведомление',
      text: d.text ? String(d.text) : undefined,
      date: d.date ? Number(new Date(d.date)) : Date.now(),
      kind: d.kind || 'info',
      action: d.action,
      actions,
      ttl: Number.isFinite(d.ttl_ms) ? d.ttl_ms : (actions ? 10000 : 5000),
      user: d.user,
      room_id: Number.isFinite(d.room_id) ? Number(d.room_id) : undefined,
    }
    items.value.push(t)
    window.setTimeout(() => {
      t._closing = true
      window.setTimeout(() => { void close(t) }, 500)
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
      .meta {
        display: flex;
        flex-direction: column;
        gap: 5px;
        flex: 1;
        min-width: 0;
      }
      img {
        width: 30px;
        height: 30px;
        border-radius: 50%;
      }
      span {
        height: 18px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      p {
        margin: 0;
      }
      .actions {
        display: flex;
        gap: 5px;
        .action {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 10px;
          height: 30px;
          border: none;
          border-radius: 5px;
          background-color: rgba($green, 0.75);
          color: $bg;
          font-size: 14px;
          font-family: Manrope-Medium;
          line-height: 1;
          cursor: pointer;
          transition: background-color 0.25s ease-in-out;
          &:hover {
            background-color: $green;
          }
          &.danger {
            background-color: rgba($red, 0.75);
            &:hover {
              background-color: $red;
            }
          }
          &.neutral {
            background-color: rgba($lead, 0.75);
            color: $fg;
            &:hover {
              background-color: $lead;
            }
          }
        }
      }
    }
  }
}

@media (max-width: 1280px) {
  .toasts {
    left: 5px;
    bottom: 5px;
    gap: 5px;
  }
}
</style>
