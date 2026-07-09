<template>
  <section class="block-profile">
    <div class="avatar">
      <span class="title">Аватар</span>
      <div class="avatar-row">
        <img class="avatar-img" v-minio-img="{ key: me.avatar_name ? `avatars/${me.avatar_name}` : '', placeholder: iconDefaultAvatar, lazy: false, animated: true }" alt="Текущий аватар" />
        <button class="btn-delete" v-if="me.avatar_name" @click="onDeleteAvatar" :disabled="busyAva || isBanned">
          <UiIcon class="btn-img-delete" :icon="iconClose" />
        </button>
      </div>
      <div class="avatar-upload">
        <input ref="fileEl" type="file" :accept="avatarAccept" @change="onPick" :disabled="avatarUploadDisabled" hidden />
        <button class="btn-upload" type="button" :class="{ 'drag-active': avatarDragActive }" :disabled="avatarUploadDisabled" @click="fileEl?.click()"
                @dragenter.prevent="onAvatarDragEnter" @dragover.prevent="onAvatarDragOver" @dragleave.prevent="onAvatarDragLeave" @drop.prevent="onAvatarDrop">
          <div class="btn-img-div">
            <UiIcon class="btn-img-upload" :icon="iconDownload" />
          </div>
          <span class="text">{{ avatarDragActive ? 'Отпустите изображение' : 'Нажмите или перетащите файл сюда' }}</span>
          <span class="hint">{{ avatarFormatHint }}</span>
        </button>
      </div>
    </div>

    <div class="profile-details">
      <div class="nickname">
        <div class="nickname-div">
          <div class="nickname-title">
            <span class="title">Никнейм</span>
            <span class="hint">Никнейм также является логином для авторизации</span>
          </div>
          <span class="nickname-changes">{{ nicknameChangesText }}</span>
        </div>
        <div class="nick-row">
          <div class="nick-input-line">
            <UiInput
              class="profile-input"
              id="profile-nick"
              v-model.trim="nick"
              :maxlength="NICK_MAX"
              :disabled="busyNick || isBanned"
              autocomplete="off"
              inputmode="text"
              label="Никнейм"
              :invalid="!!nick && !validNick"
              :aria-invalid="!!nick && !validNick"
              aria-describedby="profile-nick-hint"
            >
              <template #meta>
                <span id="profile-nick-hint">{{ nick.length }}/{{ NICK_MAX }}</span>
              </template>
            </UiInput>
          </div>
          <span class="hint"><code>латиница, кириллица, цифры, символы ()._-</code></span>
          <button class="btn confirm" @click="saveNick" :disabled="saveNickDisabled">
            {{ busyNick ? '...' : 'Сохранить' }}
          </button>
        </div>
      </div>

      <div class="nickname-history" aria-labelledby="nickname-history-title">
        <div class="nickname-history-header">
          <span id="nickname-history-title" class="nickname-history-title">История никнеймов</span>
          <button class="btn danger nickname-history-clear" type="button" :disabled="nicknameHistoryClearDisabled" @click="clearNicknameHistory">
            {{ nicknameHistoryClearBusy ? '...' : 'Очистить историю' }}
          </button>
        </div>
        <span class="nickname-history-access-text" :class="{ disabled: !canEditProfileTheme }">{{ nicknameHistoryAccessText }}</span>
        <span class="nickname-history-divider" aria-hidden="true"></span>
        <span v-if="nicknameHistoryLoading" class="nickname-history-state">Загрузка...</span>
        <div v-else-if="nicknameHistoryError" class="nickname-history-error">
          <span class="nickname-history-state danger">{{ nicknameHistoryError }}</span>
          <button class="btn dark nickname-history-retry" type="button" @click="loadNicknameHistory(true)">Повторить</button>
        </div>
        <div v-else class="nickname-history-list">
          <span v-for="(nicknameItem, index) in nicknameHistoryItems" :key="`${nicknameItem}-${index}`" :class="{ current: index === 0 }">
            {{ nicknameItem }}
          </span>
          <span v-if="!nicknameHistoryItems.length" class="nickname-history-state">-</span>
        </div>
      </div>
    </div>

    <div v-if="crop.show" ref="modalEl" class="modal" @keydown.esc="cancelCrop" tabindex="0" aria-modal="true" aria-label="Кадрирование аватара" >
      <div class="modal-body">
        <canvas ref="canvasEl" @mousedown="dragStart" @mousemove="dragMove" @mouseup="dragStop" @mouseleave="dragStop" @wheel.passive="onWheel" />
        <div class="range">
          <span>Масштаб</span>
          <UiSlider
            :model-value="crop.scale"
            :min="crop.min"
            :max="crop.max"
            :step="0.01"
            :disabled="isBanned"
            aria-label="Масштаб"
            @update:modelValue="scaleTo"
          />
        </div>
        <div class="modal-actions">
          <button class="btn danger" @click="cancelCrop">Отменить</button>
          <button class="btn confirm" @click="applyCrop" :disabled="busyAva || isBanned">Загрузить</button>
        </div>
      </div>
    </div>

    <div v-if="gifPicker.show" ref="gifModalEl" class="modal gif-modal" @keydown.esc="cancelGifPicker" tabindex="0" aria-modal="true" aria-label="Выбор статичного кадра GIF">
      <div class="modal-body gif-modal-body">
        <div class="gif-preview-row">
          <div class="gif-preview-block">
            <span>Анимация</span>
            <img v-if="gifPicker.animatedUrl" :src="gifPicker.animatedUrl" alt="GIF-анимация" />
          </div>
          <div class="gif-preview-block">
            <span>Статичный кадр</span>
            <canvas ref="gifCanvasEl" />
          </div>
        </div>
        <p v-if="gifPicker.error" class="hint red">{{ gifPicker.error }}</p>
        <div class="range">
          <span>Кадр {{ gifFrameLabel }}</span>
          <UiSlider
            :model-value="gifPicker.frameIndex"
            :min="0"
            :max="Math.max(0, gifPicker.frameCount - 1)"
            :step="1"
            :disabled="busyAva || isBanned || gifPicker.frameCount <= 1 || gifPicker.decoding"
            aria-label="Кадр GIF"
            @update:modelValue="onGifFrameRange"
          />
        </div>
        <div class="modal-actions">
          <button class="btn danger" @click="cancelGifPicker">Отменить</button>
          <button class="btn confirm" @click="applyGifPicker" :disabled="busyAva || isBanned || gifPicker.loading || gifPicker.decoding || !!gifPicker.error">Загрузить</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api, refreshAccessTokenFull } from '@/services/axios'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { formatModerationAlert } from '@/services/moderation'
