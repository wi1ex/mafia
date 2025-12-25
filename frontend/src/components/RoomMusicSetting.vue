<template>
  <Transition name="panel">
    <div v-show="open" class="music-settings" aria-label="Настройки музыки" @click.stop>
      <header>
        <span>Панель управления</span>
        <button @click="$emit('close')" aria-label="Закрыть">
          <img :src="iconClose" alt="close" />
        </button>
      </header>
      <div class="controls">
        <label class="volume">
          <span>Громкость фоновой музыки</span>
          <div class="volume-row">
            <input
              type="range"
              min="0"
              max="100"
              :value="volume"
              aria-label="Громкость фоновой музыки"
              @input="onVolumeInput"
            />
            <span class="value">{{ volume }}%</span>
          </div>
        </label>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import iconClose from '@/assets/svg/close.svg'

defineProps<{
  open: boolean
  volume: number
}>()

const emit = defineEmits<{
  'update:volume': [number]
  'close': []
}>()

function onVolumeInput(e: Event) {
  emit('update:volume', Number((e.target as HTMLInputElement).value))
}
</script>

<style scoped lang="scss">
.music-settings {
  display: flex;
  position: absolute;
  flex-direction: column;
  right: 0;
  bottom: 50px;
  width: 320px;
  border-radius: 5px;
  background-color: $dark;
  box-shadow: 3px 3px 5px rgba($black, 0.25);
  z-index: 25;
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
  .controls {
    display: flex;
    flex-direction: column;
    padding: 10px;
    gap: 10px;
    border-radius: 5px;
    background-color: $dark;
    .volume {
      display: flex;
      flex-direction: column;
      gap: 8px;
      span {
        height: 16px;
        color: $fg;
        font-size: 14px;
      }
      .volume-row {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 10px;
        align-items: center;
      }
      input[type="range"] {
        width: 100%;
        cursor: pointer;
      }
      .value {
        min-width: 42px;
        text-align: right;
        color: $fg;
        font-size: 14px;
        font-family: Manrope-Medium;
      }
    }
  }
}

.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}
.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(30px);
}

@media (max-width: 1280px) {
  .music-settings {
    bottom: 30px;
  }
}
</style>
