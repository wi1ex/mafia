<template>
  <span ref="container" class="gift-media" :role="label ? 'img' : undefined" :aria-label="label || undefined" :aria-hidden="label ? undefined : true">
    <img v-if="previewUrl" v-show="!animationReady" :src="previewUrl" alt="" decoding="async" />
    <img v-if="animationUrl && animationKind === 'image'" :src="animationUrl" alt="" decoding="async" class="gift-animation" :class="{ 'gift-animation--ready': animationReady }" @load="animationReady = true" @error="onAnimationError" />
    <video v-else-if="animationUrl" :src="animationUrl" muted loop playsinline autoplay preload="metadata" class="gift-animation" :class="{ 'gift-animation--ready': animationReady }" @playing="animationReady = true" @error="onAnimationError" />
  </span>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { presign } from '@/services/mediaCache'
import type { GiftMediaAsset } from '@/services/gifts'

const props = withDefaults(defineProps<{ media: GiftMediaAsset; animated?: boolean; label?: string }>(), {
  animated: true,
})

const container = ref<HTMLElement | null>(null)
const visible = ref(false)
const seen = ref(false)
const previewUrl = ref('')
const animationUrl = ref('')
const animationKind = ref<'image' | 'video'>('image')
const animationReady = ref(false)
const failedAnimationKeys = ref<string[]>([])
let observer: IntersectionObserver | undefined

// Prefer the alpha-compatible source for the browser and try the paired source on error.
const prefersHevc = /AppleWebKit/i.test(navigator.userAgent) && !/Chrome\/|Chromium\/|Edg\/|OPR\//i.test(navigator.userAgent)
const mediaKeys = computed(() => {
  const { preview_key, webp_key, webm_key, hevc_key } = props.media
  return { preview: preview_key, webp: webp_key, videos: prefersHevc ? [hevc_key, webm_key] : [webm_key, hevc_key] }
})
const animationKey = computed(() => {
  const { webp, videos } = mediaKeys.value
  return [webp, ...videos].find(key => key && !failedAnimationKeys.value.includes(key)) || ''
})

function onAnimationError(): void {
  if (animationKey.value) failedAnimationKeys.value = [...failedAnimationKeys.value, animationKey.value]
}

watch(mediaKeys, () => { failedAnimationKeys.value = [] })
watch([seen, () => mediaKeys.value.preview], async ([canLoad, key], _, onCleanup) => {
  let active = true
  onCleanup(() => { active = false })
  previewUrl.value = ''
  if (!canLoad || !key) return
  const url = await presign(key).catch(() => '')
  if (active) previewUrl.value = url
})
watch([visible, () => props.animated, animationKey], async ([onScreen, animated, key], _, onCleanup) => {
  let active = true
  onCleanup(() => { active = false })
  animationUrl.value = ''
  animationReady.value = false
  if (!onScreen || !animated || !key) return
  const url = await presign(key).catch(() => '')
  if (!active) return
  if (!url) { onAnimationError(); return }
  animationKind.value = key === mediaKeys.value.webp ? 'image' : 'video'
  animationUrl.value = url
})

onMounted(() => {
  if (!container.value) return
  if (typeof IntersectionObserver !== 'function') { visible.value = seen.value = true; return }
  observer = new IntersectionObserver(([entry]) => {
    visible.value = Boolean(entry?.isIntersecting)
    if (visible.value) seen.value = true
  }, { threshold: 0.1 })
  observer.observe(container.value)
})
onBeforeUnmount(() => observer?.disconnect())
</script>

<style scoped lang="scss">
.gift-media {
  position: relative;
  display: block;
  overflow: hidden;
  width: 100%;
  height: 100%;
  img,
  video {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
  .gift-animation {
    opacity: 0;
    &.gift-animation--ready {
      opacity: 1;
    }
  }
}
</style>
