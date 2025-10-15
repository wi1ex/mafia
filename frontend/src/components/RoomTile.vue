<template>
  <div class="tile" :class="[{ speaking }, side && 'side']" tabindex="0">
    <video v-show="showVideo" :ref="videoRef" playsinline autoplay :muted="id === localId" />

    <div v-show="!showVideo" class="ava-wrap">
      <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" class="ava-circle" />
    </div>

    <div class="titlebar">
      <div class="titlebar-div">
        <button class="title-btn" :disabled="id===localId" :aria-disabled="id===localId" @click.stop="$emit('toggle-panel', id)" :aria-expanded="openPanel">
          <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" class="title-ava" />
          <span class="title-nick">{{ userName(id) }}</span>
        </button>

        <div v-if="!canModerate(id)" class="status">
          <img class="status-icon" :src="stateIcon('mic', id)" alt="mic" />
          <img class="status-icon" :src="stateIcon('cam', id)" alt="cam" />
          <img class="status-icon" :src="stateIcon('speakers', id)" alt="spk" />
          <img class="status-icon" :src="stateIcon('visibility', id)" alt="vis" />
          <img class="status-icon" :src="stateIcon('screen', id)" alt="scr" />
        </div>

        <div v-else class="admin-row" aria-label="Блокировки">
          <button class="mod" @click="$emit('block','mic',id)" aria-label="block mic">
            <img class="status-icon" :src="stateIcon('mic', id)" alt="mic" />
          </button>
          <button class="mod" @click="$emit('block','cam',id)" aria-label="block cam">
            <img class="status-icon" :src="stateIcon('cam', id)" alt="cam" />
          </button>
          <button class="mod" @click="$emit('block','speakers',id)" aria-label="block speakers">
            <img class="status-icon" :src="stateIcon('speakers', id)" alt="spk" />
          </button>
          <button class="mod" @click="$emit('block','visibility',id)" aria-label="block visibility">
            <img class="status-icon" :src="stateIcon('visibility', id)" alt="vis" />
          </button>
          <button class="mod" @click="$emit('block','screen',id)" aria-label="block screen">
            <img class="status-icon" :src="stateIcon('screen', id)" alt="scr" />
          </button>
        </div>
      </div>

      <div v-if="id !== localId" class="volume">
        <button v-if="!openVol" class="vol-btn" @click.stop="$emit('toggle-volume', id)" :disabled="!speakersOn || isBlocked(id,'speakers')" aria-label="volume">
          <img class="status-icon" :src="iconVolumeMax" alt="vol" />
        </button>
        <div v-else class="vol-inline" @click.stop>
          <input class="vol-slider" type="range" min="0" max="200" :disabled="!speakersOn || isBlocked(id,'speakers')" :value="vol ?? 100"
                 @input="$emit('vol-input', id, Number(($event.target as HTMLInputElement).value))" />
          <span class="vol-val">{{ vol ?? 100 }}%</span>
        </div>
      </div>
    </div>

    <div v-if="openPanel" class="tile-panel" @click.stop>
      <div class="panel-user">
        <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" class="panel-ava" />
        <div class="panel-nick">{{ userName(id) }}</div>
        <div class="panel-nick">*информация о пользователе*</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type IconKind = 'mic' | 'cam' | 'speakers' | 'visibility' | 'screen'

const props = withDefaults(defineProps<{
  id: string
  localId: string
  speaking: boolean
  side?: boolean
  defaultAvatar: string
  iconVolumeMax: string
  videoRef: (el: HTMLVideoElement | null) => void
  openPanelFor: string
  openVolFor: string
  speakersOn: boolean
  vol?: number
  stateIcon: (k: IconKind, id: string) => string
  isOn: (id: string, k: IconKind) => boolean
  isBlocked: (id: string, k: IconKind) => boolean
  userName: (id: string) => string
  avatarKey: (id: string) => string
  canModerate: (id: string) => boolean
}>(), { side: false })

defineEmits<{
  (e: 'toggle-panel', id: string): void
  (e: 'toggle-volume', id: string): void
  (e: 'vol-input', id: string, v: number): void
  (e: 'block', key: 'mic'|'cam'|'speakers'|'visibility'|'screen', id: string): void
}>()

const openPanel = computed(() => props.openPanelFor === props.id)
const openVol   = computed(() => props.openVolFor === props.id)
const showVideo = computed(() => props.isOn(props.id, 'cam') && !props.isBlocked(props.id, 'cam'))
</script>

<style scoped lang="scss">
.tile {
  position: relative;
  border-radius: 5px;
  border: 2px solid transparent;
  transition: border-color 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
  overflow: hidden;
  &.speaking {
    border-color: $color-primary;
    box-shadow: inset 0 0 0 6px $color-primary;
  }
  video {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 5px;
  }
  .ava-wrap {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: $black;
    border-radius: 5px;
    z-index: 1;
  }
  .ava-circle {
    height: 40%;
    border-radius: 50%;
    user-select: none;
    pointer-events: none;
  }
  .titlebar {
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    max-height: 36px;
    background: rgba($black, 0.65);
    backdrop-filter: blur(4px);
    z-index: 5;
  }
  .titlebar-div {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    border: 1px solid transparent;
    background: transparent;
    color: $fg;
    padding: 2px;
    .title-btn {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      border: 1px solid transparent;
      border-radius: 5px;
      background: transparent;
      color: $fg;
      cursor: pointer;
      padding: 2px;
      &:disabled {
        cursor: default;
      }
      .title-ava {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        object-fit: cover;
      }
      .title-nick {
        max-width: 160px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }
    .status {
      display: flex;
      gap: 5px;
      align-items: center;
      .status-icon {
        width: 18px;
        height: 18px;
        display: block;
      }
    }
    .admin-row {
      display: flex;
      flex-wrap: wrap;
      .mod {
        border-radius: 5px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: 1px solid rgba($fg, 0.25);
        background: $black;
        cursor: pointer;
        .status-icon {
          width: 18px;
          height: 18px;
          display: block;
        }
      }
    }
  }
  .volume {
    display: inline-flex;
    align-items: center;
    margin-right: 4px;
  }
  .vol-btn {
    border-radius: 5px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid rgba($fg, 0.25);
    background: $black;
    cursor: pointer;
    .status-icon {
      width: 18px;
      height: 18px;
      display: block;
    }
  }
  .vol-inline {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    .vol-slider {
      flex: 1 1 auto;
      height: 24px;
      accent-color: $fg;
    }
    .vol-val {
      min-width: 48px;
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
  }
  .tile-panel {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 10px;
    background: rgba($black, 0.8);
    backdrop-filter: blur(6px);
    z-index: 6;
    .panel-user {
      margin: auto;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
    }
    .panel-ava {
      width: 96px;
      height: 96px;
      border-radius: 50%;
      object-fit: cover;
    }
    .panel-nick {
      font-weight: 600;
    }
  }
}
.tile.side {
  aspect-ratio: 16 / 9;
}
</style>
