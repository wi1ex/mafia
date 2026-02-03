<template>
  <section class="room">
    <div v-if="isReconnecting" class="reconnect-overlay" aria-live="polite">Восстанавливаем соединение…</div>

    <div v-else-if="!uiReady" class="reconnect-overlay" aria-live="polite">Загрузка комнаты…</div>

    <template v-else>
      <Transition name="fade">
        <div v-if="gameOverlayVisible" class="reconnect-overlay load-game" aria-live="polite">{{ gameOverlayText }}</div>
      </Transition>
      <Transition name="host-blur">
        <div v-if="hostBlurVisible" class="host-blur-overlay" aria-hidden="true">Пауза…</div>
      </Transition>
      <div v-if="!isTheater" class="grid" :style="gridStyle">
        <RoomTile
          v-for="id in sortedPeerIds"
          :key="id"
          :style="tileGridStyle(id)"
          :id="id"
          :local-id="localId"
          :is-mobile="IS_MOBILE"
          :hotkeys-visible="hotkeysVisible"
          :speaking="(game.daySpeech.currentId === id) || (gamePhase === 'idle' && rtc.isSpeaking(id))"
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
          :finish-role-badge="gameFinished"
          :hidden-by-visibility="hiddenByVisibility(id)"
          :visibility-hidden-avatar="visOffAvatar(id)"
          :in-game="gamePhase !== 'idle'"
          :day-speech-owner-id="game.daySpeech.currentId"
          :day-speech-remaining-ms="game.daySpeech.remainingMs"
          :fouls-count="gameFoulsByUser.get(id) ?? 0"
          :winks-left="winksLeft"
          :knocks-left="knocksLeft"
          :show-wink="game.canWinkTarget(id)"
          :show-knock="game.canKnockTarget(id)"
          :phase-label="phaseLabel"
          :night-owner-id="headUserId"
          :night-remaining-ms="night.remainingMs"
          :show-shoot="game.canShootTarget(id)"
          :show-check="game.canCheckTarget(id)"
          :pick-number="canShowHeadPicks ? (headNightPicks.get(id) ?? null) : null"
          :pick-kind="canShowHeadPicks ? headPickKind : ''"
          :show-nominate="game.canNominateTarget(id)"
          :show-unnominate="game.canUnnominateTarget(id)"
          :best-move-marked="game.isBestMoveMarked(id)"
          :show-best-move-button="game.canMakeBestMoveChoice(id)"
          :farewell-summary="game.farewellSummaryForUser(id)"
          :show-farewell-buttons="game.canMakeFarewellChoice(id)"
          :nominees="nomineeSeatNumbers"
          :lift-nominees="id === headUserId && liftHighlightNominees ? nomineeSeatNumbers : []"
          :current-nominee-seat="id === headUserId ? currentNomineeSeat : null"
          :show-nominations-bar="id === headUserId && (gamePhase === 'day' || gamePhase === 'vote')"
          :vote-blocked="id === headUserId ? voteBlocked : false"
          :offline-seats-in-game="id === headUserId && gamePhase === 'vote' && !currentFarewellSpeech ? offlineAliveSeatNumbers : []"
          :show-vote-button="amIAlive && game.canPressVoteButton()"
          :vote-enabled="game.canPressVoteButton()"
          :has-voted="(isLiftVoting ? votedUsers : votedThisRound).has(id)"
          @toggle-panel="toggleTilePanel"
          @vol-input="onVol"
          @block="(key, uid) => toggleBlock(uid, key)"
          @kick="kickUser"
          @foul="onGiveFoul"
          @wink="onWink"
          @knock="openKnockModal"
          @nominate="onNominate"
          @unnominate="onUnnominate"
          @vote="onVote"
          @shoot="shootTargetUi"
          @check="checkTargetUi"
          @farewell="onFarewell"
          @best-move="onBestMove"
        />
      </div>

      <div v-else class="theater">
        <div class="stage">
          <video :ref="stableScreenRef(screenOwnerId)" playsinline autoplay muted />
          <div v-if="screenOwnerId !== localId && streamAudioKey" class="volume" @click.stop>
            <img :src="volumeIconForStream(streamAudioKey)" alt="vol" />
            <input type="range" min="0" max="200" step="5" :disabled="!speakersOn || isBlocked(screenOwnerId,'speakers')"
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
            :is-mobile="IS_MOBILE"
            :hotkeys-visible="hotkeysVisible"
            :side="true"
            :speaking="(game.daySpeech.currentId === id) || (gamePhase === 'idle' && rtc.isSpeaking(id))"
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
            :finish-role-badge="gameFinished"
            :hidden-by-visibility="hiddenByVisibility(id)"
            :visibility-hidden-avatar="visOffAvatar(id)"
            :in-game="gamePhase !== 'idle'"
            :day-speech-owner-id="game.daySpeech.currentId"
            :day-speech-remaining-ms="game.daySpeech.remainingMs"
            :fouls-count="gameFoulsByUser.get(id) ?? 0"
            :winks-left="winksLeft"
            :knocks-left="knocksLeft"
            :show-wink="game.canWinkTarget(id)"
            :show-knock="game.canKnockTarget(id)"
            :phase-label="phaseLabel"
            :night-owner-id="headUserId"
            :night-remaining-ms="night.remainingMs"
            :show-shoot="game.canShootTarget(id)"
            :show-check="game.canCheckTarget(id)"
            :pick-number="canShowHeadPicks ? (headNightPicks.get(id) ?? null) : null"
            :pick-kind="canShowHeadPicks ? headPickKind : ''"
            :show-nominate="game.canNominateTarget(id)"
            :show-unnominate="game.canUnnominateTarget(id)"
            :best-move-marked="game.isBestMoveMarked(id)"
            :show-best-move-button="game.canMakeBestMoveChoice(id)"
            :farewell-summary="game.farewellSummaryForUser(id)"
            :show-farewell-buttons="game.canMakeFarewellChoice(id)"
            :nominees="nomineeSeatNumbers"
            :lift-nominees="id === headUserId && liftHighlightNominees ? nomineeSeatNumbers : []"
            :current-nominee-seat="id === headUserId ? currentNomineeSeat : null"
            :show-nominations-bar="id === headUserId && (gamePhase === 'day' || gamePhase === 'vote')"
            :vote-blocked="id === headUserId ? voteBlocked : false"
            :offline-seats-in-game="id === headUserId && gamePhase === 'vote' && !currentFarewellSpeech ? offlineAliveSeatNumbers : []"
            :show-vote-button="amIAlive && game.canPressVoteButton()"
            :vote-enabled="game.canPressVoteButton()"
            :has-voted="(isLiftVoting ? votedUsers : votedThisRound).has(id)"
            @toggle-panel="toggleTilePanel"
            @vol-input="onVol"
            @block="(key, uid) => toggleBlock(uid, key)"
            @kick="kickUser"
            @foul="onGiveFoul"
            @wink="onWink"
            @knock="openKnockModal"
            @nominate="onNominate"
            @unnominate="onUnnominate"
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
          <button v-if="gamePhase !== 'idle' && isHead && !gameFinished" @click="endGameUi" :disabled="endingGame" aria-label="Завершить игру">
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
          <button v-if="canShowHeadGoToMafiaTalkControl" class="btn-text" :disabled="!canHeadGoToMafiaTalkControl" @click="goToMafiaTalkUi" aria-label="Перейти к договорке">Начать договорку</button>
          <button v-if="canHeadFinishMafiaTalkControl" class="btn-text" @click="finishMafiaTalkUi" aria-label="Завершить договорку">Завершить договорку</button>
          <button v-if="canShowStartDay" class="btn-text" :disabled="!canStartDay" @click="startDayUi" aria-label="Начать день">День</button>
          <button v-if="canShowFinishSpeechHead" class="btn-text" :disabled="hostBlurLocksControls || !canFinishSpeechHead" @click="finishSpeechUi" aria-label="Завершить речь">Завершить речь</button>
          <button v-else-if="canShowPassSpeechHead" class="btn-text" :disabled="hostBlurLocksControls || !canPassSpeechHead" @click="passSpeechUi" aria-label="Передать речь">Передать речь</button>
          <button v-if="canStartVote" class="btn-text" :disabled="hostBlurLocksControls" @click="startVoteUi">Начать голосование</button>
          <button v-if="canHeadVoteControl" class="btn-text" :disabled="hostBlurLocksControls || hasOfflineAlivePlayers || !canPressHeadVoteControl" @click="onHeadVoteControl">
            {{ !voteStartedForCurrent ? 'Голосование за ' + (currentNomineeSeat ?? '') : 'Продолжить' }}
          </button>
          <button v-if="canHeadFinishVoteControl" class="btn-text" :disabled="hostBlurLocksControls" @click="finishVoteUi">Завершить голосование</button>
          <button v-if="canPrepareVoteLift" class="btn-text" :disabled="hostBlurLocksControls || hasOfflineAlivePlayers" @click="prepareVoteLiftUi">Продолжить</button>
          <button v-if="canStartVoteLift" class="btn-text" :disabled="hostBlurLocksControls || hasOfflineAlivePlayers" @click="startVoteLiftUi">Голосование за подъём</button>
          <button v-if="canShowStartLeaderSpeech" class="btn-text" :disabled="hostBlurLocksControls || !canStartLeaderSpeech" @click="startLeaderSpeechUi">Передать речь</button>
          <button v-if="canRestartVoteForLeaders" class="btn-text" :disabled="hostBlurLocksControls" @click="restartVoteForLeadersUi">Начать голосование</button>
          <button v-if="canShowNight" class="btn-text" :disabled="hostBlurLocksControls || hasOfflineAlivePlayers" @click="goToNightUi">Ночь</button>
          <button v-if="canHeadNightShootControl" class="btn-text" :disabled="hasOfflineAlivePlayers" @click="startNightShootUi">Стрельба</button>
          <button v-if="canHeadNightCheckControl" class="btn-text" :disabled="hasOfflineAlivePlayers" @click="startNightChecksUi">Проверки</button>
          <button v-if="canHeadBestMoveControl" class="btn-text" @click="startBestMoveUi">Лучший ход {{ bestMoveSeat ?? '?' }}</button>
          <button v-if="canStartDayFromNight" class="btn-text" :disabled="!canHeadDayFromNightControl" @click="startDayFromNightUi">День</button>

          <button v-if="canFinishSpeechSelf" class="btn-text" @click="finishSpeechUi">Завершить речь</button>
          <button v-else-if="canShowTakeFoulSelf" class="btn-text" @click="takeFoulUi" :disabled="!canTakeFoulSelf || foulPending">
            Взять фол
            <span v-if="!IS_MOBILE && hotkeysVisible" class="hot-btn">↩</span>
          </button>

          <button v-if="gamePhase === 'idle' && canShowStartGame && canUseReadyStart" @click="startGameUi" :disabled="startingGame" aria-label="Запустить игру">
            <img :src="iconGameStart" alt="start" />
              <span v-if="!IS_MOBILE && hotkeysVisible" class="hot-btn">G</span>
          </button>
          <button v-if="gamePhase === 'idle' && !canShowStartGame && canUseReadyToggle" @click="toggleReady" :aria-pressed="readyOn" aria-label="Готовность">
            <img :src="readyOn ? iconReadyGreen : iconReadyWhite" alt="ready" />
              <span v-if="!IS_MOBILE && hotkeysVisible" class="hot-btn">G</span>
          </button>
          <button v-if="gamePhase === 'idle' || isHead" @click="toggleMic" :disabled="pending.mic || blockedSelf.mic" :aria-pressed="micOn">
            <img :src="stateIcon('mic', localId)" alt="mic" />
              <span v-if="!IS_MOBILE && hotkeysVisible" class="hot-btn">M</span>
          </button>
          <button v-if="gamePhase === 'idle' || isHead" @click="toggleCam" :disabled="pending.cam || blockedSelf.cam" :aria-pressed="camOn">
            <img :src="stateIcon('cam', localId)" alt="cam" />
              <span v-if="!IS_MOBILE && hotkeysVisible" class="hot-btn">C</span>
          </button>
          <button v-if="gamePhase !== 'idle' && isHead" @click="toggleHostBlur" :disabled="!hostBlurToggleEnabled || hostBlurPending" :aria-pressed="hostBlurActive" aria-label="Затемнить экран">
            <img :src="hostBlurActive ? iconBlurOn : iconBlurOff" alt="blur" />
          </button>
          <button v-if="gamePhase === 'idle'" @click="toggleSpeakers" :disabled="pending.speakers || blockedSelf.speakers" :aria-pressed="speakersOn">
            <img :src="stateIcon('speakers', localId)" alt="speakers" />
              <span v-if="!IS_MOBILE && hotkeysVisible" class="hot-btn">S</span>
          </button>
          <button v-if="gamePhase === 'idle' && !IS_MOBILE && settings.streamsCanStart" @click="toggleScreen" :disabled="pendingScreen || (!!screenOwnerId && screenOwnerId !== localId) || blockedSelf.screen" :aria-pressed="isMyScreen">
            <img :src="stateIcon('screen', localId)" alt="screen" />
          </button>
        </div>

        <div class="controls-side right">
          <button v-if="canEditGame" @click.stop="openGameSettings" aria-label="Параметры игры">
            <img :src="iconParams" alt="game-settings" />
          </button>
          <button v-if="myRole === 'host' && isPrivate && gamePhase === 'idle'" @click.stop="toggleApps" :aria-expanded="openApps" aria-label="Заявки">
            <img :src="iconRequestsRoom" alt="requests" />
            <span class="count-total" :class="{ unread: appsCounts.unread > 0 }">{{ appsCounts.total < 100 ? appsCounts.total : '∞' }}</span>
          </button>
          <button v-if="canShowSettingsButton" @click.stop="toggleSettings" :aria-expanded="settingsOpen" aria-label="Настройки устройств">
            <img :src="iconSettings" alt="settings" />
          </button>
        </div>

        <RoomRequests
          v-if="myRole === 'host' && isPrivate && gamePhase === 'idle'"
          v-model:open="openApps"
          :room-id="rid"
          @counts="(p) => { appsCounts.total = p.total; appsCounts.unread = p.unread }"
        />

        <GameParamsModal
          v-model:open="gameParamsOpen"
          :room-id="rid"
        />

        <RoomSetting
          :open="settingsOpen && canShowSettingsButton"
          :in-game="gamePhase !== 'idle'"
          :is-spectator="isSpectatorInGame"
          :is-mobile="IS_MOBILE"
          :hotkeys-visible="hotkeysVisible"
          :mics="mics"
          :cams="cams"
          v-model:micId="selectedMicId"
          v-model:camId="selectedCamId"
          v-model:mirrorOn="mirrorOn"
          v-model:volume="bgmVolume"
          :volume-icon="volumeIcon(bgmVolume, bgmShouldPlay)"
          :music-enabled="musicEnabled"
          :can-toggle-known-roles="canToggleKnownRoles"
          :known-roles-visible="knownRolesVisible"
          @device-change="(kind) => rtc.onDeviceChange(kind)"
          @toggle-known-roles="toggleKnownRolesUi"
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

      <Transition name="knock-modal">
        <div v-if="knockModalOpen" class="knock-overlay" role="dialog" aria-modal="true"
             @pointerdown.self="knockModalArmed = true" @pointerup.self="knockModalArmed && closeKnockModal()"
             @pointerleave.self="knockModalArmed = false" @pointercancel.self="knockModalArmed = false">
          <div class="knock-modal" @click.stop>
            <span>Какое число хотите отстучать?</span>
            <div class="knock-grid">
              <button v-for="n in knockOptions" :key="n" type="button" @click="selectKnockCount(n)" :disabled="knockSending">{{ n }}</button>
            </div>
          </div>
        </div>
      </Transition>

      <div v-if="mediaGateVisible" class="reconnect-overlay media-gate" @click.stop.prevent="onMediaGateClick"
           @touchstart.stop.prevent="onMediaGateClick" @pointerdown.stop.prevent="onMediaGateClick">Нажмите чтобы продолжить…</div>
    </template>
    <div class="role-preload" aria-hidden="true">
      <img v-for="src in ROLE_CARD_IMAGES" :key="src" :src="src" alt="" loading="eager" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import type { Socket } from 'socket.io-client'
