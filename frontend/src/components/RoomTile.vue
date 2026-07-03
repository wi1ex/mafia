<template>
  <div class="tile" :class="[{ speaking, mafia: redMark, 'best-move': bestMoveMarked && !redMark }, side && 'side']" tabindex="0">
    <video v-show="showVideo" :ref="(el) => videoRef(el as HTMLVideoElement | null)" playsinline autoplay muted :class="videoClass" />

    <div class="icon-badge-ready" v-if="!inGame && isReady(id)" aria-hidden="true">
      <UiIcon class="ready-icon" :icon="iconReady" />
      <span class="ready-text">Готов к игре</span>
    </div>

    <button v-if="showKnock" class="icon-badge button left knock" @click="$emit('knock', id)" aria-label="Постучать">
      <span>{{ knocksLeft }}</span>
      <UiIcon class="icon-badge-icon" :icon="iconKnock" />
    </button>
    <button v-if="showWink" class="icon-badge button left wink" @click="$emit('wink', id)" aria-label="Подмигнуть">
      <span>{{ winksLeft }}</span>
      <UiIcon class="icon-badge-icon" :icon="iconWink" />
    </button>
    <button v-if="showFoulControl && inGame && seat != null && !isGameHead && !isDead(id)" class="icon-badge button left" @click="$emit('foul', id)" :disabled="!isHead" aria-label="Выдать фол">
      <span>{{ foulsCount }}</span>
      <UiIcon class="icon-badge-icon" :icon="iconFoul" />
    </button>

    <div v-if="gameRole" class="icon-badge right" :class="[gameRoleClass, { finish: finishRoleBadge }]" aria-hidden="true">
      <div v-if="finishRoleBadge" class="icon-badge-role-block">
        <UiIcon class="icon-badge-role-icon" :icon="gameRole" />
      </div>
      <UiIcon v-else class="icon-badge-role-icon" :icon="gameRole" />
    </div>

    <UiButton
      v-if="pickNumber != null && pickNumber > 0"
      class="nominate-btn nominate-btn--pick"
      size="low"
      variant="green"
      disabled
    >
      {{ pickKind === 'check' ? 'Проверил' : 'Выстрелил в' }} {{ pickNumber }}
    </UiButton>
    <UiButton
      v-if="showUnnominate"
      class="nominate-btn"
      size="low"
      variant="red"
      :icon="iconCloseCircle"
      icon-position="left"
      aria-label="Отменить"
      @click="$emit('unnominate', id)"
    >
      Отменить
    </UiButton>
    <UiButton
      v-if="showNominate"
      class="nominate-btn"
      size="low"
      variant="green"
      :icon="iconLike"
      icon-position="left"
      aria-label="Выставить"
      @click="$emit('nominate', id)"
    >
      Выставить
    </UiButton>
    <UiButton
      v-if="showShoot"
      class="nominate-btn"
      size="low"
      variant="green"
      :icon="iconKill"
      icon-position="left"
      aria-label="Выстрелить"
      @click="$emit('shoot', id)"
    >
      Выстрелить
    </UiButton>
    <UiButton
      v-if="showCheck"
      class="nominate-btn"
      size="low"
      variant="green"
      :icon="iconCheck"
      icon-position="left"
      aria-label="Проверить"
      @click="$emit('check', id)"
    >
      Проверить
    </UiButton>
    <UiButton
      v-if="showBestMoveButton"
      class="nominate-btn"
      size="low"
      variant="green"
      :icon="iconPen"
      icon-position="left"
      aria-label="Лучший ход"
      @click="$emit('best-move', id)"
    >
      Лучший ход
    </UiButton>

    <div v-if="showFarewellButtons" class="farewell-buttons">
      <button @click="$emit('farewell','citizen', id)">
        <img :src="iconRoleCitizen" alt="like" />
      </button>
      <button @click="$emit('farewell','mafia', id)">
        <img :src="iconRoleMafia" alt="dislike" />
      </button>
    </div>

    <div v-if="farewellSummary && farewellSummary.length" class="farewell-summary">
      <span class="farewell-summary-badge" v-for="item in farewellSummary" :key="item.targetId" :class="item.verdict">{{ item.seat ?? '?' }}</span>
    </div>

    <UiButton
      v-if="isGameHead && showVoteButton"
      class="vote-btn"
      size="big"
      variant="green"
      :icon="iconLike"
      icon-position="left"
      :disabled="!voteEnabled"
      @click="$emit('vote', id)"
    >
      <span>Проголосовать</span>
      <span v-if="!isMobile && hotkeysVisible" class="hot-btn" aria-hidden="true">_</span>
    </UiButton>

    <div class="head-bar" v-if="isGameHead && phaseLabel">{{ phaseLabel }}</div>
    <div class="head-bar" v-else-if="isGameHead && voteBlocked">Голосования не будет</div>
    <div class="head-bar" v-else-if="isGameHead && showNominationsBar && offlineSeatsInGame && offlineSeatsInGame.length > 0">
      <span>Ожидаем игроков: {{ offlineSeatsInGame.join(', ') }}</span>
    </div>
    <div class="head-bar nominate" v-else-if="isGameHead && showNominationsBadge && Array.isArray(nominees) && nominees.length > 0">
      <span class="nominations-badge" v-for="seatNum in nominees" :key="seatNum" :class="{ current: currentNomineeSeat === seatNum || liftNomineesSet.has(seatNum) }">
        {{ seatNum }}
      </span>
    </div>

    <div v-if="!showVideo" class="ava-wrap">
      <img v-if="isDead(id) && deadAvatar" :src="deadAvatar" alt="dead" />
      <img v-else-if="hiddenByVisibility && visibilityHiddenAvatar" :src="visibilityHiddenAvatar" alt="hidden" />
      <img v-else-if="offline && offlineAvatar" :src="offlineAvatar" alt="offline" />
      <img v-else class="avatar" v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar, lazy: false }" alt="avatar" />
    </div>

    <div v-if="hasVoted" class="icon-voted">
      <div class="icon-voted-block">
        <UiIcon class="icon-voted-img" :icon="iconLike" />
      </div>
    </div>

    <div class="user-card" :style="userCardStyle" @click.stop>
      <button class="card-head" :disabled="!canOpenProfile" aria-haspopup="dialog" @click.stop="$emit('open-profile', id)">
        <span v-if="seatLabel" class="seat-label">{{ seatLabel }}</span>
        <img class="user-avatar" v-minio-img="{ key: avatarKey(id), placeholder: defaultAvatar, lazy: false }" alt="avatar" />
        <div v-if="profileThemeIconSrcs.length" class="profile-theme-icons" aria-hidden="true">
          <img v-for="badgeSrc in profileThemeIconSrcs" :key="badgeSrc" class="profile-theme-icon" :src="badgeSrc" alt="" />
        </div>
        <span class="username">{{ userName(id) }}</span>
        <div class="status" v-if="showHeaderStatus">
          <UiIcon v-if="showMicStatus" class="status-icon" :class="stateIconClass('mic')" :icon="micStatusIcon" label="mic" />
          <UiIcon v-if="showCamStatus" class="status-icon" :class="stateIconClass('cam')" :icon="camStatusIcon" label="cam" />
          <UiIcon v-if="showSpeakersStatus" class="status-icon" :class="stateIconClass('speakers')" :icon="speakersStatusIcon" label="speakers" />
          <UiIcon v-if="showVisibilityStatus" class="status-icon" :class="stateIconClass('visibility')" :icon="visibilityStatusIcon" label="visibility" />
          <UiIcon v-if="showScreenStatus" class="status-icon" :class="stateIconClass('screen')" :icon="screenStatusIcon" label="screen" />
        </div>
      </button>
    </div>
    <div v-if="showTimeline && timelineDurationSec > 0" class="role-timer">
      <div class="role-timer-bar" :style="{ animationDuration: timelineDurationSec + 's', animationPlayState: timelinePaused ? 'paused' : 'running' }" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { GameRoleKind } from '@/composables/roomGame'
