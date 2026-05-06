<template>
  <Teleport to="body">
    <Transition name="support-site-overlay">
      <div v-if="open" class="support-site-overlay" @pointerdown.self="armed = true" @pointerup.self="armed && requestClose()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <div class="support-site-modal" role="dialog" aria-modal="true">
          <header>
            <span>Выберите сервис поддержки</span>
            <button class="icon" type="button" aria-label="Закрыть" @click="requestClose">
              <img :src="iconClose" alt="close" />
            </button>
          </header>

          <div class="site-list">
            <a class="site-option" href="https://web.tribute.tg/d/Cvc" target="_blank" rel="noopener noreferrer" @click="onSelect(site)">
              <img :src="iconTribute" alt="tribute" class="site-logo" />
              <div class="site-copy">
                <span class="site-name">Tribute</span>
                <span class="site-note">Сервис поддержки в Telegram</span>
              </div>
            </a>
            <a class="site-option" href="https://dalink.to/deceit_games" target="_blank" rel="noopener noreferrer" @click="onSelect(site)">
              <img :src="iconDonationAlerts" alt="donation" class="site-logo" />
              <div class="site-copy">
                <span class="site-name">DonationAlerts</span>
                <span class="site-note">Сторонний сервис поддержки</span>
              </div>
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
import iconTribute from '@/assets/svg/tribute.svg'
import iconDonationAlerts from '@/assets/svg/donation.svg'

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
  padding: 20px;
  background-color: rgba($black, 0.25);
  backdrop-filter: blur(5px);
  z-index: 1000;
  .support-site-modal {
    max-width: 100%;
    display: flex;
    flex-direction: column;
    padding: 10px;
    gap: 10px;
    width: 500px;
    border-radius: 5px;
    background-color: $graphite;
    box-shadow: 0 15px 30px rgba($black, 0.25);
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
        width: 30px;
        height: 30px;
        padding: 0;
        border: none;
        background: none;
        cursor: pointer;
        img {
          width: 24px;
          height: 24px;
        }
      }
    }
    .site-list {
      display: flex;
      gap: 10px;
      .site-option {
        display: flex;
        gap: 10px;
        padding: 10px;
        border: 1px solid $lead;
        border-radius: 5px;
        background-color: $dark;
        color: $fg;
        text-decoration: none;
        box-shadow: 3px 3px 5px rgba($black, 0.25);
        outline: none;
        transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
        &:hover,
        &:focus-visible {
          border-color: rgba($green, 0.5);
          background-color: $graphite;
          box-shadow: 0 15px 30px rgba($black, 0.25);
        }
        .site-logo {
          width: 75px;
          height: 75px;
        }
        .site-copy {
          display: flex;
          min-width: 0;
          flex-direction: column;
          gap: 5px;
          .site-name {
            color: $fg;
            font-size: 16px;
            font-family: Manrope-SemiBold;
            line-height: 1.2;
          }
          .site-note {
            color: $grey;
            font-size: 12px;
            line-height: 1.2;
          }
        }
      }
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

}
</style>
