<template>
  <div class="tile" :class="[{ speaking }, side && 'side']" tabindex="0">
    <video v-show="showVideo" :ref="videoRef" playsinline autoplay :muted="id === localId" :class="{ mirrored: isMirrored(id) }"
           :style="{ objectFit: fitContain ? 'contain' : 'cover' }" />

    <div class="icon-badge left" v-if="isReady(id)" aria-hidden="true">
      <img :src="iconReady" alt="ready" />
    </div>

    <div class="icon-badge right" v-if="gameRole" aria-hidden="true">
      <img :src="gameRole" alt="role" />
    </div>

    <div v-show="!showVideo" class="ava-wrap">
      <img v-if="isDead(id) && deadAvatar" :src="deadAvatar" alt="dead" />
      <img v-else-if="offline && offlineAvatar" :src="offlineAvatar" alt="offline" />
      <img v-else-if="hiddenByVisibility && visibilityHiddenAvatar" :src="visibilityHiddenAvatar" alt="hidden" />
      <img v-else class="avatar" v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar, lazy: false }" alt="avatar" />
    </div>

    <div class="user-card" :data-open="openPanel ? 1 : 0" @click.stop>
      <button class="card-head" :disabled="id === localId"
              :aria-disabled="id === localId" @click.stop="$emit('toggle-panel', id)" :aria-expanded="openPanel">
        <img v-if="seat != null && seatIcon" class="user-slot" :src="seatIcon" alt="seat" />
        <img class="user-avatar" v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar, lazy: false }" alt="avatar" />
        <span>{{ userName(id) }}</span>
        <div class="status" v-if="showStates">
          <img v-if="isBlocked(id,'mic') || !isOn(id,'mic')" :src="stateIcon('mic', id)" alt="mic" />
          <img v-if="isBlocked(id,'cam') || !isOn(id,'cam')" :src="stateIcon('cam', id)" alt="cam" />
          <img v-if="isBlocked(id,'speakers') || !isOn(id,'speakers')" :src="stateIcon('speakers', id)" alt="spk" />
          <img v-if="isBlocked(id,'visibility') || !isOn(id,'visibility')" :src="stateIcon('visibility', id)" alt="vis" />
          <img v-if="isBlocked(id,'screen')" :src="stateIcon('screen', id)" alt="scr" />
        </div>
      </button>

      <Transition name="card-body">
        <div v-show="openPanel" class="card-body" @click.stop>
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
    <div v-if="showRoleTimer && isRolePickOwner && rolePickDurationSec > 0" class="role-timer">
      <div class="role-timer-bar" :style="{ animationDuration: rolePickDurationSec + 's' }" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import iconReady from '@/assets/svg/ready.svg'
import iconLeaveRoom from '@/assets/svg/leave.svg'

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
  isReady: (id: string) => boolean
  isMirrored: (id: string) => boolean
  showStates?: boolean
  isDead?: (id: string) => boolean
  deadAvatar?: string
  seat?: number | null
  seatIcon?: string | null
  offline?: boolean
  offlineAvatar?: string
  rolePickOwnerId?: string
  rolePickRemainingMs?: number
  gameRole?: string
  hiddenByVisibility?: boolean
  visibilityHiddenAvatar?: string
}>(), {
  side: false,
  fitContain: false,
  showStates: true,
  isDead: () => false,
  deadAvatar: '',
  seat: null,
  seatIcon: null,
  offline: false,
  offlineAvatar: '',
  hiddenByVisibility: false,
  visibilityHiddenAvatar: '',
})

defineEmits<{
  (e: 'toggle-panel', id: string): void
  (e: 'vol-input', id: string, v: number): void
  (e: 'block', key: 'mic'|'cam'|'speakers'|'visibility'|'screen', id: string): void
  (e: 'kick', id: string): void
}>()

const showVideo = computed(() =>
  !props.hiddenByVisibility &&
  !props.offline &&
  !props.isDead(props.id) &&
  props.isOn(props.id, 'cam') &&
  !props.isBlocked(props.id, 'cam'),
)
const openPanel = computed(() => props.openPanelFor === props.id)
const showRoleTimer = computed(() => props.rolePickOwnerId === props.id)
const isRolePickOwner = computed(() => props.rolePickOwnerId === props.id)
const rolePickDurationSec = computed(() => {
  const ms = props.rolePickRemainingMs ?? 0
  if (!ms || ms <= 0) return 0
  return Math.max(ms / 1000, 0.1)
})