import { useUserStore } from '@/store'

import UiInput from '@/components/UiInput.vue'
import UiSlider from '@/components/UiSlider.vue'
import UiIcon from '@/components/UiIcon.vue'

import iconDefaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconDownload from '@/assets/svg/iconDownload.svg'
import iconClose from '@/assets/svg/iconClose.svg'

const NICK_MAX = 20
const NICKNAME_CHANGES_MAX = 30
const AVATAR_MAX_BYTES = 5 * 1024 * 1024
const MAX_AVATAR_GIF_FRAMES = 300
const CROP_CANVAS_DESKTOP_SIZE = 400
const CROP_CANVAS_MOBILE_SIZE = 200
const CROP_CANVAS_MOBILE_QUERY = '(max-width: 1280px)'
const STATIC_AVATAR_TYPES = new Set(['image/jpeg', 'image/png'])
const ANIMATED_AVATAR_TYPE = 'image/gif'

type NicknameHistoryResponse = {
  items?: string[] | null
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

type GifPicker = {
  show: boolean
  file?: File
  animatedUrl: string
  frameCount: number
  frameIndex: number
  loading: boolean
  decoding: boolean
  error: string
}

const userStore = useUserStore()
const me = reactive({
  id: 0,
  username: '',
  avatar_name: null as string | null,
  protected_user: false,
  subscription_active: false,
  subscription_until: null as string | null,
  nickname_changes_left: 0,
})
const fileEl = ref<HTMLInputElement | null>(null)
const modalEl = ref<HTMLDivElement | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)
const gifModalEl = ref<HTMLDivElement | null>(null)
const gifCanvasEl = ref<HTMLCanvasElement | null>(null)
const nick = ref('')
const busyNick = ref(false)
const busyAva = ref(false)
const avatarDragActive = ref(false)
const nicknameHistoryLoading = ref(false)
const nicknameHistoryError = ref('')
const nicknameHistoryItems = ref<string[]>([])
const nicknameHistoryLoaded = ref(false)
const nicknameHistoryClearBusy = ref(false)
const crop = reactive<Crop>({ show: false, scale: 1, min: 0.5, max: 3, x: 0, y: 0, dragging: false, sx: 0, sy: 0, type: 'image/jpeg' })
const gifPicker = reactive<GifPicker>({
  show: false,
  animatedUrl: '',
  frameCount: 1,
  frameIndex: 0,
  loading: false,
  decoding: false,
  error: '',
})
let nicknameHistorySeq = 0
let avatarDragDepth = 0
let gifDecoder: any = null
let gifDecodeSeq = 0
let onProfileSync: ((e: Event) => void) | null = null

