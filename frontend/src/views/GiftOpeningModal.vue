<template>
  <Teleport to="#desktop-teleport-root">
    <dialog ref="dialog" class="gift-opening" :class="{ 'gift-opening--intro': !revealed }"
            aria-labelledby="gift-opening-title" @cancel.prevent="close" @click.self="close">
      <img v-if="openingUrl" class="gift-opening-animation" :src="openingUrl" alt=""
           @load="startRevealTimer" @error="revealGift" />
      <div class="gift-opening-content" :inert="!revealed">
        <h2 id="gift-opening-title">Ваш подарок!</h2>
        <UiButton class="gift-opening-close" variant="white" size="low" :icon="iconClose" aria-label="Закрыть" @click="close" />
        <div class="gift-opening-stage">
          <div class="gift-reveal" :class="{ 'gift-reveal--visible': giftVisible }" :aria-hidden="!giftVisible">
            <GiftMedia :media="gift" :animated="revealed && !reducedMotion" :label="`Подарок №${gift.gift_id}`" @load="giftLoaded = true" />
          </div>
        </div>
        <div class="gift-opening-actions">
          <UiButton v-if="revealed" size="middle" text="Посмотреть в профиле" :disabled="!canViewProfile" @click="emit('view-profile')" />
        </div>
      </div>
      <div v-if="giftVisible && !reducedMotion && !confettiFinished" class="gift-confetti" aria-hidden="true"
           @animationend.once="confettiFinished = true">
        <span v-for="(piece, index) in confetti" :key="index" class="gift-confetti-piece" :style="piece"></span>
      </div>
    </dialog>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import UiButton from '@/components/UiButton.vue'
import GiftMedia from '@/components/GiftMedia.vue'
import giftOpenAnimation from '@/assets/video/gift-open.avif'
import iconClose from '@/assets/svg/iconClose.svg'
import type { GiftCollectionItem } from '@/services/gifts'
import { getImageURL, releaseImageURL } from '@/services/mediaCache'

// Reveal just before the 121-frame, 24 fps AVIF starts looping.
const GIFT_OPEN_REVEAL_MS = 4850
const GIFT_OPEN_LOAD_TIMEOUT_MS = 10_000
const CONFETTI_COLORS = ['#00cd9b', '#ffbd4a', '#61a9eb', '#a475f3', '#fa7770', '#fff']

