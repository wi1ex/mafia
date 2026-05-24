<template>
  <Teleport to="body">
    <Transition name="support-site-overlay">
      <div v-if="open" class="support-site-overlay" @pointerdown.self="armed = true" @pointerup.self="armed && requestClose()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <div class="support-site-modal" role="dialog" aria-modal="true">
          <header>
            <div class="support-header">
              <span class="header-title">Выбери удобный способ поддержки</span>
              <span class="header-text">Помоги развитию проекта и получи дополнительные возможности внутри платформы.</span>
            </div>
            <button type="button" aria-label="Закрыть" @click="requestClose">
              <img :src="iconClose" alt="close" />
            </button>
          </header>

          <div class="site-list">
            <a v-for="site in supportSites" :key="site.id" class="site-option" :href="site.url" target="_blank" rel="noopener noreferrer" @click="onSelect(site)">
              <img :src="site.icon" :alt="site.iconAlt" class="site-logo" />
              <div class="site-copy">
                <span class="site-name">{{ site.name }}</span>
                <span class="site-note">{{ site.note }}</span>
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

type SupportSiteOption = SupportSite & {
  icon: string
  iconAlt: string
  note: string
}

const emit = defineEmits<{
  'update:open': [boolean]
  'select': [SupportSite]
}>()

const supportSites: readonly SupportSiteOption[] = [
  {
    id: 'tribute',
    name: 'Tribute',
    url: 'https://web.tribute.tg/d/Cvc',
    icon: iconTribute,
    iconAlt: 'tribute',
    note: 'Сервис поддержки в Telegram',
  },
  {
    id: 'donation_alerts',
    name: 'DonationAlerts',
    url: 'https://dalink.to/deceit_games',
    icon: iconDonationAlerts,
    iconAlt: 'donation',
    note: 'Внешний сервис поддержки',
  },
] as const

const armed = ref(false)

function requestClose(): void {
  emit('update:open', false)
}

function onSelect(site: SupportSite): void {
  emit('select', { id: site.id, name: site.name, url: site.url })
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
  background-color: rgba($neutral-black, 0.20);
  backdrop-filter: blur(12px);
  z-index: 1000;
  .support-site-modal {
    display: flex;
    flex-direction: column;
    padding: 24px;
    gap: 32px;
    width: 558px;
    border-radius: 24px;
    background-color: $neutral-100;
    box-shadow: 0 2px 16px 0 rgba($neutral-black, 0.20);
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      .support-header {
        display: flex;
        flex-direction: column;
        gap: 8px;
        .header-title {
          color: $neutral-black;
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        .header-text {
          color: $neutral-500;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 22px;
          letter-spacing: -0.32px;
        }
      }
      button {
        padding: 0;
        width: 24px;
        height: 24px;
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
      gap: 15px;
      .site-option {
        display: flex;
        gap: 10px;
        padding: 15px;
        min-width: 210px;
        max-width: 210px;
        border: 1px solid $lead;
        border-radius: 10px;
        background-color: $dark;
        color: $fg;
        text-decoration: none;
        box-shadow: 3px 3px 5px rgba($black, 0.25);
        outline: none;
        transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
        &:hover,
        &:focus-visible {
          border-color: $grey;
          background-color: $graphite;
          box-shadow: 0 15px 30px rgba($black, 0.25);
        }
        .site-logo {
          width: 65px;
          height: 65px;
        }
        .site-copy {
          display: flex;
          min-width: 0;
          flex-direction: column;
          gap: 5px;
          .site-name {
            color: $bg;
            font-size: 18px;
            font-family: Manrope-SemiBold;
            line-height: 1.2;
          }
          .site-note {
            color: $bg;
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
  .support-site-overlay {
    .support-site-modal {
      padding: 15px;
      gap: 10px;
      width: 400px;
      header {
        span {
          font-size: 16px;
        }
        .icon {
          width: 25px;
          height: 25px;
          img {
            width: 20px;
            height: 20px;
          }
        }
      }
      .site-list {
        .site-option {
          gap: 5px;
          padding: 10px;
          min-width: 170px;
          max-width: 170px;
          .site-logo {
            width: 50px;
            height: 50px;
          }
          .site-copy {
            .site-name {
              font-size: 14px;
            }
            .site-note {
              font-size: 10px;
            }
          }
        }
      }
    }
  }
}
</style>
