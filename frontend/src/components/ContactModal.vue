<template>
  <Teleport to="body">
    <Transition name="contact-drawer">
      <div v-if="open" class="contact-drawer-overlay" @pointerdown.self="armed = true" @pointerup.self="armed && requestClose()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <form class="contact-drawer-form" @submit.prevent="submit">
          <div class="contact-drawer-panel" role="dialog" aria-modal="true" aria-labelledby="contact-request-title">
            <header>
              <span id="contact-request-title" class="header-title">Связаться с нами</span>
              <button type="button" aria-label="Закрыть" @click="requestClose">
                <UiIcon class="close-icon" :icon="iconClose" />
              </button>
            </header>

            <div class="contact-body">
              <UiInput
                id="contact-request-contact"
                v-model="replyContact"
                mode="light"
                label="Email/Telegram для обратной связи"
                :maxlength="CONTACT_MAX"
                autocomplete="off"
                :invalid="replyContactInvalid"
                :disabled="busy"
              >
                <template #meta>
                  <span>{{ replyContact.length }}/{{ CONTACT_MAX }}</span>
                </template>
              </UiInput>

              <UiInput
                id="contact-request-category"
                v-model="category"
                mode="light"
                label="Категория обращения"
                :maxlength="CATEGORY_MAX"
                autocomplete="off"
                :invalid="categoryInvalid"
                :disabled="busy"
              >
                <template #meta>
                  <span>{{ category.length }}/{{ CATEGORY_MAX }}</span>
                </template>
              </UiInput>

              <UiDropdown
                id="contact-request-topic"
                v-model="topic"
                mode="light"
                label="Тема обращения"
                placeholder="Выберите тему"
                :options="topicOptions"
                :invalid="topicInvalid"
                :disabled="busy"
              />

              <UiInput
                id="contact-request-text"
                v-model="messageText"
                class="contact-textarea"
                mode="light"
                as="textarea"
                label="Текст обращения"
                :maxlength="TEXT_MAX"
                rows="8"
                :invalid="textInvalid"
                :disabled="busy"
              >
                <template #meta>
                  <span>{{ messageText.length }}/{{ TEXT_MAX }}</span>
                </template>
              </UiInput>
            </div>

            <div class="contact-actions">
              <button type="button" class="cancel" :disabled="busy" @click="requestClose">Отмена</button>
              <button type="submit" class="submit" :disabled="busy || !canSubmit">
                {{ busy ? 'Отправка...' : 'Отправить' }}
              </button>
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

import iconClose from '@/assets/svg/iconClose.svg'

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

const CATEGORY_MAX = 80
const CONTACT_MAX = 160
const TEXT_MAX = 2000

const topicOptions: readonly TopicOption[] = [
  { value: 'technical_problem', label: 'Техническая проблема' },
  { value: 'payment_question', label: 'Вопрос по оплате' },
  { value: 'player_report', label: 'Жалоба на пользователя' },
  { value: 'gameplay_question', label: 'Вопрос по игре' },
  { value: 'feature_suggestion', label: 'Предложение по платформе' },
] as const

const armed = ref(false)
const busy = ref(false)
const submitAttempted = ref(false)
const category = ref('')
const topic = ref('')
const messageText = ref('')
const replyContact = ref('')

let prevOverflow = ''

const normalizedCategory = computed(() => normalizeInlineText(category.value).slice(0, CATEGORY_MAX))
const normalizedContact = computed(() => normalizeInlineText(replyContact.value).slice(0, CONTACT_MAX))
const normalizedText = computed(() => normalizeMessageText(messageText.value).slice(0, TEXT_MAX))
const selectedTopicLabel = computed(() => topicOptions.find((option) => option.value === topic.value)?.label || '')
const categoryOk = computed(() => normalizedCategory.value.length > 0)
const contactOk = computed(() => normalizedContact.value.length > 0)
const topicOk = computed(() => Boolean(selectedTopicLabel.value))
const textOk = computed(() => normalizedText.value.length > 0)
const canSubmit = computed(() => categoryOk.value && topicOk.value && textOk.value && contactOk.value)
const categoryInvalid = computed(() => submitAttempted.value && !categoryOk.value)
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
  category.value = ''
  topic.value = ''
  messageText.value = ''
  replyContact.value = ''
  submitAttempted.value = false
}

