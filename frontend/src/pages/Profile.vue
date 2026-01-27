<template>
  <section class="profile">
    <header>
      <nav class="tabs" aria-label="Профиль" role="tablist">
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'profile' }" :aria-selected="activeTab === 'profile'" @click="activeTab = 'profile'">
          Аккаунт
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'sanctions' }" :aria-selected="activeTab === 'sanctions'" @click="activeTab = 'sanctions'">
          Ограничения
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'stats' }" :aria-selected="activeTab === 'stats'" @click="activeTab = 'stats'" disabled>
          Статистика
        </button>
      </nav>
      <router-link class="btn nav" :to="{ name: 'home' }" aria-label="На главную">На главную</router-link>
    </header>

    <Transition name="tab-fade" mode="out-in">
      <div :key="activeTab" class="tab-panel">
        <div v-if="activeTab === 'profile'" class="grid">
          <div class="block">
            <h3>Аватар</h3>
            <div class="avatar-row">
              <img class="avatar-img" v-minio-img="{ key: me.avatar_name ? `avatars/${me.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Текущий аватар" />
              <div class="actions">
                <input ref="fileEl" type="file" accept="image/jpeg,image/png" @change="onPick" :disabled="isBanned" hidden />
                <button class="btn dark" @click="fileEl?.click()" :disabled="busyAva || isBanned">
                  <img class="btn-img" :src="iconEdit" alt="edit" />
                  Изменить
                </button>
                <span class="hint">JPG/PNG, до 5 МБ</span>
                <button class="btn danger" v-if="me.avatar_name" @click="onDeleteAvatar" :disabled="busyAva || isBanned">
                  <img class="btn-img" :src="iconDelete" alt="delete" />
                  Удалить
                </button>
              </div>
            </div>
          </div>

          <div class="block">
            <h3>Никнейм</h3>
            <div class="nick-row">
              <div class="ui-input" :class="{ filled: !!nick, invalid: nick && !validNick }">
                <input id="profile-nick" v-model.trim="nick" :maxlength="NICK_MAX" :disabled="busyNick || isBanned" placeholder=" "
                       autocomplete="off" inputmode="text" :aria-invalid="nick && !validNick" aria-describedby="profile-nick-hint" />
                <label for="profile-nick">Никнейм</label>
                <div class="underline">
                  <span :style="nickUnderlineStyle"></span>
                </div>
                <div class="meta">
                  <span id="profile-nick-hint">{{ nick.length }}/{{ NICK_MAX }}</span>
                </div>
              </div>
              <button class="btn confirm" @click="saveNick" :disabled="busyNick || isBanned || nick === me.username || !validNick">
                <img class="btn-img" :src="iconSave" alt="save" />
                {{ busyNick ? '...' : 'Сохранить' }}
              </button>
            </div>
            <span class="hint"><code>латиница, кириллица, цифры, символы ()._-</code></span>
          </div>

          <div class="block">
            <h3>Удаление аккаунта</h3>
            <div class="danger-row">
              <button class="btn danger" @click="deleteAccount" :disabled="deleteBusy">
                {{ deleteBusy ? '...' : 'Удалить аккаунт' }}
              </button>
              <p class="danger-text">Удаление произойдет навсегда без возможности восстановления.</p>
            </div>
          </div>

          <div v-if="crop.show" ref="modalEl" class="modal" @keydown.esc="cancelCrop" tabindex="0" aria-modal="true" aria-label="Кадрирование аватара" >
            <div class="modal-body">
              <canvas ref="canvasEl" @mousedown="dragStart" @mousemove="dragMove" @mouseup="dragStop" @mouseleave="dragStop" @wheel.passive="onWheel" />
              <div class="range">
                <span>Масштаб</span>
                <div class="range-wrap">
                  <div class="range-track" :style="cropRangeFillStyle" aria-hidden="true"></div>
                  <input class="range-native" type="range" aria-label="Масштаб" :min="crop.min" :max="crop.max" step="0.01" :value="crop.scale" @input="onRange" :disabled="isBanned" />
                </div>
              </div>
              <div class="modal-actions">
                <button class="btn danger" @click="cancelCrop">Отменить</button>
                <button class="btn confirm" @click="applyCrop" :disabled="busyAva || isBanned">Загрузить</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'sanctions'" class="grid grid-sanctions">
          <div class="block sanctions-block">
            <div class="sanctions-head">
              <h3>История все выданных ранее отстранений от игр, таймаутов и банов</h3>
            </div>
            <div v-if="sanctionsLoaded" class="sanctions-summary">
              <span>Всего: {{ sanctionsSummary.total }}</span>
              <span>Таймауты: {{ sanctionsSummary.timeout }}</span>
              <span>Отстранения: {{ sanctionsSummary.suspend }}</span>
              <span>Баны: {{ sanctionsSummary.ban }}</span>
            </div>
            <div v-if="sanctionsLoading" class="sanctions-empty">Загрузка…</div>
            <div v-else-if="sanctionsError" class="sanctions-empty danger">{{ sanctionsError }}</div>
            <div v-else-if="sanctions.length === 0" class="sanctions-empty">Ограничений пока не было.</div>
            <div v-else class="sanctions-list">
              <article v-for="item in sanctions" :key="item.id" class="sanction-card" :class="`sanction-card--${item.kind}`">
                <div class="sanction-head">
                  <div class="sanction-kind">
                    <span class="sanction-tag">{{ formatSanctionKind(item.kind) }}</span>
                    <span class="sanction-status" :class="`status--${sanctionStatus(item).tone}`">{{ sanctionStatus(item).text }}</span>
                  </div>
                  <span class="sanction-issued">{{ formatLocalDateTime(item.issued_at) }}</span>
                </div>
                <div class="sanction-reason">{{ item.reason || 'Причина не указана' }}</div>
                <div class="sanction-grid">
                  <div class="sanction-cell">
                    <span>Выдал</span>
                    <strong>{{ formatSanctionActor(item.issued_by_name, item.issued_by_id) }}</strong>
                  </div>
                  <div class="sanction-cell">
                    <span>Срок</span>
                    <strong>{{ formatSanctionDuration(item.duration_seconds) }}</strong>
                  </div>
                  <div v-if="isSanctionCompleted(item)" class="sanction-cell">
                    <span>Завершение</span>
                    <strong>{{ formatSanctionEnd(item) }}</strong>
                  </div>
                </div>
              </article>
            </div>
          </div>
        </div>

        <div v-else class="grid grid-empty">
          <!-- пока что пусто -->
        </div>
      </div>
    </Transition>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { api, refreshAccessTokenFull } from '@/services/axios'
