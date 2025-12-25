<template>
  <section class="room">
    <div v-if="isReconnecting" class="reconnect-overlay" aria-live="polite">Восстанавливаем соединение…</div>

    <div v-else-if="!uiReady" class="reconnect-overlay" aria-live="polite">Загрузка комнаты…</div>

    <template v-else>
      <Transition name="fade">
        <div v-if="gameOverlayVisible" class="reconnect-overlay load-game" aria-live="polite">{{ gameOverlayText }}</div>
      </Transition>
      <div v-if="!isTheater" class="grid" :style="gridStyle">
        <RoomTile
          v-for="id in sortedPeerIds"
          :key="id"
          :style="tileGridStyle(id)"
          :id="id"
          :local-id="localId"
          :speaking="(game.daySpeech.currentId === id && game.daySpeech.remainingMs > 0) || (gamePhase === 'idle' && rtc.isSpeaking(id))"
          :video-ref="stableVideoRef(id)"
          :fit-contain="fitContainInGrid"
          :default-avatar="defaultAvatar"
          :volume-icon="volumeIconForUser(id)"
          :state-icon="stateIcon"
          :is-ready="isReady"
          :is-on="isOn"
          :is-blocked="isBlocked"
          :user-name="userName"
          :avatar-key="avatarKey"
          :can-moderate="canModerate"
          :speakers-on="speakersOn"
          :open-panel-for="openPanelFor"
          :vol="volUi[id] ?? rtc.getUserVolume(id)"
          :is-mirrored="isMirrored"
          :is-game-head="game.isGameHead(id)"
          :is-head="isHead"
          :is-dead="game.isDead"
          :dead-avatar="deadAvatar(id)"
          :seat="game.seatIndex(id)"
          :seat-icon="game.seatIconForUser(id)"
          :offline="offlineInGame.has(id)"
          :offline-avatar="iconLowSignal"
          :role-pick-owner-id="rolePick.activeUserId"
          :role-pick-remaining-ms="rolePick.remainingMs"
          :mafia-talk-host-id="headUserId"
          :mafia-talk-remaining-ms="mafiaTalkRemainingMs"
          :red-mark="game.shouldHighlightMafiaTile(id) || game.foulActive.has(id)"
          :game-role="game.effectiveRoleIconForTile(id)"
          :hidden-by-visibility="hiddenByVisibility(id)"
          :visibility-hidden-avatar="visOffAvatar(id)"
          :in-game="gamePhase !== 'idle'"
          :day-speech-owner-id="game.daySpeech.currentId"
          :day-speech-remaining-ms="game.daySpeech.remainingMs"
          :fouls-count="gameFoulsByUser.get(id) ?? 0"
          :phase-label="phaseLabel"
          :night-owner-id="headUserId"
          :night-remaining-ms="night.remainingMs"
          :show-shoot="game.canShootTarget(id)"
          :show-check="game.canCheckTarget(id)"
          :pick-number="isHead ? (headNightPicks.get(id) ?? null) : null"   
          :pick-kind="headPickKind"
          :show-nominate="game.canNominateTarget(id)"
          :best-move-marked="game.isBestMoveMarked(id)"
          :show-best-move-button="game.canMakeBestMoveChoice(id)"
          :farewell-summary="game.farewellSummaryForUser(id)"
          :show-farewell-buttons="game.canMakeFarewellChoice(id)"
          :nominees="nomineeSeatNumbers"
          :lift-nominees="id === headUserId && liftHighlightNominees ? nomineeSeatNumbers : []"
          :current-nominee-seat="id === headUserId ? currentNomineeSeat : null"
          :show-nominations-bar="id === headUserId && (gamePhase === 'day' || gamePhase === 'vote')"
          :vote-blocked="id === headUserId ? voteBlocked : false"
          :offline-seats-in-game="id === headUserId && gamePhase === 'vote' ? offlineAliveSeatNumbers : []"
          :show-vote-button="amIAlive && game.canPressVoteButton()"
          :vote-enabled="game.canPressVoteButton()"
          :has-voted="(isLiftVoting ? votedUsers : votedThisRound).has(id)"
          @toggle-panel="toggleTilePanel"
          @vol-input="onVol"
          @block="(key, uid) => toggleBlock(uid, key)"
          @kick="kickUser"
          @foul="onGiveFoul"
          @nominate="onNominate"
          @vote="onVote"
          @shoot="shootTargetUi"
          @check="checkTargetUi"
          @farewell="onFarewell"
          @best-move="onBestMove"
        />
      </div>

      <div v-else class="theater">
        <div class="stage">
          <video :ref="stableScreenRef(screenOwnerId)" playsinline autoplay />
          <div v-if="screenOwnerId !== localId && streamAudioKey" class="volume" @click.stop>
            <img :src="volumeIconForStream(streamAudioKey)" alt="vol" />
            <input type="range" min="0" max="200" :disabled="!speakersOn || isBlocked(screenOwnerId,'speakers')"
                   :value="streamVol" @input="onVol(streamAudioKey, Number(($event.target as HTMLInputElement).value))" />
            <span>{{ streamVol }}%</span>
          </div>
        </div>

        <div class="sidebar">
          <RoomTile
            v-for="id in sortedPeerIds"
            :key="id"
            :id="id"
            :local-id="localId"
            :side="true"
            :speaking="(game.daySpeech.currentId === id && game.daySpeech.remainingMs > 0) || (gamePhase === 'idle' && rtc.isSpeaking(id))"
            :video-ref="stableVideoRef(id)"
            :default-avatar="defaultAvatar"
            :volume-icon="volumeIconForUser(id)"
            :state-icon="stateIcon"
            :is-ready="isReady"
            :is-on="isOn"
            :is-blocked="isBlocked"
            :user-name="userName"
            :avatar-key="avatarKey"
            :can-moderate="canModerate"
            :speakers-on="speakersOn"
            :open-panel-for="openPanelFor"
            :vol="volUi[id] ?? rtc.getUserVolume(id)"
            :is-mirrored="isMirrored"
            :is-game-head="game.isGameHead(id)"
            :is-head="isHead"
            :is-dead="game.isDead"
            :dead-avatar="deadAvatar(id)"
            :seat="game.seatIndex(id)"
            :seat-icon="game.seatIconForUser(id)"
            :offline="offlineInGame.has(id)"
            :offline-avatar="iconLowSignal"
            :role-pick-owner-id="rolePick.activeUserId"
            :role-pick-remaining-ms="rolePick.remainingMs"
            :mafia-talk-host-id="headUserId"
            :mafia-talk-remaining-ms="mafiaTalkRemainingMs"
            :red-mark="game.shouldHighlightMafiaTile(id) || game.foulActive.has(id)"
            :game-role="game.effectiveRoleIconForTile(id)"
            :hidden-by-visibility="hiddenByVisibility(id)"
            :visibility-hidden-avatar="visOffAvatar(id)"
            :in-game="gamePhase !== 'idle'"
            :day-speech-owner-id="game.daySpeech.currentId"
            :day-speech-remaining-ms="game.daySpeech.remainingMs"
            :fouls-count="gameFoulsByUser.get(id) ?? 0"
            :phase-label="phaseLabel"
            :night-owner-id="headUserId"
            :night-remaining-ms="night.remainingMs"
            :show-shoot="game.canShootTarget(id)"
            :show-check="game.canCheckTarget(id)"
            :pick-number="isHead ? (headNightPicks.get(id) ?? null) : null"
            :pick-kind="headPickKind"
            :show-nominate="game.canNominateTarget(id)"
            :best-move-marked="game.isBestMoveMarked(id)"
            :show-best-move-button="game.canMakeBestMoveChoice(id)"
            :farewell-summary="game.farewellSummaryForUser(id)"
            :show-farewell-buttons="game.canMakeFarewellChoice(id)"
            :nominees="nomineeSeatNumbers"
            :lift-nominees="id === headUserId && liftHighlightNominees ? nomineeSeatNumbers : []"
            :current-nominee-seat="id === headUserId ? currentNomineeSeat : null"
            :show-nominations-bar="id === headUserId && (gamePhase === 'day' || gamePhase === 'vote')"
            :vote-blocked="id === headUserId ? voteBlocked : false"
            :offline-seats-in-game="id === headUserId && gamePhase === 'vote' ? offlineAliveSeatNumbers : []"
            :show-vote-button="amIAlive && game.canPressVoteButton()"
            :vote-enabled="game.canPressVoteButton()"
            :has-voted="(isLiftVoting ? votedUsers : votedThisRound).has(id)"
            @toggle-panel="toggleTilePanel"
            @vol-input="onVol"
            @block="(key, uid) => toggleBlock(uid, key)"
            @kick="kickUser"
            @foul="onGiveFoul"
            @nominate="onNominate"
            @vote="onVote"
            @shoot="shootTargetUi"
            @check="checkTargetUi"
            @farewell="onFarewell"
            @best-move="onBestMove"
          />
        </div>
      </div>

      <div class="panel">
        <div class="controls-side left">
          <button @click="onLeave" aria-label="Покинуть комнату">
            <img :src="iconLeaveRoom" alt="leave" />
          </button>
          <button v-if="gamePhase !== 'idle' && isHead" @click="endGameUi" :disabled="endingGame" aria-label="Завершить игру">
            <img :src="iconGameStop" alt="end-game" />
          </button>
          <button v-if="gamePhase !== 'idle' && myGameRole === 'player' && amIAlive" @click="leaveGameUi" aria-label="Выйти из игры">
            <img :src="iconDeadPlayer" alt="leave-game" />
          </button>
        </div>

        <div v-if="showPermProbe" class="controls">
          <button class="btn-text" @click="onProbeClick">Разрешить доступ к камере и микрофону</button>
        </div>
        <div v-else-if="!gameFinished" class="controls">
          <button v-if="canHeadGoToMafiaTalkControl" class="btn-text" @click="goToMafiaTalkUi" aria-label="Перейти к договорке">Начать договорку</button>
          <button v-if="canHeadFinishMafiaTalkControl" class="btn-text" @click="finishMafiaTalkUi" aria-label="Завершить договорку">Завершить договорку</button>
          <button v-if="canStartDay" class="btn-text" @click="startDayUi" aria-label="Начать день">День</button>
          <button v-if="canFinishSpeechHead" class="btn-text" @click="finishSpeechUi" aria-label="Завершить речь">Завершить речь</button>
          <button v-else-if="canPassSpeechHead" class="btn-text" @click="passSpeechUi" aria-label="Передать речь">Передать речь</button>
          <button v-if="canStartVote" class="btn-text" @click="startVoteUi">Начать голосование</button>
          <button v-if="canHeadVoteControl" class="btn-text" :disabled="hasOfflineAlivePlayers" @click="onHeadVoteControl">
            {{ !voteStartedForCurrent ? 'Голосование за ' + (currentNomineeSeat ?? '') : 'Продолжить' }}
          </button>
          <button v-if="canHeadFinishVoteControl" class="btn-text" @click="finishVoteUi">Завершить голосование</button>
          <button v-if="canPrepareVoteLift" class="btn-text" :disabled="hasOfflineAlivePlayers" @click="prepareVoteLiftUi">Продолжить</button>
          <button v-if="canStartVoteLift" class="btn-text" :disabled="hasOfflineAlivePlayers" @click="startVoteLiftUi">Голосование за подъём</button>
          <button v-if="canStartLeaderSpeech" class="btn-text" @click="startLeaderSpeechUi">Передать речь</button>
          <button v-if="canRestartVoteForLeaders" class="btn-text" @click="restartVoteForLeadersUi">Начать голосование</button>
          <button v-if="canShowNight" class="btn-text" :disabled="hasOfflineAlivePlayers" @click="goToNightUi">Ночь</button>
          <button v-if="canHeadNightShootControl" class="btn-text" :disabled="hasOfflineAlivePlayers" @click="startNightShootUi">Стрельба</button>
          <button v-if="canHeadNightCheckControl" class="btn-text" :disabled="hasOfflineAlivePlayers" @click="startNightChecksUi">Проверки</button>        
          <button v-if="canHeadBestMoveControl" class="btn-text" @click="startBestMoveUi">Лучший ход {{ bestMoveSeat ?? '?' }}</button>
          <button v-if="canHeadDayFromNightControl" class="btn-text" @click="startDayFromNightUi">День</button>

          <button v-if="canFinishSpeechSelf" @click="finishSpeechUi">
            <img :src="iconSkip" alt="finish speech" />
          </button>
          <button v-else-if="canTakeFoulSelf" @click="takeFoulUi" :disabled="foulPending">
            <img :src="iconTakeFoul" alt="take foul" />
          </button>

          <button v-if="gamePhase === 'idle' && canShowStartGame" @click="startGameUi" :disabled="startingGame" aria-label="Запустить игру">
            <img :src="iconGameStart" alt="start" />
          </button>
          <button v-if="gamePhase === 'idle' && !canShowStartGame" @click="toggleReady" :aria-pressed="readyOn" aria-label="Готовность">
            <img :src="readyOn ? iconReady : iconClose" alt="ready" />
          </button>
          <button v-if="gamePhase === 'idle' || isHead" @click="toggleMic" :disabled="pending.mic || blockedSelf.mic" :aria-pressed="micOn">
            <img :src="stateIcon('mic', localId)" alt="mic" />
          </button>
          <button v-if="gamePhase === 'idle' || isHead" @click="toggleCam" :disabled="pending.cam || blockedSelf.cam" :aria-pressed="camOn">
            <img :src="stateIcon('cam', localId)" alt="cam" />
          </button>
          <button v-if="gamePhase === 'idle'" @click="toggleSpeakers" :disabled="pending.speakers || blockedSelf.speakers" :aria-pressed="speakersOn">
            <img :src="stateIcon('speakers', localId)" alt="speakers" />
          </button>
          <button v-if="gamePhase === 'idle'" @click="toggleVisibility" :disabled="pending.visibility || blockedSelf.visibility" :aria-pressed="visibilityOn">
            <img :src="stateIcon('visibility', localId)" alt="visibility" />
          </button>
          <button v-if="gamePhase === 'idle'" @click="toggleScreen" :disabled="pendingScreen || (!!screenOwnerId && screenOwnerId !== localId) || blockedSelf.screen" :aria-pressed="isMyScreen">
            <img :src="stateIcon('screen', localId)" alt="screen" />
          </button>
        </div>

        <div class="controls-side right">
          <button v-if="myRole === 'host' && isPrivate && gamePhase === 'idle'" @click.stop="toggleApps" :aria-expanded="openApps" aria-label="Заявки">
            <img :src="iconRequestsRoom" alt="requests" />
            <span class="count-total" :class="{ unread: appsCounts.unread > 0 }">{{ appsCounts.total < 100 ? appsCounts.total : '∞' }}</span>
          </button>
          <button v-if="gamePhase !== 'idle'" @click.stop="toggleMusicSettings" :aria-expanded="musicSettingsOpen" aria-label="Панель управления">
            <img :src="iconControls" alt="controls" />
          </button>
          <button @click.stop="toggleSettings" :aria-expanded="settingsOpen" aria-label="Настройки устройств">
            <img :src="iconSettings" alt="settings" />
          </button>
        </div>

        <RoomRequests
          v-if="myRole === 'host' && isPrivate && gamePhase === 'idle'"
          v-model:open="openApps"
          :room-id="rid"
          @counts="(p) => { appsCounts.total = p.total; appsCounts.unread = p.unread }"
        />

        <RoomControls
          :open="musicSettingsOpen"
          v-model:volume="bgmVolume"
          :can-toggle-known-roles="canToggleKnownRoles"
          :known-roles-visible="knownRolesVisible"
          @toggle-known-roles="game.toggleKnownRolesVisibility"
          @close="musicSettingsOpen=false"
        />

        <RoomSetting
          :open="settingsOpen"
          :mics="mics"
          :cams="cams"
          v-model:micId="selectedMicId"
          v-model:camId="selectedCamId"
          v-model:vq="videoQuality"
          v-model:mirrorOn="mirrorOn"
          :vq-disabled="pendingQuality"
          @device-change="(kind) => rtc.onDeviceChange(kind)"
          @close="settingsOpen=false"
        />
      </div>

      <Transition name="role-overlay-fade">
        <div v-if="gamePhase === 'roles_pick' && roleOverlayMode !== 'hidden' && (roleOverlayMode === 'reveal' || rolePick.activeUserId === localId)" class="role-overlay">
          <div class="role-overlay-inner">
            <button v-for="n in roleCardsToRender" :key="n" class="role-card" @click="game.canClickCard(n) && pickRoleCardUi(n)" :disabled="!game.canClickCard(n)"
              :class="{ 'is-revealed': roleOverlayMode === 'reveal' && roleOverlayCard === n && myGameRoleKind, 'is-taken': takenCardSet.has(n) }">
              <div class="role-card-inner">
                <div class="role-card-face back">
                  <img :src="iconCardBack" alt="card" />
                </div>
                <div class="role-card-face front">
                  <img v-if="myGameRoleKind" :src="ROLE_IMAGES[myGameRoleKind]" alt="role" />
                </div>
              </div>
            </button>
          </div>
        </div>
      </Transition>
      <div v-if="mediaGateVisible" class="reconnect-overlay media-gate" @click.stop="onMediaGateClick">Нажмите чтобы продолжить…</div>
    </template>
    <div class="role-preload" aria-hidden="true">
      <img v-for="src in ROLE_CARD_IMAGES" :key="src" :src="src" alt="" loading="eager" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Socket } from 'socket.io-client'