import { useAuthStore, useSettingsStore, useUserStore } from '@/store'
import {
  type Ack,
  type FarewellVerdict,
  type GamePhase,
  type GameRoleKind,
  type SendAckFn,
  useRoomGame
} from '@/composables/roomGame'
import { type CameraQuality, useRTC, type VQ } from '@/composables/rtc'
import { api } from '@/services/axios'
import { alertDialog, confirmDialog, useConfirmState } from '@/services/confirm'
import { createAuthedSocket } from '@/services/sio'
import RoomTile from '@/components/RoomTile.vue'
import RoomSetting from '@/components/RoomSetting.vue'
import RoomRequests from '@/components/RoomRequests.vue'
import GameParamsModal from '@/components/GameParamsModal.vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconVolumeMax from '@/assets/svg/volumeMax.svg'
import iconVolumeMid from '@/assets/svg/volumeMid.svg'
import iconVolumeLow from '@/assets/svg/volumeLow.svg'
import iconVolumeMute from '@/assets/svg/volumeMute.svg'
import gongAudioUrl from '@/assets/audio/gong.mp3'

import iconLeaveRoom from '@/assets/svg/leave.svg'
import iconSettings from '@/assets/svg/settings.svg'
import iconRequestsRoom from '@/assets/svg/requestsRoom.svg'
import iconReadyWhite from '@/assets/svg/readyWhite.svg'
import iconReadyGreen from '@/assets/svg/readyGreen.svg'
import iconParams from '@/assets/svg/params.svg'
import iconBlurOn from '@/assets/svg/blurOn.svg'
import iconBlurOff from '@/assets/svg/blurOff.svg'
import iconGameStart from '@/assets/svg/gameStart.svg'
import iconGameStop from '@/assets/svg/gameStop.svg'
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
const settings = useSettingsStore()
const userStore = useUserStore()
const confirmState = useConfirmState()
const { hotkeysVisible } = storeToRefs(userStore)

