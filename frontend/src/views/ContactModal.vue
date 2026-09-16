<template>
  <Teleport to="#desktop-teleport-root">
    <Transition name="overlay">
      <div
        v-if="open"
        class="overlay"
        @pointerdown.stop.self="armed = true"
        @pointerup.stop.self="armed && requestClose()"
        @pointerleave.stop.self="armed = false"
        @pointercancel.stop.self="armed = false"
        @click.stop
      >
        <form class="modal" role="dialog" aria-modal="true" aria-labelledby="contact-request-reply-title" @submit.prevent="$emit('save')">
          <header>
            <div class="heading">
              <span id="contact-request-reply-title">Ответ на обращение #{{ target?.id }}</span>
              <small v-if="target">{{ target.username || `user${target.user_id}` }}</small>
            </div>
            <button class="icon" type="button" aria-label="Закрыть" :disabled="saving" @click="requestClose">
              <img :src="iconClose" alt="" />
            </button>
          </header>

          <div class="modal-body">
            <UiInput
              id="contact-request-reply-text"
              :model-value="message"
              as="textarea"
              rows="8"
              maxlength="2000"
              label="Текст ответа"
              :disabled="saving"
              @update:model-value="$emit('update:message', String($event))"
            >
              <template #meta>
                <span>{{ message.length }}/2000</span>
              </template>
            </UiInput>
            <p class="hint">Ответ появится в уведомлениях пользователя. В Telegram он будет отправлен при верифицированном аккаунте.</p>
          </div>

          <div class="modal-actions">
            <button class="btn dark" type="button" :disabled="saving" @click="requestClose">Отмена</button>
            <button class="btn confirm" type="submit" :disabled="saving || !canSave">
              {{ saving ? 'Отправка...' : 'Отправить' }}
            </button>
          </div>
        </form>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import UiInput from '@/components/UiInput.vue'
import iconClose from '@/assets/svg/iconClose.svg'

type ContactRequestTarget = {
  id: number
  user_id: number
  username?: string | null
}

defineProps<{
  open: boolean
  saving: boolean
  canSave: boolean
  message: string
  target: ContactRequestTarget | null
}>()

const emit = defineEmits<{
  'update:open': [boolean]
  'update:message': [string]
  save: []
}>()

const armed = ref(false)

function requestClose(): void {
  emit('update:open', false)
}
</script>

<style scoped lang="scss">
.overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 15px;
  background-color: rgba($neutral-800, 0.2);
  backdrop-filter: blur(12px);
}

.modal {
  display: flex;
  width: 520px;
  max-width: 100%;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
  border-radius: 5px;
  background-color: $neutral-800;
}

header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.heading {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  span {
    font-family: Hauora-Regular;
    font-size: 18px;
  }
  small {
    overflow: hidden;
    color: $neutral-500;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.icon {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  place-items: center;
  border: none;
  background: none;
  cursor: pointer;
  img {
    width: 20px;
    height: 20px;
  }
  &:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
}

.modal-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

:deep(#contact-request-reply-text) {
  min-height: 170px;
}

.hint {
  margin: 0;
  color: $neutral-500;
  font-size: 12px;
  line-height: 1.35;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn {
  display: flex;
  height: 40px;
  align-items: center;
  justify-content: center;
  padding: 0 20px;
  border: none;
  border-radius: 5px;
  background-color: $neutral-100;
  color: $neutral-black;
  cursor: pointer;
  font-family: Hauora-Regular;
  font-size: 14px;
  transition: background-color 0.25s ease-in-out, opacity 0.25s ease-in-out;
  &:hover:not(:disabled) {
    background-color: $neutral-white;
  }
  &.confirm {
    background-color: rgba($green-500, 0.75);
    &:hover:not(:disabled) {
      background-color: $green-500;
    }
  }
  &.dark {
    background-color: $neutral-700;
    color: $neutral-100;
    &:hover:not(:disabled) {
      background-color: rgba($neutral-500, 0.5);
    }
  }
  &:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
}

.overlay-enter-active,
.overlay-leave-active {
  transition: opacity 0.25s ease-in-out;
}

.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}
</style>