import { useAuthStore } from '@/store'
import { useRoomGame, type SendAckFn, type Ack, type GamePhase, type FarewellVerdict } from '@/composables/roomGame'
import { useRTC, type VQ } from '@/composables/rtc'
import { confirmDialog, alertDialog } from '@/services/confirm'
import { createAuthedSocket } from '@/services/sio'
import RoomTile from '@/components/RoomTile.vue'
import RoomSetting from '@/components/RoomSetting.vue'
import RoomControls from '@/components/RoomControls.vue'
import RoomRequests from '@/components/RoomRequests.vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconVolumeMax from '@/assets/svg/volumeMax.svg'
import iconVolumeMid from '@/assets/svg/volumeMid.svg'
import iconVolumeLow from '@/assets/svg/volumeLow.svg'
import iconVolumeMute from '@/assets/svg/volumeMute.svg'

import iconClose from '@/assets/svg/close.svg'
import iconLeaveRoom from '@/assets/svg/leave.svg'
import iconControls from '@/assets/svg/controls.svg'
import iconSettings from '@/assets/svg/settings.svg'
import iconRequestsRoom from '@/assets/svg/requestsRoom.svg'
import iconReady from '@/assets/svg/ready.svg'
import iconGameStart from '@/assets/svg/gameStart.svg'
import iconGameStop from '@/assets/svg/gameStop.svg'
import iconTakeFoul from '@/assets/svg/takeFoul.svg'
import iconSkip from '@/assets/svg/skip.svg'
import iconDeadPlayer from '@/assets/svg/deadPlayer.svg'
import iconCardBack from '@/assets/images/cardBack.png'
import iconSleepPlayer from '@/assets/images/sleepPlayer.png'
import iconLowSignal from '@/assets/images/lowSignal.png'
import iconKillPlayer from '@/assets/images/killPlayer.png'
import iconVotedPlayer from '@/assets/images/votedPlayer.png'
import iconFouledPlayer from '@/assets/images/fouledPlayer.png'
import iconLeavePlayer from '@/assets/images/leavePlayer.png'