import { buildProfileThemeBgStyle } from '@/constants/profileThemes'
import { getProfileThemeBadgeSources } from '@/constants/profileIcons'

import UiIcon from '@/components/UiIcon.vue'
import UiButton from '@/components/UiButton.vue'

import iconReady from '@/assets/svg/iconCheckMark.svg'
import iconLike from '@/assets/svg/iconLike.svg'
import iconPen from '@/assets/svg/iconPen.svg'
import iconCheck from '@/assets/svg/iconCheck.svg'
import iconKill from '@/assets/svg/iconKill.svg'
import iconCloseCircle from '@/assets/svg/iconCloseCircle.svg'
import iconFoul from '@/assets/svg/iconFoul.svg'
import iconWink from '@/assets/svg/iconEmoji.svg'
import iconKnock from '@/assets/svg/iconKnock.svg'
import iconRoleCitizen from '@/assets/svg/iconRoleCitizen.svg'
import iconRoleMafia from '@/assets/svg/iconRoleMafia.svg'

type IconKind = 'mic' | 'cam' | 'speakers' | 'visibility' | 'screen'

const props = withDefaults(defineProps<{
  id: string
  localId: string
  isMobile?: boolean
  hotkeysVisible?: boolean
  speaking: boolean
  side?: boolean
  fitContain?: boolean
  defaultAvatar: string
  themeColor?: string | null
  themeIcon?: string | null
  moderationRole?: string | null
  videoRef: (el: HTMLVideoElement | null) => void
  hasVideoTrack: (id: string) => boolean
  stateIcon: (k: IconKind, id: string) => string
  isOn: (id: string, k: IconKind) => boolean
  isBlocked: (id: string, k: IconKind) => boolean
  userName: (id: string) => string
  avatarKey: (id: string) => string
  canOpenProfile?: boolean
  isReady: (id: string) => boolean
  isMirrored: (id: string) => boolean
  isGameHead?: boolean
  isHead?: boolean
  isDead?: (id: string) => boolean
  deadAvatar?: string
  seat?: number | null
  seatLabel?: string
  offline?: boolean
  offlineAvatar?: string
  rolePickOwnerId?: string
  rolePickRemainingMs?: number
  mafiaTalkHostId?: string
  mafiaTalkRemainingMs?: number
  daySpeechOwnerId?: string
  daySpeechRemainingMs?: number
  daySpeechPaused?: boolean
  redMark?: boolean
  gameRole?: string
  gameRoleKind?: GameRoleKind | ''
  finishRoleBadge?: boolean
  hiddenByVisibility?: boolean
  visibilityHiddenAvatar?: string
  inGame?: boolean
  foulsCount?: number
  winksLeft?: number
  knocksLeft?: number
  showWink?: boolean
  showKnock?: boolean
  showFoulControl?: boolean
  phaseLabel?: string
  showNominate?: boolean
  showUnnominate?: boolean
  showBestMoveButton?: boolean
  bestMoveMarked?: boolean
  farewellSummary?: { targetId: string, seat: number | null, verdict: 'citizen' | 'mafia' }[]
  showFarewellButtons?: boolean
  nominees?: number[]
  liftNominees?: number[]
  showNominationsBar?: boolean
  showNominationsBadge?: boolean
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
  isMobile: false,
  hotkeysVisible: true,
  canOpenProfile: true,
  isGameHead: false,
  isHead: false,
  isDead: () => false,
  deadAvatar: '',
  seat: null,
  seatLabel: '',
  offline: false,
  offlineAvatar: '',
  rolePickOwnerId: '',
  rolePickRemainingMs: 0,
  mafiaTalkHostId: '',
  mafiaTalkRemainingMs: 0,
  daySpeechOwnerId: '',
  daySpeechRemainingMs: 0,
  daySpeechPaused: false,
  redMark: false,
  gameRoleKind: '',
  hiddenByVisibility: false,
  visibilityHiddenAvatar: '',
  finishRoleBadge: false,
  inGame: false,
  foulsCount: 0,
  winksLeft: 0,
  knocksLeft: 0,
  showWink: false,
  showKnock: false,
  showFoulControl: false,
  phaseLabel: '',
  showNominate: false,
  showUnnominate: false,
  showBestMoveButton: false,
  bestMoveMarked: false,
  farewellSummary: () => [],
  showFarewellButtons: false,
  nominees: () => [],
  liftNominees: () => [],
  showNominationsBar: false,
  showNominationsBadge: false,
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
  themeColor: null,
  themeIcon: null,
  moderationRole: null,
})

