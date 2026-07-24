<template>
  <div class="toasts" @transitionend="onTransEnd">
    <div v-for="t in items" :key="t.key" class="toast" :data-key="t.key" :class="[toastToneClass(t), { closing: t._closing }]">
      <UiIcon class="toast-icon" :icon="toastIconVariant(t) === 'success' ? iconCheckCircle : toastIconVariant(t) === 'neutral' ? iconInfo : iconDanger" />
      <div class="toast-div">
        <header>
          <span>{{ t.title }}</span>
          <button @click="closeManual(t)">
            <UiIcon class="btn-icon" :icon="iconClose" />
          </button>
        </header>

        <div class="user">
          <div class="meta" :class="{ 'has-theme-color': hasToastUserThemeColor(t.user) }" :style="toastUserNickStyle(t.user)">
            <img v-if="t.user" v-minio-img="{ key: t.user.avatar_name ? `avatars/${t.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
            <div v-if="t.user && toastUserThemeIconSrcs(t.user).length" class="profile-theme-icons" aria-hidden="true">
              <img v-for="badgeSrc in toastUserThemeIconSrcs(t.user)" :key="`${t.user.id}-${badgeSrc}`" class="profile-theme-icon" :src="badgeSrc" alt="" />
            </div>
            <span v-if="t.user" class="nick">{{ t.user.username || ('user' + t.user.id) }}</span>
            <div v-if="t.sanctionText" class="sanction-text">
              <p class="sanction-text__lead">{{ t.sanctionText.lead }}</p>
              <p class="sanction-text__details">{{ t.sanctionText.details }}</p>
            </div>
            <p v-else-if="t.text">{{ t.text }}</p>
          </div>
          <div v-if="t.actions && t.actions.length" class="actions">
            <UiButton
              v-for="a in t.actions"
              :key="a.label"
              class="action"
              :variant="a.style === 'neutral' ? 'white' : 'green'"
              size="middle"
              :text="a.label"
              :disabled="t._actionBusy"
              @click="runAction(t, a)"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useNotifStore, inferFriendApiAction, resolveFriendsApiError } from '@/store'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { getProfileThemeOption } from '@/constants/profileThemes'
import { getProfileThemeBadgeSources } from '@/constants/profileIcons'

import UiIcon from '@/components/UiIcon.vue'
import UiButton from '@/components/UiButton.vue'

import defaultAvatar from '@/assets/svg/iconDefaultAvatarBlack.svg'
import iconClose from '@/assets/svg/iconClose.svg'
import iconCheckCircle from '@/assets/svg/iconCheckCircle.svg'
import iconInfo from '@/assets/svg/iconInfo.svg'
import iconDanger from '@/assets/svg/iconDanger.svg'

const router = useRouter()
const notif = useNotifStore()
const TOAST_TTL_MS = 30000

type RouteAction = {
  kind: 'route'
  label: string
  to: string
  style?: 'primary' | 'neutral'
}
type ApiAction = {
  kind: 'api'
  label: string
  url: string
  method?: 'get'|'post'|'delete'|'put'
  body?: any
  style?: 'primary' | 'neutral'
}
type ToastAction = RouteAction | ApiAction
type ToastUser = {
  id: number
  username?: string
  avatar_name?: string|null
  role?: string | null
  theme_color?: string | null
  theme_icon?: string | null
}
type ToastSanctionText = {
  lead: string
  details: string
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
  _actionBusy?: boolean
  _closing?: boolean
  read?: boolean
  id?: number
  sanctionText?: ToastSanctionText
}
type ToastToneClass = 'tone-yellow' | 'tone-orange' | 'tone-red' | 'tone-green' | 'tone-blue'
type ToastIconVariant = 'success' | 'neutral' | 'attention'

const items = ref<ToastItem[]>([])

