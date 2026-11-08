<template>
  <span ref="container" class="gift-media" :role="label ? 'img' : undefined" :aria-label="label || undefined" :aria-hidden="label ? undefined : true">
    <img v-if="previewUrl" v-show="!animationReady" :src="previewUrl" alt="" decoding="async" />
    <img v-if="animationUrl" :src="animationUrl" alt="" decoding="async" class="gift-animation" :class="{ 'gift-animation--ready': animationReady }" @load="animationReady = true" @error="onAnimationError" />
  </span>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
const animationReady = ref(false)
let observer: IntersectionObserver | undefined

function onAnimationError(): void {
  animationReady.value = false
  animationUrl.value = ''
}

watch([seen, () => props.media.preview_key], async ([canLoad, key], _, onCleanup) => {
  let active = true
  onCleanup(() => { active = false })
  previewUrl.value = ''
  if (!canLoad || !key) return
  const url = await presign(key).catch(() => '')
  if (active) previewUrl.value = url
})
watch([visible, () => props.animated, () => props.media.avif_key], async ([onScreen, animated, key], _, onCleanup) => {
  let active = true
  onCleanup(() => { active = false })
  animationUrl.value = ''
  animationReady.value = false
  if (!onScreen || !animated || !key) return
  const url = await presign(key).catch(() => '')
  if (active) animationUrl.value = url
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
  img {
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