defineEmits<{
  (e: 'foul', id: string): void
  (e: 'nominate', id: string): void
  (e: 'unnominate', id: string): void
  (e: 'vote', id: string): void
  (e: 'shoot', id: string): void
  (e: 'check', id: string): void
  (e: 'wink', id: string): void
  (e: 'knock', id: string): void
  (e: 'farewell', verdict: 'citizen' | 'mafia', id: string): void
  (e: 'best-move', id: string): void
  (e: 'open-profile', id: string): void
}>()

const micBlocked = computed(() => props.isBlocked(props.id, 'mic'))
const camBlocked = computed(() => props.isBlocked(props.id, 'cam'))
const speakersBlocked = computed(() => props.isBlocked(props.id, 'speakers'))
const visibilityBlocked = computed(() => props.isBlocked(props.id, 'visibility'))
const screenBlocked = computed(() => props.isBlocked(props.id, 'screen'))

const micOn = computed(() => props.isOn(props.id, 'mic'))
const camOn = computed(() => props.isOn(props.id, 'cam'))
const speakersEnabled = computed(() => props.isOn(props.id, 'speakers'))
const visibilityEnabled = computed(() => props.isOn(props.id, 'visibility'))
const screenEnabled = computed(() => props.isOn(props.id, 'screen'))

