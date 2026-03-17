<template>
  <Transition name="contacts-modal">
    <div v-if="open" class="contacts-overlay" role="dialog" aria-modal="true" @pointerdown.self="armed = true"
         @pointerup.self="armed && close()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
      <div class="contacts-modal">
        <header>
          <span>Обратная связь</span>
          <button @click="close" aria-label="Закрыть">
            <img :src="iconClose" alt="close" />
          </button>
        </header>
        <div class="contacts-body">
          <p class="body-text">
            Связаться по всем вопросам, связанным с работой и функционированием платформы, а также с предложениями и идеями по нововведениям можно в
            <a :href="contactsLink" target="_blank" rel="noopener noreferrer" @click="close">Telegram</a>
          </p>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import iconClose from '@/assets/svg/close.svg'

const props = defineProps<{ open: boolean; contactsLink: string }>()
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
.contacts-overlay {
  position: fixed;
  display: flex;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($black, 0.25);
  backdrop-filter: blur(5px);
  z-index: 1000;
  .contacts-modal {
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
    .contacts-body {
      padding: 10px;
      color: $fg;
      .body-text {
        margin: 0;
        font-size: 16px;
        line-height: 1.5;
        a {
          color: $white;
          text-decoration: underline;
          transition: opacity 0.25s ease-in-out;
          &:hover {
            opacity: 0.8;
          }
        }
      }
    }
  }
}

.contacts-modal-enter-active,
.contacts-modal-leave-active {
  transition: opacity 0.25s ease-in-out;
}

.contacts-modal-enter-from,
.contacts-modal-leave-to {
  opacity: 0;
}

.contacts-modal-enter-from .contacts-modal,
.contacts-modal-leave-to .contacts-modal {
  transform: translateY(-20px);
}

@media (max-width: 1280px) {
  .contacts-overlay {
    .contacts-modal {
      .contacts-body {
        .body-text {
          font-size: 14px;
        }
      }
    }
  }
}
</style>
