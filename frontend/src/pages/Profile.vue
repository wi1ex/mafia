<template>
  <section class="profile">
    <header>
      <nav class="tabs" aria-label="Профиль" role="tablist">
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'profile' }" :aria-selected="activeTab === 'profile'" @click="activeTab = 'profile'">
          Личные данные
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'stats' }" :aria-selected="activeTab === 'stats'" @click="activeTab = 'stats'" disabled>
          Статистика
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'history' }" :aria-selected="activeTab === 'history'" @click="activeTab = 'history'" disabled>
          История игр
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
              <img v-minio-img="{ key: me.avatar_name ? `avatars/${me.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Текущий аватар" />
              <div class="actions">
                <input ref="fileEl" type="file" accept="image/jpeg,image/png" @change="onPick" hidden />
                <button class="btn" @click="fileEl?.click()" :disabled="busyAva">Изменить</button>
                <span class="hint">JPG/PNG, до 5 МБ</span>
                <button class="btn danger" v-if="me.avatar_name" @click="onDeleteAvatar" :disabled="busyAva">Удалить</button>
              </div>
            </div>
          </div>

          <div class="block">
            <h3>Никнейм</h3>
            <div class="nick-row">
              <div class="ui-input" :class="{ filled: !!nick, invalid: nick && !validNick }">
                <input id="profile-nick" v-model.trim="nick" :maxlength="NICK_MAX" :disabled="busyNick" placeholder=" "
                       autocomplete="off" inputmode="text" :aria-invalid="nick && !validNick" aria-describedby="profile-nick-hint" />
                <label for="profile-nick">Никнейм</label>
                <div class="underline">
                  <span :style="nickUnderlineStyle"></span>
                </div>
                <div class="meta">
                  <span id="profile-nick-hint">{{ nick.length }}/{{ NICK_MAX }}</span>
                </div>
              </div>
              <button class="btn confirm" @click="saveNick" :disabled="busyNick || nick === me.username || !validNick">
                {{ busyNick ? '...' : 'Сохранить' }}
              </button>
            </div>
            <span class="hint"><code>латиница, кириллица, цифры, символы ()._-</code></span>
          </div>

          <div v-if="crop.show" ref="modalEl" class="modal" @keydown.esc="cancelCrop" tabindex="0" aria-modal="true" aria-label="Кадрирование аватара" >
            <div class="modal-body">
              <canvas ref="canvasEl" @mousedown="dragStart" @mousemove="dragMove" @mouseup="dragStop" @mouseleave="dragStop" @wheel.passive="onWheel" />
              <div class="range">
                <span>Масштаб</span>
                <div class="range-wrap">
                  <div class="range-track" :style="cropRangeFillStyle" aria-hidden="true"></div>
                  <input class="range-native" type="range" aria-label="Масштаб" :min="crop.min" :max="crop.max" step="0.01" :value="crop.scale" @input="onRange" />
                </div>
              </div>
              <div class="modal-actions">
                <button class="btn danger" @click="cancelCrop">Отменить</button>
                <button class="btn confirm" @click="applyCrop" :disabled="busyAva">Загрузить</button>
              </div>
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
import { useUserStore } from '@/store'
import { confirmDialog, alertDialog } from '@/services/confirm'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'

const userStore = useUserStore()

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

const activeTab = ref<'profile' | 'stats' | 'history'>('profile')

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
    if (st === 409 && d === 'username_taken')               await alertDialog('Данный никнейм уже занят')
    else if (st === 422 && d === 'reserved_prefix')         await alertDialog('Никнейм не должен начинаться с "user"')
    else if (st === 422 && d === 'invalid_username_format') await alertDialog('Недопустимый формат никнейма')
    else                                                    await alertDialog('Не удалось сохранить никнейм')
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
  const f = (e.target as HTMLInputElement).files?.[0]
  ;(e.target as HTMLInputElement).value = ''
  if (!f) return
  if (!['image/jpeg', 'image/png'].includes(f.type)) {
    await alertDialog('К загрузке допустимы только форматы JPG/PNG')
    return
  }
  if (f.size > 5 * 1024 * 1024) {
    await alertDialog('К загрузке допустимы только файлы менее 5 Мбайт')
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
    await alertDialog('Не удалось открыть изображение')
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
      await alertDialog('Получившийся файл оказался больше 5 Мбайт')
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
    if (st === 415 || d === 'unsupported_media_type') await alertDialog('К загрузке допустимы только форматы JPG/PNG')
    else if (st === 413)                              await alertDialog('К загрузке допустимы только файлы менее 5 Мбайт')
    else if (st === 422 && d === 'empty_file')        await alertDialog('Не удалось прочитать файл')
    else if (st === 422 && d === 'bad_image')         await alertDialog('Некорректное изображение')
    else                                              await alertDialog('Не удалось загрузить аватар')
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
  catch { await alertDialog('Не удалось удалить аватар') }
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
  loadMe().catch(() => {})
})

onBeforeUnmount(() => {
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
  .btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 20px;
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
  }
  header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    border-bottom: 3px solid $lead;
    .tabs {
      display: flex;
      align-items: flex-end;
      width: 66%;
      height: 30px;
      .tab {
        width: 200px;
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
          img {
            width: 150px;
            height: 150px;
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
        .hint {
          color: $grey;
          font-size: 14px;
          text-align: center;
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
  .profile .tab-panel .grid {
    grid-template-columns: 1fr 1fr;
    .modal .modal-body canvas {
      width: 200px;
      height: 200px;
    }
  }
}
</style>

