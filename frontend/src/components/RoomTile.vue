<template>
  <div class="tile" :class="[{ speaking, mafia: redMark, 'best-move': bestMoveMarked }, side && 'side']" tabindex="0">
    <video v-show="showVideo" :ref="videoRef" playsinline autoplay :muted="id === localId" :class="{ mirrored: isMirrored(id) }"
           :style="{ objectFit: fitContain ? 'contain' : 'cover' }" />

    <div class="icon-badge left" v-if="isReady(id)" aria-hidden="true">
      <img :src="iconReadyGreen" alt="ready" />
    </div>

    <img v-if="hasVoted" class="icon-voted" :src="iconLikeGreen" alt="voted" />
    <button v-if="inGame && seat != null && !isGameHead && !isDead(id)" class="icon-badge button left"
            @click="$emit('foul', id)" :disabled="!isHead" aria-label="Выдать фол">
      <img :src="iconFoul" alt="foul" />
      <span>{{ foulsCount }}</span>
    </button>
    <div v-if="farewellSummary && farewellSummary.length" class="farewell-summary">
      <span v-for="item in farewellSummary" :key="item.targetId" :class="item.verdict">{{ item.seat ?? '?' }}</span>
    </div>

    <div v-if="pickNumber != null && pickNumber > 0" class="nominate-btn pick-number">
      <span>{{ pickKind === 'check' ? 'Проверил' : 'Выстрелил в' }} {{ pickNumber }}</span>
    </div>
    <button v-if="showNominate" class="nominate-btn" @click="$emit('nominate', id)" aria-label="Выставить">
      <img :src="iconLikeBlack" alt="nominate" />
      <span>Выставить</span>
    </button>
    <button v-if="showShoot" class="nominate-btn" @click="$emit('shoot', id)" aria-label="Выстрелить">
      <img :src="iconKill" alt="shoot" />
      <span>Выстрелить</span>
    </button>
    <button v-if="showCheck" class="nominate-btn" @click="$emit('check', id)" aria-label="Проверить">
      <img :src="iconCheck" alt="check" />
      <span>Проверить</span>
    </button>
    <button v-if="showBestMoveButton" class="nominate-btn" @click="$emit('best-move', id)" aria-label="Лучший ход">
      <span>Лучший ход</span>
    </button>
    <div class="icon-badge right" v-if="gameRole" aria-hidden="true">
      <img :src="gameRole" alt="role" />
    </div>
    <div v-if="showFarewellButtons" class="farewell-buttons">
      <button @click="$emit('farewell','citizen', id)">
        <img :src="iconRoleCitizen" alt="like" />
      </button>
      <button @click="$emit('farewell','mafia', id)">
        <img :src="iconRoleMafia" alt="dislike" />
      </button>
    </div>

    <button v-if="isGameHead && showVoteButton" class="vote-btn" :disabled="!voteEnabled" @click="$emit('vote')">
      <img :src="iconLikeBlack" alt="vote" />
      <span>Проголосовать</span>
    </button>
    <div class="head-bar" v-if="isGameHead && phaseLabel">{{ phaseLabel }}</div>
    <div class="head-bar" v-else-if="isGameHead && voteBlocked">Голосования не будет</div>
    <div class="head-bar" v-else-if="isGameHead && showNominationsBar && offlineSeatsInGame && offlineSeatsInGame.length > 0">
      <span>Ожидаем игроков: {{ offlineSeatsInGame.join(', ') }}</span>
    </div>
    <div class="head-bar nominate" v-else-if="isGameHead && showNominationsBar && Array.isArray(nominees) && nominees.length > 0">
      <span class="nominations-badge" v-for="seatNum in nominees" :key="seatNum" :class="{ current: currentNomineeSeat === seatNum || liftNomineesSet.has(seatNum) }">
        {{ seatNum }}
      </span>
    </div>

    <div v-show="!showVideo" class="ava-wrap">
      <img v-if="isDead(id) && deadAvatar" :src="deadAvatar" alt="dead" />
      <img v-else-if="hiddenByVisibility && visibilityHiddenAvatar" :src="visibilityHiddenAvatar" alt="hidden" />
      <img v-else-if="offline && offlineAvatar" :src="offlineAvatar" alt="offline" />
      <img v-else class="avatar" v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar, lazy: false }" alt="avatar" />
    </div>

    <div class="user-card" :data-open="openPanel ? 1 : 0" :data-game="inGame ? 1 : 0" @click.stop>
      <button class="card-head" :disabled="id === localId" :aria-disabled="id === localId" @click.stop="$emit('toggle-panel', id)" :aria-expanded="openPanel">
        <img v-if="seat != null && seatIcon" class="user-slot" :src="seatIcon" alt="seat" />
        <img class="user-avatar" v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar, lazy: false }" alt="avatar" />
        <span>{{ userName(id) }}</span>
        <div class="status" v-if="!inGame || isGameHead">
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
            <input type="range" min="0" max="200" step="5" :disabled="!speakersOn || isBlocked(id,'speakers')"
                   :value="vol ?? 100" @input="$emit('vol-input', id, Number(($event.target as HTMLInputElement).value))" />
            <span>{{ vol ?? 100 }}%</span>
          </div>

          <div v-if="!inGame && canModerate(id)" class="admin-row" aria-label="Блокировки">
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
    <div v-if="showTimeline && timelineDurationSec > 0" class="role-timer">
      <div class="role-timer-bar" :style="{ animationDuration: timelineDurationSec + 's' }" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import iconReadyGreen from '@/assets/svg/readyGreen.svg'