async function submit(): Promise<void> {
  submitAttempted.value = true
  if (!canSubmit.value || busy.value) return

  busy.value = true
  try {
    await api.post('/users/contact_request', {
      category: normalizedCategory.value,
      topic: selectedTopicLabel.value,
      text: normalizedText.value,
      contact: normalizedContact.value,
    })
    resetForm()
    emit('update:open', false)
    void alertDialog('Обращение отправлено')
  } catch (e: any) {
    const status = Number(e?.response?.status || 0)
    const detail = String(e?.response?.data?.detail || e?.message || '')
    if (status === 401 || detail === 'auth_expired') {
      void alertDialog('Авторизуйтесь, чтобы отправить обращение')
    } else if (status === 422) {
      void alertDialog('Заполните все поля обращения')
    } else if (status === 503) {
      void alertDialog('Не удалось отправить обращение в Telegram. Попробуйте позже')
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
  inset: 0;
  background-color: rgba($neutral-black, 0.20);
  backdrop-filter: blur(12px);
  z-index: 1000;
  .contact-drawer-form {
    height: 100dvh;
    margin: 0;
  }
  .contact-drawer-panel {
    display: flex;
    flex-direction: column;
    gap: 24px;
    width: min(520px, 100vw);
    height: 100dvh;
    padding: 24px;
    border-radius: 24px 0 0 24px;
    background-color: $neutral-100;
    box-shadow: 0 2px 16px 0 rgba($neutral-black, 0.20);
    box-sizing: border-box;
    --ui-input-label-bg: #{$neutral-100};
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      .header-title {
        min-width: 0;
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
        &:hover,
        &:focus-visible,
        &:active {
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
      gap: 24px;
      min-height: 0;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 2px 2px 8px;
      scrollbar-width: thin;
      scrollbar-color: $neutral-300 transparent;
      &::-webkit-scrollbar {
        width: 6px;
      }
      &::-webkit-scrollbar-track {
        background-color: transparent;
      }
      &::-webkit-scrollbar-thumb {
        border-radius: 999px;
        background-color: $neutral-300;
      }
    }
    :deep(.contact-textarea textarea) {
      min-height: 180px;
      border-radius: 24px;
      line-height: 22px;
    }
    :deep(.contact-textarea label) {
      top: 28px;
    }
    :deep(.contact-textarea:focus-within label),
    :deep(.contact-textarea textarea:not(:placeholder-shown) + label),
    :deep(.contact-textarea.invalid label) {
      top: -6px;
    }
    .contact-actions {
      display: flex;
      flex: 0 0 auto;
      gap: 10px;
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 0;
        height: 48px;
        padding: 0 18px;
        border-radius: 14px;
        border: none;
        font-family: Hauora-Regular;
        font-size: 16px;
        line-height: 16px;
        letter-spacing: -0.32px;
        cursor: pointer;
        transition: background-color 0.25s ease-in-out, color 0.25s ease-in-out;
        &:disabled {
          cursor: not-allowed;
        }
      }
      .cancel {
        flex: 1 1 0;
        background-color: $neutral-white;
        color: $neutral-black;
        &:not(:disabled):hover,
        &:not(:disabled):focus-visible {
          color: $green-600;
        }
      }
      .submit {
        flex: 1.5 1 0;
        background-color: $green-500;
        color: $neutral-900;
        &:not(:disabled):hover,
        &:not(:disabled):focus-visible {
          background-color: $green-300;
          color: $neutral-black;
        }
        &:disabled {
          background-color: $neutral-200;
          color: $neutral-400;
        }
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
