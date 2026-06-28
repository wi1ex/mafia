<template>
  <Teleport to="body">
    <Transition name="contact-drawer">
      <div v-if="open" class="contact-drawer-overlay" @pointerdown.self="armed = true" @pointerup.self="armed && requestClose()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <form @submit.prevent="submit">
          <div class="contact-drawer-panel" role="dialog" aria-modal="true" aria-labelledby="contact-request-title">
            <header>
              <span id="contact-request-title" class="header-title">Связаться с администрацией</span>
              <button type="button" aria-label="Закрыть" @click="requestClose">
                <UiIcon class="close-icon" :icon="iconClose" />
              </button>
            </header>

            <div class="contact-body">
              <span class="contact-body-title">Контактные данные</span>
              <UiInput
                class="contact-body-input"
                id="contact-request-contact"
                v-model="replyContact"
                mode="light"
                label-mode="placeholder"
                label="Оставьте email/telegram для обратной связи"
                :maxlength="CONTACT_MAX"
                autocomplete="off"
                :invalid="replyContactInvalid"
                :disabled="busy"
              >
                <template #meta>
                  <span>{{ replyContact.length }}/{{ CONTACT_MAX }}</span>
                </template>
              </UiInput>

              <span class="contact-body-title">Тема обращения</span>
              <UiDropdown
                class="contact-body-input"
                id="contact-request-topic"
                v-model="topic"
                mode="light"
                label-mode="placeholder"
                label="Тема обращения"
                placeholder="Выберите тему"
                :options="topicOptions"
                :invalid="topicInvalid"
              />

              <span class="contact-body-title">Текст обращения</span>
              <UiInput
                id="contact-request-text"
                v-model="messageText"
                class="contact-textarea contact-body-input"
                mode="light"
                label-mode="placeholder"
                as="textarea"
                label="Подробно опишите обращение"
                :maxlength="TEXT_MAX"
                rows="8"
                :invalid="textInvalid"
                :disabled="busy"
              >
                <template #meta>
                  <span>{{ messageText.length }}/{{ TEXT_MAX }}</span>
                </template>
              </UiInput>

              <span class="contact-body-title">Вы также можете написать нам на email:</span>
              <div class="contact-email-block">
                <UiIcon class="contact-email-img-1" :icon="iconMail" />
                <button class="contact-email-btn" type="button" aria-label="Скопировать email" @click="copyContactEmailText">
                  <span ref="contactEmailTextEl" class="contact-email-text">support@deceit.games</span>
                  <UiIcon v-if="!emailCopied" class="contact-email-img-2" :icon="iconCopy" />
                  <UiIcon v-else class="contact-email-img-3" :icon="iconCheckMark" />
                </button>
              </div>
            </div>

            <div class="contact-actions">
              <UiButton
                class="cancel"
                variant="white"
                text="Отмена"
                :disabled="busy"
                @click="requestClose"
              />
              <UiButton
                class="submit"
                type="submit"
                :text="busy ? 'Отправка...' : 'Отправить'"
                :disabled="busy || !canSubmit"
              />
            </div>
          </div>
        </form>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'

import UiIcon from '@/components/UiIcon.vue'
import UiDropdown from '@/components/UiDropdown.vue'
import UiInput from '@/components/UiInput.vue'
import UiButton from '@/components/UiButton.vue'

import iconClose from '@/assets/svg/iconClose.svg'
import iconMail from '@/assets/svg/iconMail.svg'
import iconCopy from '@/assets/svg/iconCopy.svg'
import iconCheckMark from '@/assets/svg/iconCheckMark.svg'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [boolean]
}>()

type TopicOption = {
  value: string
  label: string
}

const CONTACT_MAX = 160
const TEXT_MAX = 2000

const topicOptions: readonly TopicOption[] = [
  { value: 'verif_question', label: 'Верификация на платформе' },
  { value: 'technical_problem', label: 'Техническая проблема' },
  { value: 'payment_question', label: 'Подписка и оплата' },
  { value: 'player_report', label: 'Жалоба на пользователя' },
  { value: 'appeal_sanction', label: 'Апелляция по санкции' },
  { value: 'feature_suggestion', label: 'Предложение по платформе' },
  { value: 'other_question', label: 'Иной вопрос' },
] as const

const armed = ref(false)
const busy = ref(false)
const submitAttempted = ref(false)
const topic = ref('')
const messageText = ref('')
const replyContact = ref('')
const emailCopied = ref(false)
const contactEmailTextEl = ref<HTMLElement | null>(null)

let prevOverflow = ''

const normalizedContact = computed(() => normalizeInlineText(replyContact.value).slice(0, CONTACT_MAX))
const normalizedText = computed(() => normalizeMessageText(messageText.value).slice(0, TEXT_MAX))
const selectedTopicLabel = computed(() => topicOptions.find((option) => option.value === topic.value)?.label || '')
const contactOk = computed(() => normalizedContact.value.length > 0)
const topicOk = computed(() => Boolean(selectedTopicLabel.value))
const textOk = computed(() => normalizedText.value.length > 0)
const canSubmit = computed(() => topicOk.value && textOk.value && contactOk.value)
const replyContactInvalid = computed(() => submitAttempted.value && !contactOk.value)
const topicInvalid = computed(() => submitAttempted.value && !topicOk.value)
const textInvalid = computed(() => submitAttempted.value && !textOk.value)