</script>

<style scoped lang="scss">
.tile {
  position: relative;
  min-width: 0;
  min-height: 0;
  border-radius: 7px;
  border: 2px solid transparent;
  transition: border-color 0.25s ease-in-out;
  &.speaking {
    border-color: $green;
  }
  video {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 5px;
    background-color: $black;
    &.mirrored {
      transform: scaleX(-1);
    }
  }
  .icon-badge {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    bottom: 5px;
    width: 30px;
    height: 30px;
    border-radius: 5px;
    backdrop-filter: blur(5px);
    background-color: rgba($dark, 0.75);
    box-shadow: 3px 3px 5px rgba($black, 0.25);
    z-index: 3;
    img {
      width: 20px;
      height: 20px;
    }
    &.left {
      left: 5px;
    }
    &.right {
      right: 5px;
    }
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
      user-select: none;
    }
    .avatar {
      border-radius: 50%;
    }
  }
  .user-card {
    position: absolute;
    left: 5px;
    top: 5px;
    padding: 5px 10px;
    inline-size: max-content;
    max-inline-size: min(250px, calc(100% - 30px));
    block-size: 30px;
    will-change: inline-size, block-size;
    border-radius: 5px;
    backdrop-filter: blur(5px);
    background-color: rgba($dark, 0.75);
    box-shadow: 3px 3px 5px rgba($black, 0.25);
    z-index: 5;
    transition: inline-size 0.25s ease-out, block-size 0.25s ease-out;
    &[data-open="1"] {
      inline-size: min(250px, calc(100% - 30px));
      block-size: 138px;
    }
    .card-head {
      display: flex;
      align-items: center;
      flex-wrap: nowrap;
      padding: 0;
      gap: 5px;
      max-inline-size: 100%;
      height: 30px;
      border: none;
      background: none;
      cursor: pointer;
      &:disabled {
        cursor: default;
      }
      .user-slot {
        width: 25px;
        height: 25px;
      }
      .user-avatar {
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
        flex: 0 0 auto;
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
      transform: translate(-60px, -60px);
    }
    .card-body-enter-active,
    .card-body-leave-active {
      transition: transform 0.25s ease-out, opacity 0.25s ease-out;
    }
    .card-body {
      display: flex;
      flex-direction: column;
      margin-top: 5px;
      gap: 10px;
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
          width: 20px;
          height: 20px;
        }
        input[type="range"] {
          min-width: calc(100% - 66px);
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
          min-width: calc((100% - 50px) / 6);
          height: 25px;
          border: none;
          border-radius: 5px;
          background-color: $graphite;
          box-shadow: 3px 3px 5px rgba($black, 0.25);
          cursor: pointer;
          transition: background-color 0.25s ease-in-out;
          &:hover {
            background-color: $lead;
          }
          &.red-button {
            background-color: rgba($red, 0.75);
            &:hover {
              background-color: $red;
            }
          }
          img {
            width: 20px;
            height: 20px;
          }
        }
      }
    }
  }
  .role-timer {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 5px;
    border-radius: 0 0 7px 7px;
    background: transparent;
    overflow: hidden;
    z-index: 10;
    .role-timer-bar {
      width: 100%;
      height: 100%;
      background: linear-gradient(to right, red 0%, yellow 50%, green 100%);
      clip-path: inset(0 0 0 0);
      animation: role-timer-decrease linear forwards;
    }
  }
}
.tile.side {
  aspect-ratio: 16 / 9;
  min-width: 280px;
  min-height: 158px;
}

@keyframes role-timer-decrease {
  from { clip-path: inset(0 0 0 0); }
  to   { clip-path: inset(0 100% 0 0); }
}

@media (max-width: 1280px) {
  .tile {
    .user-card {
      left: 3px;
      top: 3px;
      padding: 0 5px;
      max-inline-size: min(250px, calc(100% - 15px));
      &[data-open="1"] {
        inline-size: min(250px, calc(100% - 15px));
        block-size: 118px;
      }
      .card-body {
        margin-top: 0;
        gap: 5px;
        .volume {
          height: 15px;
        }
        .admin-row {
          gap: 5px;
          button {
            min-width: calc((100% - 25px) / 6);
          }
        }
      }
    }
  }
}
</style>