import { useAuthStore, useUserStore } from '@/store'
import { confirmDialog, alertDialog } from '@/services/confirm'
import { formatLocalDateTime } from '@/services/datetime'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconSave from '@/assets/svg/save.svg'
import iconEdit from '@/assets/svg/edit.svg'
import iconDelete from '@/assets/svg/delete.svg'

const userStore = useUserStore()
const auth = useAuthStore()
const isBanned = computed(() => userStore.banActive)

const me = reactive({ id: 0, username: '', avatar_name: null as string | null, role: '' })
const fileEl = ref<HTMLInputElement | null>(null)
const modalEl = ref<HTMLDivElement | null>(null)

const nick = ref('')
const busyNick = ref(false)
const validNick = computed(() =>
  new RegExp(`^[a-zA-Zа-яА-Я0-9._\\-()]{2,${NICK_MAX}}$`).test(nick.value) &&
  !/^user/i.test(nick.value)
)

const NICK_MAX = 20
const nickPct = computed(() => {
  const used = Math.min(NICK_MAX, Math.max(0, nick.value.length))
  return (used / NICK_MAX) * 100
})
const nickUnderlineStyle = computed(() => ({ width: `${nickPct.value}%` }))

const activeTab = ref<'profile' | 'stats' | 'sanctions'>('profile')
let onSanctionsUpdate: ((e: Event) => void) | null = null

type SanctionItem = {
  id: number
  kind: 'timeout' | 'ban' | 'suspend'
  reason?: string | null
  issued_at: string
  issued_by_id?: number | null
  issued_by_name?: string | null
  duration_seconds?: number | null
  expires_at?: string | null
  revoked_at?: string | null
  revoked_by_id?: number | null
  revoked_by_name?: string | null
}

