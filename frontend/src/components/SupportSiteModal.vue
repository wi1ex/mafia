<template>
  <Teleport to="body">
    <Transition name="support-site-overlay">
      <div v-if="open" class="support-site-overlay" @pointerdown.self="armed = true"
           @pointerup.self="armed && requestClose()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <div class="support-site-modal" role="dialog" aria-modal="true" :aria-labelledby="titleId">
          <header>
            <span :id="titleId">Выберите сайт поддержки</span>
            <button class="icon" type="button" aria-label="Закрыть" @click="requestClose">
              <img :src="iconClose" alt="close" />
            </button>
          </header>

          <div class="site-list">
            <a v-for="site in SUPPORT_SITES" :key="site.id" class="site-option" :href="site.url" target="_blank" rel="noopener noreferrer" @click="onSelect(site)">
              <span class="site-copy">
                <span class="site-name">{{ site.name }}</span>
                <span class="site-note">{{ site.note }}</span>
              </span>
              <span class="site-action">Перейти</span>
            </a>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

import iconClose from '@/assets/svg/close.svg'

const props = defineProps<{
  open: boolean
}>()

type SupportSite = {
  id: string
  name: string
  url: string
}

const emit = defineEmits<{
  'update:open': [boolean]
  'select': [SupportSite]
}>()

const armed = ref(false)
const titleId = 'support-site-modal-title'
const SUPPORT_SITES = [
  {
    id: 'tribute',
    name: 'Tribute',
    note: 'Сервис поддержки в Telegram.',
    url: 'https://web.tribute.tg/d/Cvc',
  },
  {
    id: 'donationalerts',
    name: 'DonationAlerts',
    note: 'Сторонний сервис поддержки.',
    url: 'https://dalink.to/deceit_games',
  },
]

function requestClose(): void {
  emit('update:open', false)
}

function onSelect(site: SupportSite): void {
  emit('select', site)
  requestClose()
}

function onKeydown(event: KeyboardEvent): void {
  if (!props.open) return
  if (event.key === 'Escape') requestClose()
}

watch(() => props.open, (open) => {
  armed.value = false
  if (open) document.addEventListener('keydown', onKeydown)
  else document.removeEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped lang="scss">
.support-site-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 15px;
  background-color: rgba($black, 0.25);
  backdrop-filter: blur(5px);
  z-index: 1000;
  .support-site-modal {
    width: 460px;
    max-width: 100%;
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 10px;
    border-radius: 5px;
    background-color: $graphite;
    box-shadow: 0 20px 40px rgba($black, 0.3);
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      span {
        font-size: 18px;
        font-family: Manrope-Medium;
      }
      .icon {
        width: 28px;
        height: 28px;
        padding: 0;
        border: none;
        background: none;
        cursor: pointer;
        img {
          width: 20px;
          height: 20px;
        }
      }
    }
    .site-list {
      display: grid;
      gap: 10px;
    }
    .site-option {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 15px;
      padding: 12px;
      min-height: 72px;
      border: 1px solid $lead;
      border-radius: 5px;
      background-color: rgba($black, 0.08);
      color: $fg;
      text-decoration: none;
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      outline: none;
      transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
      &:hover,
      &:focus-visible {
        border-color: rgba($green, 0.65);
        background-color: rgba($black, 0.16);
        box-shadow: 0 15px 30px rgba($black, 0.25);
      }
    }
    .site-copy {
      display: flex;
      min-width: 0;
      flex-direction: column;
      gap: 4px;
    }
    .site-name {
      color: $fg;
      font-size: 16px;
      font-family: Manrope-SemiBold;
      line-height: 1.2;
    }
    .site-note {
      color: $grey;
      font-size: 13px;
      line-height: 1.25;
    }
    .site-action {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      min-width: 96px;
      height: 36px;
      padding: 0 14px;
      border-radius: 5px;
      background-color: rgba($green, 0.75);
      color: $bg;
      font-size: 14px;
      font-family: Manrope-Medium;
      line-height: 1;
    }
  }
}

.support-site-overlay-enter-active,
.support-site-overlay-leave-active {
  transition: opacity 0.25s ease-in-out;
}

.support-site-overlay-enter-from,
.support-site-overlay-leave-to {
  opacity: 0;
}

@media (max-width: 1280px) {
  .support-site-overlay {
    .support-site-modal {
      .site-option {
        min-height: 62px;
      }
      .site-name {
        font-size: 14px;
      }
      .site-note {
        font-size: 12px;
      }
      .site-action {
        min-width: 82px;
        height: 30px;
        font-size: 13px;
      }
    }
  }
}
</style>