const isBanned = computed(() => userStore.banActive)
const avatarUploadDisabled = computed(() => busyAva.value || isBanned.value)
const isProtectedAdminSelf = computed(() => Boolean(me.protected_user))
const validNick = computed(() => {
  const value = nick.value
  const ok = new RegExp(`^[a-zA-Zа-яА-ЯёЁ0-9._\\-()]{2,${NICK_MAX}}$`).test(value)
  if (!ok) return false
  const lower = value.toLowerCase()
  return !lower.startsWith('deleted_') && !lower.startsWith('user_')
})
const nicknameChangesLeft = computed(() => normalizeNicknameChangesLeft(me.nickname_changes_left))
const nicknameChangesText = computed(() => {
  const value = nicknameChangesLeft.value
  if (value === 0) return 'Изменение никнейма недоступно'
  const lastTwoDigits = value % 100
  if (lastTwoDigits >= 11 && lastTwoDigits <= 14) return `Доступно ещё ${value} изменений никнейма`
  const lastDigit = value % 10
  if (lastDigit === 1) return `Доступно ещё ${value} изменение никнейма`
  if (lastDigit >= 2 && lastDigit <= 4) return `Доступно ещё ${value} изменения никнейма`
  return `Доступно ещё ${value} изменений никнейма`
})
const saveNickDisabled = computed(() => (
  busyNick.value
  || isBanned.value
  || nick.value === me.username
  || !validNick.value
  || (!isProtectedAdminSelf.value && nicknameChangesLeft.value <= 0)
))
const subscriptionUntilMs = computed(() => parseDateMs(me.subscription_until))
const hasActiveSubscription = computed(() => {
  if (subscriptionUntilMs.value > 0) return subscriptionUntilMs.value > userStore.now
  return Boolean(me.subscription_active)
})
const canEditProfileTheme = computed(() => hasActiveSubscription.value)
const canUseAnimatedAvatar = computed(() => canEditProfileTheme.value)
const avatarAccept = computed(() => (
  canUseAnimatedAvatar.value ? 'image/jpeg,image/png,image/gif' : 'image/jpeg,image/png'
))
const avatarFormatHint = computed(() => (
  canUseAnimatedAvatar.value ? 'JPG, PNG или GIF (до 5 Мб)' : 'JPG или PNG (до 5 Мб)'
))
const profileThemeAvailabilityText = computed(() => {
  const raw = me.subscription_until
  if (!raw) return 'Доступно, пока активна подписка'
  const dt = new Date(raw)
  if (Number.isNaN(dt.getTime())) return 'Доступно, пока активна подписка'
  return `Доступно для Вас до ${dt.toLocaleDateString('ru-RU')}`
})
const nicknameHistoryAccessText = computed(() => (
  canEditProfileTheme.value
    ? profileThemeAvailabilityText.value
    : 'Очистка истории никнеймов доступна только при наличии подписки'
))
const nicknameHistoryHasDeletableItems = computed(() => nicknameHistoryItems.value.length > 1)
const nicknameHistoryClearDisabled = computed(() => (
  nicknameHistoryClearBusy.value
  || nicknameHistoryLoading.value
  || !nicknameHistoryLoaded.value
  || isBanned.value
  || !canEditProfileTheme.value
))
const gifFrameLabel = computed(() => `${gifPicker.frameIndex + 1}/${Math.max(1, gifPicker.frameCount)}`)

function parseDateMs(raw: string | null | undefined): number {
  if (!raw) return 0
  const ts = Date.parse(raw)
  return Number.isFinite(ts) ? ts : 0
}

function normalizeNicknameChangesLeft(raw: unknown): number {
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? Math.min(NICKNAME_CHANGES_MAX, Math.max(0, Math.floor(parsed))) : 0
}