const hasToastUserThemeColor = (user?: ToastUser) => Boolean(getProfileThemeOption(user?.theme_color))
const toastUserNickStyle = (user?: ToastUser) => {
  const option = getProfileThemeOption(user?.theme_color)
  return option ? { '--toast-user-nick-theme': option.bg } : {}
}
const toastUserThemeIconSrcs = (user: ToastUser) => (
  getProfileThemeBadgeSources(user.theme_icon, user.role, { roleBadgeVariant: 'black', userId: user.id })
)

async function close(target: ToastItem | number) {
  const key = typeof target === 'number' ? target : target.key
  items.value = items.value.filter(x => x.key !== key)
}

async function closeManual(t: ToastItem){
  if (t.kind === 'app' && t.user?.id && t.room_id) {
    try {
      window.dispatchEvent(new CustomEvent('room-app-seen', { detail: { room_id: t.room_id, user_id: t.user.id } }))
    } catch {}
  }
  try { if (t.id && t.kind !== 'app') await notif.markReadVisible([t.id]) } catch {}
  t._closing = true
  setTimeout(() => { void close(t.key) }, 300)
}

async function runAction(t: ToastItem, action: ToastAction) {
  if (t._actionBusy) return
  t._actionBusy = true
  let actionOk = false
  try {
    if (!action) return
    if (action.kind === 'route') {
      await router.push(action.to)
    } else {
      const m = (action.method || 'post').toLowerCase()
      await (api as any)[m](action.url, action.body)
    }
    actionOk = true
  } catch (e: any) {
    if (action.kind === 'api') {
      const friendAction = inferFriendApiAction(action.url, action.method)
      if (friendAction !== 'unknown') {
        void alertDialog(resolveFriendsApiError(e, friendAction))
      } else {
        void alertDialog('Не удалось выполнить действие')
      }
    } else {
      void alertDialog('Не удалось перейти по ссылке')
    }
  } finally {
    t._actionBusy = false
    if (actionOk) await closeManual(t)
  }
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
    setTimeout(() => { void close(t.key) }, 250)
  }
}

function toastToneClass(t: ToastItem): ToastToneClass {
  const title = String(t.title || '')
  const text = String(t.text || '')

  if (title === 'Заявка в друзья от' || title === 'Заявка в комнату от' || t.kind === 'app') return 'tone-blue'
  if (title === 'Заявка в друзья принята' || title === 'Доступ разрешен' || title === 'Приглашение в комнату от') return 'tone-green'
  if (title === 'Доступ к комнате отозван' || title === 'Обратная связь') return 'tone-blue'
  if (title === 'Таймаут') return 'tone-orange'
  if (title === 'Бан' || title === 'Аватар' || title === 'Никнейм') return 'tone-red'
  if (title === 'Отстранение от игр') return 'tone-yellow'
  if (title === 'Подписка') {
    if (text.includes('истекла')) return 'tone-red'
    if (text.includes('истекает')) return 'tone-orange'
    return 'tone-green'
  }
  if (title === 'Роль') {
    if (text.includes('выдана')) return 'tone-green'
    return 'tone-blue'
  }

  return 'tone-blue'
}

function toastIconVariant(t: ToastItem): ToastIconVariant {
  const tone = toastToneClass(t)
  if (tone === 'tone-green') return 'success'
  if (tone === 'tone-blue') return 'neutral'
  return 'attention'
}

function splitSanctionToastText(kind: string | undefined, text: string | undefined): ToastSanctionText | undefined {
  if (kind !== 'sanction' || !text) return undefined

  const marker = '. Пункт правил:'
  const markerIndex = text.indexOf(marker)
  if (markerIndex <= 0) return undefined

  const lead = text.slice(0, markerIndex).trim()
  const details = text.slice(markerIndex + 2).trim()
  if (!lead || !details) return undefined

  return { lead, details }
}