const sanctions = ref<SanctionItem[]>([])
const sanctionsLoading = ref(false)
const sanctionsLoaded = ref(false)
const sanctionsError = ref('')

const sanctionsSummary = computed(() => {
  const out = { total: sanctions.value.length, timeout: 0, ban: 0, suspend: 0 }
  for (const item of sanctions.value) {
    if (item.kind === 'timeout') out.timeout += 1
    else if (item.kind === 'ban') out.ban += 1
    else if (item.kind === 'suspend') out.suspend += 1
  }
  return out
})

async function loadMe(options: { keepNickDraft?: boolean } = {}) {
  const prevUsername = me.username
  const { data } = await api.get('/users/profile_info')
  me.id = data.id
  me.username = data.username || ''
  me.avatar_name = data.avatar_name
  me.role = data.role
  const hasDraft = options.keepNickDraft && nick.value !== prevUsername
  if (!hasDraft) nick.value = me.username
  try { await userStore.fetchMe?.() } catch {}
}

async function loadSanctions(force = false) {
  if (sanctionsLoading.value) return
  if (sanctionsLoaded.value && !force) return
  sanctionsLoading.value = true
  sanctionsError.value = ''
  try {
    const { data } = await api.get<{ items: SanctionItem[] }>('/users/sanctions')
    sanctions.value = Array.isArray(data?.items) ? data.items : []
    sanctionsLoaded.value = true
  } catch {
    sanctionsError.value = 'Не удалось загрузить историю ограничений'
  } finally {
    sanctionsLoading.value = false
  }
}

async function saveNick() {
  if (!validNick.value || busyNick.value || nick.value === me.username) return
  busyNick.value = true
  try {
    const { data } = await api.patch('/users/username', { username: nick.value })
    me.username = data.username
    userStore.setUsername(data.username)
    try { await refreshAccessTokenFull(false) } catch {}
  } catch (e: any) {
    const st = e?.response?.status
    const d  = e?.response?.data?.detail
    if (st === 409 && d === 'username_taken')               void alertDialog('Данный никнейм уже занят')
    else if (st === 403 && d === 'user_banned')             void alertDialog('Аккаунт забанен. Изменение никнейма недоступно')
    else if (st === 422 && d === 'reserved_prefix')         void alertDialog('Никнейм не должен начинаться с "user"')
    else if (st === 422 && d === 'invalid_username_format') void alertDialog('Недопустимый формат никнейма')
    else                                                    void alertDialog('Не удалось сохранить никнейм')
  } finally { busyNick.value = false }
}

