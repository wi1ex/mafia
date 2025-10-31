<template>
  <header class="bar">
    <div class="brand" aria-label="Mafia">DECEIT.games (v{{ BUILD }})</div>

    <div v-if="!auth.isAuthed && !auth.foreignActive">
      <div id="tg-login" />
    </div>
    <div v-else-if="!auth.isAuthed && auth.foreignActive" class="brand">
      <span>Вы уже авторизованы в соседней вкладке</span>
    </div>

    <div v-else class="user">
      <div class="bell" ref="nb_root">
        <button @click="nb_open = !nb_open" aria-label="Уведомления">
          <img :src="notif.unread > 0 ? iconNotifBellNew : iconNotifBell" alt="requests" />
        </button>
        <div v-if="nb_open" class="panel" ref="nb_panel">
          <div class="head">
            <span>Уведомления</span>
            <button v-if="notif.unread > 0" @click="notif.markAll()">Отметить всё прочитанным</button>
          </div>
          <div class="list" ref="nb_list">
            <article v-for="it in notif.items" :key="it.id" class="item" :data-id="it.id" :class="{ unread: !it.read }">
              <p>{{ it.text }}</p>
              <time>{{ new Date(it.created_at).toLocaleString() }}</time>
            </article>
          </div>
        </div>
      </div>

      <router-link to="/profile" class="profile-link" aria-label="Профиль">
        <img v-minio-img="{ key: user.user?.avatar_name ? `avatars/${user.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Аватар" />
        <span class="nick" aria-live="polite">{{ user.user?.username || 'User' }}</span>
      </router-link>

      <button class="btn" type="button" @click="logout">Выйти</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, nextTick, ref } from 'vue'
import { useAuthStore, useUserStore, useNotifStore } from '@/store'

import defaultAvatar from "@/assets/svg/defaultAvatar.svg"
import iconNotifBell from "@/assets/svg/notifBell.svg"
import iconNotifBellNew from "@/assets/svg/notifBellNew.svg"

const auth = useAuthStore()
const user = useUserStore()
const notif = useNotifStore()

let TG_LIB_ONCE = false
const BOT = import.meta.env.VITE_TG_BOT_NAME as string || ''
const BUILD = import.meta.env.VITE_BUILD_ID as string || ''
const SIZE: 'large' | 'medium' | 'small' = 'large'

declare global {
  interface Window { __tg_cb__?: (u: any) => void }
}

async function logout() {
  try { await auth.logout() }
  finally { alert('Для "полного" выхода из аккаунта нажмите в Telegram "Terminate session" для этой сессии') }
}

function mountTGWidget() {
  if (!BOT) return
  const box = document.getElementById('tg-login')
  if (!box || box.children.length) return
  window.__tg_cb__ = async (u: any) => {
    try { auth.wipeLocalForNewLogin() } catch {}
    await auth.signInWithTelegram(u)
  }
  const s = document.createElement('script')
  s.async = true
  s.src = 'https://telegram.org/js/telegram-widget.js?19'
  s.dataset.telegramLogin = BOT
  s.dataset.size = SIZE
  s.dataset.userpic = 'true'
  s.dataset.onauth = '__tg_cb__(user)'
  s.setAttribute('data-tg-widget', TG_LIB_ONCE ? '0' : '1')
  TG_LIB_ONCE = true
  box.appendChild(s)
}

const nb_open = ref(false)
const nb_list = ref<HTMLElement|null>(null)
const nb_panel = ref<HTMLElement|null>(null)
const nb_root = ref<HTMLElement|null>(null)

let nbObs: IntersectionObserver | null = null
let nbRO: ResizeObserver | null = null
let nbOnScroll: ((e: Event) => void) | null = null

