<template>
  <Transition name="support-modal">
    <div v-if="open" class="support-overlay" role="dialog" aria-modal="true" @pointerdown.self="armed = true"
         @pointerup.self="armed && close()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
      <div class="support-modal">
        <header>
          <span>Поддержать проект</span>
          <button @click="close" aria-label="Закрыть">
            <img :src="iconClose" alt="close" />
          </button>
        </header>
        <div class="support-body">
          <span class="body-text">У Вас есть возможность поддержать функционирование и развитие платформы. Кликнув по кнопке ниже Вы будете перенаправлены на официальный сервис поддержки. Благодарим за любую оказанную помощь!</span>
          <a class="support-link" :href="supportLink" target="_blank" rel="noopener noreferrer" @click="close">Поддержать</a>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import iconClose from "@/assets/svg/close.svg"

const props = defineProps<{ open: boolean; supportLink: string }>()
const emit = defineEmits<{ (e: 'update:open', value: boolean): void }>()

const armed = ref(false)
const prevOverflow = ref('')

watch(() => props.open, (open) => {
  if (typeof document === 'undefined') return
  if (open) {
    prevOverflow.value = document.documentElement.style.overflow
    document.documentElement.style.overflow = 'hidden'
  } else {
    document.documentElement.style.overflow = prevOverflow.value
  }
})

function close() {
  emit('update:open', false)
  armed.value = false
}

onBeforeUnmount(() => {
  if (typeof document !== 'undefined') {
    document.documentElement.style.overflow = prevOverflow.value
  }
})
</script>

<style scoped lang="scss">
.support-overlay {
  position: fixed;
  display: flex;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($black, 0.25);
  backdrop-filter: blur(5px);
  z-index: 1000;
  .support-modal {
    display: flex;
    flex-direction: column;
    width: 400px;
    border-radius: 5px;
    background-color: $dark;
    transform: translateY(0);
    transition: transform 0.25s ease-in-out;
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 5px 10px;
      border-radius: 5px;
      background-color: $graphite;
      box-shadow: 0 3px 5px rgba($black, 0.25);
      span {
        font-size: 18px;
        font-weight: bold;
      }
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        width: 25px;
        height: 30px;
        border: none;
        background: none;
        cursor: pointer;
        img {
          width: 25px;
          height: 25px;
        }
      }
    }
    .support-body {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 10px;
      color: $fg;
      .body-text {
        font-size: 16px;
      }
      .support-link {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 40px;
        border-radius: 5px;
        background-color: $fg;
        color: $bg;
        font-size: 18px;
        font-family: Manrope-Medium;
        line-height: 1;
        text-decoration: none;
        transition: opacity 0.25s ease-in-out, background-color 0.25s ease-in-out;
        &:hover {
          background-color: $white;
        }
      }
    }
  }
}

.support-modal-enter-active,
.support-modal-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.support-modal-enter-from,
.support-modal-leave-to {
  opacity: 0;
}
.support-modal-enter-from .support-modal,
.support-modal-leave-to .support-modal {
  transform: translateY(-20px);
}

@media (max-width: 1280px) {
  .support-overlay {
    .support-modal {
      .support-body {
        .body-text {
          font-size: 14px;
        }
        .support-link {
          height: 30px;
          font-size: 14px;
        }
      }
    }
  }
}
</style>