const rtc = useRTC()
const { localId, mics, cams, selectedMicId, selectedCamId, peerIds } = rtc      
const bgmVolume = rtc.bgmVolume

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
  hostBlurActive,
  musicEnabled,
  night,
  headNightPicks,
  headUserId,
  offlineAliveSeatNumbers,
  hasOfflineAlivePlayers,
  headPickKind,
  phaseLabel,
  gameFinished,
  currentFarewellSpeech,
  isCurrentSpeaker,
  winksLeft,
  knocksLeft,
  playerSeatCount,
  canShowStartDay,
  canStartDay,
  canShowFinishSpeechHead,
  canFinishSpeechHead,
  canShowPassSpeechHead,
  canPassSpeechHead,
  canFinishSpeechSelf,
  canShowTakeFoulSelf,
  canTakeFoulSelf,
  canStartVote,
  canHeadVoteControl,
  canPressHeadVoteControl,
  canPrepareVoteLift,
  canStartVoteLift,
  isLiftVoting,
  liftHighlightNominees,
  canShowHeadGoToMafiaTalkControl,
  canHeadGoToMafiaTalkControl,
  canHeadFinishMafiaTalkControl,
  canHeadFinishVoteControl,
  canHeadNightShootControl,
  canHeadNightCheckControl,
  canHeadBestMoveControl,
  canHeadDayFromNightControl,
  canStartDayFromNight,
  bestMoveSeat,
  canShowStartLeaderSpeech,
  canStartLeaderSpeech,
  canRestartVoteForLeaders,
  canShowNight,
} = game

const navUserAgent = navigator.userAgent || ''
const IS_MOBILE = (navigator as any).userAgentData?.mobile === true || /Android|iPhone|iPad|iPod|Mobile/i.test(navUserAgent)
  || (window.matchMedia?.('(pointer: coarse)').matches && /Android|iPhone|iPad|iPod|Mobile|Tablet|Touch/i.test(navUserAgent))

const local = reactive({ mic: false, cam: false, speakers: true, visibility: true })
const desiredMedia = reactive({ mic: false, cam: false })
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
const MIN_GAME_VOLUME = 20
const volumeSnapTimers = new Map<string, number>()
const screenOwnerId = ref<string>('')
const openPanelFor = ref<string>('')
const pendingScreen = ref(false)
const settingsOpen = ref(false)
const gameParamsOpen = ref(false)
const uiReady = ref(false)
const leaving = ref(false)
const netReconnecting = ref(false)
const backgrounded = ref(false)
let joinPhaseApplyPending = false
const lkReconnecting = computed(() => rtc.reconnecting.value)
const isReconnecting = computed(() => netReconnecting.value || lkReconnecting.value)
const openApps = ref(false)
const appsCounts = reactive({ total: 0, unread: 0 })
const isPrivate = ref(false)
const roomUserLimit = ref<number>(0)
const gameLimitMin = computed(() => {
  const minReady = Number(settings.gameMinReadyPlayers)
  return Number.isFinite(minReady) && minReady > 0 ? minReady + 1 : 11
})
const ws_url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
const isTheater = computed(() => !!screenOwnerId.value)
const isMyScreen = computed(() => !!localId.value && screenOwnerId.value === localId.value)
const streamAudioKey = computed(() => screenOwnerId.value ? rtc.screenKey(screenOwnerId.value) : '')
const streamVol = computed(() => streamAudioKey.value ? (volUi[streamAudioKey.value] ?? rtc.getUserVolume(streamAudioKey.value)) : 100)
const fitContainInGrid = computed(() => {
  if (isTheater.value) return false
  const count = sortedPeerIds.value.length
  if (count >= 3) return false
  const limit = roomUserLimit.value
  return Number.isFinite(limit) && limit === 2
})
const isSpectatorInGame = computed(() => {
  const id = localId.value
  if (!id || gamePhase.value === 'idle') return false
  return !seatsByUser[id]
})
const hostBlurPending = ref(false)
const hostBlurToggleEnabled = computed(() => gamePhase.value === 'day' || gamePhase.value === 'vote')
const hostBlurVisible = computed(() => gamePhase.value !== 'idle' && hostBlurActive.value && !isHead.value)
const hostBlurLocksControls = computed(() => isHead.value && hostBlurActive.value)
const canEditGame = computed(() =>
  myRole.value === 'host' &&
  gamePhase.value === 'idle' &&
  roomUserLimit.value === gameLimitMin.value
)
const canShowSettingsButton = computed(() => !isSpectatorInGame.value || musicEnabled.value)
const knockModalOpen = ref(false)
const knockModalTargetId = ref<string>('')
const knockModalArmed = ref(false)
const knockSending = ref(false)
const knockOptions = computed(() => {
  const total = Number(playerSeatCount.value)
  if (!Number.isFinite(total) || total <= 0) return []
  return Array.from({ length: total }, (_, i) => i + 1)
})

const gameStartOverlayVisible = ref(false)
const gameEndOverlayVisible = ref(false)
const gameOverlayVisible = computed(() => gameStartOverlayVisible.value || gameEndOverlayVisible.value)
const gameOverlayText = computed(() => gameEndOverlayVisible.value ? 'Завершение игры…' : 'Запуск игры…')
let gameStartOverlayTimerId: number | null = null
let gameEndOverlayTimerId: number | null = null
let bgRestorePending = false
let backgroundedPhase: GamePhase | null = null
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

function closeKnockModal() {
  knockModalOpen.value = false
  knockModalTargetId.value = ''
  knockModalArmed.value = false
}

