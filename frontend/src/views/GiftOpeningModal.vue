<template>
  <Teleport to="#desktop-teleport-root">
    <dialog ref="dialog" class="gift-opening" aria-labelledby="gift-opening-title" @cancel.prevent="close" @click.self="close">
      <div class="gift-opening-content">
        <h2 id="gift-opening-title">Подарок</h2>
        <div class="gift-opening-stage">
          <div v-if="revealed" class="gift-reveal">
            <GiftMedia :media="gift" :label="`Подарок №${gift.gift_id}`" />
          </div>
          <UiIcon v-else class="gift-box" :icon="iconPresent" />
        </div>
        <UiButton size="middle" text="Закрыть" autofocus @click="close" />
      </div>
    </dialog>
  </Teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import UiIcon from '@/components/UiIcon.vue'
import UiButton from '@/components/UiButton.vue'
import GiftMedia from '@/components/GiftMedia.vue'
import iconPresent from '@/assets/svg/iconPresent.svg'
import type { GiftCollectionItem } from '@/services/gifts'

defineProps<{ gift: GiftCollectionItem }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const revealed = ref(false)
let revealTimer: number | undefined

function close(): void {
  dialog.value?.close()
  emit('close')
}

onMounted(() => {
  dialog.value?.showModal()
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) revealed.value = true
  else revealTimer = window.setTimeout(() => { revealed.value = true }, 600)
})
onBeforeUnmount(() => window.clearTimeout(revealTimer))
</script>

<style scoped lang="scss">
.gift-opening {
  width: min(440px, calc(100vw - 40px));
  max-width: none;
  padding: 0;
  border: 0;
  border-radius: 28px;
  color: $neutral-black;
  background: $neutral-100;
  &::backdrop {
    background: rgba($neutral-black, 0.52);
    backdrop-filter: blur(10px);
  }
  .gift-opening-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
    padding: 24px;
    h2 {
      margin: 0;
      font-family: Involve-Medium;
    }
    .gift-opening-stage {
      display: grid;
      place-items: center;
      width: min(230px, 65vw);
      aspect-ratio: 1;
      background: radial-gradient(circle, $green-100, transparent 72%);
      .gift-box {
        --ui-icon-width: 88px;
        --ui-icon-height: 88px;
        --ui-icon-color: #{$green-600};
        animation: gift-box-open 0.6s ease-in-out both;
      }
      .gift-reveal {
        width: 100%;
        height: 100%;
        animation: gift-reveal 0.35s ease-out both;
      }
    }
  }
}
@keyframes gift-box-open {
  0%, 55% { transform: rotate(-8deg) scale(1); }
  30% { transform: rotate(10deg) scale(1.06); }
  100% { transform: scale(1.45); opacity: 0; }
}
@keyframes gift-reveal {
  from { transform: translateY(16px) scale(0.76); opacity: 0; }
  to { transform: translateY(0) scale(1); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .gift-opening .gift-opening-stage .gift-reveal {
    animation: none;
  }
}
</style>