const props = defineProps<{ gift: GiftCollectionItem; canViewProfile?: boolean }>()
const emit = defineEmits<{ close: []; 'view-profile': [] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const revealed = ref(false)
const giftLoaded = ref(false)
const giftVisible = computed(() => revealed.value && giftLoaded.value)
const openingUrl = ref('')
const openingRequest = new AbortController()
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const confettiFinished = ref(false)
const confetti = reducedMotion ? [] : Array.from({ length: 60 }, (_, index) => {
  const angle = index * Math.PI * (3 - Math.sqrt(5))
  const reach = 0.36 + Math.random() * 0.64
  const rise = Math.sin(angle) * reach * 0.72 - 0.22
  const spin = (index % 2 === 0 ? 1 : -1) * (150 + Math.random() * 300)
  return {
    '--confetti-x': Math.cos(angle) * reach,
    '--confetti-y': rise,
    '--confetti-fall': rise + 0.32 + Math.random() * 0.38,
    '--confetti-spin': `${spin}deg`,
    '--confetti-size': `${4 + Math.random() * 5}px`,
    '--confetti-color': CONFETTI_COLORS[index % CONFETTI_COLORS.length],
  }
})
let revealTimer: number | undefined
let preloadedGiftKey: string | undefined

function stopOpening(): void {
  window.clearTimeout(revealTimer)
  openingRequest.abort()
  if (openingUrl.value) {
    URL.revokeObjectURL(openingUrl.value)
    openingUrl.value = ''
  }
}

function revealGift(): void {
  stopOpening()
  revealed.value = true
  void nextTick(() => {
    if (dialog.value?.open) dialog.value.querySelector<HTMLButtonElement>('.gift-opening-close')?.focus({ preventScroll: true })
  })
}

function startRevealTimer(): void {
  if (openingRequest.signal.aborted) return
  window.clearTimeout(revealTimer)
  revealTimer = window.setTimeout(revealGift, GIFT_OPEN_REVEAL_MS)
}

async function fetchOpeningAnimation(): Promise<Blob> {
  const response = await fetch(giftOpenAnimation, { signal: openingRequest.signal })
  if (!response.ok) throw new Error('gift_open_animation_load_failed')
  return response.blob()
}

async function preloadGiftAnimation(key: string): Promise<void> {
  await getImageURL(key, 0)
  if (openingRequest.signal.aborted) {
    releaseImageURL(key)
    return
  }
  preloadedGiftKey = key
}

async function loadOpeningAnimation(): Promise<void> {
  const key = props.gift.avif_key
  if (!key) { revealGift(); return }
  revealTimer = window.setTimeout(revealGift, GIFT_OPEN_LOAD_TIMEOUT_MS)
  try {
    const [animation] = await Promise.all([fetchOpeningAnimation(), preloadGiftAnimation(key)])
    if (!openingRequest.signal.aborted) openingUrl.value = URL.createObjectURL(animation)
  } catch {
    if (!openingRequest.signal.aborted) revealGift()
  }
}

function close(): void {
  dialog.value?.close()
  emit('close')
}

onMounted(() => {
  dialog.value?.showModal()
  if (reducedMotion) revealGift()
  else void loadOpeningAnimation()
})
onBeforeUnmount(() => {
  stopOpening()
  if (preloadedGiftKey) releaseImageURL(preloadedGiftKey)
})
</script>

<style scoped lang="scss">
.gift-opening {
  --gift-opening-size: min(600px, calc(100vw - 40px), calc(100dvh - 40px));
  width: var(--gift-opening-size);
  height: var(--gift-opening-size);
  max-width: none;
  max-height: none;
  padding: 0;
  border: 0;
  border-radius: 28px;
  color: $neutral-black;
  background: $neutral-100;
  &::backdrop {
    background: rgba($neutral-black, 0.52);
    backdrop-filter: blur(10px);
  }
  &--intro {
    overflow: hidden;
    background: $neutral-black;
    .gift-opening-animation {
      position: absolute;
      inset: 0;
      display: block;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .gift-opening-content {
      visibility: hidden;
    }
  }
  .gift-opening-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
    height: 100%;
    padding: 24px;
    box-sizing: border-box;
    h2 {
      margin: 0;
      font-family: Involve-Medium;
      font-weight: normal;
    }
    .gift-opening-close {
      position: absolute;
      top: 12px;
      right: 12px;
      --ui-button-bg: transparent;
      --ui-button-hover-bg: transparent;
      --ui-button-hover-color: #{$green-600};
    }
    .gift-opening-stage {
      display: grid;
      place-items: center;
      flex: 1;
      width: 100%;
      min-height: 0;
      background: radial-gradient(circle, $green-100, transparent 72%);
      .gift-reveal {
        width: 100%;
        height: 100%;
        opacity: 0;
        &--visible {
          opacity: 1;
          animation: gift-reveal 0.35s ease-out both;
          @media (prefers-reduced-motion: reduce) {
            animation: none;
          }
        }
      }
    }
    .gift-opening-actions {
      min-height: 40px;
    }
  }
  .gift-confetti {
    position: fixed;
    inset: 0;
    z-index: 2;
    overflow: hidden;
    pointer-events: none;
    --confetti-radius: min(40vw, max(310px, calc(var(--gift-opening-size) * 0.7)));
    .gift-confetti-piece {
      position: absolute;
      top: 50%;
      left: 50%;
      width: var(--confetti-size);
      height: calc(var(--confetti-size) * 1.4);
      border-radius: 1px;
      background: var(--confetti-color);
      animation: gift-confetti-burst 1.55s cubic-bezier(0.15, 0.72, 0.3, 1) both;
      &:nth-child(3n) {
        width: calc(var(--confetti-size) * 0.7);
        height: calc(var(--confetti-size) * 0.7);
        border-radius: 50%;
      }
      &:nth-child(5n) {
        width: 2px;
        height: calc(var(--confetti-size) * 1.75);
      }
    }
  }
}
@keyframes gift-reveal {
  from { transform: translateY(16px) scale(0.76); opacity: 0; }
  to { transform: translateY(0) scale(1); opacity: 1; }
}
@keyframes gift-confetti-burst {
  0% {
    opacity: 0;
    transform: translate3d(0, 0, 0) rotate(0deg) scale(0.35);
  }
  8%, 70% { opacity: 1; }
  34% {
    transform: translate3d(calc(var(--confetti-x) * var(--confetti-radius)), calc(var(--confetti-y) * var(--confetti-radius)), 0)
               rotate(var(--confetti-spin));
  }
  100% {
    opacity: 0;
    transform: translate3d(calc(var(--confetti-x) * var(--confetti-radius) * 1.12), calc(var(--confetti-fall) * var(--confetti-radius)), 0)
               rotate(calc(var(--confetti-spin) * 1.6));
  }
}
</style>