import iconMicOn from '@/assets/svg/micOn.svg'
import iconMicOff from '@/assets/svg/micOff.svg'
import iconMicBlocked from '@/assets/svg/micBlocked.svg'
import iconCamOn from '@/assets/svg/camOn.svg'
import iconCamOff from '@/assets/svg/camOff.svg'
import iconCamBlocked from '@/assets/svg/camBlocked.svg'
import iconSpkOn from '@/assets/svg/spkOn.svg'
import iconSpkOff from '@/assets/svg/spkOff.svg'
import iconSpkBlocked from '@/assets/svg/spkBlocked.svg'
import iconVisOn from '@/assets/svg/visOn.svg'
import iconVisOff from '@/assets/svg/visOff.svg'
import iconVisBlocked from '@/assets/svg/visBlocked.svg'
import iconScreenOn from '@/assets/svg/screenOn.svg'
import iconScreenOff from '@/assets/svg/screenOff.svg'
import iconScreenBlocked from '@/assets/svg/screenBlocked.svg'

type State01 = 0 | 1
type StatusState = {
  mic: State01
  cam: State01
  speakers: State01
  visibility: State01
  ready?: State01
  mirror?: State01
}
type BlockState = StatusState & { screen: State01 }
type IconKind = keyof StatusState | 'screen'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const rtc = useRTC()
const { localId, mics, cams, selectedMicId, selectedCamId, peerIds } = rtc

const rid = Number(route.params.id)
const game = useRoomGame(localId, ref(rid))
const {
  GAME_COLUMN_INDEX,
  GAME_ROW_INDEX,
  ROLE_IMAGES,
  ROLE_CARD_IMAGES,

  gamePhase,
  minReadyToStart,
  seatsByUser,
  offlineInGame,
  gameFoulsByUser,
  votedThisRound,
  votedUsers,
  knownRolesVisible,
  canToggleKnownRoles,
  rolePick,
  roleCardsToRender,
  roleOverlayMode,
  roleOverlayCard,
  nomineeSeatNumbers,
  currentNomineeSeat,
  startingGame,
  endingGame,
  myGameRole,
  isHead,
  myGameRoleKind,
  amIAlive,
  takenCardSet,
  mafiaTalkRemainingMs,
  voteStartedForCurrent,
  voteBlocked,
  night,
  headNightPicks,
  headUserId,
  offlineAliveSeatNumbers,
  hasOfflineAlivePlayers,
  headPickKind,
  phaseLabel,
  gameFinished,
  isCurrentSpeaker,
  canStartDay,
  canFinishSpeechHead,
  canPassSpeechHead,
  canFinishSpeechSelf,
  canTakeFoulSelf,
  canStartVote,
  canHeadVoteControl,
  canPrepareVoteLift,
  canStartVoteLift,
  isLiftVoting,
  liftHighlightNominees,
  canHeadGoToMafiaTalkControl,
  canHeadFinishMafiaTalkControl,
  canHeadFinishVoteControl,
  canHeadNightShootControl,
  canHeadNightCheckControl,
  canHeadBestMoveControl,
  canHeadDayFromNightControl,
  bestMoveSeat,
  canStartLeaderSpeech,
  canRestartVoteForLeaders,
  canShowNight,
} = game

const navUserAgent = navigator.userAgent || ''
const IS_MOBILE = (navigator as any).userAgentData?.mobile === true || /Android|iPhone|iPad|iPod|Mobile/i.test(navUserAgent)
  || (window.matchMedia?.('(pointer: coarse)').matches && /Android|iPhone|iPad|iPod|Mobile|Tablet|Touch/i.test(navUserAgent))

const local = reactive({ mic: false, cam: false, speakers: true, visibility: true })
const pending = reactive<{ [k in keyof typeof local]: boolean }>({ mic: false, cam: false, speakers: false, visibility: false })
const micOn = computed({ get: () => local.mic, set: v => { local.mic = v } })
const camOn = computed({ get: () => local.cam, set: v => { local.cam = v } })
const speakersOn = computed({ get: () => local.speakers, set: v => { local.speakers = v } })
const visibilityOn = computed({ get: () => local.visibility, set: v => { local.visibility = v } })
const socket = ref<Socket | null>(null)
const joinInFlight = ref<Promise<any> | null>(null)
const statusByUser = reactive(new Map<string, StatusState>())
const positionByUser = reactive(new Map<string, number>())
const blockByUser  = reactive(new Map<string, BlockState>())
const rolesByUser = reactive(new Map<string, string>())
const nameByUser = reactive(new Map<string, string>())
const avatarByUser = reactive(new Map<string, string | null>())
const volUi = reactive<Record<string, number>>({})
const screenOwnerId = ref<string>('')
const openPanelFor = ref<string>('')
const pendingScreen = ref(false)
const pendingQuality = ref(false)
const settingsOpen = ref(false)
const musicSettingsOpen = ref(false)
const uiReady = ref(false)
const leaving = ref(false)
const netReconnecting = ref(false)
const lkReconnecting = computed(() => rtc.reconnecting.value)
const isReconnecting = computed(() => netReconnecting.value || lkReconnecting.value)
const needInitialMediaUnlock = ref(false)
const openApps = ref(false)
const appsCounts = reactive({ total: 0, unread: 0 })
const isPrivate = ref(false)
const ws_url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
const isTheater = computed(() => !!screenOwnerId.value)
const isMyScreen = computed(() => !!localId.value && screenOwnerId.value === localId.value)
const streamAudioKey = computed(() => screenOwnerId.value ? rtc.screenKey(screenOwnerId.value) : '')
const streamVol = computed(() => streamAudioKey.value ? (volUi[streamAudioKey.value] ?? rtc.getUserVolume(streamAudioKey.value)) : 100)
const fitContainInGrid = computed(() => !isTheater.value && sortedPeerIds.value.length < 3)
const mediaGateVisible = computed(() => uiReady.value && !isReconnecting.value && needInitialMediaUnlock.value)
const isSpectatorInGame = computed(() => {
  const id = localId.value
  if (!id || gamePhase.value === 'idle') return false
  return !seatsByUser[id]
})

const gameStartOverlayVisible = ref(false)
const gameEndOverlayVisible = ref(false)
const gameOverlayVisible = computed(() => gameStartOverlayVisible.value || gameEndOverlayVisible.value)
const gameOverlayText = computed(() => gameEndOverlayVisible.value ? 'Завершение игры…' : 'Запуск игры…')
let gameStartOverlayTimerId: number | null = null
let gameEndOverlayTimerId: number | null = null
function showGameStartOverlay(ms = 1000) {
  gameStartOverlayVisible.value = true
  if (gameStartOverlayTimerId != null) window.clearTimeout(gameStartOverlayTimerId)
  gameStartOverlayTimerId = window.setTimeout(() => {
    gameStartOverlayVisible.value = false
    gameStartOverlayTimerId = null
  }, ms)
}
function showGameEndOverlay(ms = 1000) {
  gameEndOverlayVisible.value = true
  if (gameEndOverlayTimerId != null) window.clearTimeout(gameEndOverlayTimerId)
  gameEndOverlayTimerId = window.setTimeout(() => {
    gameEndOverlayVisible.value = false
    gameEndOverlayTimerId = null
  }, ms)
}

function hiddenByVisibility(id: string): boolean {
  if (id === localId.value) return false
  if (visibilityOn.value) return false
  if (gamePhase.value !== 'idle') {
    if (game.isDead(id)) return false
  }
  return true
}
function visOffAvatar(id: string): string {
  if (!hiddenByVisibility(id)) return ''
  return gamePhase.value === 'idle' ? iconVisOff : iconSleepPlayer
}

const readyCount = computed(() => {
  let cnt = 0
  statusByUser.forEach((st) => { if ((st.ready ?? 0) === 1) cnt++ })
  return cnt
})

type DeathReasonKind = 'suicide' | 'foul' | 'vote' | 'night' | string
const DEAD_ICON_BY_REASON: Record<DeathReasonKind, string> = {
  suicide: iconLeavePlayer,
  foul: iconFouledPlayer,
  vote: iconVotedPlayer,
  night: iconKillPlayer,
}
const deadAvatar = (id: string): string => {
  const reason = game.deathReason(id) as DeathReasonKind
  return DEAD_ICON_BY_REASON[reason] || iconKillPlayer
}

const totalPlayers = computed(() => sortedPeerIds.value.length)
const canShowStartGame = computed(() => {
  if (!localId.value) return false
  if (gamePhase.value !== 'idle') return false
  const total = totalPlayers.value
  const ready = readyCount.value
  const st = statusByUser.get(localId.value)
  const meReady = (st?.ready ?? 0) === 1
  const min = minReadyToStart.value
  const nonReady = total - ready
  return !meReady && total === min + 1 && ready === min && nonReady === 1
})

const videoQuality = computed<VQ>({
  get: () => rtc.remoteQuality.value,
  set: (v) => {
    if (pendingQuality.value) return
    pendingQuality.value = true
    try { rtc.setRemoteQualityForAll(v) } finally { pendingQuality.value = false }
  },
})

const isMirrored = (id: string) => (statusByUser.get(id)?.mirror ?? 0) === 1
const mirrorOn = computed({
  get: () => isMirrored(localId.value),
  set: async (v: boolean) => {
    rtc.saveLS(rtc.LS.mirror, v ? '1' : '0')
    const id = localId.value
    const cur = statusByUser.get(id) ?? { mic: 1, cam: 1, speakers: 1, visibility: 1, ready: 0, mirror: 0 }
    statusByUser.set(id, { ...cur, mirror: v ? 1 : 0 })
    try { await publishState({ mirror: v }) } catch {}
  },
})

const rerr = (...a: unknown[]) => console.error('[ROOM]', ...a)

let reloading = false
function hardReload() {
  if (reloading) return
  reloading = true
  window.location.reload()
}

function avatarKey(id: string): string {
  const name = avatarByUser.get(id) || ''
  if (!name) return ''
  return name.startsWith('avatars/') ? name : `avatars/${name}`
}
function userName(id: string) {
  return nameByUser.get(id) || `user${id}`
}