function applyMePayload(data: any, options: { keepNickDraft?: boolean } = {}) {
  const prevUserId = me.id
  const prevUsername = me.username
  me.id = Number(data?.id || 0)
  me.username = data?.username || ''
  me.avatar_name = data?.avatar_name || null
  me.protected_user = Boolean(data?.protected_user)
  me.subscription_active = Boolean(data?.subscription_active)
  me.subscription_until = data?.subscription_until || null
  me.nickname_changes_left = normalizeNicknameChangesLeft(data?.nickname_changes_left)
  const hasNickDraft = Boolean(options.keepNickDraft) && nick.value !== prevUsername
  if (!hasNickDraft) nick.value = me.username
  if (me.id !== prevUserId || me.username !== prevUsername) {
    resetNicknameHistory()
    if (me.id > 0) void loadNicknameHistory()
  }
}

async function loadMe(options: { keepNickDraft?: boolean } = {}) {
  const { data } = await api.get('/users/profile_info')
  applyMePayload(data, { keepNickDraft: options.keepNickDraft })
  userStore.applyProfile(data)
}

function normalizeNicknameHistoryItems(items: string[] | null | undefined): string[] {
  return Array.isArray(items)
    ? items.map((item) => String(item || '').trim()).filter(Boolean)
    : []
}

function resetNicknameHistory() {
  nicknameHistorySeq += 1
  nicknameHistoryLoading.value = false
  nicknameHistoryError.value = ''
  nicknameHistoryItems.value = []
  nicknameHistoryLoaded.value = false
}

async function loadNicknameHistory(force = false) {
  if (me.id <= 0 || nicknameHistoryLoading.value) return
  if (nicknameHistoryLoaded.value && !force) return

  const seq = ++nicknameHistorySeq
  nicknameHistoryLoading.value = true
  nicknameHistoryError.value = ''
  try {
    const { data } = await api.get<NicknameHistoryResponse>(`/users/${me.id}/nickname_history`)
    if (seq !== nicknameHistorySeq) return
    nicknameHistoryItems.value = normalizeNicknameHistoryItems(data?.items)
    nicknameHistoryLoaded.value = true
  } catch {
    if (seq !== nicknameHistorySeq) return
    nicknameHistoryError.value = 'Не удалось загрузить историю'
  } finally {
    if (seq === nicknameHistorySeq) nicknameHistoryLoading.value = false
  }
}

async function clearNicknameHistory() {
  if (nicknameHistoryClearDisabled.value) return
  if (!nicknameHistoryHasDeletableItems.value) {
    void alertDialog('История никнеймов уже пуста')
    return
  }

  const ok = await confirmDialog({
    title: 'Очистить историю никнеймов',
    text: 'Вы уверены, что хотите очистить историю никнеймов, оставив только текущий никнейм?',
    confirmText: 'Подтвердить',
    cancelText: 'Отмена',
  })
  if (!ok) return

  nicknameHistoryClearBusy.value = true
  try {
    const { data } = await api.delete<NicknameHistoryResponse>('/users/nickname_history')
    nicknameHistoryItems.value = normalizeNicknameHistoryItems(data?.items)
    nicknameHistoryLoaded.value = true
    void alertDialog('История никнеймов успешно очищена')
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 403 && d === 'subscription_required') {
      void loadMe({ keepNickDraft: true }).catch(() => {})
      void alertDialog('Очистка истории никнеймов доступна только при активной подписке')
    } else if (st === 403 && d === 'user_banned') {
      void alertDialog('Аккаунт забанен. Очистка истории никнеймов недоступна')
    } else if (st === 403 && d === 'user_deleted') {
      void alertDialog('Аккаунт удален. Очистка истории никнеймов недоступна')
    } else {
      void alertDialog('Не удалось очистить историю никнеймов')
    }
  } finally {
    nicknameHistoryClearBusy.value = false
  }
}