async function deleteAccount() {
  if (deleteBusy.value) return
  const ok = await confirmDialog({
    title: 'Удаление аккаунта',
    text: 'Вы уверены что хотите навсегда удалить свой аккаунт?',
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  deleteBusy.value = true
  try {
    await api.delete('/users/account')
    await auth.logout()
  } catch {
    void alertDialog('Не удалось удалить аккаунт')
  } finally {
    deleteBusy.value = false
  }
}

function formatSanctionKind(kind: SanctionItem['kind']): string {
  if (kind === 'timeout') return 'Таймаут'
  if (kind === 'suspend') return 'Отстранение'
  if (kind === 'ban') return 'Бан'
  return kind
}

function formatSanctionDuration(seconds?: number | null): string {
  if (!seconds) return 'без срока'
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  const mins = Math.floor(total / 60)
  const days = Math.floor(mins / 1440)
  const hours = Math.floor((mins % 1440) / 60)
  const minutes = mins % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days}д`)
  if (hours > 0) parts.push(`${hours}ч`)
  if (minutes > 0 || parts.length === 0) parts.push(`${minutes}м`)
  return parts.join(' ')
}

function formatSanctionActor(name?: string | null, id?: number | null): string {
  if (name) return name
  if (Number.isFinite(id)) return `#${id}`
  return '-'
}

function parseSanctionDate(value?: string | null): Date | null {
  if (!value) return null
  const dt = new Date(value)
  return Number.isNaN(dt.getTime()) ? null : dt
}

function getSanctionState(item: SanctionItem) {
  const now = Date.now()
  const revokedAt = parseSanctionDate(item.revoked_at)
  if (revokedAt) return { state: 'revoked', endAt: revokedAt, now }
  const expiresAt = parseSanctionDate(item.expires_at)
  if (expiresAt) {
    if (expiresAt.getTime() <= now) return { state: 'expired', endAt: expiresAt, now }
    return { state: 'active', endAt: expiresAt, now }
  }
  return { state: 'active_forever', endAt: null, now }
}

function isSanctionCompleted(item: SanctionItem): boolean {
  const st = getSanctionState(item)
  return st.state === 'revoked' || st.state === 'expired'
}

function sanctionStatus(item: SanctionItem): { text: string; tone: 'active' | 'ended' | 'revoked' } {
  const st = getSanctionState(item)
  if (st.state === 'revoked') return { text: 'Снято досрочно', tone: 'revoked' }
  if (st.state === 'expired') return { text: 'Срок истек', tone: 'ended' }
  return { text: 'Активно', tone: 'active' }
}

function formatSanctionEnd(item: SanctionItem): string {
  const st = getSanctionState(item)
  if (st.state === 'revoked') {
    const revokedBy = formatSanctionActor(item.revoked_by_name, item.revoked_by_id)
    return `Снято досрочно: ${revokedBy} ${formatLocalDateTime(st.endAt)}`
  }
  if (st.state === 'expired') {
    return `${formatLocalDateTime(st.endAt)}`
  }
  if (st.state === 'active') {
    return `Ожидается: ${formatLocalDateTime(st.endAt)}`
  }
  return 'Без срока'
}

type Crop = {
  show: boolean
  img?: HTMLImageElement
  scale: number
  min: number
  max: number
  x: number
  y: number
  dragging: boolean
  sx: number
  sy: number
  type: 'image/jpeg'|'image/png'
}
const crop = reactive<Crop>({ show: false, scale: 1, min: 0.5, max: 3, x: 0, y: 0, dragging: false, sx: 0, sy: 0, type: 'image/jpeg' })
const canvasEl = ref<HTMLCanvasElement | null>(null)
const busyAva = ref(false)
const deleteBusy = ref(false)

function clamp(v:number, lo:number, hi:number) { return Math.min(hi, Math.max(lo, v)) }

function fitContain(imgW: number, imgH: number, boxW: number, boxH: number) {
  return Math.min(boxW / imgW, boxH / imgH)
}

const cropRangePct = computed(() => {
  if (crop.max === crop.min) return 0
  const p = ((crop.scale - crop.min) * 100) / (crop.max - crop.min)
  return Math.max(0, Math.min(100, p))
})

const cropRangeFillStyle = computed<Record<string, string>>(() => ({
  '--fill': `${cropRangePct.value}%`,
}))

function scaleTo(next: number) {
  if (!crop.img || !canvasEl.value) return
  const c = canvasEl.value!
  const Cx = c.width / 2, Cy = c.height / 2
  const u = (Cx - crop.x) / crop.scale
  const v = (Cy - crop.y) / crop.scale
  crop.scale = next
  crop.x = Cx - u * next
  crop.y = Cy - v * next
  clampPosition()
  redraw()
}

async function onPick(e: Event) {
  if (isBanned.value) return
  const f = (e.target as HTMLInputElement).files?.[0]
  ;(e.target as HTMLInputElement).value = ''
  if (!f) return
  if (!['image/jpeg', 'image/png'].includes(f.type)) {
    void alertDialog('К загрузке допустимы только форматы JPG/PNG')
    return
  }
  if (f.size > 5 * 1024 * 1024) {
    void alertDialog('К загрузке допустимы только файлы менее 5 Мбайт')
    return
  }
  const url = URL.createObjectURL(f)
  const img = new Image()
  img.onload = async () => {
    URL.revokeObjectURL(url)
    crop.img = img
    crop.type = (f.type === 'image/png' ? 'image/png' : 'image/jpeg')
    crop.show = true
    await nextTick()
    modalEl.value?.focus()
    document.body.style.overflow = 'hidden'
    const canvas = canvasEl.value!
    const dpr = Math.max(1, window.devicePixelRatio || 1)
    const viewportH = window.innerHeight || document.documentElement.clientHeight || 0
    const S = viewportH > 500 ? 400 : 200
    canvas.width = S * dpr
    canvas.height = S * dpr
    canvas.style.width = S + 'px'
    canvas.style.height = S + 'px'
    const s = fitContain(img.width, img.height, canvas.width, canvas.height)
    crop.min = s
    crop.max = s * 3
    crop.scale = s
    crop.x = (canvas.width - img.width * s) / 2
    crop.y = (canvas.height - img.height * s) / 2
    clampPosition()
    requestAnimationFrame(redraw)
  }
  img.onerror = () => {
    URL.revokeObjectURL(url)
    void alertDialog('Не удалось открыть изображение')
  }
  img.src = url
}

function redraw() {
  const c = canvasEl.value
  const img = crop.img
  if (!c || !img) return
  const ctx = c.getContext('2d')!
  ctx.clearRect(0,0,c.width,c.height)
  ctx.fillStyle = '#000'
  ctx.fillRect(0,0,c.width,c.height)
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high' as any
  ctx.drawImage(img, crop.x, crop.y, img.width * crop.scale, img.height * crop.scale)
}

function onRange(e: Event) {
  const next = clamp(Number((e.target as HTMLInputElement).value), crop.min, crop.max)
  scaleTo(next)
}

function clampPosition() {
  const c = canvasEl.value!, img = crop.img!
  const w = img.width * crop.scale, h = img.height * crop.scale
  crop.x = w <= c.width  ? (c.width - w)/2  : Math.min(0, Math.max(c.width - w, crop.x))
  crop.y = h <= c.height ? (c.height - h)/2 : Math.min(0, Math.max(c.height - h, crop.y))
}

function dragStart(ev: MouseEvent) {
  crop.dragging = true
  crop.sx = ev.clientX - crop.x
  crop.sy = ev.clientY - crop.y
}

function dragMove(ev: MouseEvent) {
  if (!crop.dragging) return
  crop.x = ev.clientX - crop.sx
  crop.y = ev.clientY - crop.sy
  clampPosition()
  redraw()
}

function dragStop() {
  crop.dragging = false
}

function onWheel(ev: WheelEvent) {
  const dir = ev.deltaY > 0 ? -1 : 1
  const next = Math.min(crop.max, Math.max(crop.min, crop.scale * (1 + dir * 0.04)))
  if (next === crop.scale) return
  scaleTo(next)
}

function cancelCrop() {
  crop.show = false
  crop.img = undefined
  document.body.style.overflow = ''
}

async function applyCrop() {
  if (!canvasEl.value) return
  busyAva.value = true
  try {
    const OUT = 512
    const dpr = 1
    const src = canvasEl.value
    const tmp = document.createElement('canvas')
    tmp.width = OUT * dpr
    tmp.height = OUT * dpr
    const tctx = tmp.getContext('2d')!
    const img = crop.img!
    tctx.imageSmoothingEnabled = true
    tctx.imageSmoothingQuality = 'high' as any
    const k = (tmp.width / src.width)
    tctx.drawImage(img, crop.x * k, crop.y * k, img.width * crop.scale * k, img.height * crop.scale * k)
    const blob: Blob = await new Promise((res, rej) => tmp.toBlob(b => b ? res(b) : rej(new Error('toBlob')), crop.type === 'image/png' ? 'image/png' : 'image/jpeg', 0.92))
    if (blob.size > 5 * 1024 * 1024) {
      void alertDialog('Получившийся файл оказался больше 5 Мбайт')
      return
    }
    const fd = new FormData()
    fd.append('file', new File([blob], crop.type === 'image/png' ? 'avatar.png' : 'avatar.jpg', { type: crop.type }))
    const { data } = await api.post('/users/avatar', fd)
    me.avatar_name = data.avatar_name || null
    userStore.setAvatarName(me.avatar_name)
    cancelCrop()
  } catch (e: any) {
    const st = e?.response?.status
    const d  = e?.response?.data?.detail
    if (st === 403 && d === 'user_banned')                 void alertDialog('Аккаунт забанен. Изменение аватара недоступно')
    else if (st === 415 || d === 'unsupported_media_type') void alertDialog('К загрузке допустимы только форматы JPG/PNG')
    else if (st === 413)                                   void alertDialog('К загрузке допустимы только файлы менее 5 Мбайт')
    else if (st === 422 && d === 'empty_file')             void alertDialog('Не удалось прочитать файл')
    else if (st === 422 && d === 'bad_image')              void alertDialog('Некорректное изображение')
    else                                                   void alertDialog('Не удалось загрузить аватар')
  } finally { busyAva.value = false }
}

async function onDeleteAvatar() {
  const ok = await confirmDialog({
    title: 'Удаление аватара',
    text: 'Вы уверены что хотите удалить аватар?',
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  busyAva.value = true
  try {
    await api.delete('/users/avatar')
    me.avatar_name = null
    userStore.setAvatarName(null)
  }
  catch (e: any) {
    const st = e?.response?.status
    const d  = e?.response?.data?.detail
    if (st === 403 && d === 'user_banned') void alertDialog('Аккаунт забанен. Изменение аватара недоступно')
    else void alertDialog('Не удалось удалить аватар')
  }
  finally { busyAva.value = false }
}

function sanitizeUsername(s: string, max = NICK_MAX): string {
  return (s ?? "").normalize("NFKC").trim().slice(0, max)
}

watch(nick, (v) => {
  const clean = sanitizeUsername(v, NICK_MAX)
  if (v !== clean) nick.value = clean
})

watch(activeTab, (tab) => {
  if (tab === 'sanctions') {
    void loadSanctions(true)
    return
  }
  if (tab === 'profile') void loadMe({ keepNickDraft: true })
})

onMounted(() => {
  loadMe().catch(() => {})
  onSanctionsUpdate = () => {
    if (activeTab.value === 'sanctions') void loadSanctions(true)
  }
  window.addEventListener('auth-sanctions_update', onSanctionsUpdate)
})

onBeforeUnmount(() => {
  if (onSanctionsUpdate) window.removeEventListener('auth-sanctions_update', onSanctionsUpdate)
  document.body.style.overflow = ''
})
</script>

<style scoped lang="scss">
.profile {
  display: flex;
  flex-direction: column;
  margin: 0 10px;
  padding: 10px;
  border-radius: 5px;
  background-color: $dark;
  overflow: auto;
  scrollbar-width: none;
  .btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 20px;
    gap: 5px;
    height: 40px;
    border: none;
    border-radius: 5px;
    background-color: $fg;
    font-size: 14px;
    color: $bg;
    font-family: Manrope-Medium;
    line-height: 1;
    text-decoration: none;
    cursor: pointer;
    transition: opacity 0.25s ease-in-out, color 0.25s ease-in-out, border-radius 0.25s ease-in-out, background-color 0.25s ease-in-out;
    &:hover {
      background-color: $white;
    }
    &.nav {
      font-size: 16px;
      border-radius: 5px 5px 0 0;
    }
    &.dark {
      background-color: $lead;
      color: $fg;
      &:hover {
        background-color: rgba($grey, 0.5);
      }
    }
    &.confirm {
      background-color: rgba($green, 0.75);
      &:hover {
        background-color: $green;
      }
    }
    &.danger {
      background-color: rgba($red, 0.75);
      color: $fg;
      &:hover {
        background-color: $red;
      }
    }
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .btn-img {
      width: 20px;
      height: 20px;
    }
  }
  header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    border-bottom: 3px solid $lead;
    .tabs {
      display: flex;
      align-items: flex-end;
      width: 80%;
      height: 30px;
      .tab {
        min-width: 150px;
        width: auto;
        padding: 0 20px;
        height: 30px;
        border: none;
        border-radius: 5px 5px 0 0;
        background-color: $graphite;
        color: $fg;
        font-size: 18px;
        font-family: Manrope-Medium;
        line-height: 1;
        cursor: pointer;
        transition: opacity 0.25s ease-in-out, height 0.25s ease-in-out, background-color 0.25s ease-in-out;
        &.active {
          height: 40px;
          background-color: $lead;
        }
        &:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      }
    }
  }
  .tab-panel {
    margin-top: 10px;
    .grid {
      display: grid;
      gap: 10px;
      grid-template-columns: 1fr 1fr 1fr;
      .block {
        border: 3px solid $lead;
        border-radius: 5px;
        padding: 15px;
        h3 {
          margin: 0 0 20px;
          font-size: 20px;
          color: $fg;
        }
        .avatar-row {
          display: flex;
          gap: 10px;
          align-items: center;
          .avatar-img {
            width: 115px;
            height: 115px;
            object-fit: cover;
            border-radius: 50%;
          }
          .actions {
            display: flex;
            flex-direction: column;
            gap: 10px;
          }
        }
        .nick-row {
          display: flex;
          align-items: center;
          margin-bottom: 5px;
          gap: 10px;
          .ui-input {
            flex: 1 1 auto;
            max-width: 320px;
            display: block;
            position: relative;
            width: 100%;
            box-shadow: 3px 3px 5px rgba($black, 0.25);
            input {
              width: calc(100% - 22px);
              padding: 20px 10px 5px;
              border: 1px solid $lead;
              border-radius: 5px 5px 0 0;
              background-color: $graphite;
              color: $fg;
              font-size: 16px;
              font-family: Manrope-Medium;
              line-height: 1;
              outline: none;
              transition: border-color 0.25s ease-in-out, background-color 0.25s ease-in-out;
            }
            input::placeholder {
              color: transparent;
            }
            label {
              position: absolute;
              top: 50%;
              left: 12px;
              color: $fg;
              transform: translateY(-50%);
              pointer-events: none;
              transition: all 0.25s ease-in-out;
            }
            .underline {
              position: absolute;
              left: 0;
              right: 0;
              bottom: -3px;
              height: 3px;
              border-radius: 0 0 3px 3px;
              overflow: hidden;
              span {
                position: absolute;
                left: 0;
                bottom: 0;
                height: 3px;
                width: 0;
                background-color: $fg;
                transition: width 0.25s ease-in-out;
              }
            }
            .underline::before {
              content: "";
              position: absolute;
              inset: 0;
              background-color: $lead;
              transition: background-color 0.25s ease-in-out;
            }
            .meta {
              position: absolute;
              top: 5px;
              right: 10px;
              pointer-events: none;
              span {
                font-size: 12px;
                color: $grey;
              }
            }
            &.invalid input {
              border-color: rgba($red, 0.75);
            }
            &.invalid label {
              color: $red;
            }
            &.invalid .underline::before {
              background-color: rgba($red, 0.75);
            }
          }
          .ui-input:focus-within label,
          .ui-input input:not(:placeholder-shown) + label,
          .ui-input.filled label {
            top: 5px;
            left: 10px;
            transform: none;
            font-size: 12px;
            color: $grey;
          }
        }
        .danger-row {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 10px;
        }
        .danger-text {
          margin: 0;
          color: $red;
          font-size: 14px;
        }
        .hint {
          color: $grey;
          font-size: 14px;
          text-align: center;
        }
        &.sanctions-block {
          .sanctions-head {
            display: flex;
            flex-wrap: wrap;
            align-items: flex-start;
            justify-content: space-between;
            gap: 10px;
          }
          .sanctions-summary {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            font-size: 14px;
            color: $fg;
          }
          .sanctions-empty {
            padding: 20px 0;
            color: $ashy;
            &.danger {
              color: $red;
            }
          }
          .sanctions-list {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
            .sanction-card {
              border: 3px solid $lead;
              border-radius: 5px;
              padding: 10px;
              &.sanction-card--timeout {
                border-color: rgba($yellow, 0.5);
                background-color: rgba($yellow, 0.25);
              }
              &.sanction-card--suspend {
                border-color: rgba($orange, 0.5);
                background-color: rgba($orange, 0.25);
              }
              &.sanction-card--ban {
                border-color: rgba($red, 0.5);
                background-color: rgba($red, 0.25);
              }
              .sanction-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                .sanction-kind {
                  display: flex;
                  align-items: center;
                  gap: 5px;
                  flex-wrap: wrap;
                  .sanction-tag {
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    padding: 5px 10px;
                    min-width: 30px;
                    border-radius: 999px;
                    background-color: $dark;
                    font-size: 12px;
                    color: $fg;
                  }
                  .sanction-status {
                    font-size: 12px;
                    color: $grey;
                    &.status--active {
                      color: $orange;
                    }
                    &.status--ended {
                      color: $green;
                    }
                    &.status--revoked {
                      color: $ashy;
                    }
                  }
                }
                .sanction-issued {
                  font-size: 12px;
                  color: $ashy;
                  white-space: nowrap;
                }
              }
              .sanction-reason {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 5px 10px;
                min-width: 30px;
                border-radius: 5px;
                background-color: $graphite;
                margin-top: 5px;
                font-size: 14px;
                color: $fg;
              }
              .sanction-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 10px 0;
                margin-top: 10px;
                .sanction-cell {
                  display: flex;
                  flex-direction: column;
                  gap: 3px;
                  font-size: 14px;
                  span {
                    color: $ashy;
                    font-size: 12px;
                  }
                  strong {
                    color: $fg;
                  }
                }
              }
            }
          }
        }
      }
      .modal {
        display: flex;
        position: fixed;
        align-items: center;
        justify-content: center;
        inset: 0;
        background-color: rgba($black, 0.75);
        backdrop-filter: blur(5px);
        overscroll-behavior: contain;
        z-index: 50;
        .modal-body {
          display: flex;
          flex-direction: column;
          padding: 10px;
          gap: 10px;
          border: 1px solid $graphite;
          border-radius: 5px;
          background-color: $dark;
          canvas {
            align-self: center;
            width: 200px;
            height: 200px;
            border-radius: 5px;
            background-color: $black;
          }
          .range {
            display: flex;
            flex-direction: column;
            gap: 5px;
            .range-wrap {
              position: relative;
              height: 20px;
              box-shadow: 3px 3px 5px rgba($black, 0.25);
              .range-track {
                position: absolute;
                inset: 0;
                border-radius: 5px;
                border: 1px solid $lead;
                background-color: $graphite;
                overflow: hidden;
              }
              .range-track::after {
                content: "";
                position: absolute;
                inset: 0 auto 0 0;
                width: var(--fill);
                background-color: $fg;
                border-radius: inherit;
                transition: width 0.25s ease-in-out;
                will-change: width;
              }
              .range-native {
                position: absolute;
                inset: 0;
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                background: none;
                cursor: pointer;
                z-index: 2;
                -webkit-appearance: none;
                appearance: none;
              }
              .range-native::-webkit-slider-runnable-track {
                background: transparent;
                height: 100%;
              }
              .range-native::-moz-range-track {
                background: transparent;
                height: 100%;
              }
              .range-native::-ms-track {
                background: transparent;
                color: transparent;
                border: none;
                height: 100%;
              }
              .range-native::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 1px;
                height: 100%;
                background: transparent;
                border: none;
              }
              .range-native::-moz-range-thumb {
                width: 1px;
                height: 100%;
                background: transparent;
                border: none;
              }
              .range-native:focus-visible {
                outline: 2px solid $lead;
                outline-offset: 2px;
              }
              .range-native:disabled {
                cursor: not-allowed;
              }
            }
          }
          .modal-actions {
            display: flex;
            justify-content: space-between;
            gap: 10px;
          }
        }
      }
      &.grid-sanctions {
        grid-template-columns: 1fr;
      }
    }
    .grid-empty {
      min-height: 200px;
    }
  }
}

.tab-fade-enter-active,
.tab-fade-leave-active {
  transition: opacity 0.15s ease-in-out;
}
.tab-fade-enter-from,
.tab-fade-leave-to {
  opacity: 0;
}

@media (max-width: 1280px) {
  .profile {
    .btn {
      padding: 0 10px;
      &.nav {
        font-size: 14px;
      }
    }
    header {
      .tabs {
        .tab {
          min-width: 125px;
          padding: 0 10px;
          font-size: 14px;
        }
      }
    }
    .tab-panel {
      .grid {
        grid-template-columns: 1fr 1fr;
        .block {
          &.sanctions-block {
            .sanctions-list {
              grid-template-columns: 1fr 1fr;
            }
          }
        }
      }
    }
  }
}
</style>