function memoRef<K, F extends (k:K) => any> (cache: Map<any, any>, factory: F) {
  return (k: K) => {
    const c = cache.get(k)
    if (c) return c
    const f = factory(k)
    cache.set(k,f)
    return f
  }
}
const videoRefMemo = new Map<string, (el: HTMLVideoElement | null) => void>()
const screenRefMemo = new Map<string, (el: HTMLVideoElement | null) => void>()
const stableVideoRef = memoRef(videoRefMemo, (id: string) => rtc.videoRef(id))
const stableScreenRef = memoRef(screenRefMemo, (id: string) => id ? rtc.screenVideoRef(id) : () => {})

const STATE_ICONS = {
  mic:        { on: iconMicOn,    off: iconMicOff,    blk: iconMicBlocked },
  cam:        { on: iconCamOn,    off: iconCamOff,    blk: iconCamBlocked },
  speakers:   { on: iconSpkOn,    off: iconSpkOff,    blk: iconSpkBlocked },
  visibility: { on: iconVisOn,    off: iconVisOff,    blk: iconVisBlocked },
  screen:     { on: iconScreenOn, off: iconScreenOff, blk: iconScreenBlocked },
} as const
function stateIcon(kind: IconKind, id: string) {
  if (isBlocked(id, kind)) return STATE_ICONS[kind].blk
  return isOn(id, kind) ? STATE_ICONS[kind].on : STATE_ICONS[kind].off
}
function closePanels(except?: 'card'|'apps'|'settings'|'music') {
  if (except !== 'card') openPanelFor.value = ''
  if (except !== 'apps') openApps.value = false
  if (except !== 'settings') settingsOpen.value = false
  if (except !== 'music') musicSettingsOpen.value = false
}
const toggleTilePanel = (id: string) => {
  if (id === localId.value) return
  const next = openPanelFor.value === id ? '' : id
  closePanels('card')
  openPanelFor.value = next
}
function toggleSettings() {
  const next = !settingsOpen.value
  closePanels('settings')
  settingsOpen.value = next
  if (next) void rtc.refreshDevices().catch(() => {})
}
function toggleApps() {
  const next = !openApps.value
  closePanels('apps')
  openApps.value = next
}
function toggleMusicSettings() {
  const next = !musicSettingsOpen.value
  closePanels('music')
  musicSettingsOpen.value = next
}
function onDocClick() {
  closePanels()
  void rtc.resumeAudio()
  void ensureBgmPlayback()
}
function volumeIcon(val: number, enabled: boolean) {
  if (!enabled) return iconVolumeMute
  const v = Math.round(val)
  return v < 1 ? iconVolumeMute : v < 25 ? iconVolumeLow : v < 100 ? iconVolumeMid : iconVolumeMax
}
function volumeIconForUser(id: string) {
  return volumeIcon(volUi[id] ?? rtc.getUserVolume(id), speakersOn.value && !isBlocked(id,'speakers'))
}
function volumeIconForStream(key: string) {
  if (!key) return iconVolumeMute
  return volumeIcon(volUi[key] ?? rtc.getUserVolume(key), speakersOn.value && !isBlocked(screenOwnerId.value,'speakers'))
}

const BGM_VOLUME_LS = 'bgm:volume'
const BGM_DEFAULT_VOLUME = 50
const BGM_MAX_VOLUME = 1
const BGM_FILES = Object.values(
  import.meta.glob('@/assets/music/*.mp3', { eager: true, as: 'url' })
) as string[]
const BGM_ACTIVE_PHASES: GamePhase[] = ['roles_pick', 'mafia_talk_start', 'mafia_talk_end', 'night']

const bgmAudio = ref<HTMLAudioElement | null>(null)
const bgmVolume = ref<number>(loadBgmVolume())
const bgmCurrentSrc = ref<string>('')

function pickRandomBgmSource(): string {
  if (!BGM_FILES.length) return ''
  const idx = Math.floor(Math.random() * BGM_FILES.length)
  return BGM_FILES[idx]
}

function clampBgmVolume(v: number) {
  if (!Number.isFinite(v)) return BGM_DEFAULT_VOLUME
  return Math.min(100, Math.max(0, Math.round(v)))
}
function loadBgmVolume(): number {
  if (typeof window === 'undefined') return BGM_DEFAULT_VOLUME
  try {
    const raw = window.localStorage.getItem(BGM_VOLUME_LS)
    if (raw == null) return BGM_DEFAULT_VOLUME
    const parsed = Number(raw)
    return clampBgmVolume(parsed)
  } catch {
    return BGM_DEFAULT_VOLUME
  }
}
function saveBgmVolume(v: number) {
  if (typeof window === 'undefined') return
  try { window.localStorage.setItem(BGM_VOLUME_LS, String(v)) } catch {}
}
function resolveBgmUrl(src: string) {
  if (typeof window === 'undefined') return src
  try { return new URL(src, window.location.origin).toString() } catch { return src }
}
function ensureBgmAudio(): HTMLAudioElement {
  if (bgmAudio.value) return bgmAudio.value
  const el = new Audio()
  el.loop = true
  el.preload = 'auto'
  bgmAudio.value = el
  applyBgmVolume()
  return el
}
function applyBgmVolume() {
  const el = bgmAudio.value
  if (!el) return
  const scaled = (clampBgmVolume(bgmVolume.value) / 100) * BGM_MAX_VOLUME
  el.volume = Math.min(1, Math.max(0, scaled))
}
function stopBgm() {
  const el = bgmAudio.value
  if (!el) return
  try { el.pause() } catch {}
  try { el.currentTime = 0 } catch {}
  bgmCurrentSrc.value = ''
}
function destroyBgm() {
  const el = bgmAudio.value
  if (!el) return
  stopBgm()
  try { el.src = '' } catch {}
  bgmAudio.value = null
}

const bgmShouldPlay = computed(() => BGM_ACTIVE_PHASES.includes(gamePhase.value))

function ensureBgmPlayback() {
  if (!bgmShouldPlay.value) {
    stopBgm()
    return
  }
  if (!BGM_FILES.length) {
    stopBgm()
    return
  }
  const el = ensureBgmAudio()
  if (!bgmCurrentSrc.value) bgmCurrentSrc.value = pickRandomBgmSource()
  const src = bgmCurrentSrc.value
  if (!src) return
  const resolved = resolveBgmUrl(src)
  if (resolved && el.src !== resolved) {
    el.src = src
    try { el.currentTime = 0 } catch {}
  }
  applyBgmVolume()
  void el.play().catch(() => {})
}

watch(bgmVolume, (v) => {
  const next = clampBgmVolume(v)
  if (next !== v) {
    bgmVolume.value = next
    return
  }
  saveBgmVolume(next)
  applyBgmVolume()
}, { immediate: true })

watch(bgmShouldPlay, (on, was) => {
  if (!on) {
    stopBgm()
    return
  }
  if (!was) bgmCurrentSrc.value = ''
  ensureBgmPlayback()
}, { immediate: true })

async function sendAck(event: string, payload: any, timeoutMs = 15000): Promise<Ack> {
  try {
    return await socket.value!.timeout(timeoutMs).emitWithAck(event, payload)
  } catch (e:any) {
    rerr('ack fail', { event, payload, name: e?.name, message: e?.message })
    return null
  }
}
function ensureOk(resp: Ack, msgByCode: Record<number, string>, netMsg: string): boolean {
  if (resp && resp.ok) return true
  const code = resp?.status
  void alertDialog((code && msgByCode[code]) || netMsg)
  return false
}

const sendAckGame: SendAckFn = (event, payload, timeoutMs) => sendAck(event, payload, timeoutMs)
const startGameUi = () => game.startGame(sendAckGame)
const endGameUi = () => game.endGame(sendAckGame)
const leaveGameUi = () => game.leaveGame(sendAckGame)
const pickRoleCardUi = (card: number) => game.pickRoleCard(card, sendAckGame)
const goToMafiaTalkUi = () => game.goToMafiaTalk(sendAckGame)
const finishMafiaTalkUi = () => game.finishMafiaTalk(sendAckGame)
const startDayUi = () => game.startDay(sendAckGame)
const passSpeechUi = () => game.passSpeech(sendAckGame)
const finishSpeechUi = () => game.finishSpeech(sendAckGame)
const startVoteUi = () => game.startVotePhase(sendAckGame)
const finishVoteUi = () => game.finishVote(sendAckGame)
const prepareVoteLiftUi = () => game.prepareVoteLift(sendAckGame)
const startVoteLiftUi = () => game.startVoteLift(sendAckGame)
const startLeaderSpeechUi = () => game.startLeaderSpeech(sendAckGame)
const restartVoteForLeadersUi = () => game.restartVoteForLeaders(sendAckGame)
const shootTargetUi = (targetId: string) => game.shootTarget(targetId, sendAckGame)
const checkTargetUi = (targetId: string) => game.checkTarget(targetId, sendAckGame)
const startNightShootUi = () => game.startNightShoot(sendAckGame)
const startNightChecksUi = () => game.startNightChecks(sendAckGame)
const startBestMoveUi = () => game.startBestMove(sendAckGame)
const goToNightUi = () => game.goToNight(sendAckGame)
const startDayFromNightUi = () => game.startDayFromNight(sendAckGame)      
const onHeadVoteControl = () => game.headVoteControl(sendAckGame)
const onGiveFoul = (targetId: string) => game.giveFoul(targetId, sendAckGame)

const foulPending = ref(false)
async function takeFoulUi() {
  if (foulPending.value) return
  foulPending.value = true
  try {
    const ms = await game.takeFoul(sendAckGame)
    const delay = typeof ms === 'number' && ms > 0 ? ms : 0
    if (delay > 0) {
      if (!micOn.value) try { await toggleMic() } catch {}
      window.setTimeout(async () => {
        try {
          const speakingNow = isCurrentSpeaker.value
          if (!speakingNow && micOn.value) await toggleMic()
        } catch {}
        finally { foulPending.value = false }
      }, delay)
    } else { foulPending.value = false }
  } catch { foulPending.value = false }
}

const showPermProbe = computed(() => !rtc.hasAudioInput.value || !rtc.hasVideoInput.value)
async function onProbeClick() {
  try { await rtc.resumeAudio() } catch {}
  await rtc.probePermissions({ audio: true, video: true })
}