async function saveNick() {
  if (saveNickDisabled.value) return
  busyNick.value = true
  try {
    const { data } = await api.patch('/users/username', { username: nick.value })
    me.username = data.username
    me.nickname_changes_left = normalizeNicknameChangesLeft(data?.nickname_changes_left)
    userStore.setUsername(data.username)
    userStore.setNicknameChangesLeft(me.nickname_changes_left)
    resetNicknameHistory()
    void loadNicknameHistory()
    try { await refreshAccessTokenFull(false) } catch {}
  } catch (e: any) {
    const st = e?.response?.status
    const d  = e?.response?.data?.detail
    const moderationText = formatModerationAlert(d)
    if (st === 409 && d === 'username_taken')               void alertDialog('Данный никнейм уже занят')
    else if (st === 403 && d === 'user_banned')             void alertDialog('Аккаунт забанен. Изменение никнейма недоступно')
    else if (st === 403 && d === 'protected_user')          void alertDialog('Администратору нельзя изменять свой никнейм')
    else if (st === 403 && d === 'nickname_change_limit_exhausted') {
      me.nickname_changes_left = 0
      userStore.setNicknameChangesLeft(0)
      void alertDialog('Лимит изменений никнейма исчерпан')
    }
    else if (st === 422 && moderationText)                  void alertDialog({ title: 'Отказ в сохранении', text: moderationText })
    else if (st === 422 && d === 'invalid_username_format') void alertDialog('Никнейм не должен начинаться с deleted_ или user_ и не должен содержать символы кроме ()._-')
    else                                                    void alertDialog('Не удалось сохранить никнейм')
  } finally { busyNick.value = false }
}

function clamp(v:number, lo:number, hi:number) { return Math.min(hi, Math.max(lo, v)) }

function fitContain(imgW: number, imgH: number, boxW: number, boxH: number) {
  return Math.min(boxW / imgW, boxH / imgH)
}

function cropCanvasDisplaySize(): number {
  return window.matchMedia(CROP_CANVAS_MOBILE_QUERY).matches
    ? CROP_CANVAS_MOBILE_SIZE
    : CROP_CANVAS_DESKTOP_SIZE
}

function gifCanvasDisplaySize(canvas: HTMLCanvasElement): number {
  canvas.style.width = ''
  canvas.style.height = ''
  const cssWidth = Number.parseFloat(window.getComputedStyle(canvas).width)
  return Number.isFinite(cssWidth) && cssWidth > 0 ? Math.round(cssWidth) : 300
}

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

function closeGifDecoder() {
  try { gifDecoder?.close?.() } catch {}
  gifDecoder = null
}

function resetGifPicker() {
  closeGifDecoder()
  gifDecodeSeq += 1
  if (gifPicker.animatedUrl) {
    try { URL.revokeObjectURL(gifPicker.animatedUrl) } catch {}
  }
  gifPicker.show = false
  gifPicker.file = undefined
  gifPicker.animatedUrl = ''
  gifPicker.frameCount = 1
  gifPicker.frameIndex = 0
  gifPicker.loading = false
  gifPicker.decoding = false
  gifPicker.error = ''
}

function cancelGifPicker() {
  resetGifPicker()
  document.body.style.overflow = ''
}

async function drawGifFrame(frameIndex: number) {
  const decoder = gifDecoder
  if (!decoder || !gifCanvasEl.value) return
  const seq = ++gifDecodeSeq
  gifPicker.decoding = true
  try {
    const decoded = await decoder.decode({ frameIndex })
    const image = decoded?.image
    if (!image) throw new Error('decode_failed')
    if (seq !== gifDecodeSeq) {
      try { image.close?.() } catch {}
      return
    }

    const canvas = gifCanvasEl.value
    const dpr = Math.max(1, window.devicePixelRatio || 1)
    const size = gifCanvasDisplaySize(canvas)
    canvas.width = Math.round(size * dpr)
    canvas.height = Math.round(size * dpr)

    const width = Number(image.displayWidth || image.codedWidth || image.width || 1)
    const height = Number(image.displayHeight || image.codedHeight || image.height || 1)
    const scale = Math.min(canvas.width / width, canvas.height / height)
    const drawW = width * scale
    const drawH = height * scale
    const dx = (canvas.width - drawW) / 2
    const dy = (canvas.height - drawH) / 2
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.fillStyle = '#000'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.imageSmoothingEnabled = true
    ctx.imageSmoothingQuality = 'high' as any
    ctx.drawImage(image as CanvasImageSource, dx, dy, drawW, drawH)
    try { image.close?.() } catch {}
  } catch {
    if (seq === gifDecodeSeq) gifPicker.error = 'Не удалось показать выбранный кадр GIF'
  } finally {
    if (seq === gifDecodeSeq) gifPicker.decoding = false
  }
}