function normalizeInlineText(value: string): string {
  return String(value || '')
    .normalize('NFKC')
    .replace(/[\u0000-\u001F\u007F]/g, '')
    .replace(/[\u200B-\u200F\u202A-\u202E\u2066-\u2069]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function normalizeMessageText(value: string): string {
  return String(value || '')
    .normalize('NFKC')
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, '')
    .replace(/[\u200B-\u200F\u202A-\u202E\u2066-\u2069]/g, '')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{4,}/g, '\n\n\n')
    .trim()
}

function requestClose(): void {
  if (busy.value) return
  emit('update:open', false)
}

function resetForm(): void {
  topic.value = ''
  messageText.value = ''
  replyContact.value = ''
  emailCopied.value = false
  submitAttempted.value = false
}

function copyTextFallback(text: string): boolean {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()

  try {
    return document.execCommand('copy')
  } finally {
    textarea.remove()
  }
}

async function copyContactEmailText(): Promise<void> {
  const text = normalizeInlineText(contactEmailTextEl.value?.textContent || '')
  if (!text) return

  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      emailCopied.value = true
      return
    }

    emailCopied.value = copyTextFallback(text)
  } catch {
    emailCopied.value = copyTextFallback(text)
  }
}

async function submit(): Promise<void> {
  submitAttempted.value = true
  if (!canSubmit.value || busy.value) return

  busy.value = true
  try {
    await api.post('/users/contact_request', {
      topic: selectedTopicLabel.value,
      text: normalizedText.value,
      contact: normalizedContact.value,
    })
    resetForm()
    emit('update:open', false)
    void alertDialog('Обращение отправлено')
  } catch (e: any) {
    const status = Number(e?.response?.status || 0)
    if (status === 422) {
      void alertDialog('Заполните все поля обращения')
    } else {
      void alertDialog('Не удалось отправить обращение')
    }
  } finally {
    busy.value = false
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (!props.open) return
  if (event.key === 'Escape') requestClose()
}

watch(() => props.open, (open) => {
  armed.value = false
  emailCopied.value = false
  if (open) {
    prevOverflow = document.documentElement.style.overflow
    document.documentElement.style.overflow = 'hidden'
    document.addEventListener('keydown', onKeydown)
  } else {
    document.documentElement.style.overflow = prevOverflow
    document.removeEventListener('keydown', onKeydown)
  }
})

onBeforeUnmount(() => {
  document.documentElement.style.overflow = prevOverflow
  document.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped lang="scss">
.contact-drawer-overlay {
  display: flex;
  position: fixed;
  justify-content: flex-end;
  inset: 10px;
  background-color: rgba($neutral-black, 0.20);
  backdrop-filter: blur(12px);
  z-index: 1000;
  .contact-drawer-panel {
    display: flex;
    flex-direction: column;
    padding: 24px;
    gap: 40px;
    width: 482px;
    height: 100%;
    border-radius: 24px;
    background-color: $neutral-100;
    box-shadow: 0 0 16px 0 rgba($neutral-black, 0.16);
    box-sizing: border-box;
    --ui-input-label-bg: #{$neutral-100};
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      .header-title {
        color: $neutral-black;
        font-family: Involve-Medium;
        font-size: 24px;
        line-height: 26px;
        letter-spacing: -0.48px;
      }
      button {
        flex: 0 0 auto;
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
        &:not(:disabled):hover,
        &:not(:disabled):focus-visible,
        &:not(:disabled):active {
          .close-icon {
            --ui-icon-color: #{$green-500};
          }
        }
      }
    }
    .contact-body {
      display: flex;
      flex: 1 1 auto;
      flex-direction: column;
      gap: 16px;
      .contact-body-title {
        margin-left: 12px;
        color: $neutral-black;
        font-family: Hauora-SemiBold;
        font-size: 16px;
        line-height: 18px;
        letter-spacing: -0.32px;
      }
      .contact-body-input {
        margin-bottom: 8px;
      }
      .contact-email-block {
        display: flex;
        align-items: center;
        margin-top: -8px;
        margin-left: 12px;
        padding: 0;
        gap: 12px;
        border: none;
        background: none;
        cursor: pointer;
        .contact-email-img-1 {
          --ui-icon-width: 24px;
          --ui-icon-height: 24px;
          --ui-icon-color: #{$blue-600};
        }
        .contact-email-btn {
          display: flex;
          align-items: center;
          padding: 0;
          gap: 4px;
          border: none;
          background: none;
          .contact-email-text {
            color: $neutral-900;
            font-family: Hauora-Regular;
            font-size: 16px;
            line-height: 16px;
            letter-spacing: -0.32px;
          }
          .contact-email-img-2,
          .contact-email-img-3 {
            --ui-icon-width: 16px;
            --ui-icon-height: 16px;
            --ui-icon-color: #{$neutral-black};
          }
          &:not(:disabled):hover,
          &:not(:disabled):focus-visible,
          &:not(:disabled):active {
            .contact-email-img-2 {
              --ui-icon-color: #{$green-600};
            }
          }
        }
      }
    }
    :deep(.contact-textarea textarea) {
      min-height: 200px;
      border-radius: 24px;
      line-height: 22px;
    }
    .contact-actions {
      display: flex;
      flex: 0 0 auto;
      gap: 10px;
      .cancel {
        flex: 1 1 0;
      }
      .submit {
        flex: 1 1 0;
      }
    }
  }
}

.contact-drawer-enter-active,
.contact-drawer-leave-active {
  transition: opacity 0.25s ease-in-out;
  .contact-drawer-panel {
    transition: transform 0.25s ease-in-out;
  }
}

.contact-drawer-enter-from,
.contact-drawer-leave-to {
  opacity: 0;
  .contact-drawer-panel {
    transform: translateX(100%);
  }
}

</style>