onMounted(() => {
  window.addEventListener('toast', (e: any) => {
    const d = e?.detail || {}
    const key = Date.now() + Math.random()
    const actions = Array.isArray(d.actions) ? d.actions : (d.action ? [d.action] : undefined)
    const kind = d.kind || 'info'
    const text = d.text ? String(d.text) : undefined
    const t: ToastItem = {
      key,
      id: d.id,
      title: d.title ?? 'Уведомление',
      text,
      date: d.date ? Number(new Date(d.date)) : Date.now(),
      kind,
      action: d.action,
      actions,
      ttl: TOAST_TTL_MS,
      user: d.user,
      room_id: Number.isFinite(d.room_id) ? Number(d.room_id) : undefined,
      sanctionText: splitSanctionToastText(kind, text),
    }
    items.value.push(t)
    window.setTimeout(() => {
      const current = items.value.find(x => x.key === key)
      if (!current) return
      current._closing = true
      window.setTimeout(() => { void close(key) }, 500)
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
  left: 40px;
  bottom: 40px;
  gap: 10px;
  z-index: 2000;
  pointer-events: none;
  .toast {
    --toast-border-color: #{$blue-500};
    display: flex;
    box-sizing: border-box;
    padding: 16px;
    gap: 8px;
    width: 450px;
    pointer-events: auto;
    border-left: 4px solid var(--toast-border-color);
    border-radius: 24px;
    background-color: $neutral-100;
    box-shadow: 0 2px 16px 0 rgba($neutral-black, 0.20);
    opacity: 1;
    transform: translateY(0);
    transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
    will-change: opacity, transform;
    &.closing {
      opacity: 0;
      transform: translateY(30px);
      pointer-events: none;
    }
    &.tone-yellow {
      --toast-border-color: #{$yellow-500};
    }
    &.tone-orange {
      --toast-border-color: #{$orange-500};
    }
    &.tone-red {
      --toast-border-color: #{$red-500};
    }
    &.tone-green {
      --toast-border-color: #{$green-500};
    }
    &.tone-blue {
      --toast-border-color: #{$blue-500};
    }
    .toast-icon {
      --ui-icon-width: 24px;
      --ui-icon-height: 24px;
      --ui-icon-color: var(--toast-border-color);
    }
    .toast-div {
      display: flex;
      flex-direction: column;
      width: 386px;
      gap: 16px;
      header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        span {
          color: $neutral-black;
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        button {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          width: 24px;
          height: 24px;
          border: none;
          background: none;
          cursor: pointer;
          .btn-icon {
            --ui-icon-width: 24px;
            --ui-icon-height: 24px;
            --ui-icon-color: #{$neutral-black};
          }
          &:not(:disabled):hover,
          &:not(:disabled):focus-visible,
          &:not(:disabled):active {
            .btn-icon {
              --ui-icon-color: #{$green-600};
            }
          }
        }
      }
      .user {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        .meta {
          display: flex;
          align-items: center;
          gap: 8px;
          min-width: 0;
          &.has-theme-color .nick {
            background: var(--toast-user-nick-theme);
            background-clip: text;
            color: transparent;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
          }
          img {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            object-fit: cover;
          }
          .profile-theme-icons {
            display: inline-flex;
            align-items: center;
            margin-left: -8px;
            .profile-theme-icon {
              border-radius: 0;
              object-fit: contain;
            }
          }
          span {
            max-width: 170px;
            color: $neutral-900;
            font-family: Hauora-Regular;
            font-size: 16px;
            line-height: 22px;
            letter-spacing: -0.32px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          p {
            margin: 0;
            color: $neutral-500;
            font-family: Hauora-Regular;
            font-size: 16px;
            line-height: 22px;
            letter-spacing: -0.32px;
          }
          .sanction-text {
            display: flex;
            flex-direction: column;
            gap: 12px;
            min-width: 0;
            .sanction-text__lead {
              color: $neutral-900;
              font-family: Hauora-Bold;
              font-size: 16px;
              line-height: 18px;
              letter-spacing: -0.32px;
            }
            .sanction-text__details {
              color: $neutral-500;
            }
          }
        }
        .actions {
          display: flex;
          align-items: center;
          gap: 4px;
        }
      }
    }
  }
}

</style>
