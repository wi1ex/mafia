<template>
  <Teleport to="body">
    <Transition name="overlay">
      <div v-if="open" class="overlay" :style="{ zIndex }" @pointerdown.stop.self="armed = true"
           @pointerup.stop.self="armed && requestClose()" @pointerleave.stop.self="armed = false" @pointercancel.stop.self="armed = false" @click.stop>
        <div class="modal" role="dialog" aria-modal="true" :aria-label="title" @pointerdown.stop @pointerup.stop @click.stop>
          <header>
            <div class="heading">
              <span>{{ title }}</span>
              <small v-if="statusText">{{ statusText }}</small>
            </div>
            <button class="icon" type="button" aria-label="Закрыть" @click="requestClose">
              <img :src="iconClose" alt="close" />
            </button>
          </header>
          <div class="modal-body">
            <div v-if="target" class="selected-user">
              <div class="user-cell">
                <img class="user-avatar" v-minio-img="{ key: target.avatar_name ? `avatars/${target.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                <span>{{ target.username || `user${target.user_id}` }}</span>
              </div>
            </div>
            <div class="grid duration-grid">
              <UiInput
                id="subscription-modal-months"
                v-model.number="form.months"
                type="number"
                min="0"
                max="240"
                step="1"
                label="Месяцы"
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
                :disabled="saving"
              />
            </div>
          </div>
          <div class="modal-actions">
            <button class="btn dark" type="button" @click="requestClose">Отмена</button>
            <button class="btn confirm" type="button" :disabled="saving || !canSave" @click="$emit('save')">
              {{ saving ? '...' : saveLabel }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import UiInput from '@/components/UiInput.vue'

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
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba($black, 0.25);
  backdrop-filter: blur(5px);
  z-index: 1000;
  .modal {
    width: 420px;
    max-width: calc(100% - 30px);
    border-radius: 5px;
    background-color: $graphite;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    .btn {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 20px;
      gap: 5px;
      height: 40px;
      border: none;
      border-radius: 5px;
      background-color: $fg;
      font-size: 14px;
      color: $bg;
      font-family: Manrope-Medium;
      line-height: 1;
      cursor: pointer;
      transition: opacity 0.25s ease-in-out, color 0.25s ease-in-out, border-radius 0.25s ease-in-out, background-color 0.25s ease-in-out;
      &:hover {
        background-color: $white;
      }
      &.confirm {
        background-color: rgba($green, 0.75);
        &:hover {
          background-color: $green;
        }
      }
      &.dark {
        background-color: $lead;
        color: $fg;
        &:hover {
          background-color: rgba($grey, 0.5);
        }
      }
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      .heading {
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      span {
        font-size: 18px;
        font-family: Manrope-Medium;
      }
      small {
        color: $grey;
        font-size: 12px;
      }
      .icon {
        width: 28px;
        height: 28px;
        border: none;
        background: none;
        cursor: pointer;
        img {
          width: 20px;
          height: 20px;
        }
      }
    }
    .modal-body {
      display: flex;
      flex-direction: column;
      gap: 10px;
      .grid {
        display: grid;
        gap: 10px;
      }
      .duration-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    .selected-user {
      display: flex;
      flex-direction: column;
      gap: 5px;
      padding: 10px;
      border: 1px solid $lead;
      border-radius: 5px;
      background-color: rgba($black, 0.08);
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      .user-cell {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        span {
          font-family: Manrope-Medium;
        }
      }
    }
    .user-avatar {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      object-fit: cover;
    }
    .modal-actions {
      display: flex;
      justify-content: flex-end;
      margin-top: 10px;
      gap: 10px;
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