const micStatusIcon = computed(() => props.stateIcon('mic', props.id))
const camStatusIcon = computed(() => props.stateIcon('cam', props.id))
const speakersStatusIcon = computed(() => props.stateIcon('speakers', props.id))
const visibilityStatusIcon = computed(() => props.stateIcon('visibility', props.id))
const screenStatusIcon = computed(() => props.stateIcon('screen', props.id))

const showMicStatus = computed(() => micBlocked.value || !micOn.value)
const showCamStatus = computed(() => camBlocked.value || !camOn.value)
const showSpeakersStatus = computed(() => speakersBlocked.value || !speakersEnabled.value)
const showVisibilityStatus = computed(() => visibilityBlocked.value || !visibilityEnabled.value)
const showScreenStatus = computed(() => screenBlocked.value || screenEnabled.value)

function stateIconClass(kind: IconKind) {
  if (props.isBlocked(props.id, kind)) return 'blocked'
  return props.isOn(props.id, kind) ? 'on' : 'off'
}

const isAdminUser = computed(() => String(props.moderationRole || '').trim().toLowerCase() === 'admin')
const showHeaderStatus = computed(() => !isAdminUser.value && (!props.inGame || props.isGameHead))
const isDeadTile = computed(() => props.isDead(props.id))
const showVideo = computed(() =>
  !props.hiddenByVisibility &&
  !props.offline &&
  !isDeadTile.value &&
  camOn.value &&
  props.hasVideoTrack(props.id) &&
  !camBlocked.value
)
const videoClass = computed(() =>
  `${props.fitContain ? 'contain' : 'cover'}${props.isMirrored(props.id) ? ' mirrored' : ''}`
)
const liftNomineesSet = computed(() => new Set(props.liftNominees || []))
const hasRolePickTimer = computed(() => props.rolePickOwnerId === props.id && (props.rolePickRemainingMs ?? 0) > 0)
const hasMafiaTalkTimer = computed(() => props.mafiaTalkHostId === props.id && (props.mafiaTalkRemainingMs ?? 0) > 0)
const hasDaySpeechTimer = computed(() => props.daySpeechOwnerId === props.id && (props.daySpeechRemainingMs ?? 0) > 0)
const hasNightTimer = computed(() => props.nightOwnerId === props.id && (props.nightRemainingMs ?? 0) > 0)
const showTimeline = computed(() => hasRolePickTimer.value || hasMafiaTalkTimer.value || hasDaySpeechTimer.value || hasNightTimer.value)
const timelinePaused = computed(() => hasDaySpeechTimer.value && props.daySpeechPaused)
const timelineDurationSec = computed(() => {
  let ms = 0
  if (hasRolePickTimer.value) ms = props.rolePickRemainingMs ?? 0
  else if (hasMafiaTalkTimer.value) ms = props.mafiaTalkRemainingMs ?? 0
  else if (hasDaySpeechTimer.value) ms = props.daySpeechRemainingMs ?? 0
  else if (hasNightTimer.value) ms = props.nightRemainingMs ?? 0
  if (!ms || ms <= 0) return 0
  return Math.max(ms / 1000, 0.1)
})

const userCardStyle = computed(() => buildProfileThemeBgStyle(props.themeColor))
const gameRoleClass = computed(() => props.gameRoleKind ? `role-${props.gameRoleKind}` : '')
const profileThemeIconSrcs = computed(() => getProfileThemeBadgeSources(
  props.themeIcon,
  props.moderationRole,
  {
    hideAdminBadge: props.inGame,
    hideModeratorBadge: props.inGame,
  },
))