const sortedPeerIds = computed(() => {
  const idsSet = new Set<string>()
  if (gamePhase.value !== 'idle') {
    for (const uid of Object.keys(seatsByUser)) { idsSet.add(String(uid)) }
  } else {
    positionByUser.forEach((_pos, uid) => idsSet.add(uid))
  }
  if (idsSet.size === 0) {
    peerIds.value.forEach((id) => idsSet.add(id))
  }
  const ids = Array.from(idsSet)
  return ids.sort((a, b) => {
    if (gamePhase.value !== 'idle') {
      const sa = seatsByUser[a]
      const sb = seatsByUser[b]
      if (sa && sb && sa !== sb) return sa - sb
    }
    const pa = positionByUser.get(a) ?? Number.POSITIVE_INFINITY
    const pb = positionByUser.get(b) ?? Number.POSITIVE_INFINITY
    return pa !== pb ? pa - pb : String(a).localeCompare(String(b))
  })
})
const gridStyle = computed(() => {
  if (gamePhase.value !== 'idle') {
    return { gridTemplateColumns: 'repeat(8, 1fr)', gridTemplateRows: 'repeat(6, 1fr)' }
  }
  const count = sortedPeerIds.value.length
  const cols = count <= 2 ? 2 : count <= 6 ? 3 : 4
  const rows = count <= 2 ? 1 : count <= 6 ? 2 : 3
  return { gridTemplateColumns: `repeat(${cols}, 1fr)`, gridTemplateRows: `repeat(${rows}, 1fr)` }
})

const tileGridStyle = (id: string) => {
  if (gamePhase.value === 'idle') return {}
  const pos = seatsByUser[id]
  if (!pos) return {}
  const col = GAME_COLUMN_INDEX[pos] ?? 1
  const row = GAME_ROW_INDEX[pos] ?? 1
  return { gridColumn: `${col} / span 2`, gridRow: `${row} / span 2` }
}

const isEmpty = (v: any) => v === undefined || v === null || v === ''
const pick01 = (v: any, fallback: 0 | 1) => isEmpty(v) ? fallback : norm01(v, fallback)
function norm01(v: unknown, fallback: 0 | 1): 0 | 1 {
  if (typeof v === 'boolean') return v ? 1 : 0
  if (typeof v === 'number') return v === 1 ? 1 : v === 0 ? 0 : fallback
  if (typeof v === 'string') {
    const s = v.trim().toLowerCase()
    if (s === '1' || s === 'true') return 1
    if (s === '0' || s === 'false') return 0
  }
  return fallback
}

function onVol(id: string, v: number) {
  volUi[id] = v
  rtc.setUserVolume(id, v)
  void rtc.resumeAudio()
}

function rol(id: string): string { return rolesByUser.get(id) || 'user' }
const myRole = computed(() => rol(localId.value))

function onNominate(targetId: string) {
  game.nominateTarget(targetId, sendAck)
}

function onFarewell(verdict: FarewellVerdict, targetId: string) {
  if (!game.canMakeFarewellChoice(targetId)) return
  void game.markFarewellChoice(targetId, verdict, sendAckGame)
}

function onBestMove(targetId: string) {
  if (!game.canMakeBestMoveChoice(targetId)) return
  void game.markBestMoveChoice(targetId, sendAckGame)
}

const onVote = () => {
  game.voteForCurrent(sendAck)
}

function isOn(id: string, kind: IconKind) {
  if (kind === 'screen') return !!id && id === screenOwnerId.value
  if (id === localId.value) {
    if (kind === 'mic') return micOn.value
    if (kind === 'cam') return camOn.value
    if (kind === 'speakers') return speakersOn.value
    return visibilityOn.value
  }
  const st = statusByUser.get(id)
  return st ? st[kind] === 1 : true
}

function isBlocked(id: string, kind: IconKind) {
  const st = blockByUser.get(id)
  return st ? st[kind] === 1 : false
}

const blockedSelf = computed<BlockState>(() => {
  const s = blockByUser.get(localId.value)
  return {
    mic: s?.mic ?? 0,
    cam: s?.cam ?? 0,
    speakers: s?.speakers ?? 0,
    visibility: s?.visibility ?? 0,
    screen: s?.screen ?? 0,
  }
})

const readyOn = computed({
  get: () => (statusByUser.get(localId.value)?.ready ?? 0) === 1,
  set: (v: boolean) => {
    const cur = statusByUser.get(localId.value) ?? { mic: 1, cam: 1, speakers: 1, visibility: 1, ready: 0 }
    statusByUser.set(localId.value, { ...cur, ready: v ? 1 : 0 })
  }
})
const isReady = (id: string) => (statusByUser.get(id)?.ready ?? 0) === 1

async function toggleReady() {
  const want = !readyOn.value
  readyOn.value = want
  try {
    await publishState({ ready: want })
  } catch {}
}

function canModerate(targetId: string): boolean {
  if (targetId === localId.value) return false
  if (gamePhase.value !== 'idle') return false
  const me = myRole.value
  const trg = rol(targetId)
  if (me === trg) return false
  if (me === 'admin') return trg !== 'admin'
  if (me === 'host') return trg !== 'admin' && trg !== 'host'
  return false
}

async function toggleBlock(targetId: string, key: keyof BlockState) {
  const want = !isBlocked(targetId, key)
  const resp = await sendAck('moderate', { user_id: Number(targetId), blocks: { [key]: want } })
  if (!ensureOk(resp, { 403: 'Недостаточно прав', 404: 'Пользователь не в комнате' }, 'Сеть/таймаут при модерации')) return
}