import iconLeaveRoom from '@/assets/svg/leave.svg'
import iconFoul from '@/assets/svg/foul.svg'
import iconRoleCitizen from '@/assets/images/roleCitizen.png'
import iconRoleMafia from '@/assets/images/roleMafia.png'
import iconLikeGreen from '@/assets/svg/likeGreen.svg'
import iconLikeBlack from '@/assets/svg/likeBlack.svg'
import iconCheck from '@/assets/svg/check.svg'
import iconKill from '@/assets/svg/kill.svg'

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
  isGameHead?: boolean
  isHead?: boolean
  isDead?: (id: string) => boolean
  deadAvatar?: string
  seat?: number | null
  seatIcon?: string | null
  offline?: boolean
  offlineAvatar?: string
  rolePickOwnerId?: string
  rolePickRemainingMs?: number
  mafiaTalkHostId?: string
  mafiaTalkRemainingMs?: number
  daySpeechOwnerId?: string
  daySpeechRemainingMs?: number
  redMark?: boolean
  gameRole?: string
  hiddenByVisibility?: boolean
  visibilityHiddenAvatar?: string
  inGame?: boolean
  foulsCount?: number
  phaseLabel?: string
  showNominate?: boolean
  showBestMoveButton?: boolean
  bestMoveMarked?: boolean
  farewellSummary?: { targetId: string, seat: number | null, verdict: 'citizen' | 'mafia' }[]
  showFarewellButtons?: boolean
  nominees?: number[]
  liftNominees?: number[]
  showNominationsBar?: boolean
  voteBlocked?: boolean
  currentNomineeSeat?: number | null
  showVoteButton?: boolean
  voteEnabled?: boolean
  hasVoted?: boolean
  offlineSeatsInGame?: number[]
  showShoot?: boolean
  showCheck?: boolean
  pickNumber?: number | null
  pickKind?: 'shoot' | 'check' | ''
  nightOwnerId?: string
  nightRemainingMs?: number
}>(), {
  side: false,
  fitContain: false,
  isGameHead: false,
  isHead: false,
  isDead: () => false,
  deadAvatar: '',
  seat: null,
  seatIcon: null,
  offline: false,
  offlineAvatar: '',
  rolePickOwnerId: '',
  rolePickRemainingMs: 0,
  mafiaTalkHostId: '',
  mafiaTalkRemainingMs: 0,
  daySpeechOwnerId: '',
  daySpeechRemainingMs: 0,
  redMark: false,
  hiddenByVisibility: false,
  visibilityHiddenAvatar: '',
  inGame: false,
  foulsCount: 0,
  phaseLabel: '',
  showNominate: false,
  showBestMoveButton: false,
  bestMoveMarked: false,
  farewellSummary: () => [],
  showFarewellButtons: false,
  nominees: () => [],
  liftNominees: () => [],
  showNominationsBar: false,
  voteBlocked: false,
  currentNomineeSeat: null,
  showVoteButton: false,
  voteEnabled: false,
  hasVoted: false,
  offlineSeatsInGame: () => [],
  showShoot: false,
  showCheck: false,
  pickNumber: null,
  pickKind: '',
  nightOwnerId: '',
  nightRemainingMs: 0,
})

