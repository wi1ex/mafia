<template>
  <section class="profile card">
    <div class="page-actions">
      <router-link class="btn" :to="{ name: 'home' }" aria-label="На главную">На главную</router-link>
    </div>

    <nav class="tabs" aria-label="Профиль">
      <button class="tab active" aria-selected="true">Личные данные</button>
      <button class="tab" disabled>Статистика</button>
      <button class="tab" disabled>История игр</button>
    </nav>

    <div class="grid">
      <div class="block">
        <h3 class="title">Аватар</h3>
        <div class="avatar-row">
          <img class="avatar" v-minio-img="{ key: me.avatar_name ? `avatars/${me.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Текущий аватар" />
          <div class="actions">
            <input ref="fileEl" type="file" accept="image/jpeg,image/png" @change="onPick" hidden />
            <button class="btn primary" @click="fileEl?.click()" :disabled="busyAva">Изменить аватар</button>
            <button class="btn danger" v-if="me.avatar_name" @click="onDeleteAvatar" :disabled="busyAva">Удалить</button>
            <div class="hint">JPG/PNG, до 5 МБ</div>
          </div>
        </div>
      </div>

      <div class="block">
        <h3 class="title">Никнейм</h3>
        <div class="nick-row">
          <input class="input" v-model.trim="nick" maxlength="20" :disabled="busyNick" placeholder="Никнейм" />
          <button class="btn" @click="saveNick" :disabled="busyNick || nick === me.username || !validNick">{{ busyNick ? '...' : 'Сохранить' }}</button>
        </div>
        <div class="hint">
          2–20 символов: латиница, кириллица, цифры, символы <code>( . _ - )</code>.
        </div>
      </div>

      <div v-if="crop.show" ref="modalEl" class="modal" @keydown.esc="cancelCrop" tabindex="0" aria-modal="true" aria-label="Кадрирование аватара" >
        <div class="modal-body">
          <canvas ref="canvasEl" @mousedown="dragStart" @mousemove="dragMove" @mouseup="dragStop" @mouseleave="dragStop" @wheel.passive="onWheel" />
          <input class="range" type="range" aria-label="Масштаб" :min="crop.min" :max="crop.max" step="0.01" :value="crop.scale" @input="onRange" />
          <div class="modal-actions">
            <button class="btn danger" @click="cancelCrop">Отменить</button>
            <button class="btn" @click="applyCrop" :disabled="busyAva">Загрузить</button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { api, refreshAccessTokenFull } from '@/services/axios'
import { useUserStore } from '@/store'
import defaultAvatar from '@/assets/svg/defaultAvatar.svg'

const userStore = useUserStore()
const me = reactive({ id: 0, username: '', avatar_name: null as string | null, role: '' })
const fileEl = ref<HTMLInputElement | null>(null)
const modalEl = ref<HTMLDivElement | null>(null)

const nick = ref('')
const busyNick = ref(false)
const validNick = computed(() => /^[a-zA-Zа-яА-Я0-9._\-()]{2,20}$/.test(nick.value) && !/^user/i.test(nick.value))

async function loadMe() {
  const { data } = await api.get('/users/profile_info')
  me.id = data.id
  me.username = data.username || ''
  me.avatar_name = data.avatar_name
  me.role = data.role
  nick.value = me.username
  try { await userStore.fetchMe?.() } catch {}
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
    if (st === 409 && d === 'username_taken') alert('Ник уже занят')
    else if (st === 422 && d === 'reserved_prefix') alert('Ник не должен начинаться с "user"')
    else alert('Не удалось сохранить ник')
  } finally { busyNick.value = false }
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

function clamp(v:number, lo:number, hi:number) { return Math.min(hi, Math.max(lo, v)) }

function fitContain(imgW: number, imgH: number, boxW: number, boxH: number) {
  return Math.min(boxW / imgW, boxH / imgH)
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

async function onPick(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  ;(e.target as HTMLInputElement).value = ''
  if (!f) return
  if (!['image/jpeg', 'image/png'].includes(f.type)) {
    alert('Только JPG/PNG')
    return
  }
  if (f.size > 5 * 1024 * 1024) {
    alert('Файл больше 5 МБ')
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
    const S = 240
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
    alert('Не удалось открыть изображение')
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
      alert('Получившийся файл больше 5 МБ')
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
    if (st === 415 || d === 'unsupported_media_type') alert('Только JPG/PNG')
    else if (st === 413) alert('Файл больше 5 МБ')
    else alert('Не удалось загрузить аватар')
  } finally { busyAva.value = false }
}

async function onDeleteAvatar() {
  if (!confirm('Удалить аватар?')) return
  busyAva.value = true
  try {
    await api.delete('/users/avatar')
    me.avatar_name = null
    userStore.setAvatarName(null)
  } catch { alert('Не удалось удалить аватар') } finally { busyAva.value = false }
}

onMounted(() => {
  loadMe().catch(() => {})
})

onBeforeUnmount(() => {
  document.body.style.overflow = ''
})
</script>

<style scoped lang="scss">
.profile {
  &.card {
    padding: 10px;
  }
  .btn {
    padding: 10px;
    border-radius: 5px;
    cursor: pointer;
    background-color: $green;
    color: $bg;
    border: 1px solid $green;
    &.primary {
      background-color: $blue;
      border-color: $blue;
    }
    &.danger {
      background-color: $red;
      border-color: $red;
      color: $fg;
    }
    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }
  .hint {
    margin-top: 5px;
    color: $grey;
    font-size: 12px;
  }
  .page-actions {
    display: flex;
    justify-content: flex-start;
    margin-bottom: 25px;
    .btn {
      text-decoration: none;
    }
  }
  .tabs {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
    .tab {
      padding: 10px;
      border-radius: 5px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      background-color: $bg;
      color: $fg;
      &.active {
        border-color: $blue;
        background-color: rgba(14, 165, 233, 0.07);
      }
      &:disabled {
        opacity: 0.6;
        cursor: not-allowed;
      }
    }
  }
  .grid {
    display: grid;
    gap: 10px;
    grid-template-columns: 1fr 1fr;
  }
  .block {
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 5px;
    padding: 10px;
    .title {
      margin: 0 0 10px;
      color: $fg;
    }
    .avatar-row {
      display: flex;
      gap: 10px;
      align-items: center;
      .avatar {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        object-fit: cover;
        background-color: $black;
      }
      .actions {
        display: flex;
        flex-direction: column;
        gap: 10px;
        align-items: flex-end;
      }
    }
    .nick-row {
      display: flex;
      gap: 10px;
      align-items: center;
      .input {
        padding: 10px;
        border-radius: 5px;
        border: 1px solid $fg;
        color: $fg;
        background-color: $bg;
        min-width: 240px;
      }
    }
  }
  .modal {
    position: fixed;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(3px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
    overscroll-behavior: contain;
    .modal-body {
      background-color: $bg;
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 5px;
      padding: 15px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      canvas {
        background-color: $black;
        border-radius: 5px;
        width: 240px;
        height: 240px;
      }
      .range {
        width: 100%;
        accent-color: $fg;
      }
      .modal-actions {
        display: flex;
        gap: 10px;
        justify-content: space-between;
      }
    }
  }
}
</style>

