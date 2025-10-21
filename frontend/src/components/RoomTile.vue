<template>
  <div class="tile" :class="[{ speaking }, side && 'side']" tabindex="0">
    <video v-show="showVideo" :ref="videoRef" playsinline autoplay :muted="id === localId" />

    <div v-show="!showVideo" class="ava-wrap">
      <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" />
    </div>

    <div class="titlebar">
      <div class="titlebar-div">
        <button :disabled="id===localId" :aria-disabled="id===localId" @click.stop="$emit('toggle-panel', id)" :aria-expanded="openPanel">
          <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" />
          <span>{{ userName(id) }}</span>
        </button>

        <div class="status">
          <img v-if="isBlocked(id,'mic') || !isOn(id,'mic')" :src="stateIcon('mic', id)" alt="mic" />
          <img v-if="isBlocked(id,'cam') || !isOn(id,'cam')" :src="stateIcon('cam', id)" alt="cam" />
          <img v-if="isBlocked(id,'speakers') || !isOn(id,'speakers')" :src="stateIcon('speakers', id)" alt="spk" />
          <img v-if="isBlocked(id,'visibility') || !isOn(id,'visibility')" :src="stateIcon('visibility', id)" alt="vis" />
          <img v-if="isBlocked(id,'screen')" :src="stateIcon('screen', id)" alt="scr" />
        </div>
      </div>
    </div>

    <div v-if="openPanel" class="tile-panel" @click.stop>
      <button class="panel-close" aria-label="Закрыть" @click.stop="$emit('toggle-panel', id)">
        <img :src="iconClose" alt="close" />
      </button>

      <div class="panel-user">
        <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar }" alt="" />
        <span>{{ userName(id) }}</span>
      </div>

      <div v-if="id !== localId" class="volume" @click.stop>
        <img :src="volumeIcon" alt="vol" />
        <input type="range" min="0" max="200" :disabled="!speakersOn || isBlocked(id,'speakers')" :value="vol ?? 100"
               @input="$emit('vol-input', id, Number(($event.target as HTMLInputElement).value))" />
        <span>{{ vol ?? 100 }}%</span>
      </div>

      <div v-if="canModerate(id)" class="admin-row" aria-label="Блокировки">
        <button @click="$emit('block','mic',id)" aria-label="block mic">
          <img :src="stateIcon('mic', id)" alt="mic" />
        </button>
        <button @click="$emit('block','cam',id)" aria-label="block cam">
          <img :src="stateIcon('cam', id)" alt="cam" />
        </button>
        <button @click="$emit('block','speakers',id)" aria-label="block speakers">
          <img :src="stateIcon('speakers', id)" alt="spk" />
        </button>
        <button @click="$emit('block','visibility',id)" aria-label="block visibility">
          <img :src="stateIcon('visibility', id)" alt="vis" />
        </button>
        <button @click="$emit('block','screen',id)" aria-label="block screen">
          <img :src="stateIcon('screen', id)" alt="scr" />
        </button>
        <button class="red-button" @click="$emit('kick', id)" aria-label="kick user">
          <img :src="iconLeaveRoom" alt="kick" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import iconClose from '@/assets/svg/close.svg'
import iconLeaveRoom from '@/assets/svg/leaveRoom.svg'

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
  (e: 'vol-input', id: string, v: number): void
  (e: 'block', key: 'mic'|'cam'|'speakers'|'visibility'|'screen', id: string): void
  (e: 'kick', id: string): void
}>()

const openPanel = computed(() => props.openPanelFor === props.id)
const showVideo = computed(() => props.isOn(props.id, 'cam') && !props.isBlocked(props.id, 'cam'))
</script>

<style scoped lang="scss">
.tile {
  position: relative;
  min-width: 0;
  min-height: 0;
  border-radius: 5px;
  border: 2px solid transparent;
  transition: border-color 0.25s ease-in-out;
  overflow: hidden;
  &.speaking {
    border-color: $green;
  }
  video {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 3px;
    background-color: $black;
  }
  .ava-wrap {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    inset: 0;
    background-color: $black;
    border-radius: 3px;
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
    background-color: rgba($black, 0.5);
    backdrop-filter: blur(5px);
    z-index: 5;
    .titlebar-div {
      display: flex;
      align-items: center;
      min-width: 0;
      button {
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
        span {
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
  }
  .tile-panel {
    display: flex;
    position: absolute;
    flex-direction: column;
    top: 5px;
    left: 5px;
    padding: 5px;
    gap: 10px;
    width: 226px;
    height: 118px;
    background-color: rgba($black, 0.8);
    backdrop-filter: blur(5px);
    z-index: 10;
    .panel-close {
      position: absolute;
      top: 5px;
      right: 5px;
      width: 30px;
      height: 30px;
      border: none;
      border-radius: 3px;
      background-color: $dark;
      cursor: pointer;
      img {
        width: 20px;
        height: 20px;
      }
    }
    .panel-user {
      display: flex;
      align-items: flex-start;
      gap: 5px;
      img {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        object-fit: cover;
      }
      span {
        color: $fg;
        font-size: 20px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }
    .volume {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 8px;
    width: calc(100% - 16px);
    height: 30px;
    border: none;
    border-radius: 3px;
    background-color: $dark;
    cursor: pointer;
    -webkit-overflow-scrolling: touch;
      img {
        width: 24px;
        height: 24px;
      }
      input[type="range"] {
        width: 140px;
        height: 10px;
        accent-color: $fg;
      }
      span {
        text-align: center;
        font-size: 12px;
      }
    }
    .admin-row {
      display: flex;
      gap: 9px;
      button {
        border-radius: 3px;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 5px;
        border: none;
        background-color: rgba($grey, 0.25);
        cursor: pointer;
        &.red-button {
          background-color: rgba($red, 0.5);
        }
        img {
          width: 20px;
          height: 20px;
        }
      }
    }
  }
}
.tile.side {
  aspect-ratio: 16 / 9;
}
</style>
