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
        <div v-if="canToggleKnownRoles" class="switch">
          <span class="switch-label">Показ ролей:</span>
          <label>
            <input type="checkbox" :checked="knownRolesVisible" aria-label="Показ ролей" @change="onToggleKnownRoles" />
            <div class="slider">
              <span>Откл</span>
              <span>Вкл</span>
            </div>
          </label>
        </div>
        <div class="volume-block">
          <span>Громкость музыки:</span>
          <div class="volume">
            <img :src="iconVolumeMid" alt="vol" />
            <input type="range" min="0" max="100" :value="volume" aria-label="Громкость фоновой музыки" @input="onVolumeInput" />
            <span>{{ volume }}%</span>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import iconClose from '@/assets/svg/close.svg'
import iconVolumeMid from '@/assets/svg/volumeMid.svg'

defineProps<{
  open: boolean
  volume: number
  canToggleKnownRoles: boolean
  knownRolesVisible: boolean
}>()

const emit = defineEmits<{
  'update:volume': [number]
  'toggle-known-roles': []
  'close': []
}>()

function onVolumeInput(e: Event) {
  emit('update:volume', Number((e.target as HTMLInputElement).value))
}
function onToggleKnownRoles() {
  emit('toggle-known-roles')
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
    .switch {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      .switch-label {
        height: 18px;
        color: $fg;
        font-size: 14px;
      }
      label {
        position: relative;
        width: 120px;
        height: 25px;
        box-shadow: 3px 3px 5px rgba($black, 0.25);
        input {
          position: absolute;
          opacity: 0;
          width: 0;
          height: 0;
        }
        .slider {
          display: flex;
          align-items: center;
          justify-content: space-around;
          position: absolute;
          inset: 0;
          cursor: pointer;
          border: 1px solid $lead;
          border-radius: 5px;
          background-color: $graphite;
          span {
            position: relative;
            width: 100%;
            color: $fg;
            font-size: 14px;
            text-align: center;
            transition: color 0.25s ease-in-out;
          }
        }
        .slider:before {
          content: "";
          position: absolute;
          top: 0;
          left: 0;
          width: 58px;
          height: 23px;
          background-color: $fg;
          border-radius: 5px;
          transition: transform 0.25s ease-in-out;
        }
        input:checked + .slider:before {
          transform: translateX(60px);
        }
        input:not(:checked) + .slider span:first-child,
        input:checked + .slider span:last-child {
          color: $bg;
        }
      }
    }
    .volume-block {
      display: flex;
      flex-direction: column;
      gap: 8px;
      span {
        height: 16px;
        color: $fg;
        font-size: 14px;
      }
    }
    .volume {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 5px;
      gap: 5px;
      width: calc(100% - 10px);
      height: 20px;
      border-radius: 5px;
      background-color: $graphite;
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      -webkit-overflow-scrolling: touch;
      img {
        flex: 0 0 auto;
        width: 20px;
        height: 20px;
      }
      input[type="range"] {
        flex: 1 1 auto;
        min-width: 0;
        height: 8px;
        accent-color: $fg;
        cursor: pointer;
        appearance: none;
        background: transparent;
      }
      span {
        flex: 0 0 auto;
        min-width: 32px;
        text-align: center;
        font-size: 12px;
      }
      input[type="range"]:disabled {
        cursor: default;
        opacity: 0.5;
      }
      input[type="range"]:focus-visible {
        outline: 1px solid $fg;
        outline-offset: 1px;
      }
      input[type="range"]::-webkit-slider-runnable-track {
        height: 6px;
        border-radius: 3px;
        background-color: $grey;
      }
      input[type="range"]::-webkit-slider-thumb {
        -webkit-appearance: none;
        appearance: none;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background-color: $fg;
        border: 3px solid $dark;
        margin-top: calc(-18px / 2 + 3px);
      }
      input[type="range"]::-moz-range-track {
        height: 6px;
        border-radius: 3px;
        background-color: $grey;
      }
      input[type="range"]::-moz-range-thumb {
        width: 16px;
        height: 16px;
        border-radius: 50%;
        background-color: $fg;
        border: 3px solid $dark;
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