defineEmits<{
  (e: 'toggle-panel', id: string): void
  (e: 'vol-input', id: string, v: number): void
  (e: 'block', key: 'mic'|'cam'|'speakers'|'visibility'|'screen', id: string): void
  (e: 'kick', id: string): void
  (e: 'foul', id: string): void
  (e: 'nominate', id: string): void
  (e: 'vote', id: string): void
  (e: 'shoot', id: string): void
  (e: 'check', id: string): void
  (e: 'farewell', verdict: 'citizen' | 'mafia', id: string): void
  (e: 'best-move', id: string): void
}>()

const showVideo = computed(() => !props.hiddenByVisibility && !props.offline && !props.isDead(props.id) && props.isOn(props.id, 'cam') && !props.isBlocked(props.id, 'cam'))
const openPanel = computed(() => props.openPanelFor === props.id)
const liftNomineesSet = computed(() => new Set(props.liftNominees || []))
const hasRolePickTimer = computed(() => props.rolePickOwnerId === props.id && (props.rolePickRemainingMs ?? 0) > 0)
const hasMafiaTalkTimer = computed(() => props.mafiaTalkHostId === props.id && (props.mafiaTalkRemainingMs ?? 0) > 0)
const hasDaySpeechTimer = computed(() => props.daySpeechOwnerId === props.id && (props.daySpeechRemainingMs ?? 0) > 0)
const hasNightTimer = computed(() => props.nightOwnerId === props.id && (props.nightRemainingMs ?? 0) > 0)
const showTimeline = computed(() => hasRolePickTimer.value || hasMafiaTalkTimer.value || hasDaySpeechTimer.value || hasNightTimer.value)
const timelineDurationSec = computed(() => {
  let ms = 0
  if (hasRolePickTimer.value) ms = props.rolePickRemainingMs ?? 0
  else if (hasMafiaTalkTimer.value) ms = props.mafiaTalkRemainingMs ?? 0
  else if (hasDaySpeechTimer.value) ms = props.daySpeechRemainingMs ?? 0
  else if (hasNightTimer.value) ms = props.nightRemainingMs ?? 0
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
  &.mafia {
    border-color: $red;
  }
  &.speaking.mafia {
    border-color: $red;
  }
  &.best-move {
    border-color: $orange;
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
    padding: 0;
    width: 30px;
    height: 30px;
    border: none;
    border-radius: 5px;
    background-color: rgba($dark, 0.75);
    backdrop-filter: blur(5px);
    box-shadow: 3px 3px 5px rgba($black, 0.25);
    z-index: 3;
    img {
      width: 24px;
      height: 24px;
    }
    span {
      position: absolute;
      top: 5px;
      right: 12px;
      color: $fg;
      font-size: 20px;
      font-family: Manrope-Medium;
      line-height: 1;
      font-weight: bold;
      font-variant-numeric: tabular-nums;
      transition: background-color 0.25s ease-in-out;
    }
    &.button {
      cursor: pointer;
    }
    &:disabled,
    &.button:disabled {
      cursor: default;
      pointer-events: none;
    }
    &.left {
      left: 5px;
    }
    &.right {
      right: 5px;
    }
  }
  .icon-voted {
    position: absolute;
    top: 50%;
    left: 50%;
    height: 90%;
    transform: translate(-50%, -50%);
    pointer-events: none;
  }
  .head-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    padding: 0 0 5px 0;
    gap: 10px;
    height: 30px;
    font-size: 16px;
    color: $fg;
    border-radius: 0 0 5px 5px;
    background-color: rgba($dark, 0.75);
    z-index: 10;
    &.nominate {
      background: none;
    }
    .nominations-badge {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 30px;
      height: 30px;
      border-radius: 5px;
      background-color: $graphite;
      font-size: 18px;
      color: $fg;
      &.current {
        background-color: $green;
        color: $bg;
      }
    }
  }
  .nominate-btn {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    left: 50%;
    bottom: 5px;
    transform: translate(-50%);
    padding: 0 10px;
    gap: 5px;
    height: 30px;
    border: none;
    border-radius: 5px;
    background-color: rgba($green, 0.75);
    backdrop-filter: blur(5px);
    box-shadow: 3px 3px 5px rgba($black, 0.25);
    cursor: pointer;
    z-index: 20;
    &.pick-number {
      cursor: default;
    }
    img {
      width: 24px;
      height: 24px;
    }
    span {
      color: $bg;
      font-size: 16px;
      font-family: Manrope-Medium;
      line-height: 1;
    }
  }
  .farewell-buttons {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    left: 50%;
    bottom: 5px;
    transform: translate(-50%);
    gap: 10px;
    z-index: 15;
    button {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 30px;
      height: 30px;
      border: none;
      border-radius: 5px;
      background-color: rgba($dark, 0.75);
      backdrop-filter: blur(5px);
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      cursor: pointer;
      img {
        width: 24px;
        height: 24px;
      }
    }
  }
  .farewell-summary {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    left: 50%;
    bottom: 6px;
    transform: translate(-50%);
    gap: 5px;
    z-index: 15;
    span {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      border-radius: 5px;
      border: none;
      background-color: $graphite;
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      &.citizen {
        background-color: $red;
      }
    }
  }
  .vote-btn {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    padding: 0 15px;
    gap: 5px;
    height: 50px;
    border: none;
    border-radius: 5px;
    background-color: $green;
    backdrop-filter: blur(5px);
    box-shadow: 3px 3px 5px rgba($black, 0.25);
    cursor: pointer;
    z-index: 3;
    &:disabled {
      background-color: rgba($dark, 0.75);
      cursor: default;
      span {
        color: $fg;
      }
    }
    img {
      width: 32px;
      height: 32px;
    }
    span {
      color: $bg;
      font-size: 20px;
      font-family: Manrope-Medium;
      line-height: 1;
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
      height: 75%;
      user-select: none;
    }
    .avatar {
      height: 40%;
      border-radius: 50%;
    }
  }
  .user-card {
    position: absolute;
    left: 5px;
    top: 5px;
    padding: 5px 10px;
    inline-size: max-content;
    max-inline-size: min(210px, calc(100% - 30px));
    block-size: 30px;
    will-change: inline-size, block-size;
    border-radius: 5px;
    backdrop-filter: blur(5px);
    background-color: rgba($dark, 0.75);
    box-shadow: 3px 3px 5px rgba($black, 0.25);
    z-index: 20;
    transition: inline-size 0.25s ease-out, block-size 0.25s ease-out;
    &[data-open="1"] {
      inline-size: min(210px, calc(100% - 30px));
      block-size: 138px;
    }
    &[data-open="1"][data-game="1"] {
      block-size: 103px;
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
        width: 28px;
        height: 28px;
      }
      .user-avatar {
        width: 24px;
        height: 24px;
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
      .admin-row {
        display: flex;
        gap: 5px;
        button {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          min-width: calc((100% - 25px) / 6);
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
            width: 18px;
            height: 18px;
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
    z-index: 20;
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
  min-width: 320px;
  min-height: 180px;
}

@keyframes role-timer-decrease {
  from { clip-path: inset(0 0 0 0); }
  to   { clip-path: inset(0 100% 0 0); }
}

@media (max-width: 1280px) {
  .tile {
    .icon-badge {
      bottom: 3px;
      width: 20px;
      height: 20px;
      img {
        width: 16px;
        height: 16px;
      }
      span {
        top: 4px;
        right: 9px;
        font-size: 12px;
      }
      &.left {
        left: 3px;
      }
      &.right {
        right: 3px;
      }
    }
    .head-bar {
      padding: 0 0 3px 0;
      gap: 5px;
      height: 15px;
      font-size: 10px;
      .nominations-badge {
        width: 15px;
        height: 15px;
        border-radius: 3px;
        font-size: 10px;
      }
    }
    .nominate-btn {
      bottom: 3px;
      padding: 0 5px;
      gap: 3px;
      height: 20px;
      img {
        width: 16px;
        height: 16px;
      }
      span {
        font-size: 12px;
      }
    }
    .farewell-buttons {
      bottom: 3px;
      button {
        width: 20px;
        height: 20px;
        img {
          width: 16px;
          height: 16px;
        }
      }
    }
    .farewell-summary {
      bottom: 4px;
      gap: 3px;
      span {
        width: 18px;
        height: 18px;
        font-size: 10px;
      }
    }
    .vote-btn {
      padding: 0 10px;
      gap: 3px;
      height: 30px;
      img {
        width: 20px;
        height: 20px;
      }
      span {
        font-size: 14px;
      }
    }
    .user-card {
      left: 3px;
      top: 3px;
      padding: 3px 5px;
      max-inline-size: min(160px, calc(100% - 15px));
      block-size: 16px;
      &[data-open="1"] {
        inline-size: min(160px, calc(100% - 15px));
        block-size: 90px;
      }
      &[data-open="1"][data-game="1"] {
        block-size: 65px;
      }
      .card-head {
        gap: 3px;
        height: 16px;
        .user-slot {
          width: 16px;
          height: 16px;
        }
        .user-avatar {
          width: 14px;
          height: 14px;
        }
        span {
          height: 12px;
          font-size: 10px;
        }
        .status {
          gap: 3px;
          img {
            width: 14px;
            height: 14px;
          }
        }
      }
      .card-body {
        margin-top: 3px;
        gap: 5px;
        .volume {
          padding: 3px 5px;
          gap: 3px;
          height: 14px;
          img {
            width: 14px;
            height: 14px;
          }
          input[type="range"] {
            height: 6px;
          }
          span {
            min-width: 26px;
            font-size: 10px;
          }
          input[type="range"]::-webkit-slider-runnable-track {
            height: 4px;
            border-radius: 2px;
          }
          input[type="range"]::-webkit-slider-thumb {
            width: 12px;
            height: 12px;
            border: 2px solid $dark;
            margin-top: calc(-12px / 2 + 2px);
          }
          input[type="range"]::-moz-range-track {
            height: 4px;
            border-radius: 2px;
          }
          input[type="range"]::-moz-range-thumb {
            width: 8px;
            height: 8px;
            border: 2px solid $dark;
          }
        }
        .admin-row {
          button {
            height: 20px;
            img {
              width: 14px;
              height: 14px;
            }
          }
        }
      }
    }
    .role-timer {
      height: 3px;
    }
  }
  .tile.side {
    min-width: 240px;
    min-height: 135px;
  }
}
</style>
