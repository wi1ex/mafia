<template>
  <div class="tile" :class="[{ speaking }, side && 'side']" tabindex="0">
    <video v-show="showVideo" :ref="videoRef" playsinline autoplay :muted="id === localId" />

    <div v-show="!showVideo" class="ava-wrap">
      <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" />
    </div>

    <div class="titlebar">
      <div class="titlebar-div">
        <button class="title-btn" :disabled="id===localId" :aria-disabled="id===localId" @click.stop="$emit('toggle-panel', id)" :aria-expanded="openPanel">
          <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" />
          <span class="title-nick">{{ userName(id) }}</span>
        </button>

        <div class="status">
          <img v-if="isBlocked(id,'mic') || !isOn(id,'mic')" :src="stateIcon('mic', id)" alt="mic" />
          <img v-if="isBlocked(id,'cam') || !isOn(id,'cam')" :src="stateIcon('cam', id)" alt="cam" />
          <img v-if="isBlocked(id,'speakers') || !isOn(id,'speakers')" :src="stateIcon('speakers', id)" alt="spk" />
          <img v-if="isBlocked(id,'visibility') || !isOn(id,'visibility')" :src="stateIcon('visibility', id)" alt="vis" />
        </div>
      </div>

      <div v-if="id !== localId" class="volume">
        <button v-if="!openVol" @click.stop="$emit('toggle-volume', id)" :disabled="!speakersOn || isBlocked(id,'speakers')" aria-label="volume">
          <img :src="volumeIcon" alt="vol" />
        </button>
        <div v-else class="vol-inline" @click.stop>
          <img :src="volumeIcon" alt="vol" />
          <input type="range" min="0" max="200" :disabled="!speakersOn || isBlocked(id,'speakers')" :value="vol ?? 100"
                 @input="$emit('vol-input', id, Number(($event.target as HTMLInputElement).value))" />
          <span class="vol-val">{{ vol ?? 100 }}%</span>
        </div>
      </div>
    </div>

    <div v-if="openPanel" class="tile-panel" @click.stop>
      <div class="panel-user">
        <img class="panel-ava" v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" />
        <div class="panel-nick">{{ userName(id) }}</div>
        <div class="panel-nick">*информация о пользователе*</div>

        <div v-if="canModerate(id)" class="admin-row" aria-label="Блокировки">
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
  volumeIcon: string
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
const openVol = computed(() => props.openVolFor === props.id)
const showVideo = computed(() => props.isOn(props.id, 'cam') && !props.isBlocked(props.id, 'cam'))
</script>

<style scoped lang="scss">
.tile {
  position: relative;
  border: 2px solid transparent;
  border-radius: 5px;
  transition: border-color 0.25s ease-in-out;
  &.speaking {
    border-color: $green;
  }
  video {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 3px;
  }
  .ava-wrap {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: $black;
    z-index: 1;
    img {
      height: 40%;
      border-radius: 50%;
      user-select: none;
    }
  }
  .titlebar {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: space-between;
    left: 5px;
    right: 5px;
    top: 5px;
    gap: 5px;
    height: 40px;
    border-radius: 3px;
    background: rgba($black, 0.5);
    backdrop-filter: blur(5px);
    z-index: 5;
    .titlebar-div {
      display: flex;
      align-items: center;
      min-width: 0;
      .title-btn {
        display: flex;
        align-items: center;
        padding: 0 5px;
        gap: 5px;
        min-width: 0;
        border: none;
        background: none;
        cursor: pointer;
        &:disabled {
          cursor: default;
        }
        img {
          width: 24px;
          height: 24px;
          border-radius: 50%;
          object-fit: cover;
        }
        .title-nick {
          color: $fg;
          font-size: 20px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }
      .status {
        display: flex;
        align-items: center;
        gap: 5px;
        img {
          width: 24px;
          height: 24px;
        }
      }
    }
    .volume {
      display: flex;
      position: relative;
      -webkit-overflow-scrolling: touch;
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        border: none;
        border-radius: 3px;
        background: rgba($dark, 0.5);
        cursor: pointer;
        img {
          width: 24px;
          height: 24px;
        }
      }
      .vol-inline {
        display: flex;
        position: absolute;
        flex-direction: column;
        align-items: center;
        justify-content: space-between;
        top: -20px;
        right: 0;
        padding: 8px 5px;
        width: 30px;
        height: 200px;
        border: none;
        border-radius: 3px;
        background: $dark;
        cursor: pointer;
        img {
          width: 24px;
          height: 24px;
        }
        input[type="range"] {
          width: 140px;
          height: 10px;
          accent-color: $fg;
          transform: rotate(270deg);
        }
        .vol-val {
          text-align: center;
          font-size: 12px;
        }
      }
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
      .panel-ava {
        width: 96px;
        height: 96px;
        border-radius: 50%;
        object-fit: cover;
      }
      .panel-nick {
        font-weight: 600;
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
  }
}
.tile.side {
  aspect-ratio: 16 / 9;
}
</style>
