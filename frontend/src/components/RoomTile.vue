<template>
  <div class="tile" :class="[{ speaking }, side && 'side']" tabindex="0">
    <video v-show="showVideo" :ref="videoRef" playsinline autoplay :muted="id === localId" :style="{ objectFit: fitContain ? 'contain' : 'cover' }" />

    <div v-show="!showVideo" class="ava-wrap">
      <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar, lazy: false }" alt="" />
    </div>

    <div class="user-card" :class="{ expanded: openPanel }">
      <button class="card-head" :disabled="id === localId" :aria-disabled="id === localId" @click.stop="$emit('toggle-panel', id)" :aria-expanded="openPanel">
        <img v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar, lazy: false }" alt="" />
        <span>{{ userName(id) }}</span>
        <div class="status">
          <img v-if="isBlocked(id,'mic') || !isOn(id,'mic')" :src="stateIcon('mic', id)" alt="mic" />
          <img v-if="isBlocked(id,'cam') || !isOn(id,'cam')" :src="stateIcon('cam', id)" alt="cam" />
          <img v-if="isBlocked(id,'speakers') || !isOn(id,'speakers')" :src="stateIcon('speakers', id)" alt="spk" />
          <img v-if="isBlocked(id,'visibility') || !isOn(id,'visibility')" :src="stateIcon('visibility', id)" alt="vis" />
          <img v-if="isBlocked(id,'screen')" :src="stateIcon('screen', id)" alt="scr" />
        </div>
      </button>

      <Transition name="card-body">
        <div v-if="openPanel" class="card-body" @click.stop>
          <div class="panel-user">
            <span>{{ userName(id) }}</span>
            <button class="panel-close" aria-label="Закрыть" @click.stop="$emit('toggle-panel', id)">
              <img :src="iconClose" alt="close" />
            </button>
          </div>

          <div v-if="id !== localId" class="volume">
            <img :src="volumeIcon" alt="vol" />
            <input type="range" min="0" max="200" :disabled="!speakersOn || isBlocked(id,'speakers')"
                   :value="vol ?? 100" @input="$emit('vol-input', id, Number(($event.target as HTMLInputElement).value))" />
            <span>{{ vol ?? 100 }}%</span>
          </div>

          <div v-if="canModerate(id)" class="admin-row" aria-label="Блокировки">
            <button @click="$emit('block','mic',id)" aria-label="block mic"><img :src="stateIcon('mic', id)" alt="mic" /></button>
            <button @click="$emit('block','cam',id)" aria-label="block cam"><img :src="stateIcon('cam', id)" alt="cam" /></button>
            <button @click="$emit('block','speakers',id)" aria-label="block speakers"><img :src="stateIcon('speakers', id)" alt="spk" /></button>
            <button @click="$emit('block','visibility',id)" aria-label="block visibility"><img :src="stateIcon('visibility', id)" alt="vis" /></button>
            <button @click="$emit('block','screen',id)" aria-label="block screen"><img :src="stateIcon('screen', id)" alt="scr" /></button>
            <button class="red-button" @click="$emit('kick', id)" aria-label="kick user"><img :src="iconLeaveRoom" alt="kick" /></button>
          </div>
        </div>
      </Transition>
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
  fitContain?: boolean
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

<style lang="scss" scoped>
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
    border-radius: 5px;
    background-color: $black;
  }
  .ava-wrap {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    inset: 0;
    background-color: $black;
    border-radius: 5px;
    z-index: 1;
    img {
      height: 40%;
      border-radius: 50%;
      user-select: none;
    }
  }
  .user-card {
    position: absolute;
    left: 5px;
    top: 5px;
    width: 250px;
    border-radius: 5px;
    backdrop-filter: blur(5px);
    background-color: rgba($graphite, 0.75);
    z-index: 5;
    overflow: hidden;
    max-height: 30px;
    transition: max-height 0.25s ease-in-out, background-color 0.25s ease-in-out;
    &.expanded {
      background-color: rgba($dark, 0.75);
      max-height: 190px;
    }
    .card-head {
      display: flex;
      align-items: center;
      gap: 5px;
      height: 30px;
      width: 100%;
      padding: 0 10px;
      border: none;
      background: none;
      cursor: pointer;
      &:disabled {
        cursor: default;
      }
      img {
        width: 20px;
        height: 20px;
        border-radius: 50%;
        object-fit: cover;
      }
      span {
        flex: 1 1 auto;
        min-width: 0;
        height: 18px;
        color: $fg;
        font-size: 16px;
        font-family: Manrope-Medium;
        line-height: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .status {
        display: flex;
        align-items: center;
        gap: 5px;
        img {
          width: 20px;
          height: 20px;
        }
      }
    }
    .card-body-enter-from,
    .card-body-leave-to {
      opacity: 0;
      transform: translateY(-4px);
    }
    .card-body-enter-active,
    .card-body-leave-active {
      transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
    }
    .card-body {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 5px 10px 10px;
      .panel-user {
        display: flex;
        align-items: center;
        justify-content: space-between;
        height: 30px;
        span {
          color: $fg;
          font-size: 16px;
        }
        .panel-close {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 20px;
          height: 30px;
          border: none;
          background: none;
          cursor: pointer;
          img {
            width: 20px;
            height: 20px;
          }
        }
      }
      .volume {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-top: -5px;
        padding: 5px;
        gap: 5px;
        width: calc(100% - 10px);
        height: 20px;
        border-radius: 5px;
        background-color: rgba($graphite, 0.75);
        -webkit-overflow-scrolling: touch;
        img {
          width: 20px;
          height: 20px;
        }
        input[type="range"] {
          width: 174px;
          height: 10px;
          accent-color: $fg;
          cursor: pointer;
        }
        span {
          min-width: 32px;
          text-align: center;
          font-size: 12px;
        }
      }
      .admin-row {
        display: flex;
        gap: 10px;
        button {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          width: calc(200px / 6);
          height: 25px;
          border: none;
          border-radius: 5px;
          background-color: rgba($graphite, 0.75);
          cursor: pointer;
          &.red-button {
            background-color: rgba($red, 0.75);
          }
          img {
            width: 20px;
            height: 20px;
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