async function openGifFramePicker(file: File) {
  const ImageDecoderCtor = (window as any).ImageDecoder
  if (!ImageDecoderCtor) {
    await alertDialog('В этом браузере недоступен выбор кадра GIF. Будет использован первый кадр.')
    await uploadAvatarFile(file, 0)
    return
  }

  resetGifPicker()
  gifPicker.file = file
  gifPicker.animatedUrl = URL.createObjectURL(file)
  gifPicker.show = true
  gifPicker.loading = true
  document.body.style.overflow = 'hidden'
  await nextTick()
  gifModalEl.value?.focus()

  try {
    const buffer = await file.arrayBuffer()
    const decoder = new ImageDecoderCtor({ data: buffer, type: file.type || ANIMATED_AVATAR_TYPE })
    if (decoder.tracks?.ready) await decoder.tracks.ready
    const track = decoder.tracks?.selectedTrack
    const frameCountRaw = Number(track?.frameCount || 1)
    if (!Number.isFinite(frameCountRaw) || frameCountRaw <= 0) throw new Error('bad_frame_count')
    if (frameCountRaw > MAX_AVATAR_GIF_FRAMES) throw new Error('too_many_frames')
    gifDecoder = decoder
    gifPicker.frameCount = Math.max(1, Math.trunc(frameCountRaw))
    gifPicker.frameIndex = 0
    gifPicker.loading = false
    await nextTick()
    await drawGifFrame(0)
  } catch (e: any) {
    closeGifDecoder()
    gifPicker.loading = false
    gifPicker.error = e?.message === 'too_many_frames'
      ? `В GIF больше ${MAX_AVATAR_GIF_FRAMES} кадров`
      : 'Не удалось прочитать кадры GIF'
  }
}

function onGifFrameRange(value: number) {
  const next = clamp(Math.trunc(Number(value)), 0, Math.max(0, gifPicker.frameCount - 1))
  gifPicker.frameIndex = next
  void drawGifFrame(next)
}

async function applyGifPicker() {
  if (!gifPicker.file || gifPicker.loading || gifPicker.decoding || gifPicker.error) return
  const ok = await uploadAvatarFile(gifPicker.file, gifPicker.frameIndex)
  if (ok) cancelGifPicker()
}

function isAvatarFileDrag(event: DragEvent): boolean {
  return Array.from(event.dataTransfer?.types || []).includes('Files')
}

function resetAvatarDragState() {
  avatarDragDepth = 0
  avatarDragActive.value = false
}

function onAvatarDragEnter(event: DragEvent) {
  if (avatarUploadDisabled.value || !isAvatarFileDrag(event)) return
  avatarDragDepth += 1
  avatarDragActive.value = true
}

function onAvatarDragOver(event: DragEvent) {
  if (avatarUploadDisabled.value || !isAvatarFileDrag(event) || !event.dataTransfer) return
  event.dataTransfer.dropEffect = 'copy'
}

function onAvatarDragLeave() {
  avatarDragDepth = Math.max(0, avatarDragDepth - 1)
  avatarDragActive.value = avatarDragDepth > 0
}

async function onAvatarDrop(event: DragEvent) {
  const file = event.dataTransfer?.files?.[0]
  resetAvatarDragState()
  if (avatarUploadDisabled.value || !file) return
  await handleAvatarFile(file)
}

