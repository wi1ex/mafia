<template>
  <Teleport to="body">
    <Transition name="support-site-overlay">
      <div
        v-if="open"
        class="support-site-overlay"
        @pointerdown.self="armed = true"
        @pointerup.self="armed && requestClose()"
        @pointerleave.self="armed = false"
        @pointercancel.self="armed = false"
      >
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
            <component
              :is="site.enabled ? 'a' : 'button'"
              v-for="site in supportSites"
              :key="site.id"
              class="site-option"
              :href="site.enabled ? site.url : undefined"
              :target="site.enabled ? '_blank' : undefined"
              :rel="site.enabled ? 'noopener noreferrer' : undefined"
              :type="site.enabled ? undefined : 'button'"
              :disabled="!site.enabled"
              @click="onSelect(site)"
            >
              <div class="site-title">
                <img :src="site.icon" :alt="site.iconAlt" class="site-logo" />
                <UiIcon class="arrow-icon" :icon="iconArrowNext" />
              </div>
              <div class="site-copy">
                <span class="site-name">{{ site.name }}</span>
                <span class="site-note">{{ site.note }}</span>
              </div>
            </component>

            <button class="site-option lava-option" type="button" :disabled="lavaBusy" @click="onLavaPay">
              <div class="site-title">
                <span class="lava-logo">Lava</span>
                <UiIcon class="arrow-icon" :icon="iconArrowNext" />
              </div>
              <div class="site-copy">
                <span class="site-name">Lava.top</span>
                <span class="site-note">Подписка на месяц или год</span>
              </div>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import UiIcon from '@/components/UiIcon.vue'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { useAuthStore, useSettingsStore } from '@/store'

import iconClose from '@/assets/svg/iconClose.svg'
import iconArrowNext from '@/assets/svg/iconArrowNext.svg'
import iconSupportService1 from '@/assets/images/donateTribute.png'
import iconSupportService2 from '@/assets/images/donateBoosty.png'

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
  enabled: boolean
}

const emit = defineEmits<{
  'update:open': [boolean]
  'select': [SupportSite]
}>()

const auth = useAuthStore()
const settings = useSettingsStore()
const lavaBusy = ref(false)

const supportSites = computed<readonly SupportSiteOption[]>(() => [
  {
    id: 'service_1',
    name: 'Tribute',
    url: 'https://web.tribute.tg/d/Cvc',
    icon: iconSupportService1,
    iconAlt: 'tribute',
    note: 'Сервис поддержки в Telegram',
    enabled: Boolean(settings.supportService1Enabled),
  },
  {
    id: 'service_2',
    name: 'Boosty',
    url: 'https://boosty.to/deceit_games',
    icon: iconSupportService2,
    iconAlt: 'boosty',
    note: 'Внешний сервис поддержки',
    enabled: Boolean(settings.supportService2Enabled),
  },
])

const armed = ref(false)

function requestClose(): void {
  emit('update:open', false)
}

function onSelect(site: SupportSiteOption): void {
  if (!site.enabled) return
  emit('select', { id: site.id, name: site.name, url: site.url })
  requestClose()
}

async function onLavaPay(): Promise<void> {
  if (lavaBusy.value) return
  if (!auth.isAuthed) {
    void alertDialog('Войдите в аккаунт перед оплатой')
    return
  }

  lavaBusy.value = true
  const paymentWindow = window.open('', '_blank')
  if (paymentWindow) paymentWindow.opener = null
  try {
    const { data } = await api.post<{ payment_url: string }>('/payments/lava/link')
    const paymentUrl = String(data?.payment_url || '')
    if (!paymentUrl) throw new Error('payment_url_missing')
    emit('select', { id: 'lava', name: 'Lava.top', url: paymentUrl })
    requestClose()
    if (paymentWindow) paymentWindow.location.href = paymentUrl
    else window.location.assign(paymentUrl)
  } catch (e: any) {
    if (paymentWindow) paymentWindow.close()
    const st = Number(e?.response?.status || 0)
    const detail = String(e?.response?.data?.detail || '')
    if (st === 401) void alertDialog('Войдите в аккаунт перед оплатой')
    else if (st === 503 && detail === 'lava_product_missing') void alertDialog('Оплата Lava пока не настроена')
    else void alertDialog('Не удалось открыть оплату Lava')
  } finally {
    lavaBusy.value = false
  }
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
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
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
        text-align: left;
        text-decoration: none;
        outline: none;
        transition: border-color 0.25s ease-in-out, opacity 0.25s ease-in-out;
        &:not(:disabled):hover,
        &:not(:disabled):focus-visible,
        &:not(:disabled):active {
          border-color: $green-600;
          .site-title {
            .arrow-icon {
              --ui-icon-color: #{$green-600};
            }
          }
        }
        &:disabled {
          width: 274px;
          height: 154px;
          filter: grayscale(100%) brightness(60%);
          opacity: 0.5;
          cursor: not-allowed;
        }
        .site-title {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          .site-logo {
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

</style>
