<template>
  <Teleport to="body">
    <Transition name="support-site-overlay">
      <div v-if="open" class="support-site-overlay" @pointerdown.self="armed = true" @pointerup.self="armed && requestClose()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <div class="support-site-modal" role="dialog" aria-modal="true">
          <header>
            <div class="header-div">
              <span class="header-title">Выбери удобный способ поддержки</span>
              <span class="header-text">Помоги развитию проекта и получи дополнительные возможности внутри платформы.</span>
            </div>
            <button type="button" aria-label="Закрыть" @click="requestClose">
              <UiIcon class="close-icon" :icon="iconClose" />
            </button>
          </header>

          <div class="site-list">
            <a v-for="site in supportSites" :key="site.id" class="site-option" :href="site.url" target="_blank" rel="noopener noreferrer" @click="onSelect(site)">
              <div class="site-title">
                <img :src="site.icon" :alt="site.iconAlt" class="site-logo" />
                <UiIcon class="arrow-icon" :icon="iconArrowNext" />
              </div>
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

import UiIcon from '@/components/UiIcon.vue'

import iconClose from '@/assets/svg/iconClose.svg'
import iconArrowNext from '@/assets/svg/iconArrowNext.svg'
import iconTribute from '@/assets/images/donateTribute.png'
import iconDonationAlerts from '@/assets/images/donateDonation.png'

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
      .header-div {
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
        .close-icon {
          --ui-icon-width: 24px;
          --ui-icon-height: 24px;
          --ui-icon-color: #{$neutral-black};
        }
        &:hover,
        &:focus-visible,
        &:active {
          .close-icon {
            --ui-icon-color: #{$green-500};
          }
        }
      }
    }
    .site-list {
      display: flex;
      gap: 10px;
      .site-option {
        display: flex;
        flex-direction: column;
        padding: 16px;
        gap: 40px;
        width: 242px;
        height: 122px;
        border-radius: 20px;
        border: 1px solid $neutral-white;
        background-color: $neutral-white;
        color: $fg;
        text-decoration: none;
        outline: none;
        transition: border-color 0.25s ease-in-out;
        &:hover,
        &:focus-visible,
        &:active {
          border-color: $green-600;
          .site-title {
            .arrow-icon {
              --ui-icon-color: #{$green-600};
            }
          }
        }
        .site-title {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          .site-logo {
            width: 40px;
            height: 40px;
          }
          .arrow-icon {
            --ui-icon-width: 20px;
            --ui-icon-height: 20px;
            --ui-icon-color: #{$neutral-white};
          }
        }
        .site-copy {
          display: flex;
          flex-direction: column;
          gap: 8px;
          .site-name {
            color: $neutral-black;
            font-family: Hauora-Bold;
            font-size: 16px;
            line-height: 18px;
            letter-spacing: -0.32px;
          }
          .site-note {
            color: $neutral-500;
            font-family: Hauora-Regular;
            font-size: 16px;
            line-height: 16px;
            letter-spacing: -0.32px;
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
