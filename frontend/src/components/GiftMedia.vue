<template>
  <span ref="container" class="gift-media" :role="label ? 'img' : undefined" :aria-label="label || undefined" :aria-hidden="label ? undefined : true">
    <img v-if="previewUrl" v-show="!animationReady" :src="previewUrl" alt="" decoding="async" @load="emit('load')" />
    <img v-if="animationUrl" :src="animationUrl" alt="" decoding="async" class="gift-animation" :class="{ 'gift-animation--ready': animationReady }" @load="onAnimationLoad" @error="onAnimationError" />
  </span>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import { getImageURL, releaseImageURL } from '@/services/mediaCache'
import type { GiftMediaAsset } from '@/services/gifts'

const props = withDefaults(defineProps<{ media: GiftMediaAsset; animated?: boolean; label?: string }>(), {
  animated: false,
})
const emit = defineEmits<{ load: [] }>()

const container = ref<HTMLElement | null>(null)
const visible = ref(false)
const seen = ref(false)
const previewUrl = ref('')
const animationUrl = ref('')
const animationReady = ref(false)
let observer: IntersectionObserver | undefined

function onAnimationLoad(): void {
  animationReady.value = true
  emit('load')
}

function onAnimationError(): void {
  animationReady.value = false
  animationUrl.value = ''
}

async function loadGiftImage(key: string, source: Ref<string>, onCleanup: (cleanup: () => void) => void): Promise<void> {
  let active = true
  let retained = false
  onCleanup(() => {
    active = false
    if (retained) releaseImageURL(key)
  })
  try {
    const url = await getImageURL(key, 0)
    if (!active) {
      releaseImageURL(key)
      return
    }
    retained = true
    source.value = url
  } catch {}
}

watch([seen, () => props.media.preview_key], ([canLoad, key], _, onCleanup) => {
  previewUrl.value = ''
  if (canLoad && key) return loadGiftImage(key, previewUrl, onCleanup)
})
watch([visible, () => props.animated, () => props.media.avif_key], ([onScreen, animated, key], _, onCleanup) => {
  animationUrl.value = ''
  animationReady.value = false
  if (onScreen && animated && key) return loadGiftImage(key, animationUrl, onCleanup)
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