function nbAttachObserver() {
  if (!nb_list.value || !nb_panel.value) return
  try { nbObs?.disconnect() } catch {}
  nbObs = new IntersectionObserver((entries) => {
    const ids: number[] = []
    for (const e of entries) {
      if (!e.isIntersecting || e.intersectionRatio < 0.5) continue
      const id = Number((e.target as HTMLElement).dataset.id)
      const it = notif.items.find(x => x.id === id)
      if (it && !it.read) ids.push(id)
    }
    if (ids.length) void notif.markReadVisible(ids)
  }, { root: nb_panel.value, threshold: 0.5 })
  queueMicrotask(() => nb_list.value?.querySelectorAll('.item').forEach(el => nbObs?.observe(el)))
}
function nbMarkVisibleNow() {
  if (!nb_list.value || !nb_panel.value) return
  const rootBox = nb_panel.value.getBoundingClientRect()
  const ids: number[] = []
  nb_list.value.querySelectorAll<HTMLElement>('.item').forEach(el => {
    const r = el.getBoundingClientRect()
    const visible = Math.max(0, Math.min(rootBox.bottom, r.bottom) - Math.max(rootBox.top, r.top))
    const ratio = visible / Math.max(1, r.height)
    if (ratio >= 0.5) {
      const id = Number(el.dataset.id)
      const it = notif.items.find(x => x.id === id)
      if (it && !it.read) ids.push(id)
    }
  })
  if (ids.length) void notif.markReadVisible(ids)
}
function nbBindScroll() {
  if (!nb_panel.value || nbOnScroll) return
  nbOnScroll = () => nbMarkVisibleNow()
  nb_panel.value.addEventListener('scroll', nbOnScroll, { passive: true })
}
function nbUnbindScroll() {
  if (nb_panel.value && nbOnScroll) nb_panel.value.removeEventListener('scroll', nbOnScroll)
  nbOnScroll = null
}
function nbBindResize() {
  if (nbRO || !nb_panel.value) return
  nbRO = new ResizeObserver(() => nbMarkVisibleNow())
  nbRO.observe(nb_panel.value)
}
function nbUnbindResize() {
  try { nbRO?.disconnect() } catch {}
  nbRO = null
}
function nbOnDocClick(e: Event) {
  const t = e.target as Node | null
  if (!t) return
  if (!nb_root.value?.contains(t)) nb_open.value = false
}
function nbBindDoc() { document.addEventListener('pointerdown', nbOnDocClick, true) }
function nbUnbindDoc() { document.removeEventListener('pointerdown', nbOnDocClick, true) }

watch(() => notif.items.length, async () => {
  if (!nb_open.value) return
  await nextTick()
  nbAttachObserver()
  nbMarkVisibleNow()
})

watch(nb_open, async v => {
  if (v) {
    await nextTick()
    nbBindDoc()
    nbAttachObserver()
    nbMarkVisibleNow()
    nbBindScroll()
    nbBindResize()
  } else {
    try { nbObs?.disconnect() } catch {}
    nbUnbindScroll()
    nbUnbindResize()
    nbUnbindDoc()
    if (!nb_root.value) nbUnbindDoc()
  }
})

watch([() => auth.isAuthed, () => auth.foreignActive], async () => {
  if (!auth.isAuthed && !auth.foreignActive) {
    await nextTick()
    mountTGWidget()
  } else {
    document.getElementById('tg-login')?.replaceChildren()
  }
}, { flush: 'post' })

watch(() => auth.isAuthed, async ok => {
  if (ok) { notif.ensureWS(); await notif.fetchAll() }
})

onMounted(async () => {
  if (!auth.isAuthed && !auth.foreignActive) {
    await nextTick()
    mountTGWidget()
  }
  if (auth.isAuthed) {
    notif.ensureWS()
    await notif.fetchAll()
  }
})

onBeforeUnmount(() => {
  delete window.__tg_cb__
  try { nbObs?.disconnect() } catch {}
  nbUnbindScroll()
  nbUnbindResize()
  nbUnbindDoc()
})
</script>

<style lang="scss" scoped>
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
  width: calc(100% - 20px);
  height: 60px;
  .brand {
    display: flex;
    align-items: center;
    padding: 0 10px;
    height: 40px;
    border-radius: 5px;
    background-color: $dark;
    color: $fg;
    font-size: 16px;
  }
  .note {
    max-width: 460px;
    color: $fg;
  }
  .user {
    display: flex;
    align-items: center;
    gap: 10px;
    .bell {
      position: relative;
      border-radius: 5px;
      button {
        padding: 0 10px;
        height: 40px;
        border-radius: 5px;
        border: none;
        background-color: $dark;
        font-size: 16px;
        cursor: pointer;
      }
      .panel {
        position: absolute;
        right: 0;
        top: 44px;
        width: 360px;
        max-height: 420px;
        overflow: auto;
        background-color: #1e1e1e;
        border-radius: 8px;
        padding: 8px;
        z-index: 100;
        .head {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 6px;
        }
        .list {
          .item {
            padding: 8px;
            border-bottom: 1px solid #333;
          }
          .item.unread p {
            font-weight: 600;
          }
        }
      }
    }
    .profile-link {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 10px;
      gap: 5px;
      height: 40px;
      border-radius: 5px;
      background-color: $lead;
      text-decoration: none;
      img {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        object-fit: cover;
      }
      .nick {
        color: $fg;
        font-size: 16px;
      }
    }
    .btn {
      padding: 0 10px;
      height: 40px;
      border-radius: 5px;
      border: none;
      background-color: $dark;
      color: $fg;
      font-size: 16px;
      cursor: pointer;
    }
  }
}
</style>
