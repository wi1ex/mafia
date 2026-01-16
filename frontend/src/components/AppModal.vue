<template>
  <Transition name="install-modal">
    <div v-if="open" class="install-overlay" role="dialog" aria-modal="true" @pointerdown.self="armed = true"
         @pointerup.self="armed && close()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
      <div class="install-modal">
        <header>
          <span>Установить как приложение</span>
          <button @click="close" aria-label="Закрыть">
            <img :src="iconClose" alt="close" />
          </button>
        </header>
        <div class="install-body">
          <span class="body-text">Установка позволяет использовать сайт в полноэкранном режиме. Иконка приложения будет добавлена на главный экран</span>
          <div class="section">
            <span class="body-title">Android (Chrome)</span>
            <ol>
              <li>Откройте меню браузера (⋮)</li>
              <li>Выберите «Установить приложение» или «Добавить на главный экран»</li>
            </ol>
          </div>
          <div class="section">
            <span class="body-title">iPhone/iPad (Safari/Chrome)</span>
            <ol>
              <li>Нажмите «Поделиться»</li>
              <li>Выберите «На экран Домой»</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import iconClose from "@/assets/svg/close.svg"

const props = defineProps<{ open: boolean }>()
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
.install-overlay {
  position: fixed;
  display: flex;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($black, 0.75);
  z-index: 1000;
  .install-modal {
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
    .install-body {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 10px;
      color: $fg;
      .body-text {
        font-size: 16px;
      }
      .section {
        display: flex;
        flex-direction: column;
        gap: 5px;
        .body-title {
          font-size: 16px;
          font-weight: bold;
        }
        ol {
          display: flex;
          flex-direction: column;
          margin: 0;
          padding-left: 20px;
          li {
            font-size: 14px;
            line-height: 1.5;
          }
        }
      }
    }
  }
}

.install-modal-enter-active,
.install-modal-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.install-modal-enter-from,
.install-modal-leave-to {
  opacity: 0;
}
.install-modal-enter-from .install-modal,
.install-modal-leave-to .install-modal {
  transform: translateY(-20px);
}

@media (max-width: 1280px) {
  .install-overlay {
    .install-modal {
      .install-body {
        .body-text {
          font-size: 14px;
        }
        .section {
          .body-title {
            font-size: 14px;
          }
          ol {
            li {
              font-size: 12px;
            }
          }
        }
      }
    }
  }
}
</style>