function openKnockModal(targetId: string) {
  if (!game.canKnockTarget(targetId)) return
  knockModalTargetId.value = targetId
  knockModalOpen.value = true
  knockModalArmed.value = false
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
const canUseReadyStart = computed(() => {
  const limit = roomUserLimit.value
  const min = minReadyToStart.value
  if (!Number.isFinite(limit) || !Number.isFinite(min)) return false
  if (limit <= 0 || min <= 0) return false
  return limit === min + 1
})
const canUseReadyToggle = computed(() => canUseReadyStart.value)
const canShowHeadPicks = computed(() => isHead.value && knownRolesVisible.value)
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

const desiredCameraQuality = computed<CameraQuality>(() => {
  if (roomUserLimit.value === 2 && !screenOwnerId.value) return 'high'
  return 'low'
})

const autoRemoteQuality = computed<VQ>(() => (desiredCameraQuality.value === 'low' ? 'sd' : 'hd'))

watch(desiredCameraQuality, (quality) => {
  void rtc.setCameraQuality(quality)
}, { immediate: true })

watch(autoRemoteQuality, (quality) => {
  rtc.setRemoteQualityForAll(quality, { persist: false })
}, { immediate: true })

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
function closePanels(except?: 'card'|'apps'|'settings'|'game') {
  if (except !== 'card') openPanelFor.value = ''
  if (except !== 'apps') openApps.value = false
  if (except !== 'settings') settingsOpen.value = false
  if (except !== 'game') gameParamsOpen.value = false
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
function openGameSettings() {
  const next = !gameParamsOpen.value
  closePanels('game')
  gameParamsOpen.value = next
}
function onDocClick() {
  closePanels()
  void rtc.resumeAudio()
  void rtc.unlockBgmOnGesture()
  void rtc.ensureBgmPlayback()
}
function isEditableTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  if (!el) return false
  const tag = el.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true
  return el.isContentEditable
}
function onHotkey(e: KeyboardEvent) {
  if (e.defaultPrevented || e.repeat) return
  if (isEditableTarget(e.target)) return
  if (confirmState.open) return
  if (e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return
  if (hostBlurActive.value) return
  if (gamePhase.value !== 'idle' && !(isHead.value || amIAlive.value)) return
  const code = e.code

  if (code === 'Enter' || code === 'NumpadEnter') {
    if (gamePhase.value !== 'idle' && canShowTakeFoulSelf.value && canTakeFoulSelf.value && !foulPending.value) {
      e.preventDefault()
      e.stopPropagation()
      void takeFoulUi()
    }
    return
  }
  if (code === 'Space') {
    if (gamePhase.value !== 'idle' && game.canPressVoteButton()) {
      e.preventDefault()
      e.stopPropagation()
      onVote()
    }
    return
  }
  if (code === 'KeyR') {
    if (gamePhase.value !== 'idle' && canToggleKnownRoles.value) {
      e.preventDefault()
      e.stopPropagation()
      toggleKnownRolesUi()
    }
    return
  }

  if (code === 'KeyC') {
    if ((gamePhase.value === 'idle' || isHead.value) && !pending.cam && !blockedSelf.value.cam) {
      e.preventDefault()
      e.stopPropagation()
      void toggleCam()
    }
    return
  }
  if (code === 'KeyM') {
    if ((gamePhase.value === 'idle' || isHead.value) && !pending.mic && !blockedSelf.value.mic) {
      e.preventDefault()
      e.stopPropagation()
      void toggleMic()
    }
    return
  }

  if (gamePhase.value !== 'idle') return

  if (code === 'KeyS') {
    if (!pending.speakers && !blockedSelf.value.speakers) {
      e.preventDefault()
      e.stopPropagation()
      void toggleSpeakers()
    }
    return
  }
  if (code === 'KeyG') {
    if (canShowStartGame.value && canUseReadyStart.value && !startingGame.value) {
      e.preventDefault()
      e.stopPropagation()
      startGameUi()
      return
    }
    if (!canShowStartGame.value && canUseReadyToggle.value) {
      e.preventDefault()
      e.stopPropagation()
      void toggleReady()
    }
  }
}

function toggleKnownRolesUi(): void {
  if (!canToggleKnownRoles.value) return
  game.toggleKnownRolesVisibility()
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

const BGM_ACTIVE_PHASES: GamePhase[] = ['roles_pick', 'mafia_talk_start', 'mafia_talk_end', 'night']
const bgmShouldPlay = computed(() => musicEnabled.value && BGM_ACTIVE_PHASES.includes(gamePhase.value))

watch(bgmShouldPlay, (on) => {
  rtc.setBgmPlaying(on)
}, { immediate: true })

const canKeepKnockModal = computed(() => {
  if (!knockModalOpen.value) return false
  const targetId = knockModalTargetId.value
  if (!targetId) return false
  return game.canKnockTarget(targetId)
})

watch(canKeepKnockModal, (ok) => {
  if (!ok && knockModalOpen.value) closeKnockModal()
})

const speechGongAudio = new Audio(gongAudioUrl)
speechGongAudio.preload = 'auto'

function playSpeechGong(): void {
  try { speechGongAudio.currentTime = 0 } catch {}
  const res = speechGongAudio.play()
  if (res && typeof res.catch === 'function') res.catch(() => {})
}

async function sendAck(event: string, payload: any, timeoutMs = 15000): Promise<Ack> {
  const s = socket.value
  if (!s) return null
  try {
    return await s.timeout(timeoutMs).emitWithAck(event, payload)
  } catch (e:any) {
    rerr('ack fail', { event, payload, name: e?.name, message: e?.message })
    return null
  }
}

async function stopScreenBeforeLeave() {
  if (!isMyScreen.value) return
  const target = Number(localId.value)
  if (!Number.isFinite(target)) return
  const s = socket.value
  if (!s) return
  try {
    const resp = await s.timeout(1500).emitWithAck('screen', { on: false, target })
    if (resp?.ok) return
  } catch {}
  try { s.emit('screen', { on: false, target }) } catch {}
}

function ensureOk(resp: Ack, msgByCode: Record<number, string>, netMsg: string): boolean {
  if (resp && resp.ok) return true
  const code = resp?.status
  void alertDialog((code && msgByCode[code]) || netMsg)
  return false
}

const sendAckGame: SendAckFn = (event, payload, timeoutMs) => sendAck(event, payload, timeoutMs)
const startGameUi = async () => {
  if (!canUseReadyStart.value) return
  if (!(await ensureGameParticipationAllowed())) return
  await game.startGame(sendAckGame)
}
const endGameUi = () => game.endGame(sendAckGame)
const leaveGameUi = () => game.leaveGame(sendAckGame)
const pickRoleCardUi = (card: number) => game.pickRoleCard(card, sendAckGame)
const goToMafiaTalkUi = () => game.goToMafiaTalk(sendAckGame)
const finishMafiaTalkUi = () => game.finishMafiaTalk(sendAckGame)
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
const goToNightUi = () => game.goToNight(sendAckGame)
const onHeadVoteControl = () => game.headVoteControl(sendAckGame)
const onGiveFoul = (targetId: string) => game.giveFoul(targetId, sendAckGame)
const startBestMoveUi = () => game.startBestMove(sendAckGame)
const startDayFromNightUi = () => game.startDayFromNight(sendAckGame)
const startDayUi = () => game.startDay(sendAckGame)
const onWink = async (targetId: string) => {
  const ok = await confirmDialog({
    title: 'Подмигивание',
    text: 'Вы хотите подмигнуть игроку?',
    confirmText: 'Подмигнуть',
    cancelText: 'Отмена',
  })
  if (!ok) return
  void game.winkTarget(targetId, sendAckGame)
}

async function selectKnockCount(count: number) {
  if (knockSending.value) return
  const targetId = knockModalTargetId.value
  if (!targetId) return
  knockSending.value = true
  try {
    const ok = await game.knockTarget(targetId, count, sendAckGame)
    if (ok) closeKnockModal()
  } finally {
    knockSending.value = false
  }
}

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

const wantsAudioRequest = computed(() => desiredMedia.mic || (desiredMedia.cam && rtc.hasAudioInput.value))
const wantsVideoRequest = computed(() => desiredMedia.cam || (desiredMedia.mic && rtc.hasVideoInput.value))
const needsMediaAccess = computed(() => wantsAudioRequest.value || wantsVideoRequest.value)
const showPermProbe = computed(() => {
  if (isSpectatorInGame.value) return false
  if (!needsMediaAccess.value) return false
  const needAudio = wantsAudioRequest.value && (!rtc.hasAudioInput.value || !rtc.permAudio.value)
  const needVideo = wantsVideoRequest.value && (!rtc.hasVideoInput.value || !rtc.permVideo.value)
  return needAudio || needVideo
})

async function requestMediaPermissions(opts?: { force?: boolean }) {
  if (isSpectatorInGame.value) return
  if (!needsMediaAccess.value) return
  const audio = wantsAudioRequest.value
  const video = wantsVideoRequest.value
  if (!audio && !video) return
  if (!opts?.force && !showPermProbe.value) return
  if (opts?.force) {
    await rtc.probePermissions({ audio, video })
    return
  }
  const needAny = (audio && !rtc.permAudio.value) || (video && !rtc.permVideo.value)
  if (needAny) {
    const ok = await rtc.probePermissions({ audio: true, video: true })
    if (ok) return
  }
  await rtc.probePermissions({ audio, video })
}
async function onProbeClick() {
  if (isSpectatorInGame.value) return
  try { await rtc.resumeAudio({ force: true }) } catch {}
  await rtc.unlockBgmOnGesture()
  await requestMediaPermissions()
  await enableInitialMedia()
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
  const limit = roomUserLimit.value
  const isTwoSeatRoom = Number.isFinite(limit) && limit === 2
  const count = sortedPeerIds.value.length
  const cols = count <= 2 ? (isTwoSeatRoom ? 2 : 3) : count <= 6 ? 3 : 4
  const rows = count <= 2 ? (isTwoSeatRoom ? 1 : 2) : count <= 6 ? 2 : 3
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

function clearVolumeSnap(id: string): void {
  const tm = volumeSnapTimers.get(id)
  if (tm != null) {
    window.clearTimeout(tm)
    volumeSnapTimers.delete(id)
  }
}

function scheduleVolumeSnap(id: string, value: number): void {
  clearVolumeSnap(id)
  const tm = window.setTimeout(() => {
    volUi[id] = value
    volumeSnapTimers.delete(id)
  }, 250)
  volumeSnapTimers.set(id, tm)
}

function onVol(id: string, v: number) {
  const next = enforceMinVolume(id, v)
  const clamped = next !== v
  if (clamped) {
    volUi[id] = v
    scheduleVolumeSnap(id, next)
  } else {
    clearVolumeSnap(id)
    volUi[id] = next
  }
  rtc.setUserVolume(id, next)
  void rtc.resumeAudio()
}

function shouldEnforceMinVolume(id: string): boolean {
  if (gamePhase.value === 'idle') return false
  if (!id || id === localId.value) return false
  if (rtc.isScreenKey(id)) return false
  if (myGameRole.value === 'none') return false
  const seat = seatsByUser[id]
  if (!seat || seat <= 0) return false
  if (myGameRole.value === 'head') return seat !== 11
  return true
}

function enforceMinVolume(id: string, v: number): number {
  if (!shouldEnforceMinVolume(id)) return v
  return v < MIN_GAME_VOLUME ? MIN_GAME_VOLUME : v
}

function enforceMinGameVolumes(): void {
  if (gamePhase.value === 'idle') return
  if (myGameRole.value === 'none') return
  let changed = false
  for (const [uid, seat] of Object.entries(seatsByUser)) {
    if (!uid || uid === localId.value) continue
    if (!seat || seat <= 0) continue
    if (myGameRole.value === 'head' && seat === 11) continue
    const current = volUi[uid] ?? rtc.getUserVolume(uid)
    if (current < MIN_GAME_VOLUME) {
      clearVolumeSnap(uid)
      volUi[uid] = MIN_GAME_VOLUME
      rtc.setUserVolume(uid, MIN_GAME_VOLUME)
      changed = true
    }
  }
  if (changed) void rtc.resumeAudio()
}

function rol(id: string): string { return rolesByUser.get(id) || 'user' }
const myRole = computed(() => rol(localId.value))

function onNominate(targetId: string) {
  game.nominateTarget(targetId, sendAck)
}

function onUnnominate(targetId: string) {
  game.unnominateTarget(targetId, sendAck)
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
const hasRemotePeers = computed(() => {
  const lid = localId.value
  if (!lid) return false
  return rtc.peerIds.value.some(id => id !== lid)
})
const audioGateNeeded = computed(() => {
  if (rtc.autoplayUnlocked.value) return false
  if (!speakersOn.value || blockedSelf.value.speakers) return false
  return hasRemotePeers.value
})
const mediaGateVisible = computed(() => uiReady.value && !isReconnecting.value && audioGateNeeded.value)

const readyOn = computed({
  get: () => (statusByUser.get(localId.value)?.ready ?? 0) === 1,
  set: (v: boolean) => {
    const cur = statusByUser.get(localId.value) ?? { mic: 1, cam: 1, speakers: 1, visibility: 1, ready: 0 }
    statusByUser.set(localId.value, { ...cur, ready: v ? 1 : 0 })
  }
})
const isReady = (id: string) => (statusByUser.get(id)?.ready ?? 0) === 1

async function ensureGameParticipationAllowed(): Promise<boolean> {
  if (userStore.suspendActive) {
    void alertDialog('Вам временно запрещено участие в играх')
    return false
  }
  if (!settings.verificationRestrictions) return true
  if (!userStore.telegramVerified) {
    const ok = await confirmDialog({
      title: 'Требуется верификация',
      text: 'Для участия в играх необходимо пройти верификацию.',
      confirmText: 'Пройти верификацию',
      cancelText: 'Позже',
    })
    if (ok) await router.push({ name: 'profile', query: { tab: 'account' } })
    return false
  }
  return true
}

async function ensureVerifiedForMedia(): Promise<boolean> {
  if (!settings.verificationRestrictions) return true
  if (userStore.telegramVerified) return true
  const ok = await confirmDialog({
    title: 'Требуется верификация',
    text: 'Для включения камеры и трансляций необходимо пройти верификацию.',
    confirmText: 'Пройти верификацию',
    cancelText: 'Позже',
  })
  if (ok) await router.push({ name: 'profile', query: { tab: 'account' } })
  return false
}

async function toggleReady() {
  if (!canUseReadyToggle.value) return
  if (!(await ensureGameParticipationAllowed())) return
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
  if (!isEmpty(pref?.mic)) {
    const next = norm01(pref.mic, local.mic ? 1 : 0) === 1
    local.mic = next
    desiredMedia.mic = next
  }
  if (!isEmpty(pref?.cam)) {
    const next = norm01(pref.cam, local.cam ? 1 : 0) === 1
    local.cam = next
    desiredMedia.cam = next
  }
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
  clearVolumeSnap(id)
  clearVolumeSnap(rtc.screenKey(id))
  delete volUi[id]
  delete volUi[rtc.screenKey(id)]
  if (screenOwnerId.value === id) screenOwnerId.value = ''
}

function clearScreenVolume(id: string | null | undefined) {
  if (!id) return
  clearVolumeSnap(rtc.screenKey(id))
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
      await handleJoinFailure(ack)
      return
    }
    if (uiReady.value) applyJoinAck(ack)
    if (bgRestorePending) void restoreAfterBackgroundFromServer()
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
      positionByUser.delete(id)
      game.maybeAskRevoteOnDisconnect(id, sendAckGame)
      offlineInGame.add(id)
      rtc.cleanupPeer(id, { keepVideo: true, keepScreen: true })
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
        desiredMedia.cam = false
        try { await rtc.disable('videoinput') } catch {}
      }
      if ('mic' in blocks && norm01(blocks.mic, 0) === 1) {
        local.mic = false
        desiredMedia.mic = false
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

  socket.value.on('force_leave', async (p:any) => {
    const reason = String(p?.reason || '')
    try { await onLeave() } catch {}
    if (reason === 'admin_kick_all') {
      void alertDialog('Упс! Кажется пришло обновление... через 5 минут все заработает!')
    } else if (reason === 'room_kick') {
      void alertDialog('Вас выгнали из комнаты')
    } else if (reason === 'room_deleted') {
      void alertDialog('Комната была удалена администратором')
    }
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
    if (musicEnabled.value) {
      rtc.setBgmSeed(p?.bgm_seed, rid)
    } else {
      rtc.setBgmPlaying(false)
    }
    statusByUser.forEach((st, uid) => {
      statusByUser.set(uid, { ...st, ready: 0 as 0 })
    })
    enforceMinGameVolumes()
    void enforceInitialGameControls()
  })

  socket.value?.on('game_finished', (p: any) => {
    game.handleGameFinished(p)
    if (myGameRole.value === 'player') void restoreAfterGameEnd()
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
    if (roleBeforeEnd === 'player') void restoreAfterGameEnd()
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
    if (musicEnabled.value && p?.bgm_seed != null && to === 'night') {
      rtc.setBgmSeed(p.bgm_seed, rid)
    } else if (!musicEnabled.value && to === 'night') {
      rtc.setBgmPlaying(false)
    }
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

  socket.value.on('game_winked', (p: any) => {
    const seat = Number(p?.from_seat || 0)
    if (seat > 0) {
      void alertDialog(`${seat}й игрок подмигнул`)
    } else {
      void alertDialog('Игрок подмигнул Вам')
    }
  })

  socket.value.on('game_knocked', (p: any) => {
    const seat = Number(p?.from_seat || 0)
    const count = Number(p?.count || 0)
    if (seat > 0 && count > 0) {
      void alertDialog(`${seat}й игрок отстучал ${count}`)
    } else if (seat > 0) {
      void alertDialog(`${seat}й игрок отстучал`)
    } else {
      void alertDialog('Игрок отстучал вам')
    }
  })

  socket.value.on('game_nominee_added', (p: any) => {
    game.handleGameNomineeAdded(p)
  })
  socket.value.on('game_nominee_removed', (p: any) => {
    game.handleGameNomineeRemoved(p)
  })

  socket.value.on('game_farewell_update', (p: any) => {
    game.handleGameFarewellUpdate(p)
  })

  socket.value.on('game_best_move_update', (p: any) => {
    game.handleGameBestMoveUpdate(p)
    if ((p as any)?.best_move?.active) rtc.setBgmPlaying(false)
  })

  socket.value.on('game_host_blur', (p: any) => {
    game.handleGameHostBlur(p)
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
  if (backgrounded.value) return
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

async function enforceNoPublishWhenInactive(): Promise<void> {
  if (gamePhase.value === 'idle') return
  if (amIAlive.value) return
  if (!localId.value) return
  const isSpectator = isSpectatorInGame.value
  let changed = false
  if (local.mic) {
    local.mic = false
    desiredMedia.mic = false
    changed = true
    try { await rtc.disable('audioinput') } catch {}
  }
  if (local.cam) {
    local.cam = false
    desiredMedia.cam = false
    changed = true
    try { await rtc.disable('videoinput') } catch {}
  }
  if (isSpectator && screenOwnerId.value === localId.value) {
    try { await rtc.stopScreenShare() } catch {}
    screenOwnerId.value = ''
    try { await sendAck('screen', { on: false }) } catch {}
  }
  if (changed) {
    try { await publishState({ mic: false, cam: false }) } catch {}
  }
}

async function enforceReturnStateAfterJoin() {
  if (gamePhase.value === 'idle') return
  if (!localId.value) {
    joinPhaseApplyPending = true
    return
  }
  await applyGameReturnState()
}

async function restoreAfterGameEnd() {
  if (backgrounded.value) return
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
  if (backgrounded.value) return
  if (prev === 'idle' && next !== 'idle') closePanels()
  if (prev === 'roles_pick' && next === 'mafia_talk_start') void applyMafiaTalkStartForLocal()
  if (prev === 'mafia_talk_start' && next === 'mafia_talk_end') void applyMafiaTalkEndForLocal()
  if (next === 'night') void applyNightStartForLocal()
  if ((prev === 'mafia_talk_end' && next === 'day') || (prev === 'night' && next === 'day')) void applyDayStartForLocal()
  void enforceSpectatorPhaseVisibility(next)
}

function syncSubscriptionsFromState(): void {
  rtc.setAudioSubscriptionsForAll(local.speakers)
  rtc.setVideoSubscriptionsForAll(local.visibility)
}

function applyJoinAck(j: any) {
  isPrivate.value = (j?.privacy || j?.room?.privacy) === 'private'
  const limitRaw = Number(j?.user_limit ?? j?.room_user_limit ?? 0)
  roomUserLimit.value = Number.isFinite(limitRaw) ? limitRaw : 0
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
    if (!isUserId && !isKeep) {
      clearVolumeSnap(k)
      delete volUi[k]
    }
  }

  const snapshotIds = Object.keys(j.snapshot || {})
  game.applyFromJoinAck(j, snapshotIds)
  if (musicEnabled.value) {
    rtc.setBgmSeed(j?.game_runtime?.bgm_seed, rid)
  } else {
    rtc.setBgmPlaying(false)
  }
  void enforceReturnStateAfterJoin()
  void enforceSpectatorPhaseVisibility(gamePhase.value)
  syncSubscriptionsFromState()
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
    if (k === 'mic') desiredMedia.mic = want
    if (k === 'cam') desiredMedia.cam = want
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
  async () => {
    if (!(await ensureVerifiedForMedia())) return false
    return await rtc.enable('videoinput')
  },
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
  if (!isMyScreen.value && !(await ensureVerifiedForMedia())) return
  pendingScreen.value = true
  try {
    if (!isMyScreen.value) {
      const resp = await sendAck('screen', { on: true })
      if (!resp || !resp.ok) {
        if (resp?.status === 409 && resp?.owner) screenOwnerId.value = String(resp.owner)
        else if (resp?.status === 403 && resp?.error === 'streams_start_disabled') void alertDialog('Запуск трансляций отключен')
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

const toggleHostBlur = async () => {
  if (hostBlurPending.value || !hostBlurToggleEnabled.value) return
  const wantEnable = !hostBlurActive.value
  const ok = await confirmDialog({
    text: wantEnable
      ? 'Вы хотите активировать размытие стола у игроков?'
      : 'Вы хотите прекратить размытие стола у игроков?',
  })
  if (!ok) return
  hostBlurPending.value = true
  try {
    const resp = await sendAck('game_host_blur', { on: wantEnable })
    if (resp?.ok && 'enabled' in resp) {
      hostBlurActive.value = !!(resp as any).enabled
    }
  } finally {
    hostBlurPending.value = false
  }
}

async function enableInitialMedia(): Promise<boolean> {
  if (isSpectatorInGame.value) return false
  let failed = false
  if (desiredMedia.cam && !blockedSelf.value.cam) {
    const ok = await rtc.enable('videoinput')
    if (!ok) {
      failed = true
      camOn.value = false
      try { await publishState({ cam: false }) } catch {}
    } else if (!camOn.value) {
      camOn.value = true
      try { await publishState({ cam: true }) } catch {}
    }
  }
  if (desiredMedia.mic && !blockedSelf.value.mic) {
    const ok = await rtc.enable('audioinput')
    if (!ok) {
      failed = true
      micOn.value = false
      try { await publishState({ mic: false }) } catch {}
    } else if (!micOn.value) {
      micOn.value = true
      try { await publishState({ mic: true }) } catch {}
    }
  }
  return failed
}

async function onMediaGateClick() {
  closePanels()
  rtc.autoplayUnlocked.value = true
  rtc.primeAudioOnGesture()
  try { await rtc.startAudio() } catch {}
  if (speakersOn.value && !blockedSelf.value.speakers) {
    rtc.setAudioSubscriptionsForAll(true)
  }
  syncSubscriptionsFromState()
  rtc.resumeVideo()
  void rtc.resumeAudio({ force: true })
  window.setTimeout(() => { void rtc.resumeAudio({ force: true }) }, 250)
  void rtc.unlockBgmOnGesture()
  rtc.ensureBgmPlayback()
}

async function handleJoinFailure(j: any) {
  if (leaving.value) return
  if (j?.status === 403 && j?.error === 'rooms_entry_disabled') {
    void alertDialog('Вход в комнату заблокирован')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  if (j?.status === 403 && j?.error === 'user_timeout') {
    await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  if (j?.status === 403 && j?.error === 'user_banned') {
    await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  if (j?.status === 403 && j?.error === 'private_room') {
    try { await api.post(`/rooms/${rid}/apply`) } catch {}
    void alertDialog('Комната приватная, запрос в комнату отправлен')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  if (j?.status === 409 && j?.error === 'room_is_full') {
    void alertDialog('Комната заполнена')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  if (j?.status === 409 && (j?.error === 'game_in_progress' || j?.error === 'spectators_full')) {
    void alertDialog('В комнате нет мест для зрителей')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  void alertDialog(j?.status === 404 ? 'Комната не найдена' : j?.status === 410 ? 'Комната закрыта' : j?.status === 409 ? 'Комната заполнена' : 'Ошибка входа в комнату')
  await router.replace('/')
}

async function onLeave(goHome = true) {
  if (leaving.value) return
  leaving.value = true
  try {
      document.removeEventListener('click', onDocClick)
      document.removeEventListener('visibilitychange', onBackgroundVisibility)
      window.removeEventListener('pagehide', onBackgroundVisibility)
      window.removeEventListener('keydown', onHotkey)
  } catch {}
  try {
    await stopScreenBeforeLeave()
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

async function rememberIdleStateOnServer(): Promise<void> {
  if (!IS_MOBILE) return
  if (gamePhase.value !== 'idle') return
  if (!socket.value || !socket.value.connected) return
  try {
    await sendAck('bg_state', {
      state: {
        mic: local.mic,
        cam: local.cam,
        speakers: local.speakers,
        visibility: local.visibility,
      },
    })
  } catch {}
}

function mergeBlockedState(blocks: any): BlockState {
  const cur = blockedSelf.value
  return {
    mic: pick01(blocks?.mic, cur.mic),
    cam: pick01(blocks?.cam, cur.cam),
    speakers: pick01(blocks?.speakers, cur.speakers),
    visibility: pick01(blocks?.visibility, cur.visibility),
    screen: pick01(blocks?.screen, cur.screen),
  }
}

async function applyLocalStateFromServer(state: any, blocks: any): Promise<void> {
  if (!state || typeof state !== 'object') return
  const lid = localId.value
  const hasBlocks = !!blocks && typeof blocks === 'object'
  if (lid && hasBlocks) applyBlocks(lid, blocks)
  const mergedBlocks = hasBlocks ? mergeBlockedState(blocks) : blockedSelf.value
  const nextMic = !mergedBlocks.mic && norm01(state.mic, local.mic ? 1 : 0) === 1
  const nextCam = !mergedBlocks.cam && norm01(state.cam, local.cam ? 1 : 0) === 1
  const nextSpeakers = !mergedBlocks.speakers && norm01(state.speakers, local.speakers ? 1 : 0) === 1
  const nextVisibility = !mergedBlocks.visibility && norm01(state.visibility, local.visibility ? 1 : 0) === 1

  desiredMedia.mic = nextMic
  desiredMedia.cam = nextCam
  local.mic = nextMic
  local.cam = nextCam
  local.speakers = nextSpeakers
  local.visibility = nextVisibility
  if (lid) {
    applyPeerState(lid, {
      mic: nextMic ? 1 : 0,
      cam: nextCam ? 1 : 0,
      speakers: nextSpeakers ? 1 : 0,
      visibility: nextVisibility ? 1 : 0,
    })
  }

  if (mergedBlocks.screen && screenOwnerId.value === lid) {
    try { await rtc.stopScreenShare() } catch {}
    screenOwnerId.value = ''
  }

  try {
    if (nextMic) await rtc.enable('audioinput')
    else await rtc.disable('audioinput')
  } catch {}
  try {
    if (nextCam) await rtc.enable('videoinput')
    else await rtc.disable('videoinput')
  } catch {}
  try { rtc.setAudioSubscriptionsForAll(nextSpeakers) } catch {}
  try { rtc.setVideoSubscriptionsForAll(nextVisibility) } catch {}
  if (nextSpeakers && !mergedBlocks.speakers) {
    try { void rtc.resumeAudio() } catch {}
  }
}

function isBlackTeam(kind: GameRoleKind | null | undefined): boolean {
  return kind === 'mafia' || kind === 'don'
}

function gameReturnTargets(phase: GamePhase) {
  if (isHead.value) {
    return {
      mic: false,
      cam: false,
      speakers: true,
      visibility: true,
    }
  }
  const isDayVote = phase === 'day' || phase === 'vote'
  const isMafiaTalk = phase === 'mafia_talk_start'
  const isAlivePlayer = myGameRole.value === 'player' && amIAlive.value
  return {
    mic: isCurrentSpeaker.value,
    cam: isAlivePlayer,
    speakers: true,
    visibility: isDayVote || (isMafiaTalk && isBlackTeam(myGameRoleKind.value)),
  }
}

async function applyGameReturnState(): Promise<void> {
  if (backgrounded.value) return
  const phase = gamePhase.value
  if (phase === 'idle') return
  const target = gameReturnTargets(phase)
  const nextMic = target.mic && !blockedSelf.value.mic
  const nextCam = target.cam && !blockedSelf.value.cam
  const nextSpeakers = target.speakers && !blockedSelf.value.speakers
  const nextVisibility = target.visibility && !blockedSelf.value.visibility
  const canTouchMedia = !!rtc.lk.value

  const delta: PublishDelta = {}
  if (local.mic !== nextMic) {
    local.mic = nextMic
    desiredMedia.mic = nextMic
    delta.mic = nextMic
    if (canTouchMedia) {
      try {
        if (nextMic) await rtc.enable('audioinput')
        else await rtc.disable('audioinput')
      } catch {}
    }
  }
  if (local.cam !== nextCam) {
    local.cam = nextCam
    desiredMedia.cam = nextCam
    delta.cam = nextCam
    if (canTouchMedia) {
      try {
        if (nextCam) await rtc.enable('videoinput')
        else await rtc.disable('videoinput')
      } catch {}
    }
  }
  if (local.speakers !== nextSpeakers) {
    local.speakers = nextSpeakers
    delta.speakers = nextSpeakers
  }
  if (local.visibility !== nextVisibility) {
    local.visibility = nextVisibility
    delta.visibility = nextVisibility
  }

  try { rtc.setAudioSubscriptionsForAll(nextSpeakers) } catch {}
  try { rtc.setVideoSubscriptionsForAll(nextVisibility) } catch {}
  if (nextSpeakers && !blockedSelf.value.speakers) {
    try { void rtc.resumeAudio() } catch {}
  }

  if (Object.keys(delta).length) {
    try { await publishState(delta) } catch {}
  }
}

async function restoreAfterBackgroundFromServer(): Promise<void> {
  if (!IS_MOBILE) return
  if (!socket.value || !socket.value.connected) {
    bgRestorePending = true
    return
  }

  bgRestorePending = false
  const nowPhase = gamePhase.value
  const phase = nowPhase === 'idle' ? (backgroundedPhase ?? nowPhase) : nowPhase
  backgroundedPhase = null
  if (phase === 'idle') {
    const resp = await sendAck('bg_restore', {})
    if (resp?.ok && resp?.state) {
      await applyLocalStateFromServer(resp.state, resp.blocked ?? resp.blocks)
      return
    }
  }
  if (phase !== 'idle') {
    await applyGameReturnState()
  }
}

async function applyBackgroundMute(): Promise<void> {
  if (backgrounded.value) return
  backgroundedPhase = gamePhase.value
  await rememberIdleStateOnServer()
  backgrounded.value = true

  desiredMedia.mic = false
  desiredMedia.cam = false

  const delta: PublishDelta = {}
  if (local.mic) {
    local.mic = false
    delta.mic = false
  }
  if (local.cam) {
    local.cam = false
    delta.cam = false
  }
  if (local.visibility) {
    local.visibility = false
    delta.visibility = false
  }
  try { await rtc.disable('audioinput') } catch {}
  try { await rtc.disable('videoinput') } catch {}
  try { rtc.setVideoSubscriptionsForAll(false) } catch {}
  if (local.speakers && !blockedSelf.value.speakers) {
    try { rtc.setAudioSubscriptionsForAll(true) } catch {}
    try { void rtc.resumeAudio() } catch {}
  }

  if (Object.keys(delta).length) {
    try { await publishState(delta) } catch {}
  }
}

function onBackgroundVisibility(e?: PageTransitionEvent) {
  const type = (e as any)?.type
  const hidden = document.visibilityState === 'hidden' || type === 'pagehide'
  if (hidden) rtc.flushVolumePrefs()
  if (!IS_MOBILE) return
  if (leaving.value) return
  if (hidden) {
    void applyBackgroundMute()
  } else if (backgrounded.value) {
    backgrounded.value = false
    void restoreAfterBackgroundFromServer()
  }
}

function handleOffline() { netReconnecting.value = true }

function handleOnline() { if (netReconnecting.value) hardReload() }

watch(isCurrentSpeaker, async (now, was) => {
  if (now === was) return
  if (backgrounded.value) return
  if (isSpectatorInGame.value) return
  try {
    if (now) { if (!micOn.value) await toggleMic() }
    else { if (micOn.value) await toggleMic() }
  } catch {}
})

watch(canEditGame, (ok) => {
  if (!ok && gameParamsOpen.value) gameParamsOpen.value = false
})

watch(() => [gamePhase.value, amIAlive.value, isSpectatorInGame.value, localId.value], () => {
  void enforceNoPublishWhenInactive()
}, { immediate: true })

let speechAudioKickId: number | null = null
function kickSpeechAudio() {
  if (speechAudioKickId != null) return
  speechAudioKickId = window.setTimeout(() => {
    speechAudioKickId = null
    if (!speakersOn.value || blockedSelf.value.speakers) return
    rtc.setAudioSubscriptionsForAll(true)
    void rtc.resumeAudio()
  }, 100)
}

watch(() => [gamePhase.value, game.daySpeech.currentId, game.daySpeech.remainingMs, speakersOn.value, blockedSelf.value.speakers], ([phase, cur, ms]) => {
  if ((phase !== 'day' && phase !== 'vote') || !cur) return
  if ((ms ?? 0) > 0) return
  kickSpeechAudio()
}, { immediate: true })

watch(
  () => [gamePhase.value, game.daySpeech.currentId, game.daySpeech.remainingMs],
  ([phase, cur, ms], [_prevPhase, prevCur, prevMs]) => {
    if ((phase !== 'day' && phase !== 'vote') || !cur) return
    if (prevCur !== cur) return
    const before = Number(prevMs ?? 0)
    const now = Number(ms ?? 0)
    if (before <= 0 || now > 0) return
    void rtc.resumeAudio({ force: true })
    playSpeechGong()
  }
)

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

    await rtc.setCameraQuality(desiredCameraQuality.value)

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
    if (joinPhaseApplyPending && localId.value) {
      joinPhaseApplyPending = false
      await applyGameReturnState()
    }
    rtc.setAudioSubscriptionsForAll(local.speakers)
    rtc.setVideoSubscriptionsForAll(local.visibility)
    const wantInitialCam = desiredMedia.cam && !blockedSelf.value.cam
    const wantInitialMic = desiredMedia.mic && !blockedSelf.value.mic
    if (wantInitialCam || wantInitialMic) {
      await enableInitialMedia()
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
    window.addEventListener('keydown', onHotkey)
    document.addEventListener('visibilitychange', onBackgroundVisibility, { passive: true })
    window.addEventListener('pagehide', onBackgroundVisibility, { passive: true })
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
  window.removeEventListener('keydown', onHotkey)
  volumeSnapTimers.forEach((tm) => { try { window.clearTimeout(tm) } catch {} })
  volumeSnapTimers.clear()
  if (gameStartOverlayTimerId != null) window.clearTimeout(gameStartOverlayTimerId)
  if (gameEndOverlayTimerId != null) window.clearTimeout(gameEndOverlayTimerId)
  rtc.flushVolumePrefs()
  rtc.destroyBgm()
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
    background-color: rgba($black, 0.25);
    backdrop-filter: blur(5px);
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
  .host-blur-overlay {
    display: flex;
    position: fixed;
    align-items: center;
    justify-content: center;
    inset: 0;
    font-size: 32px;
    color: white;
    z-index: 850;
    background-color: rgba($black, 0.25);
    backdrop-filter: blur(25px);
    pointer-events: fill;
  }
  .grid {
    display: grid;
    width: calc(100vw - 20px);
    height: calc(100dvh - 70px);
    gap: 10px;
  }
  .theater {
    display: grid;
    grid-template-columns: 1fr 324px;
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
      width: 324px;
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
      .hot-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        position: absolute;
        bottom: 0;
        right: 0;
        width: 16px;
        height: 16px;
        border-radius: 5px;
        background-color: $fg;
        color: $black;
        font-size: 12px;
        font-weight: bold;
        font-family: Manrope-Medium;
        line-height: 1;
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
    background-color: rgba($black, 0.25);
    backdrop-filter: blur(5px);
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
  .knock-overlay {
    display: flex;
    position: fixed;
    align-items: center;
    justify-content: center;
    inset: 0;
    background-color: rgba($black, 0.25);
    backdrop-filter: blur(5px);
    z-index: 900;
    .knock-modal {
      display: flex;
      flex-direction: column;
      padding: 30px;
      gap: 20px;
      width: min(60%, 600px);
      border-radius: 5px;
      background-color: $dark;
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      span {
        text-align: center;
        font-size: 20px;
      }
      .knock-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(20px, 1fr));
        gap: 20px;
        button {
          padding: 0;
          height: 30px;
          border: none;
          border-radius: 5px;
          background-color: $graphite;
          color: $fg;
          font-size: 16px;
          font-family: Manrope-Medium;
          cursor: pointer;
          transition: background-color 0.25s ease-in-out;
          &:hover:enabled {
            background-color: $lead;
          }
          &:disabled {
            cursor: default;
            opacity: 0.5;
          }
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

.knock-modal-enter-active,
.knock-modal-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.knock-modal-enter-from,
.knock-modal-leave-to {
  opacity: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.host-blur-enter-active,
.host-blur-leave-active {
  transition: opacity 0.5s ease-in-out, backdrop-filter 0.5s ease-in-out;
}
.host-blur-enter-from,
.host-blur-leave-to {
  opacity: 0;
  backdrop-filter: blur(0);
}
.host-blur-enter-to,
.host-blur-leave-from {
  opacity: 1;
  backdrop-filter: blur(10px);
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
    .host-blur-overlay {
      font-size: 20px;
    }
    .grid {
      width: calc(100vw - 10px);
      height: calc(100dvh - 40px);
      gap: 3px;
    }
    .theater {
      grid-template-columns: 1fr 244px;
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
        width: 244px;
        gap: 1px;
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
        .hot-btn {
          width: 8px;
          height: 8px;
          border-radius: 3px;
          font-size: 6px;
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

