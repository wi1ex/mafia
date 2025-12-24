<template>
  <Teleport to="body">
    <Transition name="overlay">
      <div v-if="open" class="overlay" @click.self="close">
        <div class="modal" role="dialog" aria-modal="true" :aria-label="title">
          <header>
            <span>{{ title }}</span>
            <button class="icon" @click="close" aria-label="Закрыть">
              <img :src="iconClose" alt="close" />
            </button>
          </header>
          <div class="modal-body">
            <div class="ui-input" :class="{ filled: Boolean(form.version) }">
              <input id="update-version" v-model.trim="form.version" type="text" placeholder=" " autocomplete="off" />
              <label for="update-version">Версия</label>
            </div>
            <div class="ui-input" :class="{ filled: Boolean(form.date) }">
              <input id="update-date" v-model="form.date" type="date" placeholder=" " autocomplete="off" />
              <label for="update-date">Дата</label>
            </div>
            <div class="ui-input textarea" :class="{ filled: Boolean(form.description) }">
              <textarea id="update-desc" v-model.trim="form.description" rows="5" placeholder=" "></textarea>
              <label for="update-desc">Описание</label>
            </div>
          </div>
          <div class="modal-actions">
            <button class="btn" @click="close">Отмена</button>
            <button class="btn confirm" :disabled="saving || !canSave" @click="$emit('save')">
              <img v-if="saveIcon" class="btn-img" :src="saveIcon" alt="save" />
              Сохранить
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import iconClose from '@/assets/svg/close.svg'

defineProps<{
  open: boolean
  title: string
  saving: boolean
  canSave: boolean
  saveIcon?: string
  form: {
    version: string
    date: string
    description: string
  }
}>()

const emit = defineEmits<{
  'update:open': [boolean]
  'save': []
}>()

function close() {
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
  background-color: rgba($black, 0.75);
  z-index: 1000;
  .modal {
    width: 520px;
    max-width: calc(100% - 30px);
    border-radius: 8px;
    background-color: $graphite;
    box-shadow: 0 10px 30px rgba($black, 0.4);
    padding: 15px;
    display: flex;
    flex-direction: column;
    gap: 15px;
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
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .btn-img {
        width: 20px;
        height: 20px;
      }
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      span {
        font-size: 18px;
        font-family: Manrope-Medium;
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
      gap: 12px;
    }
    .ui-input {
      display: block;
      position: relative;
      width: 100%;
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      input,
      textarea {
        width: calc(100% - 22px);
        padding: 20px 10px 5px;
        border: 1px solid $lead;
        border-radius: 5px;
        background-color: $graphite;
        color: $fg;
        font-size: 16px;
        font-family: Manrope-Medium;
        line-height: 1;
        outline: none;
        transition: border-color 0.25s ease-in-out, background-color 0.25s ease-in-out;
      }
      input::placeholder,
      textarea::placeholder {
        color: transparent;
      }
      textarea {
        resize: vertical;
        min-height: 120px;
      }
      label {
        position: absolute;
        top: 50%;
        left: 12px;
        color: $fg;
        transform: translateY(-50%);
        pointer-events: none;
        transition: all 0.25s ease-in-out;
      }
      &:focus-within label,
      input:not(:placeholder-shown) + label,
      textarea:not(:placeholder-shown) + label,
      &.filled label {
        top: 5px;
        left: 10px;
        transform: none;
        font-size: 12px;
        color: $grey;
      }
    }
    .ui-input + .ui-input {
      margin-top: 10px;
    }
    .modal-actions {
      display: flex;
      justify-content: flex-end;
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
