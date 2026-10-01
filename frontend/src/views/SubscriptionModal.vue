<template>
  <Teleport to="#desktop-teleport-root">
    <Transition name="overlay">
      <div v-if="open" class="overlay" :style="{ zIndex }" @pointerdown.stop.self="armed = true"
           @pointerup.stop.self="armed && requestClose()" @pointerleave.stop.self="armed = false" @pointercancel.stop.self="armed = false" @click.stop>
        <div class="modal" role="dialog" aria-modal="true" :aria-label="title" @pointerdown.stop @pointerup.stop @click.stop>
          <header>
            <div class="heading">
              <h2>{{ title }}</h2>
              <small v-if="statusText">{{ statusText }}</small>
            </div>
            <UiButton variant="white" size="low" :icon="iconClose" width="40px" aria-label="Закрыть" @click="requestClose" />
          </header>
          <div class="modal-body">
            <div v-if="target" class="selected-user">
              <div class="user-cell">
                <img class="user-avatar" v-minio-img="{ key: target.avatar_name ? `avatars/${target.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                <span>{{ target.username || `user${target.user_id}` }}</span>
              </div>
            </div>
            <div class="duration-card">
              <h3>Срок</h3>
              <div class="duration-grid">
                <UiInput
                  id="subscription-modal-months"
                  v-model.number="form.months"
                  type="number"
                  min="0"
                  max="240"
                  step="1"
                  label="Месяцы"
                  size="low"
                  :disabled="saving"
                />
                <UiInput
                  id="subscription-modal-days"
                  v-model.number="form.days"
                  type="number"
                  min="0"
                  max="31"
                  step="1"
                  label="Дни"
                  size="low"
                  :disabled="saving"
                />
              </div>
            </div>
          </div>
          <div class="modal-actions">
            <UiButton variant="white" size="middle" text="Отмена" @click="requestClose" />
            <UiButton size="middle" :text="saving ? 'Сохранение…' : saveLabel" :disabled="saving || !canSave" @click="$emit('save')" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import UiInput from '@/components/UiInput.vue'
import UiButton from '@/components/UiButton.vue'

import defaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconClose from '@/assets/svg/iconClose.svg'

type SubscriptionTarget = {
  user_id: number
  username?: string | null
  avatar_name?: string | null
}

withDefaults(defineProps<{
  open: boolean
  title: string
  statusText?: string
  saveLabel: string
  saving: boolean
  canSave: boolean
  zIndex?: number
  target: SubscriptionTarget | null
  form: {
    months: number
    days: number
  }
}>(), {
  statusText: '',
  zIndex: 1000,
})

const emit = defineEmits<{
  'update:open': [boolean]
  'save': []
}>()

const armed = ref(false)

function requestClose(): void {
  emit('update:open', false)
}
</script>

<style scoped lang="scss">
.overlay {
  display: flex;
  position: fixed;
  inset: 0;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 40px;
  background-color: rgba($neutral-black, 0.6);
  backdrop-filter: blur(12px);
  z-index: 1000;
  .modal {
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    width: 560px;
    max-width: 100%;
    max-height: 100%;
    min-height: 0;
    padding: 24px;
    gap: 24px;
    border-radius: 24px;
    background-color: $soft-purple-900;
    color: $neutral-100;
    font-family: Hauora-Regular;
    line-height: 1.4;
    overflow: auto;
    overscroll-behavior: contain;
    scrollbar-width: thin;
    scrollbar-color: $soft-purple-700 transparent;
    > * {
      flex-shrink: 0;
    }
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
      .heading {
        display: flex;
        flex-direction: column;
        min-width: 0;
        gap: 10px;
        h2 {
          min-width: 0;
          margin: 0;
          color: $neutral-white;
          font-family: Involve-Medium;
          font-weight: 500;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        small {
          color: $neutral-300;
          font-size: 14px;
          line-height: 20px;
        }
      }
    }
    .modal-body {
      display: flex;
      flex-direction: column;
      min-width: 0;
      gap: 10px;
      --ui-input-label-bg: #{$soft-purple-800};
      .selected-user {
        padding: 20px;
        border-radius: 20px;
        background-color: $soft-purple-800;
        .user-cell {
          display: flex;
          align-items: center;
          min-width: 0;
          gap: 12px;
          .user-avatar {
            flex: 0 0 40px;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
          }
          span {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-family: Hauora-Medium;
            font-size: 16px;
            line-height: 22px;
          }
        }
      }
      .duration-card {
        display: flex;
        flex-direction: column;
        min-width: 0;
        padding: 20px;
        gap: 20px;
        border-radius: 20px;
        background-color: $soft-purple-800;
        h3 {
          margin: 0;
          color: $neutral-white;
          font-family: Involve-Medium;
          font-weight: 500;
          font-size: 20px;
          line-height: 24px;
          letter-spacing: -0.4px;
        }
        .duration-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px;
          :deep(input) {
            box-sizing: content-box;
          }
        }
      }
    }
    .modal-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 12px;
    }
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