</script>

<style scoped lang="scss">
.tile {
  position: relative;
  min-width: 0;
  min-height: 0;
  border-radius: 24px;
  border: 4px solid transparent;
  overflow: hidden;
  transition: border-color 0.25s ease-in-out;
  &.speaking {
    border-color: $green-500;
  }
  &.mafia {
    border-color: $red-500;
  }
  &.speaking.mafia {
    border-color: $red-500;
  }
  &.best-move {
    border-color: $orange-500;
  }
  video {
    width: 100%;
    height: 100%;
    background-color: black;
    &.cover {
      object-fit: cover;
    }
    &.contain {
      object-fit: contain;
    }
    &.mirrored {
      transform: scaleX(-1);
    }
  }
  .icon-badge-ready {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    left: calc(50% - 67px);
    bottom: 8px;
    padding: 0 16px;
    gap: 4px;
    height: 36px;
    border: none;
    border-radius: 12px;
    background-color: $soft-purple-950;
    z-index: 3;
    .ready-icon {
      --ui-icon-width: 20px;
      --ui-icon-height: 20px;
      --ui-icon-color: #{$green-500};
    }
    .ready-text {
      color: $green-500;
      font-family: Hauora-Regular;
      font-size: 14px;
      line-height: 14px;
      letter-spacing: -0.28px;
    }
  }
  .ava-wrap {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    inset: 0;
    background-color: $soft-purple-900;
    z-index: 1;
    img {
      height: 100%;
      user-select: none;
    }
    .avatar {
      aspect-ratio: 1;
      height: 35%;
      border-radius: 50%;
    }
  }
  .user-card {
    position: absolute;
    left: 8px;
    top: 8px;
    border-radius: 12px;
    background-color: var(--user-theme-bg, $soft-purple-950);
    z-index: 20;
    .card-head {
      display: flex;
      align-items: center;
      padding: 8px;
      gap: 4px;
      max-width: 288px;
      border: none;
      background: none;
      cursor: pointer;
      &:disabled {
        cursor: default;
      }
      img {
        width: 20px;
        height: 20px;
      }
      .seat-label {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 20px;
        height: 20px;
        border-radius: 4px;
        background-color: $soft-purple-800;
        color: $neutral-white;
        font-family: Hauora-Regular;
        font-size: 12px;
        line-height: 12px;
        letter-spacing: -0.24px;
      }
      .user-avatar {
        border-radius: 50%;
        object-fit: cover;
      }
      .profile-theme-icons {
        display: inline-flex;
        align-items: center;
        margin-left: -4px;
        .profile-theme-icon {
          object-fit: contain;
        }
      }
      .username {
        color: $neutral-white;
        font-family: Hauora-Regular;
        font-size: 14px;
        line-height: 18px;
        letter-spacing: -0.28px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .status {
        display: flex;
        align-items: center;
        margin-left: 4px;
        gap: 4px;
        .status-icon {
          --ui-icon-width: 16px;
          --ui-icon-height: 16px;
          --ui-icon-color: #{$neutral-100};
          &.on {
            --ui-icon-color: #{$green-500};
          }
          &.off {
            --ui-icon-color: #{$neutral-100};
          }
          &.blocked {
            --ui-icon-color: #{$red-500};
          }
        }
      }
    }
  }
  .icon-badge {
    --icon-badge-role-bg: #{$soft-purple-950};
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    bottom: 8px;
    padding: 0;
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 12px;
    background-color: var(--icon-badge-role-bg);
    z-index: 3;
    .icon-badge-icon {
      --ui-icon-width: 16px;
      --ui-icon-height: 16px;
      --ui-icon-color: #{$neutral-white};
    }
    .icon-badge-role-icon {
      --ui-icon-width: 24px;
      --ui-icon-height: 24px;
      --ui-icon-color: #{$neutral-white};
    }
    .icon-badge-role-block {
      display: flex;
      align-items: center;
      justify-content: center;
      background-color: var(--icon-badge-role-bg);
    }
    span {
      margin: 0 -1px 0 2px;
      min-width: 11px;
      color: $neutral-white;
      font-family: Hauora-Bold;
      font-size: 18px;
      line-height: 20px;
      letter-spacing: -0.36px;
    }
    &.button {
      cursor: pointer;
    }
    &.left {
      left: 8px;
    }
    &.right {
      right: 8px;
    }
    &.wink {
      bottom: 46px;
    }
    &.knock {
      left: 46px;
    }
    &.role-citizen {
      --icon-badge-role-bg: #{$role-citizen};
    }
    &.role-sheriff {
      --icon-badge-role-bg: #{$role-sheriff};
    }
    &.role-mafia {
      --icon-badge-role-bg: #{$role-mafia};
    }
    &.role-don {
      --icon-badge-role-bg: #{$role-don};
    }
    &.finish {
      inset: 0;
      width: 100%;
      height: 100%;
      background-color: rgba($neutral-black, 0.6);
      z-index: 25;
      cursor: default;
      pointer-events: none;
      .icon-badge-role-block {
        width: clamp(72px, 24%, 128px);
        aspect-ratio: 1;
        border-radius: 24px;
      }
      .icon-badge-role-icon {
        --ui-icon-width: 65%;
        --ui-icon-height: 65%;
      }
    }
    &:disabled {
      cursor: default;
      pointer-events: none;
    }
  }
  .head-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    left: 8px;
    right: 8px;
    bottom: 8px;
    gap: 2px;
    height: 36px;
    border-radius: 12px;
    background-color: $soft-purple-950;
    color: $neutral-white;
    font-family: Hauora-Regular;
    font-size: 14px;
    line-height: 14px;
    letter-spacing: -0.28px;
    z-index: 10;
    &.nominate {
      background: none;
    }
    .nominations-badge {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
      border-radius: 12px;
      background-color: $neutral-600;
      color: $neutral-white;
      font-family: Hauora-Bold;
      font-size: 18px;
      line-height: 20px;
      letter-spacing: -0.36px;
      &.current {
        background-color: $green-500;
      }
    }
  }
  .nominate-btn {
    position: absolute;
    left: 50%;
    bottom: 8px;
    transform: translate(-50%);
    z-index: 20;
    &.nominate-btn--pick {
      --ui-button-disabled-bg: #{$green-500};
      --ui-button-disabled-color: #{$neutral-900};
      cursor: default;
    }
    &.nominate-btn--pick.ui-button--disabled {
      cursor: default;
    }
  }
  .farewell-buttons {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    left: 50%;
    bottom: 8px;
    transform: translate(-50%);
    gap: 2px;
    z-index: 15;
    button {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 36px;
      height: 36px;
      border: 1px solid $green-500;
      border-radius: 12px;
      background-color: $soft-purple-800;
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
    bottom: 8px;
    transform: translate(-50%);
    gap: 2px;
    z-index: 15;
    .farewell-summary-badge {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
      border-radius: 12px;
      background-color: $neutral-600;
      color: $neutral-white;
      font-family: Hauora-Bold;
      font-size: 18px;
      line-height: 20px;
      letter-spacing: -0.36px;
      &.citizen {
        background-color: $red-500;
      }
    }
  }
  .vote-btn {
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    touch-action: manipulation;
    z-index: 3;
    :deep(.ui-button__text) {
      overflow: visible;
    }
    .hot-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      position: absolute;
      bottom: 7.5px;
      right: 7.5px;
      width: 14px;
      height: 14px;
      border-radius: 999px;
      background-color: $neutral-white;
      color: $soft-purple-900;
      font-family: Hauora-Bold;
      font-size: 12px;
      line-height: 12px;
      letter-spacing: -0.24px;
    }
  }
  .icon-voted {
    display: flex;
    position: absolute;
    align-items: center;
    justify-content: center;
    inset: 0;
    width: 100%;
    height: 100%;
    background-color: rgba($neutral-black, 0.6);
    z-index: 20;
    pointer-events: none;
    .icon-voted-block {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 96px;
      height: 96px;
      border-radius: 999px;
      background-color: $soft-purple-800;
      .icon-voted-img {
        --ui-icon-width: 64px;
        --ui-icon-height: 64px;
        --ui-icon-color: #{$green-500};
      }
    }
  }
  .role-timer {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 6px;
    background: transparent;
    overflow: hidden;
    z-index: 20;
    .role-timer-bar {
      width: 100%;
      height: 100%;
      background: linear-gradient(to right, rgba(68, 16, 122, 1) 0%, rgba(91, 0, 255, 1) 30%, rgba(255, 19, 97, 1) 60%, rgba(255, 248, 0, 1) 100%);
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

</style>