async function handleAvatarFile(file: File) {
  if (avatarUploadDisabled.value) return
  if (!STATIC_AVATAR_TYPES.has(file.type) && file.type !== ANIMATED_AVATAR_TYPE) {
    void alertDialog('К загрузке допустимы только форматы JPG/PNG/GIF')
    return
  }
  if (file.size > AVATAR_MAX_BYTES) {
    void alertDialog('К загрузке допустимы только файлы менее 5 Мбайт')
    return
  }
  if (file.type === ANIMATED_AVATAR_TYPE) {
    if (!canUseAnimatedAvatar.value) {
      void alertDialog('GIF-аватары доступны только при активной подписке')
      return
    }
    await openGifFramePicker(file)
    return
  }
  const url = URL.createObjectURL(file)
  const img = new Image()
  img.onload = async () => {
    URL.revokeObjectURL(url)
    crop.img = img
    crop.type = (file.type === 'image/png' ? 'image/png' : 'image/jpeg')
    crop.show = true
    await nextTick()
    modalEl.value?.focus()
    document.body.style.overflow = 'hidden'
    const canvas = canvasEl.value!
    const dpr = Math.max(1, window.devicePixelRatio || 1)
    const S = cropCanvasDisplaySize()
    canvas.width = Math.round(S * dpr)
    canvas.height = Math.round(S * dpr)
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

async function onPick(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  await handleAvatarFile(file)
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

function showAvatarUploadError(e: any) {
  const st = e?.response?.status
  const d  = e?.response?.data?.detail
  if (st === 403 && d === 'user_banned')                 void alertDialog('Аккаунт забанен. Изменение аватара недоступно')
  else if (st === 403 && d === 'subscription_required')  void alertDialog('GIF-аватары доступны только при активной подписке')
  else if (st === 415 || d === 'unsupported_media_type') void alertDialog('К загрузке допустимы только форматы JPG/PNG/GIF')
  else if (st === 413)                                   void alertDialog('К загрузке допустимы только файлы менее 5 Мбайт')
  else if (st === 422 && d === 'empty_file')             void alertDialog('Не удалось прочитать файл')
  else if (st === 422 && d === 'bad_image')              void alertDialog('Некорректное изображение')
  else                                                   void alertDialog('Не удалось загрузить аватар')
}

async function uploadAvatarFile(file: File, staticFrameIndex?: number): Promise<boolean> {
  busyAva.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    if (typeof staticFrameIndex === 'number') fd.append('static_frame_index', String(Math.max(0, Math.trunc(staticFrameIndex))))
    const { data } = await api.post('/users/avatar', fd)
    me.avatar_name = data.avatar_name || null
    userStore.setAvatarName(me.avatar_name)
    return true
  } catch (e: any) {
    showAvatarUploadError(e)
    return false
  } finally {
    busyAva.value = false
  }
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
    if (blob.size > AVATAR_MAX_BYTES) {
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
    showAvatarUploadError(e)
  } finally { busyAva.value = false }
}

async function onDeleteAvatar() {
  const ok = await confirmDialog({
    title: 'Удаление аватара',
    text: 'Вы уверены, что хотите удалить аватар?',
    confirmText: 'Подтвердить',
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

onMounted(() => {
  void loadMe()
  onProfileSync = (e: Event) => {
    const payload = (e as CustomEvent)?.detail
    if (!payload) return
    applyMePayload(payload, { keepNickDraft: true })
  }
  window.addEventListener('auth-profile_sync', onProfileSync)
})

onBeforeUnmount(() => {
  if (onProfileSync) window.removeEventListener('auth-profile_sync', onProfileSync)
  resetGifPicker()
  document.body.style.overflow = ''
})
</script>

<style scoped lang="scss">
.block-profile {
  display: flex;
  gap: 10px;
  width: 100%;
  .avatar {
    display: flex;
    box-sizing: border-box;
    flex-direction: column;
    padding: 24px;
    gap: 40px;
    width: calc(50% - 5px);
    height: 578px;
    border-radius: 24px;
    background-color: $soft-purple-900;
    .title {
      color: $neutral-white;
      font-family: Involve-Medium;
      font-size: 24px;
      line-height: 26px;
      letter-spacing: -0.48px;
    }
    .avatar-row {
      display: flex;
      position: relative;
      align-self: center;
      .avatar-img {
        width: 256px;
        height: 256px;
        border-radius: 50%;
        object-fit: cover;
      }
      .btn-delete {
        display: flex;
        position: absolute;
        align-items: center;
        justify-content: center;
        top: 0;
        right: 0;
        border: 1px solid $neutral-800;
        border-radius: 999px;
        background: none;
        width: 32px;
        height: 32px;
        cursor: pointer;
        .btn-img-delete {
          --ui-icon-width: 20px;
          --ui-icon-height: 20px;
          --ui-icon-color: #{$neutral-white};
        }
        &:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        &:not(:disabled):hover,
        &:not(:disabled):focus-visible,
        &:not(:disabled):active {
          .btn-img-delete {
            --ui-icon-color: #{$green-500};
          }
        }
      }
    }
    .avatar-upload {
      display: flex;
      width: 100%;
      height: 168px;
      .btn-upload {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 24px;
        gap: 8px;
        width: 100%;
        height: 100%;
        border: 2px dashed $neutral-600;
        border-radius: 20px;
        background-color: $soft-purple-800;
        cursor: pointer;
        transition: border-color 0.25s ease-in-out;
        &.drag-active {
          border-color: $green-500;
        }
        &:not(:disabled):hover,
        &:not(:disabled):focus-visible,
        &:not(:disabled):active {
          border-color: $green-500;
        }
        .btn-img-div {
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 8px;
          width: 64px;
          height: 64px;
          border-radius: 999px;
          background-color: rgba($soft-purple-900, 0.65);
          .btn-img-upload {
            --ui-icon-width: 40px;
            --ui-icon-height: 40px;
            --ui-icon-color: #{$green-500};
          }
        }
        .text {
          color: $neutral-white;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 16px;
          letter-spacing: -0.32px;
        }
        .hint {
          color: $neutral-300;
          font-family: Hauora-Regular;
          font-size: 14px;
          line-height: 14px;
          letter-spacing: -0.28px;
        }
      }
    }
  }
  .profile-details {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: calc(50% - 5px);
    height: 578px;
    .nickname {
      display: flex;
      box-sizing: border-box;
      flex-direction: column;
      padding: 24px;
      gap: 24px;
      height: calc(50% - 5px);
      border-radius: 24px;
      background-color: $soft-purple-900;
      --ui-input-label-bg: #{$soft-purple-900};
      .title {
        color: $neutral-white;
        font-family: Involve-Medium;
        font-size: 24px;
        line-height: 26px;
        letter-spacing: -0.48px;
      }
      .nick-row {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 16px;
        width: 100%;
        .nick-input-line {
          display: flex;
          align-items: center;
          width: 100%;
          :deep(.profile-input) {
            width: 100%;
          }
        }
        .hint {
          color: $neutral-300;
          font-family: Hauora-Regular;
          font-size: 14px;
          line-height: 14px;
          letter-spacing: -0.28px;
          &.red {
            color: $red-500;
          }
        }
      }
    }
    .nickname-history {
      display: flex;
      box-sizing: border-box;
      flex-direction: column;
      padding: 24px;
      gap: 16px;
      height: calc(50% - 5px);
      border-radius: 24px;
      background-color: $soft-purple-900;
      .nickname-history-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        .nickname-history-title {
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        .nickname-history-clear {
          flex: 0 0 auto;
          min-height: 30px;
          font-size: 14px;
        }
      }
      .nickname-history-access-text {
        color: $neutral-300;
        overflow-wrap: anywhere;
        &.disabled {
          color: $neutral-500;
        }
      }
      .nickname-history-divider {
        width: 100%;
        height: 1px;
        background-color: rgba($neutral-white, 0.1);
      }
      > .nickname-history-state {
        color: $neutral-300;
      }
      .nickname-history-error {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        .nickname-history-state {
          color: $neutral-300;
          &.danger {
            color: $red-500;
          }
        }
        .nickname-history-retry {
          flex: 0 0 auto;
          min-height: 30px;
          font-size: 14px;
        }
      }
      .nickname-history-list {
        display: flex;
        flex-direction: column;
        max-height: 250px;
        gap: 5px;
        overflow-y: auto;
        scrollbar-width: thin;
        span {
          color: $neutral-300;
          overflow-wrap: anywhere;
          &.current {
            color: $neutral-100;
            font-family: Hauora-SemiBold;
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
    background-color: rgba($neutral-800, 0.2);
    backdrop-filter: blur(12px);
    overscroll-behavior: contain;
    z-index: 50;
    .modal-body {
      display: flex;
      flex-direction: column;
      padding: 10px;
      gap: 10px;
      border: 1px solid $neutral-800;
      border-radius: 5px;
      background-color: $neutral-900;
      > canvas {
        align-self: center;
        width: 300px;
        height: 300px;
        border-radius: 5px;
        background-color: black;
      }
      .range {
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      .modal-actions {
        display: flex;
        justify-content: space-between;
        gap: 10px;
      }
    }
    &.gif-modal {
      .gif-modal-body {
        .gif-preview-row {
          display: flex;
          flex-wrap: wrap;
          align-items: stretch;
          justify-content: center;
          gap: 10px;
          .gif-preview-block {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 5px;
            span {
              color: $neutral-500;
              font-size: 18px;
            }
            img {
              width: 300px;
              height: 300px;
              border-radius: 5px;
              background-color: black;
              object-fit: contain;
            }
            canvas {
              align-self: center;
              width: 300px;
              height: 300px;
              border-radius: 5px;
              background-color: black;
            }
          }
        }
        .hint {
          margin: 0;
          color: $neutral-500;
          font-size: 14px;
          &.red {
            color: $red-500;
          }
        }
      }
    }
  }
}
</style>