async function kickUser(targetId: string) {
  if (!canModerate(targetId)) return
  const ok = await confirmDialog({
    title: 'Удаление пользователя',
    text: 'Вы уверены что хотите удалить пользователя?',
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  const resp = await sendAck('kick', { user_id: Number(targetId) })
  if (!ensureOk(resp, { 403: 'Недостаточно прав', 404: 'Пользователь не в комнате' }, 'Сеть/таймаут при удалении')) return
}

function applyPeerState(uid: string, patch: any) {
  const cur = statusByUser.get(uid) ?? { mic: 1, cam: 1, speakers: 1, visibility: 1 }
  statusByUser.set(uid, {
    mic:        pick01(patch?.mic, cur.mic),
    cam:        pick01(patch?.cam, cur.cam),
    speakers:   pick01(patch?.speakers, cur.speakers),
    visibility: pick01(patch?.visibility, cur.visibility),
    ready:      pick01(patch?.ready, cur.ready ?? 0),
    mirror:     pick01(patch?.mirror, cur.mirror ?? 0),
  })
}
function applyBlocks(uid: string, patch: any) {
  const cur = blockByUser.get(uid) ?? { mic: 0, cam: 0, speakers: 0, visibility: 0, screen: 0 }
  blockByUser.set(uid, {
    mic:        pick01(patch?.mic, cur.mic),
    cam:        pick01(patch?.cam, cur.cam),
    speakers:   pick01(patch?.speakers, cur.speakers),
    visibility: pick01(patch?.visibility, cur.visibility),
    screen:     pick01(patch?.screen, cur.screen),
  })
}
function applySelfPref(pref: any) {
  if (!isEmpty(pref?.mic)) local.mic = norm01(pref.mic, local.mic ? 1 : 0) === 1
  if (!isEmpty(pref?.cam)) local.cam = norm01(pref.cam, local.cam ? 1 : 0) === 1
  if (!isEmpty(pref?.speakers)) local.speakers = norm01(pref.speakers, local.speakers ? 1 : 0) === 1
  if (!isEmpty(pref?.visibility)) local.visibility = norm01(pref.visibility, local.visibility ? 1 : 0) === 1
}

function purgePeerUI(id: string) {
  statusByUser.delete(id)
  positionByUser.delete(id)
  blockByUser.delete(id)
  rolesByUser.delete(id)
  nameByUser.delete(id)
  avatarByUser.delete(id)
  videoRefMemo.delete(id)
  screenRefMemo.delete(id)
  offlineInGame.delete(id)
  if (openPanelFor.value === id || openPanelFor.value === rtc.screenKey(id)) openPanelFor.value = ''
  delete volUi[id]
  delete volUi[rtc.screenKey(id)]
  if (screenOwnerId.value === id) screenOwnerId.value = ''
}

function clearScreenVolume(id: string | null | undefined) {
  if (!id) return
  delete volUi[rtc.screenKey(id)]
}

function setScreenOwner(id: string) {
  const prev = screenOwnerId.value
  screenOwnerId.value = id
  if (openPanelFor.value === rtc.screenKey(prev)) openPanelFor.value = ''
  clearScreenVolume(prev)
}

function connectSocket() {
  if (socket.value && socket.value.connected) return
  socket.value = createAuthedSocket('/room', {
    path: '/ws/socket.io',
    transports: ['websocket','polling'],
    upgrade: true,
    autoConnect: true,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 200,
    reconnectionDelayMax: 2000,
  })

  try {
    socket.value?.io.on('reconnect_attempt', () => { netReconnecting.value = true })
    socket.value?.io.on('reconnect_error',   () => { netReconnecting.value = true })
    socket.value?.io.on('reconnect_failed',  () => { netReconnecting.value = true })
    socket.value?.io.on('reconnect',         () => { netReconnecting.value = false })
  } catch {}

socket.value?.on('connect', async () => {
  netReconnecting.value = false
  if (!leaving.value) {
    const ack = await safeJoin()
    if (!ack?.ok) {
      if (ack?.status === 404 || ack?.status === 410) {
        void alertDialog('Комната недоступна')
        router.replace({ name: 'home' }).catch(() => {})
        return
      }
      return
    }
    if (uiReady.value) applyJoinAck(ack)
  }
  if (pendingDeltas.length) {
    const merged = Object.assign({}, ...pendingDeltas.splice(0))
    const resp = await sendAck('state', merged)
    if (!resp?.ok) pendingDeltas.unshift(merged)
  }
})

  socket.value?.on('disconnect', () => {
    if (!leaving.value) netReconnecting.value = true
    openPanelFor.value = ''
  })

  socket.value.on('force_logout', async () => {
    try { await onLeave() } finally { await auth.localSignOut?.() }
  })

  socket.value.on('state_changed', (p: any) => {
    const id = String(p.user_id)
    ensurePeer(id)
    applyPeerState(id, p)
  })

  socket.value.on('member_joined', (p: any) => {
    const id = String(p.user_id)
    offlineInGame.delete(id)
    ensurePeer(id)
    applyPeerState(id, p?.state || {})
    if (p?.role) rolesByUser.set(id, String(p.role))
    if (p?.blocks) applyBlocks(id, p.blocks)
    const av = p?.avatar_name
    if (typeof av === 'string' && av.trim() !== '') avatarByUser.set(id, av)
    const un = p?.username
    if (typeof un === 'string' && un.trim() !== '') nameByUser.set(id, String(un))
  })

  socket.value.on('member_left', (p: any) => {
    const id = String(p.user_id)
    const seat = seatsByUser[id]
    const isInGameNow = gamePhase.value !== 'idle' && Number.isFinite(seat) && seat > 0
    if (isInGameNow) {
      game.maybeAskRevoteOnDisconnect(id, sendAckGame)
      offlineInGame.add(id)
      rtc.cleanupPeer(id)
      return
    }
    purgePeerUI(id)
    rtc.cleanupPeer(id)
  })

  socket.value.on('positions', (p: any) => {
    const ups = Array.isArray(p?.updates) ? p.updates : []
    for (const u of ups) {
      const id = String(u.user_id)
      const pos = Number(u.position)
      if (Number.isFinite(pos)) positionByUser.set(id, pos)
      ensurePeer(id)
    }
  })

  socket.value.on('moderation', async (p: any) => {
    const uid = String(p?.user_id ?? '')
    const blocks = (p?.blocks ?? {}) as Record<string, any>
    applyBlocks(uid, blocks)
    if (uid === String(localId.value)) {
      if ('cam' in blocks && norm01(blocks.cam, 0) === 1) {
        local.cam = false
        try { await rtc.disable('videoinput') } catch {}
      }
      if ('mic' in blocks && norm01(blocks.mic, 0) === 1) {
        local.mic = false
        try { await rtc.disable('audioinput') } catch {}
      }
      if ('speakers' in blocks && norm01(blocks.speakers, 0) === 1) {
        local.speakers = false
        rtc.setAudioSubscriptionsForAll(false)
      }
      if ('visibility' in blocks && norm01(blocks.visibility, 0) === 1) {
        local.visibility = false
        rtc.setVideoSubscriptionsForAll(false)
      }
      if ('screen' in blocks && norm01(blocks.screen, 0) === 1) {
        if (screenOwnerId.value === localId.value) { try { await rtc.stopScreenShare() } catch {} }
        screenOwnerId.value = ''
      }
    }
  })

  socket.value.on('force_leave', async (_p:any) => {
    try { await onLeave() } catch {}
  })

  socket.value.on('screen_owner', (p: any) => {
    setScreenOwner(p?.user_id ? String(p.user_id) : '')
  })

  socket.value?.on('game_starting', async (p: any) => {
    const delayMs = Number(p?.delay_ms || 0)
    const ms = Number.isFinite(delayMs) && delayMs > 0 ? delayMs : 1000
    showGameStartOverlay(ms + 250)
    await nextTick()
  })

  socket.value?.on('game_started', (p: any) => {
    game.handleGameStarted(p)
    statusByUser.forEach((st, uid) => {
      statusByUser.set(uid, { ...st, ready: 0 as 0 })
    })
    void enforceInitialGameControls()
  })

  socket.value?.on('game_finished', (p: any) => {
    game.handleGameFinished(p)
    if (myGameRole.value === 'player' || myGameRole.value === 'head') void restoreAfterGameEnd()
  })

  socket.value?.on('game_ended', async (p: any) => {
    const reason = String(p?.reason || '')
    if (reason !== 'early_leave_before_day') {
      showGameEndOverlay()
      await nextTick()
      await new Promise((resolve) => window.setTimeout(resolve, 250))
    } else {
      void alertDialog('Игра была остановлена т.к. игрок покинул игру до ее начала')
    }
    const roleBeforeEnd = game.handleGameEnded(p)
    const connectedIds = new Set(rtc.peerIds.value)
    const toDrop: string[] = []
    statusByUser.forEach((_st, uid) => {
      if (!connectedIds.has(uid)) toDrop.push(uid)
    })
    for (const uid of toDrop) {
      purgePeerUI(uid)
      rtc.cleanupPeer(uid)
    }
    if (roleBeforeEnd === 'player' || roleBeforeEnd === 'head') void restoreAfterGameEnd()
  })

  socket.value?.on('game_player_left', (p: any) => {
    game.handleGamePlayerLeft(p)
  })

  socket.value?.on('game_roles_turn', (p: any) => {
    game.handleGameRolesTurn(p)
  })

  socket.value?.on('game_roles_picked', (p: any) => {
    game.handleGameRolesPicked(p)
  })

  socket.value?.on('game_role_assigned', (p: any) => {
    game.handleGameRoleAssigned(p)
  })

  socket.value?.on('game_roles_reveal', (p: any) => {
    game.handleGameRolesReveal(p)
  })

  socket.value?.on('game_phase_change', (p: any) => {
    const prevPhase = gamePhase.value as GamePhase
    game.handleGamePhaseChange(p)
    const to = (p?.to ? String(p.to) : gamePhase.value) as GamePhase
    handleGamePhaseChangeUi(prevPhase, to)
  })

  socket.value.on('game_day_speech', (p: any) => {
    game.handleGameDaySpeech(p)
  })

  socket.value.on('game_foul', (p: any) => {
    game.handleGameFoul(p)
  })

  socket.value.on('game_fouls', (p: any) => {
    game.handleGameFouls(p)
  })

  socket.value.on('game_nominee_added', (p: any) => {
    game.handleGameNomineeAdded(p)
  })

  socket.value.on('game_farewell_update', (p: any) => {
    game.handleGameFarewellUpdate(p)
  })

  socket.value.on('game_best_move_update', (p: any) => {
    game.handleGameBestMoveUpdate(p)
  })

  socket.value.on('game_vote_state', (p: any) => {
    game.handleGameVoteState(p)
  })

  socket.value.on('game_voted', (p: any) => {
    game.handleGameVoted(p)
  })

  socket.value.on('game_vote_result', (p: any) => {
    game.handleGameVoteResult(p)
  })

  socket.value.on('game_vote_aborted', (p: any) => {
    game.handleGameVoteAborted(p)
  })

  socket.value.on('game_night_state', (p: any) => {
    game.handleGameNightState(p)
  })

  socket.value.on('game_night_head_picks', (p: any) => {
    game.handleGameNightHeadPicks(p)
  })

  socket.value.on('game_night_reveal', (p: any) => {
    game.handleGameNightReveal(p)
  })
}

async function safeJoin() {
  if (!socket.value) connectSocket()
  if (joinInFlight.value) return joinInFlight.value
  const p = (async () => {
    if (!socket.value!.connected) {
      await new Promise<void>((res, rej) => {
        const t = setTimeout(() => rej(new Error('connect timeout')), 3000)
        socket.value!.once('connect', () => {
          clearTimeout(t)
          res()
        })
      })
    }
    return await sendAck('join', { room_id: rid, state: { ...local } })
  })()
  joinInFlight.value = p
  try {
    return await p
  } finally {
    if (joinInFlight.value === p) joinInFlight.value = null
  }
}

function ensurePeer(id: string) {
  if (!rtc.peerIds.value.includes(id)) {
    rtc.peerIds.value = [...rtc.peerIds.value, id]
  }
}

function optimisticUnblockSelfAfterGame() {
  const id = localId.value
  if (!id) return
  const cur = blockByUser.get(id)
  if (!cur) return
  blockByUser.set(id, {
    mic: 0,
    cam: 0,
    speakers: 0,
    visibility: 0,
    screen: cur.screen ?? 0,
  })
}

async function enforceInitialGameControls() {
  const id = localId.value
  if (!id) return
  const seat = seatsByUser[id]
  if (!seat) return
  if (seat === 11) {
    if (!speakersOn.value) {
      await toggleSpeakers()
    }
    if (!visibilityOn.value) {
      await toggleVisibility()
    }
    return
  }
  if (!camOn.value && !blockedSelf.value.cam) {
    await toggleCam()
  }
  if (!speakersOn.value && !blockedSelf.value.speakers) {
    await toggleSpeakers()
  }
}

async function forceMicOffLocal() {
  if (!micOn.value) return
  try { await toggleMic() } catch {}
  if (micOn.value) {
    local.mic = false
    try { await rtc.disable('audioinput') } catch {}
    try { await publishState({ mic: false }) } catch {}
  }
}

async function enforceMicAfterJoin() {
  if (gamePhase.value === 'idle') return
  if (isCurrentSpeaker.value) return
  if (isSpectatorInGame.value) return
  await forceMicOffLocal()
}

async function restoreAfterGameEnd() {
  const id = localId.value
  if (!id) return
  optimisticUnblockSelfAfterGame()
  if (micOn.value) await toggleMic()
  if (!camOn.value) await toggleCam()
  if (!speakersOn.value) await toggleSpeakers()
  if (!visibilityOn.value) await toggleVisibility()
}

async function applyMafiaTalkStartForLocal(): Promise<void> {
  const roleKind = myGameRoleKind.value
  if (roleKind !== 'mafia' && roleKind !== 'don') return
  if (visibilityOn.value) return
  if (blockedSelf.value.visibility) return
  try { await toggleVisibility() } catch {}
}

async function applyMafiaTalkEndForLocal(): Promise<void> {
  const roleKind = myGameRoleKind.value
  if (roleKind !== 'mafia' && roleKind !== 'don') return
  if (!visibilityOn.value) return
  if (blockedSelf.value.visibility) return
  try { await toggleVisibility() } catch {}
}

async function applyDayStartForLocal(): Promise<void> {
  if (blockedSelf.value.visibility) return
  if (visibilityOn.value) return
  try { await toggleVisibility() } catch {}
}

async function applyNightStartForLocal(): Promise<void> {
  if (isSpectatorInGame.value) return
  const me = localId.value
  const hasActiveFoul = !!(me && game.foulActive.has(me)) || foulPending.value
  try { if (!isHead.value && !hasActiveFoul && !blockedSelf.value.mic && micOn.value) await toggleMic() } catch {}
  try { if (!isHead.value && !blockedSelf.value.visibility && visibilityOn.value) await toggleVisibility() } catch {}
}

async function enforceSpectatorPhaseVisibility(phase: GamePhase): Promise<void> {
  if (!isSpectatorInGame.value) return
  const shouldHide = phase === 'roles_pick' || phase === 'night' || phase === 'mafia_talk_start' || phase === 'mafia_talk_end'
  try {
    if (shouldHide && visibilityOn.value && !blockedSelf.value.visibility) await toggleVisibility()
    if (!shouldHide && !visibilityOn.value && !blockedSelf.value.visibility) await toggleVisibility()
  } catch {}
}

function handleGamePhaseChangeUi(prev: GamePhase, next: GamePhase): void {
  if (prev === 'roles_pick' && next === 'mafia_talk_start') void applyMafiaTalkStartForLocal()
  if (prev === 'mafia_talk_start' && next === 'mafia_talk_end') void applyMafiaTalkEndForLocal()
  if (next === 'night') void applyNightStartForLocal()
  if ((prev === 'mafia_talk_end' && next === 'day') || (prev === 'night' && next === 'day')) void applyDayStartForLocal()
  void enforceSpectatorPhaseVisibility(next)
}

function applyJoinAck(j: any) {
  isPrivate.value = (j?.privacy || j?.room?.privacy) === 'private'
  // const game = j.game
  const me = localId.value
  if (me) game.foulActive.delete(me)
  foulPending.value = false

  positionByUser.clear()
  for (const [uid, pos] of Object.entries(j.positions || {})) {
    const p = Number(pos)
    if (Number.isFinite(p)) positionByUser.set(String(uid), p)
  }

  statusByUser.clear()
  for (const [uid, st] of Object.entries(j.snapshot || {})) {
    statusByUser.set(String(uid), {
      mic:        pick01(st.mic, 0),
      cam:        pick01(st.cam, 0),
      speakers:   pick01(st.speakers, 1),
      visibility: pick01(st.visibility, 1),
      ready:      pick01(st.ready, 0),
      mirror:     pick01((st as any).mirror, 0),
    })
  }

  const ids = new Set<string>(rtc.peerIds.value)
  Object.keys(j.snapshot || {}).forEach(uid => ids.add(String(uid)))
  Object.keys(j.positions || {}).forEach(uid => ids.add(String(uid)))
  rtc.peerIds.value = [...ids]

  blockByUser.clear()
  for (const [uid, bl] of Object.entries(j.blocked || {})) {
    blockByUser.set(String(uid), {
      mic:        pick01(bl.mic, 0),
      cam:        pick01(bl.cam, 0),
      speakers:   pick01(bl.speakers, 0),
      visibility: pick01(bl.visibility, 0),
      screen:     pick01(bl.screen, 0),
    })
  }

  rolesByUser.clear()
  for (const [uid, r] of Object.entries(j.roles || {})) {
    rolesByUser.set(String(uid), String(r || 'user'))
  }

  const prof = j.profiles || {}
  for (const [uid, m] of Object.entries(prof)) {
    const id = String(uid)
    const mm = m as any
    if (typeof mm?.avatar_name === 'string' && mm.avatar_name.trim() !== '') avatarByUser.set(id, mm.avatar_name)
    if (typeof mm?.username === 'string' && mm.username.trim() !== '') nameByUser.set(id, String(mm.username))
  }

  if (j.self_pref) applySelfPref(j.self_pref)
  screenOwnerId.value = j.screen_owner ? String(j.screen_owner) : ''
  const keepKey = screenOwnerId.value ? rtc.screenKey(screenOwnerId.value) : ''
  for (const k in volUi) {
    const isUserId = statusByUser.has(k)
    const isKeep = keepKey && k === keepKey
    if (!isUserId && !isKeep) delete volUi[k]
  }

  const snapshotIds = Object.keys(j.snapshot || {})
  game.applyFromJoinAck(j, snapshotIds)
  void enforceMicAfterJoin()
  void enforceSpectatorPhaseVisibility(gamePhase.value)
}

type PublishDelta = Partial<{
  mic: boolean
  cam: boolean
  speakers: boolean
  visibility: boolean
  ready: boolean
  mirror: boolean
}>
const pendingDeltas: PublishDelta[] = []
async function publishState(delta: PublishDelta) {
  if (!socket.value || !socket.value.connected) {
    pendingDeltas.push(delta)
    return false
  }
  const resp = await sendAck('state', delta)
  if (resp?.ok) return true
  pendingDeltas.push(delta)
  return false
}

const toggleFactory = (k: keyof typeof local, onEnable?: () => Promise<boolean | void>, onDisable?: () => Promise<void>) => async () => {
  if (pending[k]) return
  if (blockedSelf.value[k]) return
  try {
    pending[k] = true
    const want = !local[k]
    if (want) {
      const okLocal = (await onEnable?.()) !== false
      if (!okLocal) return
      local[k] = true
      try { await publishState({ [k]: true } as PublishDelta) } catch {}
    } else {
      await onDisable?.()
      local[k] = false
      try { await publishState({ [k]: false } as PublishDelta) } catch {}
    }
  } finally { pending[k] = false }
}

const toggleMic = toggleFactory('mic',
  async () => await rtc.enable('audioinput'),
  async () => await rtc.disable('audioinput'),
)
const toggleCam = toggleFactory('cam',
  async () => await rtc.enable('videoinput'),
  async () => await rtc.disable('videoinput'),
)
const toggleSpeakers = toggleFactory('speakers',
  async () => {
    rtc.setAudioSubscriptionsForAll(true)
    return true
  },
  async () => rtc.setAudioSubscriptionsForAll(false),
)
const toggleVisibility = toggleFactory('visibility',
  async () => {
    rtc.setVideoSubscriptionsForAll(true)
    return true
  },
  async () => rtc.setVideoSubscriptionsForAll(false),
)

const toggleScreen = async () => {
  if (pendingScreen.value) return
  pendingScreen.value = true
  try {
    if (!isMyScreen.value) {
      const resp = await sendAck('screen', { on: true })
      if (!resp || !resp.ok) {
        if (resp?.status === 409 && resp?.owner) screenOwnerId.value = String(resp.owner)
        else if (resp?.status === 403 && resp?.error === 'blocked') void alertDialog('Стрим запрещён администратором')
        else void alertDialog('Не удалось запустить трансляцию')
        return
      }
      const ok = await rtc.startScreenShare({ audio: true })
      if (ok) {
        screenOwnerId.value = localId.value
        return
      }
      if (!ok) {
        await sendAck('screen', { on: false, canceled: true })
        screenOwnerId.value = ''
        const reason = rtc.getLastScreenShareError?.()
        void alertDialog(reason === 'canceled' ? 'Трансляция отменена' : 'Ошибка публикации видеопотока')
      }
    } else {
      await rtc.stopScreenShare()
      setScreenOwner('')
      try { await sendAck('screen', { on: false, target: Number(localId.value) }) } catch {}
    }
  } finally { pendingScreen.value = false }
}

async function enableInitialMedia(): Promise<boolean> {
  const tasks: Promise<void>[] = []
  let failed = false
  if (camOn.value && !blockedSelf.value.cam) {
    tasks.push((async () => {
      const ok = await rtc.enable('videoinput')
      if (!ok) {
        failed = true
        camOn.value = false
        try { await publishState({ cam: false }) } catch {}
      }
    })())
  }
  if (micOn.value && !blockedSelf.value.mic) {
    tasks.push((async () => {
      const ok = await rtc.enable('audioinput')
      if (!ok) {
        failed = true
        micOn.value = false
        try { await publishState({ mic: false }) } catch {}
      }
    })())
  }
  if (tasks.length) { try { await Promise.all(tasks) } catch {} }
  return failed
}

async function onMediaGateClick() {
  needInitialMediaUnlock.value = false
  closePanels()
  try { await rtc.resumeAudio() } catch {}
  ensureBgmPlayback()
  await enableInitialMedia()
}

async function handleJoinFailure(j: any) {
  if (leaving.value) return
  if (j?.status === 403 && j?.error === 'private_room') {
    void alertDialog('Комната является приватной')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
  } else if (j?.status === 409 && j?.error === 'game_in_progress') {
    void alertDialog('В комнате идёт игра')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
  } else if (j?.status === 409 && j?.error === 'spectators_full') {
    void alertDialog('Лимит зрителей исчерпан')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
  } else {
    void alertDialog(j?.status === 404 ? 'Комната не найдена' : j?.status === 410 ? 'Комната закрыта' : j?.status === 409 ? 'Комната заполнена' : 'Ошибка входа в комнату')
    await router.replace('/')
  }
}

async function onLeave(goHome = true) {
  if (leaving.value) return
  leaving.value = true
  try {
    document.removeEventListener('click', onDocClick)
    document.removeEventListener('visibilitychange', onBackgroundMaybeLeave)
    window.removeEventListener('pagehide', onBackgroundMaybeLeave)
  } catch {}
  try {
    const s = socket.value
    socket.value = null
    if (s) {
      try { (s.io.opts as any).reconnection = false } catch {}
      try { s.removeAllListeners?.() } catch {}
      try { s.close() } catch {}
    }
    const disc = rtc.disconnect().catch(() => {})
    if (goHome) await router.replace('/')
    await disc
  } finally {
    leaving.value = false
  }
}

function onBackgroundMaybeLeave(e?: PageTransitionEvent) {
  if (!IS_MOBILE) return
  if (document.visibilityState === 'hidden' || (e && (e as any).persisted === true)) void onLeave()
}

function handleOffline() { netReconnecting.value = true }

function handleOnline() { if (netReconnecting.value) hardReload() }

watch(isCurrentSpeaker, async (now, was) => {
  if (now === was) return
  if (isSpectatorInGame.value) return
  try {
    if (now) { if (!micOn.value) await toggleMic() }
    else { if (micOn.value) await toggleMic() }
  } catch {}
})

watch(() => auth.isAuthed, (ok) => { if (!ok) { void onLeave() } })

watch(localId, (id, prev) => {
  if (!id || id === prev) return
  void enforceSpectatorPhaseVisibility(gamePhase.value)
})

onMounted(async () => {
  try {
    if (!auth.ready) { try { await auth.init() } catch {} }
    connectSocket()

    const j:any = await safeJoin()
    if (!j?.ok) {
      await handleJoinFailure(j)
      return
    }

    await rtc.refreshDevices()
    applyJoinAck(j)

    const bindLK = () => rtc.initRoom({
      onScreenShareEnded: async () => {
        if (isMyScreen.value) {
          screenOwnerId.value = ''
          try { await sendAck('screen', { on: false }) } catch {}
        }
      },
      onRemoteScreenShareEnded: (id: string) => {
        if (screenOwnerId.value === id) setScreenOwner('')
      },
      onDisconnected: async () => {
        if (leaving.value) return
        if (navigator.onLine) hardReload()
        else netReconnecting.value = true
      },
    })
    bindLK()

    await rtc.connect(ws_url, j.token, { autoSubscribe: false })
    rtc.setAudioSubscriptionsForAll(local.speakers)
    rtc.setVideoSubscriptionsForAll(local.visibility)
    const wantInitialCam = camOn.value && !blockedSelf.value.cam
    const wantInitialMic = micOn.value && !blockedSelf.value.mic
    if (wantInitialCam || wantInitialMic) {
      const failed = await enableInitialMedia()
      if (failed) needInitialMediaUnlock.value = true
    }

    const hasLsMirror = rtc.loadLS(rtc.LS.mirror)
    if (hasLsMirror == null) {
      rtc.saveLS(rtc.LS.mirror, '0')
      if (isMirrored(localId.value)) { void publishState({ mirror: false }) }
    } else {
      const want = hasLsMirror === '1'
      if (isMirrored(localId.value) !== want) { void publishState({ mirror: want }) }
    }

    document.addEventListener('click', onDocClick)
    document.addEventListener('visibilitychange', onBackgroundMaybeLeave, { passive: true })
    window.addEventListener('pagehide', onBackgroundMaybeLeave, { passive: true })
    window.addEventListener('offline', handleOffline)
    window.addEventListener('online', handleOnline)

    uiReady.value = true
  } catch (err) {
    rerr('room onMounted fatal', err)
    try { await rtc.disconnect() } catch {}
    if (!leaving.value) {
      void alertDialog('Ошибка входа в комнату')
      await router.replace('/')
    }
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('offline', handleOffline)
  window.removeEventListener('online', handleOnline)
  if (gameStartOverlayTimerId != null) window.clearTimeout(gameStartOverlayTimerId)
  if (gameEndOverlayTimerId != null) window.clearTimeout(gameEndOverlayTimerId)
  destroyBgm()
  void onLeave(false)
})
</script>

<style scoped lang="scss">
.room {
  display: flex;
  position: relative;
  flex-direction: column;
  padding: 10px;
  gap: 10px;
  overflow: hidden;
  .reconnect-overlay {
    display: flex;
    position: fixed;
    align-items: center;
    justify-content: center;
    inset: 0;
    backdrop-filter: blur(5px);
    background-color: rgba($black, 0.75);
    color: $fg;
    z-index: 1000;
    pointer-events: none;
    &.load-game {
      background-color: $black;
    }
    &.media-gate {
      pointer-events: auto;
      cursor: pointer;
    }
  }
  .grid {
    display: grid;
    width: calc(100vw - 20px);
    height: calc(100dvh - 70px);
    gap: 10px;
  }
  .theater {
    display: grid;
    grid-template-columns: 1fr 284px;
    width: calc(100vw - 20px);
    height: calc(100dvh - 70px);
    gap: 10px;
    .stage {
      position: relative;
      border: 5px solid $dark;
      border-radius: 5px;
      overflow: hidden;
      video {
        width: 100%;
        height: 100%;
        object-fit: contain;
        background-color: $black;
      }
      .volume {
        display: flex;
        position: absolute;
        align-items: center;
        justify-content: space-between;
        top: 5px;
        left: 5px;
        padding: 5px;
        gap: 5px;
        width: 20%;
        max-width: 200px;
        height: 20px;
        border-radius: 5px;
        background-color: rgba($dark, 0.75);
        backdrop-filter: blur(5px);
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
    .sidebar {
      display: flex;
      flex-direction: column;
      width: 284px;
      gap: 10px;
      overflow-y: auto;
      scrollbar-width: none;
      -ms-overflow-style: none;
    }
    .sidebar::-webkit-scrollbar {
      width: 0;
      height: 0;
    }
  }
  .panel {
    display: flex;
    position: relative;
    align-items: center;
    justify-content: space-between;
    width: calc(100vw - 20px);
    height: 40px;
    button {
      display: flex;
      position: relative;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 60px;
      height: 40px;
      border: none;
      border-radius: 5px;
      background-color: $dark;
      cursor: pointer;
      transition: background-color 0.25s ease-in-out;
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      &:hover {
        background-color: $graphite;
      }
      img {
        width: 30px;
        height: 30px;
      }
      .count-total {
        display: flex;
        align-items: center;
        justify-content: center;
        position: absolute;
        top: 5px;
        right: 7px;
        width: 17px;
        height: 17px;
        border-radius: 50%;
        background-color: $grey;
        color: $white;
        font-size: 12px;
        font-family: Manrope-Medium;
        line-height: 1;
        transition: background-color 0.25s ease-in-out;
        &.unread {
          background-color: $red;
        }
      }
    }
    .controls-side {
      display: flex;
      gap: 10px;
      min-width: 130px;
      &.left {
        justify-content: flex-start;
      }
      &.right {
        justify-content: flex-end;
      }
    }
    .btn-text {
      padding: 0 20px;
      width: fit-content;
      color: $fg;
      font-size: 16px;
      font-family: Manrope-Medium;
      line-height: 1;
    }
    .controls {
      display: flex;
      gap: 10px;
    }
  }
  .role-overlay {
    display: flex;
    position: fixed;
    align-items: center;
    justify-content: center;
    inset: 0;
    backdrop-filter: blur(5px);
    background-color: rgba($black, 0.75);
    z-index: 900;
    .role-overlay-inner {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      padding: 30px;
      gap: 50px;
      width: calc(100% - 60px);
      height: calc(100% - 60px);
      background-color: $dark;
      perspective: 1000px;
      .role-card {
        position: relative;
        padding: 0;
        border: none;
        border-radius: 5px;
        background: transparent;
        cursor: pointer;
        transition: transform 0.15s ease-in-out, opacity 0.25s ease-in-out;
        &.is-taken:not(.is-revealed) {
          pointer-events: none;
          .role-card-inner {
            visibility: hidden;
          }
        }
        &.is-revealed:disabled {
          opacity: 1;
          cursor: default;
        }
        &:hover:enabled:not(.is-revealed) {
          transform: scale(1.1);
        }
        &:disabled {
          opacity: 0.5;
          cursor: default;
        }
        .role-card-inner {
          position: relative;
          height: 100%;
          box-shadow: 3px 3px 5px rgba($black, 0.25);
          transform-style: preserve-3d;
          transition: transform 0.5s ease-in-out;
          .role-card-face {
            position: absolute;
            inset: 0;
            border-radius: 5px;
            backface-visibility: hidden;
            overflow: hidden;
            img {
              width: 100%;
              height: 100%;
              object-fit: cover;
            }
            &.back {
              transform: rotateY(0deg);
            }
            &.front {
              transform: rotateY(180deg);
            }
          }
        }
        &.is-revealed .role-card-inner {
          transform: rotateY(180deg);
        }
      }
    }
  }
  .role-preload {
    position: absolute;
    inset: 0;
    width: 0;
    height: 0;
    overflow: hidden;
    opacity: 0;
    pointer-events: none;
    img {
      width: 0;
      height: 0;
    }
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.role-overlay-fade-enter-active,
.role-overlay-fade-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}
.role-overlay-fade-enter-from,
.role-overlay-fade-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
.role-overlay-fade-enter-to,
.role-overlay-fade-leave-from {
  opacity: 1;
  transform: scale(1);
}

@media (max-width: 1280px) {
  .room {
    padding: 5px;
    gap: 5px;
    .grid {
      width: calc(100vw - 10px);
      height: calc(100dvh - 40px);
      gap: 3px;
    }
    .theater {
      width: calc(100vw - 10px);
      height: calc(100dvh - 40px);
      gap: 3px;
      .stage {
        .volume {
          top: 3px;
          left: 3px;
          padding: 3px 5px;
          gap: 3px;
          width: 30%;
          max-width: 200px;
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
      }
      .sidebar {
        gap: 5px;
      }
    }
    .panel {
      width: calc(100vw - 10px);
      height: 25px;
      button {
        width: 35px;
        height: 25px;
        img {
          width: 20px;
          height: 20px;
        }
        .count-total {
          top: 3px;
          right: 5px;
          width: 12px;
          height: 12px;
          font-size: 10px;
        }
      }
      .controls-side {
        min-width: 80px;
      }
      .btn-text {
        font-size: 12px;
      }
    }
    .role-overlay .role-overlay-inner {
      padding: 15px;
      gap: 25px;
      width: calc(100% - 30px);
      height: calc(100% - 30px);
    }
  }
}
</style>
