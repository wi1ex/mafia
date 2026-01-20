<template>
  <Teleport to="body">
    <Transition name="overlay">
      <div v-if="open" class="overlay" @pointerdown.self="armed = true" @pointerup.self="armed && close()"
           @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <div class="modal" role="dialog" aria-modal="true" :aria-label="title">
          <header>
            <span>{{ title }}</span>
            <button class="icon" @click="close" aria-label="Закрыть">
              <img :src="iconClose" alt="close" />
            </button>
          </header>
          <div class="modal-body">
            <div v-if="showDuration" class="grid">
              <div class="ui-input" :class="{ filled: Number.isFinite(form.months) }">
                <input id="sanction-months" v-model.number="form.months" type="number" min="0" placeholder=" " autocomplete="off" />
                <label for="sanction-months">Месяцы</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(form.days) }">
                <input id="sanction-days" v-model.number="form.days" type="number" min="0" placeholder=" " autocomplete="off" />
                <label for="sanction-days">Дни</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(form.hours) }">
                <input id="sanction-hours" v-model.number="form.hours" type="number" min="0" placeholder=" " autocomplete="off" />
                <label for="sanction-hours">Часы</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(form.minutes) }">
                <input id="sanction-minutes" v-model.number="form.minutes" type="number" min="0" placeholder=" " autocomplete="off" />
                <label for="sanction-minutes">Минуты</label>
              </div>
            </div>
            <div class="ui-input" :class="{ filled: Boolean(form.reason) }">
              <select id="sanction-reason" v-model="form.reason">
                <option v-for="item in reasons" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
              <label for="sanction-reason">Причина</label>
            </div>
          </div>
          <div class="modal-actions">
            <button class="btn dark" @click="close">Отмена</button>
            <button class="btn confirm" :disabled="saving || !canSave" @click="$emit('save')">
              Применить
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import iconClose from '@/assets/svg/close.svg'

withDefaults(defineProps<{
  open: boolean
  title: string
  saving: boolean
  canSave: boolean
  showDuration?: boolean
  reasons: { value: string; label: string }[]
  form: {
    months: number
    days: number
    hours: number
    minutes: number
    reason: string
  }
}>(), {
  showDuration: true,
})

const emit = defineEmits<{
  'update:open': [boolean]
  'save': []
}>()

const armed = ref(false)

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
      gap: 10px;
      .grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }
    }
    .ui-input {
      display: block;
      position: relative;
      width: 100%;
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      input,
      select {
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
      select {
        appearance: none;
      }
      input::placeholder {
        color: transparent;
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
      select:valid + label,
      &.filled label {
        top: 5px;
        left: 10px;
        transform: none;
        font-size: 12px;
        color: $grey;
      }
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

@media (max-width: 1280px) {
  .overlay {
    .modal {
      .btn {
        padding: 0 10px;
        height: 30px;
      }
      .modal-body {
        .grid {
          grid-template-columns: 1fr;
        }
      }
    }
  }
}
</style>
