<template>
  <section class="room">
    <div v-if="isReconnecting" class="reconnect-overlay" role="status" aria-live="polite">
      <UiLoaderIcon class="reconnect-overlay__icon" />
      <span class="reconnect-overlay__text">Восстанавливаем соединение…</span>
    </div>

    <div v-else-if="!uiReady" class="reconnect-overlay" role="status" aria-live="polite">
      <UiLoaderIcon class="reconnect-overlay__icon" />
      <span class="reconnect-overlay__text">Загрузка комнаты…</span>
    </div>

    <template v-else>
      <Transition name="fade">
        <div v-if="gameOverlayVisible" class="reconnect-overlay" role="status" aria-live="polite">
          <UiLoaderIcon class="reconnect-overlay__icon" />
          <span class="reconnect-overlay__text">{{ gameOverlayText }}</span>
        </div>
      </Transition>
      <Transition name="host-blur">
        <div v-if="hostBlurVisible" class="host-blur-overlay" :class="{ 'host-blur-overlay-head': hostBlurUsesHeadView }" aria-hidden="true">
          <div class="pause-block">
            <UiIcon class="pause-img" :icon="iconPauseOn" />
            <span class="pause-text">Пауза</span>
          </div>
        </div>
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
          :has-video-track="rtc.hasCameraTrack"
          :fit-contain="fitContainInGrid"
          :default-avatar="iconDefaultAvatar"
          :state-icon="stateIcon"
          :is-ready="isReady"
          :is-on="isOn"
          :is-blocked="isBlocked"
          :user-name="userName"
          :avatar-key="avatarKey"
          :theme-color="themeColorFor(id)"
          :theme-icon="themeIconFor(id)"
          :moderation-role="moderationRol(id)"
          :can-open-profile="canOpenMiniProfileFromTile(id)"
          :is-mirrored="isMirrored"
          :is-game-head="game.isGameHead(id)"
          :is-head="isHead"
          :is-dead="game.isDead"
          :dead-avatar="deadAvatar(id)"
          :seat="game.seatIndex(id)"
          :seat-label="game.seatLabelForUser(id)"
          :offline="offlineInGame.has(id)"
          :offline-avatar="iconLowSignal"
          :role-pick-owner-id="rolePickOwnerIdFor(id)"
          :role-pick-remaining-ms="rolePickRemainingMsFor(id)"
          :mafia-talk-host-id="mafiaTalkHostIdFor(id)"
          :mafia-talk-remaining-ms="mafiaTalkRemainingMsFor(id)"
          :red-mark="game.shouldHighlightMafiaTile(id) || game.foulActive.has(id)"
          :game-role-kind="game.effectiveRoleKindForTile(id)"
          :game-role="game.effectiveRoleIconForTile(id)"
          :finish-role-badge="gameFinished"
          :hidden-by-visibility="hiddenByVisibility(id)"
          :visibility-hidden-avatar="visOffAvatar(id)"
          :in-game="gamePhase !== 'idle'"
          :day-speech-owner-id="daySpeechOwnerIdFor(id)"
          :day-speech-remaining-ms="daySpeechRemainingMsFor(id)"
          :day-speech-paused="hostBlurActive"
          :fouls-count="gameFoulsByUser.get(id) ?? 0"
          :winks-left="winksLeft"
          :knocks-left="knocksLeft"
          :show-wink="game.canWinkTarget(id)"
          :show-knock="game.canKnockTarget(id)"
          :phase-label="phaseLabelFor(id)"
          :night-owner-id="nightOwnerIdFor(id)"
          :night-remaining-ms="nightRemainingMsFor(id)"
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
          :nominees="nomineesFor(id)"
          :lift-nominees="liftNomineesFor(id)"
          :current-nominee-seat="id === headUserId ? currentNomineeSeat : null"
          :show-nominations-bar="id === headUserId && (gamePhase === 'day' || gamePhase === 'vote')"
          :show-nominations-badge="id === headUserId && canShowHeadNominationsBadge"
          :vote-blocked="voteBlockedFor(id)"
          :offline-seats-in-game="offlineSeatsInGameFor(id)"
          :show-vote-button="amIAlive && game.canPressVoteButton()"
          :vote-enabled="game.canPressVoteButton()"
          :has-voted="(isLiftVoting ? votedUsers : votedThisRound).has(id)"
          :show-foul-control="canShowFoulButtons"
          @open-profile="openMiniProfileFromTile"
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
          <video :ref="(el) => stableScreenRef(screenOwnerId)(el as HTMLVideoElement | null)" playsinline autoplay muted />
          <div v-if="screenOwnerId" class="screen-quality" :aria-label="`${screenQualityLabel}: ${SCREEN_QUALITY_HINT}`">
            <UiIcon class="dot-img" :icon="iconDotBig" />
            <span class="screen-text">{{ screenQualityLabel }}</span>
          </div>
          <div v-if="screenOwnerId !== localId && streamAudioKey" class="volume" @click.stop>
            <UiIcon class="volume-img" :icon="volumeIconForStream(streamAudioKey)" />
            <UiSlider
              :model-value="streamVol"
              :min="0"
              :max="200"
              :step="10"
              :disabled="!speakersOn || isBlocked(screenOwnerId,'speakers')"
              aria-label="Громкость трансляции"
              @update:modelValue="onVol(streamAudioKey, $event)"
            />
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
            :has-video-track="rtc.hasCameraTrack"
            :fit-contain="fitContainInGrid"
            :default-avatar="iconDefaultAvatar"
            :state-icon="stateIcon"
            :is-ready="isReady"
            :is-on="isOn"
            :is-blocked="isBlocked"
            :user-name="userName"
            :avatar-key="avatarKey"
            :theme-color="themeColorFor(id)"
            :theme-icon="themeIconFor(id)"
            :moderation-role="moderationRol(id)"
            :can-open-profile="canOpenMiniProfileFromTile(id)"
            :is-mirrored="isMirrored"
            :is-game-head="game.isGameHead(id)"
            :is-head="isHead"
            :is-dead="game.isDead"
            :dead-avatar="deadAvatar(id)"
            :seat="game.seatIndex(id)"
            :seat-label="game.seatLabelForUser(id)"
            :offline="offlineInGame.has(id)"
            :offline-avatar="iconLowSignal"
            :role-pick-owner-id="rolePickOwnerIdFor(id)"
            :role-pick-remaining-ms="rolePickRemainingMsFor(id)"
            :mafia-talk-host-id="mafiaTalkHostIdFor(id)"
            :mafia-talk-remaining-ms="mafiaTalkRemainingMsFor(id)"
            :red-mark="game.shouldHighlightMafiaTile(id) || game.foulActive.has(id)"
            :game-role-kind="game.effectiveRoleKindForTile(id)"
            :game-role="game.effectiveRoleIconForTile(id)"
            :finish-role-badge="gameFinished"
            :hidden-by-visibility="hiddenByVisibility(id)"
            :visibility-hidden-avatar="visOffAvatar(id)"
            :in-game="gamePhase !== 'idle'"
            :day-speech-owner-id="daySpeechOwnerIdFor(id)"
            :day-speech-remaining-ms="daySpeechRemainingMsFor(id)"
            :day-speech-paused="hostBlurActive"
            :fouls-count="gameFoulsByUser.get(id) ?? 0"
            :winks-left="winksLeft"
            :knocks-left="knocksLeft"
            :show-wink="game.canWinkTarget(id)"
            :show-knock="game.canKnockTarget(id)"
            :phase-label="phaseLabelFor(id)"
            :night-owner-id="nightOwnerIdFor(id)"
            :night-remaining-ms="nightRemainingMsFor(id)"
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
            :nominees="nomineesFor(id)"
            :lift-nominees="liftNomineesFor(id)"
            :current-nominee-seat="id === headUserId ? currentNomineeSeat : null"
            :show-nominations-bar="id === headUserId && (gamePhase === 'day' || gamePhase === 'vote')"
            :show-nominations-badge="id === headUserId && canShowHeadNominationsBadge"
            :vote-blocked="voteBlockedFor(id)"
            :offline-seats-in-game="offlineSeatsInGameFor(id)"
            :show-vote-button="amIAlive && game.canPressVoteButton()"
            :vote-enabled="game.canPressVoteButton()"
            :has-voted="(isLiftVoting ? votedUsers : votedThisRound).has(id)"
            :show-foul-control="canShowFoulButtons"
            @open-profile="openMiniProfileFromTile"
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

      <div class="panel" :class="{ 'panel-high': buttonsHigh }">
        <div class="controls-side left">
          <button @click="() => void onLeave()" aria-label="Покинуть комнату">
            <UiIcon class="panel-icon panel-icon-neutral leave-room-icon" :icon="iconLeaveRoom" />
          </button>
          <button v-if="gamePhase !== 'idle' && isHead && !gameFinished" @click="endGameUi" :disabled="endingGame" aria-label="Завершить игру">
            <UiIcon class="panel-icon panel-icon-red" :icon="iconGameStop" />
          </button>
          <button v-if="canShowLeaveGameButton" @click="leaveGameUi" :aria-label="leaveGameButtonLabel">
            <UiIcon class="panel-icon panel-icon-neutral" :icon="iconDeadPlayer" />
          </button>
        </div>

        <div v-if="showPermProbe" class="controls">
          <button class="btn-text" @click="onProbeClick">Разрешить доступ к камере и микрофону</button>
        </div>
        <div v-else-if="!gameFinished" class="controls">
          <button v-if="canShowHeadGoToMafiaTalkControl" class="btn-text" :disabled="!canHeadGoToMafiaTalkControl" @click="goToMafiaTalkUi" aria-label="Перейти к договорке">
            Начать договорку
            <span v-if="showSpaceHotkeyHint('goToMafiaTalk')" class="hot-btn">_</span>
          </button>
          <button v-if="canHeadFinishMafiaTalkControl" class="btn-text" @click="finishMafiaTalkUi" aria-label="Завершить договорку">
            Завершить договорку
            <span v-if="showSpaceHotkeyHint('finishMafiaTalk')" class="hot-btn">_</span>
          </button>
          <button v-if="canShowStartDay" class="btn-text" :disabled="!canStartDay" @click="startDayUi" aria-label="Начать день">
            День
            <span v-if="showSpaceHotkeyHint('startDay')" class="hot-btn">_</span>
          </button>
          <button v-if="canShowFinishSpeechHead" class="btn-text" :disabled="hostBlurLocksControls || !canFinishSpeechHead" @click="finishSpeechUi" aria-label="Завершить речь">
            Завершить речь
            <span v-if="showSpaceHotkeyHint('finishSpeechHead')" class="hot-btn">_</span>
          </button>
          <button v-else-if="canShowPassSpeechHead" class="btn-text" :disabled="hostBlurLocksControls || !canPassSpeechHead" @click="passSpeechUi" aria-label="Передать речь">
            Передать речь
            <span v-if="showSpaceHotkeyHint('passSpeechHead')" class="hot-btn">_</span>
          </button>
          <button v-if="canStartVote" class="btn-text" :disabled="hostBlurLocksControls" @click="startVoteUi">
            Начать голосование
            <span v-if="showSpaceHotkeyHint('startVote')" class="hot-btn">_</span>
          </button>
          <button v-if="canHeadVoteControl" class="btn-text" :disabled="hostBlurLocksControls || hasOfflineAlivePlayers || !canPressHeadVoteControl" @click="onHeadVoteControl">
            {{ !voteStartedForCurrent ? 'Голосование за ' + (currentNomineeSeat ?? '') : 'Продолжить' }}
            <span v-if="showSpaceHotkeyHint('headVoteControl')" class="hot-btn">_</span>
          </button>
          <button v-if="canHeadFinishVoteControl" class="btn-text" :disabled="hostBlurLocksControls" @click="finishVoteUi">
            Завершить голосование
            <span v-if="showSpaceHotkeyHint('finishVote')" class="hot-btn">_</span>
          </button>
          <button v-if="canPrepareVoteLift" class="btn-text" :disabled="hostBlurLocksControls || hasOfflineAlivePlayers" @click="prepareVoteLiftUi">
            Продолжить
            <span v-if="showSpaceHotkeyHint('prepareVoteLift')" class="hot-btn">_</span>
          </button>
          <button v-if="canStartVoteLift" class="btn-text" :disabled="hostBlurLocksControls || hasOfflineAlivePlayers" @click="startVoteLiftUi">
            Голосование за подъём
            <span v-if="showSpaceHotkeyHint('startVoteLift')" class="hot-btn">_</span>
          </button>
          <button v-if="canShowStartLeaderSpeech" class="btn-text" :disabled="hostBlurLocksControls || !canStartLeaderSpeech" @click="startLeaderSpeechUi">
            Передать речь
            <span v-if="showSpaceHotkeyHint('startLeaderSpeech')" class="hot-btn">_</span>
          </button>
          <button v-if="canRestartVoteForLeaders" class="btn-text" :disabled="hostBlurLocksControls" @click="restartVoteForLeadersUi">
            Начать голосование
            <span v-if="showSpaceHotkeyHint('restartVoteForLeaders')" class="hot-btn">_</span>
          </button>
          <button v-if="canShowNight" class="btn-text" :disabled="hostBlurLocksControls || hasOfflineAlivePlayers" @click="goToNightUi">
            Ночь
            <span v-if="showSpaceHotkeyHint('goToNight')" class="hot-btn">_</span>
          </button>
          <button v-if="canHeadNightShootControl" class="btn-text" :disabled="hasOfflineAlivePlayers" @click="startNightShootUi">
            Стрельба
            <span v-if="showSpaceHotkeyHint('startNightShoot')" class="hot-btn">_</span>
          </button>
          <button v-if="canHeadNightCheckControl" class="btn-text" :disabled="hasOfflineAlivePlayers" @click="startNightChecksUi">
            Проверки
            <span v-if="showSpaceHotkeyHint('startNightChecks')" class="hot-btn">_</span>
          </button>
          <button v-if="canHeadBestMoveControl" class="btn-text" @click="startBestMoveUi">
            Лучший ход {{ bestMoveSeat ?? '?' }}
            <span v-if="showSpaceHotkeyHint('startBestMove')" class="hot-btn">_</span>
          </button>
          <button v-if="canStartDayFromNight" class="btn-text" :disabled="!canHeadDayFromNightControl" @click="startDayFromNightUi">
            День
            <span v-if="showSpaceHotkeyHint('startDayFromNight')" class="hot-btn">_</span>
          </button>

          <button v-if="canFinishSpeechSelf" class="btn-text" @click="finishSpeechUi">
            Завершить речь
            <span v-if="showSpaceHotkeyHint('finishSpeechSelf')" class="hot-btn">_</span>
          </button>
          <button v-else-if="canShowTakeFoulSelf" class="btn-text" @click="takeFoulUi" :disabled="!canTakeFoulSelf || foulPending">
            Взять фол
            <span v-if="!IS_MOBILE && hotkeysVisible" class="hot-btn">↩</span>
          </button>

          <button v-if="gamePhase === 'idle' && !adminSpectator && canShowStartGame && canUseReadyStart" @click="startGameUi" :disabled="startingGame" aria-label="Запустить игру">
            <UiIcon class="panel-icon panel-icon-green" :icon="iconGameStart" />
          </button>
          <button v-if="gamePhase === 'idle' && !adminSpectator && !canShowStartGame && canUseReadyToggle" @click="toggleReady" :aria-pressed="readyOn" aria-label="Готовность">
            <UiIcon class="ready-icon" :class="{ 'ready-icon-on': readyOn }" :icon="iconReady" />
          </button>
          <button v-if="!adminSpectator && (gamePhase === 'idle' || isHead)" @click="toggleMic" :disabled="pending.mic || blockedSelf.mic === 1" :aria-pressed="micOn">
            <UiIcon class="control-state-icon" :class="stateIconClass('mic', localId)" :icon="stateIcon('mic', localId)" label="mic" />
              <span v-if="!IS_MOBILE && hotkeysVisible" class="hot-btn">M</span>
          </button>
          <button v-if="!adminSpectator && (gamePhase === 'idle' || isHead)" @click="toggleCam" :disabled="pending.cam || blockedSelf.cam === 1" :aria-pressed="camOn">
            <UiIcon class="control-state-icon" :class="stateIconClass('cam', localId)" :icon="stateIcon('cam', localId)" label="cam" />
              <span v-if="!IS_MOBILE && hotkeysVisible" class="hot-btn">C</span>
          </button>
          <button v-if="gamePhase === 'idle'" @click="toggleSpeakers" :disabled="pending.speakers || blockedSelf.speakers === 1" :aria-pressed="speakersOn">
            <UiIcon class="control-state-icon" :class="stateIconClass('speakers', localId)" :icon="stateIcon('speakers', localId)" label="speakers" />
              <span v-if="!IS_MOBILE && hotkeysVisible" class="hot-btn">S</span>
          </button>
          <button v-if="gamePhase === 'idle' && !adminSpectator && !IS_MOBILE" @click="toggleScreen" :disabled="pendingScreen || (!!screenOwnerId && screenOwnerId !== localId) || blockedSelf.screen === 1" :aria-pressed="isMyScreen">
            <UiIcon class="control-state-icon" :class="stateIconClass('screen', localId)" :icon="stateIcon('screen', localId)" label="screen" />
          </button>
          <button v-if="gamePhase !== 'idle' && isHead && hostBlurToggleEnabled" @click="toggleHostBlur" :disabled="hostBlurPending" :aria-pressed="hostBlurActive" aria-label="Пауза">
            <UiIcon class="panel-icon" :class="hostBlurActive ? 'panel-icon-green' : 'panel-icon-neutral'" :icon="hostBlurActive ? iconPauseOn : iconPauseOff" />
              <span v-if="!IS_MOBILE && hotkeysVisible" class="hot-btn">P</span>
          </button>
        </div>

        <div class="controls-side right">
          <button v-if="canViewGameSettings" @click.stop="openGameSettings" aria-label="Параметры игры">
            <UiIcon class="panel-icon panel-icon-neutral" :icon="iconParams" />
          </button>
          <button v-if="myRole === 'host' && isPrivate && gamePhase === 'idle'" @click.stop="toggleApps" :aria-expanded="openApps" aria-label="Заявки">
            <UiIcon class="panel-icon panel-icon-neutral" :icon="iconRequestsRoom" />
            <span class="count-total" :class="{ unread: appsCounts.unread > 0 }">{{ appsCounts.total < 100 ? appsCounts.total : '∞' }}</span>
          </button>
          <button v-if="showRoomFriendsButton" ref="roomFriendsEl" @click.stop="toggleFriendsPanel" :aria-expanded="friendsPanelOpen" aria-label="Друзья">
            <UiIcon class="panel-icon panel-icon-neutral" :icon="iconFriends" />
            <span v-if="friends.incomingCount > 0" class="count-total unread">{{ friends.incomingCount < 100 ? friends.incomingCount : '∞' }}</span>
          </button>
          <button v-if="showGlobalChatButton" @click.stop="toggleGlobalChat" :aria-expanded="chat.open" aria-label="Общий чат">
            <UiIcon class="panel-icon panel-icon-neutral" :icon="iconChat" />
            <span v-if="chat.unread > 0" class="count-total unread">{{ chat.unread < 100 ? chat.unread : '∞' }}</span>
          </button>
          <button @click.stop="toggleSettings" :aria-expanded="settingsOpen" aria-label="Настройки устройств">
            <UiIcon class="panel-icon panel-icon-neutral" :icon="iconSettings" />
          </button>
        </div>

        <RoomRequests
          v-if="myRole === 'host' && isPrivate && gamePhase === 'idle'"
          v-model:open="openApps"
          :room-id="rid"
          @counts="onAppsCounts"
        />

        <GameParams
          v-model:open="gameParamsOpen"
          :room-id="rid"
          :can-edit="canEditGameSettings"
          :external-game="roomGameSnapshot"
          @saved="applyRoomGameSnapshot"
        />

        <Friends
          v-if="showRoomFriendsButton"
          v-model:open="friendsPanelOpen"
          :anchor="roomFriendsEl"
          mode="room"
          :room-id="rid"
        />

        <MiniProfile
          v-model:open="miniProfileOpen"
          :user-id="miniProfileUserId"
          :initial-profile="miniProfileInitial"
          :show-stats-button="true"
          :room-controls="miniProfileRoomControls"
          @room-volume-change="onMiniProfileRoomVolume"
          @room-block="onMiniProfileRoomBlock"
          @room-kick="onMiniProfileRoomKick"
        />

        <RoomSetting
          :open="settingsOpen"
          :in-game="gamePhase !== 'idle'"
          :is-spectator="isSpectatorLike"
          :show-hotkeys-toggle="canShowHotkeysToggle"
          :show-mirror-toggle="canShowMirrorToggle"
          :is-mobile="IS_MOBILE"
          :hotkeys-visible="hotkeysVisible"
          :hotkeys-toggle-pending="hotkeysTogglePending"
          :mics="mics"
          :cams="cams"
          v-model:micId="selectedMicId"
          v-model:camId="selectedCamId"
          v-model:mirrorOn="mirrorOn"
          v-model:buttonsHigh="buttonsHigh"
          v-model:videoFillOn="videoFillOn"
          v-model:volume="bgmVolume"
          :show-video-fill-toggle="showVideoFillToggle"
          :volume-icon="volumeIcon(bgmVolume, bgmShouldPlay)"
          :music-enabled="musicEnabled"
          :can-toggle-known-roles="canToggleKnownRoles"
          :known-roles-visible="knownRolesVisible"
          @device-change="(kind) => rtc.onDeviceChange(kind)"
          @toggle-hotkeys="onToggleRoomHotkeys"
          @toggle-known-roles="toggleKnownRolesUi"
          @close="settingsOpen=false"
        />
      </div>

      <Transition name="role-overlay-fade">
        <div class="role-overlay" v-if="gamePhase === 'roles_pick' && roleOverlayMode !== 'hidden' && (roleOverlayMode === 'reveal' || rolePick.activeUserId === localId)">
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
      </Transition>

      <Transition name="knock-modal">
        <div v-if="knockModalOpen" class="knock-overlay" role="dialog" aria-modal="true"
             @pointerdown.self="knockModalArmed = true" @pointerup.self="knockModalArmed && closeKnockModal()"
             @pointerleave.self="knockModalArmed = false" @pointercancel.self="knockModalArmed = false">
          <div class="knock-modal" @click.stop>
            <div class="knock-header">
              <span>Какое число хотите отстучать?</span>
              <button class="close-btn" type="button" @click="closeKnockModal">
                <UiIcon class="close-icon" :icon="iconClose" />
              </button>
            </div>
            <div class="knock-grid">
              <button class="knock-btn" v-for="n in knockOptions" :key="n" type="button" @click="selectKnockCount(n)" :disabled="knockSending">{{ n }}</button>
            </div>
          </div>
        </div>
      </Transition>

      <div v-if="mediaGateVisible" class="reconnect-overlay media-gate" @click.stop.prevent="onMediaGateClick" @touchstart.stop.prevent="onMediaGateClick" @pointerdown.stop.prevent="onMediaGateClick">
        <span class="reconnect-overlay__text">Нажмите чтобы продолжить…</span>
      </div>
    </template>
    <div class="role-preload" aria-hidden="true">
      <img v-for="src in ROLE_CARD_IMAGES" :key="src" :src="src" alt="" loading="eager" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import type { Socket } from 'socket.io-client'
import {
  useAuthStore,
  useSettingsStore,
  useUserStore,
  useFriendsStore,
  useGlobalChatStore,
} from '@/store'
import {
  type Ack,
  type FarewellVerdict,
  type GamePhase,
  type GameRoleKind,
  type SendAckFn,
  useRoomGame
} from '@/composables/roomGame'
import { type CameraQuality, type ScreenShareQuality, useRTC, type VQ } from '@/composables/rtc'
import { api } from '@/services/axios'
import { alertDialog, confirmDialog, confirmDialogWithRadio, useConfirmState } from '@/services/confirm'
import { normalizeRoomGameParams, type RoomGameParams } from '@/services/gameParams'
import { canOpenMiniProfileTarget } from '@/services/miniProfile'
import { setPageTitle } from '@/services/pwa'
import { createAuthedSocket, disposeAuthedSocket } from '@/services/sio'
import RoomTile from '@/components/RoomTile.vue'
import RoomRequests from '@/components/RoomRequests.vue'
import RoomSetting from '@/components/RoomSetting.vue'
import GameParams from '@/components/GameParams.vue'
import Friends from '@/components/Friends.vue'
import MiniProfile from '@/components/MiniProfile.vue'
import UiSlider from '@/components/UiSlider.vue'
import UiIcon from '@/components/UiIcon.vue'
import UiLoaderIcon from '@/components/UiLoaderIcon.vue'

import iconDefaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconVolumeMax from '@/assets/svg/iconVolumeMax.svg'
import iconVolumeMid from '@/assets/svg/iconVolumeMid.svg'
import iconVolumeLow from '@/assets/svg/iconVolumeLow.svg'
import iconVolumeMute from '@/assets/svg/iconVolumeMute.svg'
import gongAudioUrl from '@/assets/audio/gong.mp3'

import iconLeaveRoom from '@/assets/svg/iconLeave.svg'
import iconRequestsRoom from '@/assets/svg/iconRequestsRoom.svg'
import iconFriends from '@/assets/svg/iconFriends.svg'
import iconChat from '@/assets/svg/iconChat.svg'
import iconSettings from '@/assets/svg/iconSettings.svg'
import iconParams from '@/assets/svg/iconParams.svg'
import iconReady from '@/assets/svg/iconReady.svg'
import iconPauseOn from '@/assets/svg/iconPauseOn.svg'
import iconPauseOff from '@/assets/svg/iconPauseOff.svg'
import iconGameStart from '@/assets/svg/iconPlay.svg'
import iconGameStop from '@/assets/svg/iconStop.svg'
import iconDeadPlayer from '@/assets/svg/iconDead.svg'
import iconCardBack from '@/assets/images/cardBack.png'
import iconSleepPlayer from '@/assets/images/sleepPlayer.png'
import iconLowSignal from '@/assets/images/lowSignal.png'
import iconKillPlayer from '@/assets/images/killPlayer.png'
import iconVotedPlayer from '@/assets/images/votedPlayer.png'
import iconFouledPlayer from '@/assets/images/fouledPlayer.png'
import iconLeavePlayer from '@/assets/images/leavePlayer.png'
import iconDotBig from '@/assets/svg/iconDotBig.svg'
import iconClose from '@/assets/svg/iconClose.svg'

import iconMicOn from '@/assets/svg/iconMicOn.svg'
import iconMicOff from '@/assets/svg/iconMicOff.svg'
import iconMicBlocked from '@/assets/svg/iconMicBlocked.svg'
import iconCamOn from '@/assets/svg/iconCamOn.svg'
import iconCamOff from '@/assets/svg/iconCamOff.svg'
import iconCamBlocked from '@/assets/svg/iconCamBlocked.svg'
import iconSpkOn from '@/assets/svg/iconSpkOn.svg'
import iconSpkOff from '@/assets/svg/iconSpkOff.svg'
import iconSpkBlocked from '@/assets/svg/iconSpkBlocked.svg'
import iconVisOn from '@/assets/svg/iconVisOn.svg'
import iconVisOff from '@/assets/svg/iconVisOff.svg'
import iconVisBlocked from '@/assets/svg/iconVisBlocked.svg'
import iconScreenOn from '@/assets/svg/iconScreenOn.svg'
import iconScreenOff from '@/assets/svg/iconScreenOff.svg'
import iconScreenBlocked from '@/assets/svg/iconScreenBlocked.svg'

type State01 = 0 | 1
type MediaState = {
  mic: State01
  cam: State01
  speakers: State01
  visibility: State01
}
type StatusState = Partial<MediaState> & {
  ready?: State01
  mirror?: State01
}
type BlockState = MediaState & { screen: State01 }
type IconKind = keyof MediaState | 'screen'
type RoomMiniProfileInitial = {
  id: number
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  theme_color?: string | null
  theme_icon?: string | null
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const settings = useSettingsStore()
const userStore = useUserStore()
const friends = useFriendsStore()
const chat = useGlobalChatStore()
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
  nominateMode,
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
  canFinishSpeechSelf: canFinishSpeechSelfBase,
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

const canFinishSpeechSelf = computed(() => (
  settings.selfSpeechFinishEnabled && canFinishSpeechSelfBase.value
))

const navUserAgent = navigator.userAgent || ''
const isUaDataMobile = (navigator as any).userAgentData?.mobile === true
const isMobileUa = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|Tablet/i.test(navUserAgent)
const isIpadOsDesktopUa = /Macintosh/i.test(navUserAgent) && (navigator.maxTouchPoints || 0) > 1
const IS_MOBILE = isUaDataMobile || isMobileUa || isIpadOsDesktopUa

const local = reactive({ mic: false, cam: false, speakers: true, visibility: true })
const desiredMedia = reactive({ mic: false, cam: false })
const adminSpectatorRequested = computed(() => String(route.query.spectator || '').toLowerCase() === 'admin')
const adminSpectator = ref(false)
const pending = reactive<{ [k in keyof typeof local]: boolean }>({ mic: false, cam: false, speakers: false, visibility: false })
const micOn = computed({ get: () => local.mic, set: v => { local.mic = v } })
const camOn = computed({ get: () => local.cam, set: v => { local.cam = v } })
const speakersOn = computed({ get: () => local.speakers, set: v => { local.speakers = v } })
const visibilityOn = computed({ get: () => local.visibility, set: v => { local.visibility = v } })
const socket = shallowRef<Socket | null>(null)
const joinInFlight = ref<Promise<any> | null>(null)
const statusByUser = reactive(new Map<string, StatusState>())
const positionByUser = reactive(new Map<string, number>())
const blockByUser  = reactive(new Map<string, BlockState>())
const rolesByUser = reactive(new Map<string, string>())
const moderationRolesByUser = reactive(new Map<string, string>())
const profileRolesByUser = reactive(new Map<string, string>())
const nameByUser = reactive(new Map<string, string>())
const avatarByUser = reactive(new Map<string, string | null>())
const themeColorByUser = reactive(new Map<string, string | null>())
const themeIconByUser = reactive(new Map<string, string | null>())
const volUi = reactive<Record<string, number>>({})
const MIN_GAME_VOLUME = 10
const EMPTY_NUMBERS: number[] = []
const EMPTY_STYLE = Object.freeze({}) as Readonly<Record<string, never>>
const GAME_GRID_STYLE = Object.freeze({
  gridTemplateColumns: 'repeat(8, 1fr)',
  gridTemplateRows: 'repeat(6, 1fr)',
})
const IDLE_GRID_STYLE_CACHE = new Map<string, Readonly<{ gridTemplateColumns: string; gridTemplateRows: string }>>()
const SEAT_TILE_STYLE_CACHE = new Map<number, Readonly<{ gridColumn: string; gridRow: string }>>()
const volumeSnapTimers = new Map<string, number>()
const screenOwnerId = ref<string>('')
const screenQuality = ref<ScreenShareQuality>('low')
const miniProfileOpen = ref(false)
const miniProfileUserId = ref<number | null>(null)
const miniProfileInitial = ref<RoomMiniProfileInitial | null>(null)
const pendingScreen = ref(false)
const settingsOpen = ref(false)
const hotkeysTogglePending = ref(false)
const friendsPanelOpen = ref(false)
const roomFriendsEl = ref<HTMLElement | null>(null)
const gameParamsOpen = ref(false)
const roomGameSnapshot = ref<RoomGameParams | null>(null)
const uiReady = ref(false)
const leaving = ref(false)
const netReconnecting = ref(false)
const backgrounded = ref(false)
let joinPhaseApplyPending = false
const lkReconnecting = computed(() => rtc.reconnecting.value)
const isReconnecting = computed(() => netReconnecting.value || lkReconnecting.value)
const reconnectBursts = ref<number[]>([])
const canUseVerifiedFeatures = computed(() => {
  if (!auth.ready || !settings.ready || !auth.isAuthed) return false
  if (!userStore.user) return false
  return !(settings.verificationRestrictions && !userStore.telegramVerified)
})
const isAdminUser = computed(() => String(userStore.user?.role || '').toLowerCase() === 'admin')
const showRoomFriendsButton = computed(() => gamePhase.value === 'idle' && !adminSpectator.value && canUseVerifiedFeatures.value)
const showGlobalChatButton = computed(() => {
  if (!canUseVerifiedFeatures.value) return false
  if (!settings.chatOpenEnabled && !isAdminUser.value) return false
  return !(userStore.banActive || userStore.timeoutActive || userStore.inActiveGameAsPlayer)
})
function onAppsCounts(p: { total?: number; unread?: number }) {
  appsCounts.total = Number(p?.total || 0)
  appsCounts.unread = Number(p?.unread || 0)
}

watch(showRoomFriendsButton, ok => {
  if (!ok) friendsPanelOpen.value = false
})

watch(isReconnecting, (now, prev) => {
  if (leaving.value) return
  if (!now || prev) return
  const ts = Date.now()
  const next = reconnectBursts.value.filter(t => ts - t <= 10_000)
  next.push(ts)
  reconnectBursts.value = next
  if (next.length >= 3) hardReload()
})
const openApps = ref(false)
const appsCounts = reactive({ total: 0, unread: 0 })
const isPrivate = ref(false)
const roomUserLimit = ref<number>(0)
const buttonsHighState = ref(rtc.loadLS(rtc.LS.buttonsHigh) === '1')
const videoFillOnState = ref(rtc.loadLS(rtc.LS.videoFill) !== '0')
const showVideoFillToggle = computed(() => {
  const limit = roomUserLimit.value
  return Number.isFinite(limit) && limit > 2
})
const buttonsHigh = computed({
  get: () => buttonsHighState.value,
  set: (v: boolean) => {
    buttonsHighState.value = v
    rtc.saveLS(rtc.LS.buttonsHigh, v ? '1' : '0')
  },
})
const videoFillOn = computed({
  get: () => videoFillOnState.value,
  set: (v: boolean) => {
    videoFillOnState.value = v
    rtc.saveLS(rtc.LS.videoFill, v ? '1' : '0')
  },
})
const gameLimitMin = computed(() => {
  const minReady = Number(settings.gameMinReadyPlayers)
  return Number.isFinite(minReady) && minReady > 0 ? minReady + 1 : 11
})
const ws_url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
const isTheater = computed(() => !!screenOwnerId.value)
const isMyScreen = computed(() => !!localId.value && screenOwnerId.value === localId.value)
const streamAudioKey = computed(() => screenOwnerId.value ? rtc.screenKey(screenOwnerId.value) : '')
const SCREEN_QUALITY_HINT = 'Качество 720p и 1080p доступно только для обладателей подписки'
const SCREEN_QUALITY_OPTIONS = [
  { value: 'low', label: '540p' },
  { value: 'medium', label: '720p' },
  { value: 'high', label: '1080p' },
] satisfies Array<{ value: ScreenShareQuality; label: string }>
const screenQualityLabel = computed(() => {
  if (screenQuality.value === 'high') return '1080p'
  if (screenQuality.value === 'medium') return '720p'
  return '540p'
})
function normalizeScreenQuality(raw: unknown, fallback: ScreenShareQuality = 'low'): ScreenShareQuality {
  return raw === 'high' || raw === 'medium' || raw === 'low' ? raw : fallback
}
function volumeFor(id: string, fallback = 100): number {
  if (!id) return fallback
  const raw = volUi[id] ?? rtc.getUserVolume(id)
  const n = Number(raw)
  return Number.isFinite(n) ? n : fallback
}
const streamVol = computed(() => streamAudioKey.value ? volumeFor(streamAudioKey.value) : 100)
const rolePickOwnerIdFor = (id: string) => rolePick.activeUserId === id ? id : ''
const rolePickRemainingMsFor = (id: string) => rolePick.activeUserId === id ? rolePick.remainingMs : 0
const mafiaTalkHostIdFor = (id: string) => headUserId.value === id ? id : ''
const mafiaTalkRemainingMsFor = (id: string) => headUserId.value === id ? mafiaTalkRemainingMs.value : 0
const daySpeechOwnerIdFor = (id: string) => game.daySpeech.currentId === id ? id : ''
const daySpeechRemainingMsFor = (id: string) => game.daySpeech.currentId === id ? game.daySpeech.remainingMs : 0
const nightOwnerIdFor = (id: string) => headUserId.value === id ? id : ''
const nightRemainingMsFor = (id: string) => headUserId.value === id ? night.remainingMs : 0
const phaseLabelFor = (id: string) => headUserId.value === id ? phaseLabel.value : ''
const nomineesFor = (id: string) => headUserId.value === id ? nomineeSeatNumbers.value : EMPTY_NUMBERS
const liftNomineesFor = (id: string) => (headUserId.value === id && liftHighlightNominees.value) ? nomineeSeatNumbers.value : EMPTY_NUMBERS
const voteBlockedFor = (id: string) => headUserId.value === id ? voteBlocked.value : false
const offlineSeatsInGameFor = (id: string) => (headUserId.value === id && gamePhase.value === 'vote' && !currentFarewellSpeech.value) ? offlineAliveSeatNumbers.value : EMPTY_NUMBERS
const canShowHeadNominationsBadge = computed(() => {
  const nominationsPhase = gamePhase.value === 'day' || gamePhase.value === 'vote'
  if (!nominationsPhase) return false
  return nominateMode.value !== 'head' || isHead.value
})
const fitContainInGrid = computed(() => {
  const limit = roomUserLimit.value
  if (Number.isFinite(limit) && limit > 2) return !videoFillOn.value
  if (isTheater.value) return false
  const count = sortedPeerIds.value.length
  if (count >= 3) return false
  return Number.isFinite(limit) && limit === 2
})
const isSpectatorInGame = computed(() => {
  const id = localId.value
  if (!id || gamePhase.value === 'idle') return false
  return !seatsByUser[id]
})
const isSpectatorLike = computed(() => adminSpectator.value || isSpectatorInGame.value)
const hostBlurPending = ref(false)
const hostBlurToggleEnabled = computed(() => gamePhase.value === 'day' || gamePhase.value === 'vote')
const hostBlurVisible = computed(() => gamePhase.value !== 'idle' && hostBlurActive.value)
const hostBlurUsesHeadView = computed(() => isHead.value || isSpectatorInGame.value)
const hostBlurLocksControls = computed(() => isHead.value && hostBlurActive.value)
const ACTION_PHASES = ['day', 'vote', 'night'] as const
const canShowLeaveGameButton = computed(() =>
  myGameRole.value === 'player' &&
  amIAlive.value &&
  ACTION_PHASES.includes(gamePhase.value as (typeof ACTION_PHASES)[number])
)
const leaveGameActsAsFinishSpeech = computed(() => currentFarewellSpeech.value && isCurrentSpeaker.value)
const leaveGameButtonLabel = computed(() => leaveGameActsAsFinishSpeech.value ? 'Завершить речь' : 'Выйти из игры')
const canShowFoulButtons = computed(() =>
  !adminSpectator.value &&
  ACTION_PHASES.includes(gamePhase.value as (typeof ACTION_PHASES)[number])
)
const isMafiaLimitRoom = computed(() => roomUserLimit.value === gameLimitMin.value)
const canStartStreams = computed(() => settings.streamsCanStart || isAdminUser.value)
const canViewGameSettings = computed(() => !adminSpectator.value && isMafiaLimitRoom.value)
const canEditGameSettings = computed(() =>
  !adminSpectator.value &&
  (myRole.value === 'host' || isAdminUser.value) &&
  gamePhase.value === 'idle' &&
  isMafiaLimitRoom.value
)
const canShowMirrorToggle = computed(() =>
  !adminSpectator.value &&
  (gamePhase.value === 'idle' || (!isSpectatorInGame.value && amIAlive.value))
)
const canShowHotkeysToggle = computed(() =>
  !adminSpectator.value &&
  (gamePhase.value === 'idle' || (!isSpectatorInGame.value && amIAlive.value))
)
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
let foregroundMediaRetryShortId: number | null = null
let foregroundMediaRetryLongId: number | null = null
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
const roomTabTitle = computed(() => gamePhase.value === 'idle' ? `Участники: ${Math.max(0, totalPlayers.value)}` : 'Игра')
const canUseReadyStart = computed(() => {
  const limit = roomUserLimit.value
  const min = minReadyToStart.value
  if (!Number.isFinite(limit) || !Number.isFinite(min)) return false
  if (limit <= 0 || min <= 0) return false
  return limit === min + 1
})
const canUseReadyToggle = computed(() => !adminSpectator.value && canUseReadyStart.value)
const canShowHeadPicks = computed(() => isHead.value && knownRolesVisible.value)
const canShowStartGame = computed(() => {
  if (adminSpectator.value) return false
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
    if (!id) return
    const cur = statusByUser.get(id) ?? {}
    statusByUser.set(id, { ...cur, mirror: v ? 1 : 0 })
    try { await publishState({ mirror: v }) } catch {}
  },
})
const rerr = (...a: unknown[]) => console.error('[ROOM]', ...a)

let reloading = false
let roomDisconnectFailClosedTimer: number | null = null
function hardReload() {
  if (reloading) return
  reloading = true
  window.location.reload()
}

function clearRoomDisconnectFailClosedTimer() {
  if (roomDisconnectFailClosedTimer == null) return
  window.clearTimeout(roomDisconnectFailClosedTimer)
  roomDisconnectFailClosedTimer = null
}

function shouldDeferRoomDisconnectFailClosed(): boolean {
  if (!backgrounded.value) return false
  const phase = backgroundedPhase ?? gamePhase.value
  return phase === 'idle'
}

function armRoomDisconnectFailClosedTimer() {
  if (shouldDeferRoomDisconnectFailClosed()) return
  if (roomDisconnectFailClosedTimer != null) return
  roomDisconnectFailClosedTimer = window.setTimeout(async () => {
    roomDisconnectFailClosedTimer = null
    if (leaving.value) return
    if (!netReconnecting.value) return
    if (socket.value?.connected) return
    try { await rtc.disconnect() } catch {}
    if (navigator.onLine) hardReload()
  }, 6500)
}

function avatarKey(id: string): string {
  const name = avatarByUser.get(id) || ''
  if (!name) return ''
  return name.startsWith('avatars/') ? name : `avatars/${name}`
}
function userName(id: string) {
  return nameByUser.get(id) || `user${id}`
}
function themeColorFor(id: string): string | null {
  return themeColorByUser.get(id) ?? null
}
function themeIconFor(id: string): string | null {
  return themeIconByUser.get(id) ?? null
}

function applyProfileTheme(id: string, source: any): void {
  const themeColor = typeof source?.theme_color === 'string' && source.theme_color.trim() !== '' ? source.theme_color.trim() : null
  if (themeColor) themeColorByUser.set(id, themeColor)
  else themeColorByUser.delete(id)

  const themeIcon = typeof source?.theme_icon === 'string' && source.theme_icon.trim() !== '' ? source.theme_icon.trim() : null
  if (themeIcon) themeIconByUser.set(id, themeIcon)
  else themeIconByUser.delete(id)
}

function applyProfileRole(id: string, source: any): void {
  const role = typeof source?.role === 'string' && source.role.trim() !== '' ? source.role.trim() : ''
  if (role) profileRolesByUser.set(id, role)
  else profileRolesByUser.delete(id)
}

function applyRoomRoleSync(id: string, source: any): void {
  const role = typeof source?.role === 'string' && source.role.trim() !== '' ? source.role.trim() : ''
  const moderationRole = typeof source?.moderation_role === 'string' && source.moderation_role.trim() !== ''
    ? source.moderation_role.trim()
    : ''
  const baseRole = typeof source?.base_role === 'string' && source.base_role.trim() !== ''
    ? source.base_role.trim()
    : ''

  if (role) rolesByUser.set(id, role)
  if (moderationRole) moderationRolesByUser.set(id, moderationRole)
  else if (role) moderationRolesByUser.set(id, role)
  if (baseRole) profileRolesByUser.set(id, baseRole)
}

function memoRef<K, V>(cache: Map<K, V>, factory: (k: K) => V): (k: K) => V {
  return (k: K) => {
    const c = cache.get(k)
    if (c) return c
    const value = factory(k)
    cache.set(k, value)
    return value
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
function stateIconClass(kind: IconKind, id: string) {
  if (isBlocked(id, kind)) return 'blocked'
  return isOn(id, kind) ? 'on' : 'off'
}
function closePanels(except?: 'apps'|'settings'|'friends'|'game', opts?: { keepFriendsWhenConfirm?: boolean }) {
  const keepFriends =
    Boolean(opts?.keepFriendsWhenConfirm) &&
    confirmState.open &&
    friendsPanelOpen.value
  if (except !== 'apps') openApps.value = false
  if (except !== 'settings') settingsOpen.value = false
  if (except !== 'friends' && !keepFriends) friendsPanelOpen.value = false
  if (except !== 'game') gameParamsOpen.value = false
}

function canOpenMiniProfileFromTile(id: string): boolean {
  const uid = Number(id)
  return canOpenMiniProfileTarget({
    targetId: uid,
    viewerId: localId.value,
    viewerRole: userStore.user?.role,
    targetRole: profileRol(id),
  })
}

function openMiniProfileFromTile(id: string): void {
  const uid = Number(id)
  if (!canOpenMiniProfileFromTile(id)) return
  miniProfileUserId.value = uid
  miniProfileInitial.value = {
    id: uid,
    username: nameByUser.get(id) || null,
    avatar_name: avatarByUser.get(id) || null,
    role: profileRol(id),
    theme_color: themeColorFor(id),
    theme_icon: themeIconFor(id),
  }
  closePanels()
  miniProfileOpen.value = true
}

function toggleSettings() {
  const next = !settingsOpen.value
  if (next && chat.open) chat.closePanel()
  closePanels('settings')
  settingsOpen.value = next
  if (next) void rtc.refreshDevices().catch(() => {})
}
function toggleApps() {
  const next = !openApps.value
  if (next && chat.open) chat.closePanel()
  closePanels('apps')
  openApps.value = next
}
function toggleFriendsPanel() {
  if (!showRoomFriendsButton.value) {
    friendsPanelOpen.value = false
    return
  }
  const next = !friendsPanelOpen.value
  if (next && chat.open) chat.closePanel()
  closePanels('friends')
  friendsPanelOpen.value = next
}
function toggleGlobalChat() {
  if (chat.open) {
    chat.closePanel()
    return
  }
  closePanels()
  chat.openPanel()
}
function openGameSettings() {
  if (!canViewGameSettings.value) return
  const next = !gameParamsOpen.value
  if (next && chat.open) chat.closePanel()
  closePanels('game')
  gameParamsOpen.value = next
}
function applyRoomGameSnapshot(raw: unknown) {
  roomGameSnapshot.value = normalizeRoomGameParams(raw, {
    allowDisableSpectators: true,
  })
}
function onDocClick() {
  closePanels(undefined, { keepFriendsWhenConfirm: true })
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

type SpaceHotkeyAction =
  | 'goToMafiaTalk'
  | 'finishMafiaTalk'
  | 'startDay'
  | 'finishSpeechHead'
  | 'passSpeechHead'
  | 'startVote'
  | 'headVoteControl'
  | 'finishVote'
  | 'prepareVoteLift'
  | 'startVoteLift'
  | 'startLeaderSpeech'
  | 'restartVoteForLeaders'
  | 'goToNight'
  | 'startNightShoot'
  | 'startNightChecks'
  | 'startBestMove'
  | 'startDayFromNight'
  | 'finishSpeechSelf'
  | 'playerVote'

const spaceHotkeyAction = computed<SpaceHotkeyAction | null>(() => {
  if (gamePhase.value === 'idle') return null
  if (canShowHeadGoToMafiaTalkControl.value && canHeadGoToMafiaTalkControl.value) return 'goToMafiaTalk'
  if (canHeadFinishMafiaTalkControl.value) return 'finishMafiaTalk'
  if (canShowStartDay.value && canStartDay.value) return 'startDay'
  if (canShowFinishSpeechHead.value && canFinishSpeechHead.value && !hostBlurLocksControls.value) return 'finishSpeechHead'
  if (!canShowFinishSpeechHead.value && canShowPassSpeechHead.value && canPassSpeechHead.value && !hostBlurLocksControls.value) return 'passSpeechHead'
  if (canStartVote.value && !hostBlurLocksControls.value) return 'startVote'
  if (canHeadVoteControl.value && canPressHeadVoteControl.value && !hostBlurLocksControls.value && !hasOfflineAlivePlayers.value) return 'headVoteControl'
  if (canHeadFinishVoteControl.value && !hostBlurLocksControls.value) return 'finishVote'
  if (canPrepareVoteLift.value && !hostBlurLocksControls.value && !hasOfflineAlivePlayers.value) return 'prepareVoteLift'
  if (canStartVoteLift.value && !hostBlurLocksControls.value && !hasOfflineAlivePlayers.value) return 'startVoteLift'
  if (canShowStartLeaderSpeech.value && canStartLeaderSpeech.value && !hostBlurLocksControls.value) return 'startLeaderSpeech'
  if (canRestartVoteForLeaders.value && !hostBlurLocksControls.value) return 'restartVoteForLeaders'
  if (canShowNight.value && !hostBlurLocksControls.value && !hasOfflineAlivePlayers.value) return 'goToNight'
  if (canHeadNightShootControl.value && !hasOfflineAlivePlayers.value) return 'startNightShoot'
  if (canHeadNightCheckControl.value && !hasOfflineAlivePlayers.value) return 'startNightChecks'
  if (canHeadBestMoveControl.value) return 'startBestMove'
  if (canStartDayFromNight.value && canHeadDayFromNightControl.value) return 'startDayFromNight'
  if (canFinishSpeechSelf.value) return 'finishSpeechSelf'
  if (game.canPressVoteButton()) return 'playerVote'
  return null
})

const visibleSpaceHotkeyAction = computed<SpaceHotkeyAction | null>(() => {
  if (gamePhase.value === 'idle') return null
  if (canShowHeadGoToMafiaTalkControl.value) return 'goToMafiaTalk'
  if (canHeadFinishMafiaTalkControl.value) return 'finishMafiaTalk'
  if (canShowStartDay.value) return 'startDay'
  if (canShowFinishSpeechHead.value) return 'finishSpeechHead'
  if (!canShowFinishSpeechHead.value && canShowPassSpeechHead.value) return 'passSpeechHead'
  if (canStartVote.value) return 'startVote'
  if (canHeadVoteControl.value) return 'headVoteControl'
  if (canHeadFinishVoteControl.value) return 'finishVote'
  if (canPrepareVoteLift.value) return 'prepareVoteLift'
  if (canStartVoteLift.value) return 'startVoteLift'
  if (canShowStartLeaderSpeech.value) return 'startLeaderSpeech'
  if (canRestartVoteForLeaders.value) return 'restartVoteForLeaders'
  if (canShowNight.value) return 'goToNight'
  if (canHeadNightShootControl.value) return 'startNightShoot'
  if (canHeadNightCheckControl.value) return 'startNightChecks'
  if (canHeadBestMoveControl.value) return 'startBestMove'
  if (canStartDayFromNight.value) return 'startDayFromNight'
  if (canFinishSpeechSelf.value) return 'finishSpeechSelf'
  if (game.canPressVoteButton()) return 'playerVote'
  return null
})

function showSpaceHotkeyHint(action: SpaceHotkeyAction): boolean {
  return !IS_MOBILE && hotkeysVisible.value && visibleSpaceHotkeyAction.value === action
}

function tryHandleSpaceHotkey(): boolean {
  switch (spaceHotkeyAction.value) {
    case 'goToMafiaTalk':
      void goToMafiaTalkUi()
      return true
    case 'finishMafiaTalk':
      void finishMafiaTalkUi()
      return true
    case 'startDay':
      void startDayUi()
      return true
    case 'finishSpeechHead':
    case 'finishSpeechSelf':
      void finishSpeechUi()
      return true
    case 'passSpeechHead':
      void passSpeechUi()
      return true
    case 'startVote':
      void startVoteUi()
      return true
    case 'headVoteControl':
      void onHeadVoteControl()
      return true
    case 'finishVote':
      void finishVoteUi()
      return true
    case 'prepareVoteLift':
      void prepareVoteLiftUi()
      return true
    case 'startVoteLift':
      void startVoteLiftUi()
      return true
    case 'startLeaderSpeech':
      void startLeaderSpeechUi()
      return true
    case 'restartVoteForLeaders':
      void restartVoteForLeadersUi()
      return true
    case 'goToNight':
      void goToNightUi()
      return true
    case 'startNightShoot':
      void startNightShootUi()
      return true
    case 'startNightChecks':
      void startNightChecksUi()
      return true
    case 'startBestMove':
      void startBestMoveUi()
      return true
    case 'startDayFromNight':
      void startDayFromNightUi()
      return true
    case 'playerVote':
      void onVote()
      return true
    default:
      return false
  }
}
function onHotkey(e: KeyboardEvent) {
  if (e.defaultPrevented || e.repeat) return
  if (isEditableTarget(e.target)) return
  if (confirmState.open) return
  if (e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return
  const code = e.code

  if (code === 'KeyP') {
    if (gamePhase.value !== 'idle' && isHead.value && hostBlurToggleEnabled.value && !hostBlurPending.value) {
      e.preventDefault()
      e.stopPropagation()
      void toggleHostBlur()
    }
    return
  }
  if (code === 'KeyC') {
    if (!adminSpectator.value && (gamePhase.value === 'idle' || isHead.value) && !pending.cam && !blockedSelf.value.cam) {
      e.preventDefault()
      e.stopPropagation()
      void toggleCam()
    }
    return
  }
  if (code === 'KeyM') {
    if (!adminSpectator.value && (gamePhase.value === 'idle' || isHead.value) && !pending.mic && !blockedSelf.value.mic) {
      e.preventDefault()
      e.stopPropagation()
      void toggleMic()
    }
    return
  }
  if (code === 'Space') {
    e.preventDefault()
    e.stopPropagation()
    if (!adminSpectator.value && !hostBlurActive.value && (gamePhase.value === 'idle' || isHead.value || amIAlive.value)) {
      tryHandleSpaceHotkey()
    }
    return
  }

  if (hostBlurActive.value) return
  if (gamePhase.value !== 'idle' && !(isHead.value || amIAlive.value)) return

  if (code === 'Enter' || code === 'NumpadEnter') {
    if (gamePhase.value !== 'idle' && canShowTakeFoulSelf.value && canTakeFoulSelf.value && !foulPending.value) {
      e.preventDefault()
      e.stopPropagation()
      void takeFoulUi()
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

  if (gamePhase.value !== 'idle') return

  if (code === 'KeyS') {
    if (!pending.speakers && !blockedSelf.value.speakers) {
      e.preventDefault()
      e.stopPropagation()
      void toggleSpeakers()
    }
    return
  }
}

function toggleKnownRolesUi(): void {
  if (!canToggleKnownRoles.value) return
  game.toggleKnownRolesVisibility()
}
async function onToggleRoomHotkeys(next: boolean): Promise<void> {
  if (hotkeysTogglePending.value) return
  hotkeysTogglePending.value = true
  try { await userStore.setHotkeysVisible(next) }
  finally { hotkeysTogglePending.value = false }
}
function volumeIcon(val: number, enabled: boolean) {
  if (!enabled) return iconVolumeMute
  const v = Math.round(val)
  return v < 1 ? iconVolumeMute : v < 25 ? iconVolumeLow : v < 100 ? iconVolumeMid : iconVolumeMax
}
function volumeIconForUser(id: string) {
  return volumeIcon(volumeFor(id), speakersOn.value && !isBlocked(id,'speakers'))
}
function volumeIconForStream(key: string) {
  if (!key) return iconVolumeMute
  return volumeIcon(volumeFor(key), speakersOn.value && !isBlocked(screenOwnerId.value,'speakers'))
}

const BGM_ACTIVE_PHASES: GamePhase[] = ['roles_pick', 'mafia_talk_start', 'mafia_talk_end', 'night']
const bgmShouldPlay = computed(() => musicEnabled.value && BGM_ACTIVE_PHASES.includes(gamePhase.value))

function syncBgmPlayback(opts?: { forceStop?: boolean }) {
  if (bgmShouldPlay.value) {
    rtc.setBgmPlaying(true)
    return
  }
  if (opts?.forceStop !== false) {
    rtc.forceStopBgm()
    return
  }
  rtc.setBgmPlaying(false)
}

watch(bgmShouldPlay, (on) => {
  if (on) {
    rtc.setBgmPlaying(true)
    return
  }
  rtc.forceStopBgm()
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
speechGongAudio.volume = 0.5

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

function showTransientToast(title: string, text: string): void {
  window.dispatchEvent(new CustomEvent('toast', {
    detail: {
      title,
      text,
      date: new Date().toISOString(),
      kind: 'info',
      read: true,
      ttl_ms: 30000,
    },
  }))
}

const sendAckGame: SendAckFn = (event, payload, timeoutMs) => sendAck(event, payload, timeoutMs)
const startGameUi = async () => {
  if (adminSpectator.value) return
  if (!canUseReadyStart.value) return
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
  if (isSpectatorLike.value) return false
  if (!needsMediaAccess.value) return false
  const needAudio = wantsAudioRequest.value && (!rtc.hasAudioInput.value || !rtc.permAudio.value)
  const needVideo = wantsVideoRequest.value && (!rtc.hasVideoInput.value || !rtc.permVideo.value)
  return needAudio || needVideo
})

async function requestMediaPermissions(opts?: { force?: boolean }) {
  if (isSpectatorLike.value) return
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
  if (isSpectatorLike.value) return
  rtc.primeAudioOnGesture()
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
  const ids = Array.from(idsSet).filter(id => !(adminSpectator.value && id === localId.value))
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

const miniProfileRoomUserId = computed(() => {
  if (!miniProfileOpen.value) return ''
  const uid = Number(miniProfileUserId.value || 0)
  if (!Number.isFinite(uid) || uid <= 0) return ''
  const id = String(Math.trunc(uid))
  return sortedPeerIds.value.includes(id) ? id : ''
})
const showMiniProfileRoomVolume = computed(() => {
  const id = miniProfileRoomUserId.value
  return Boolean(id && id !== localId.value)
})
const miniProfileRoomVolumeDisabled = computed(() => {
  const id = miniProfileRoomUserId.value
  return !id || !speakersOn.value || isBlocked(id, 'speakers')
})
const showMiniProfileRoomAdminActions = computed(() => {
  const id = miniProfileRoomUserId.value
  return Boolean(id && id !== localId.value && gamePhase.value === 'idle' && canModerate(id))
})
const showMiniProfileRoomControls = computed(() => showMiniProfileRoomVolume.value || showMiniProfileRoomAdminActions.value)
const miniProfileRoomControls = computed(() => {
  const id = miniProfileRoomUserId.value
  if (!id || !showMiniProfileRoomControls.value) return null

  return {
    showVolume: showMiniProfileRoomVolume.value,
    volume: volumeFor(id),
    volumeIcon: volumeIconForUser(id),
    volumeDisabled: miniProfileRoomVolumeDisabled.value,
    showAdminActions: showMiniProfileRoomAdminActions.value,
    micIcon: stateIcon('mic', id),
    micIconClass: stateIconClass('mic', id),
    camIcon: stateIcon('cam', id),
    camIconClass: stateIconClass('cam', id),
    speakersIcon: stateIcon('speakers', id),
    speakersIconClass: stateIconClass('speakers', id),
    screenIcon: stateIcon('screen', id),
    screenIconClass: stateIconClass('screen', id),
  }
})

function onMiniProfileRoomVolume(v: number): void {
  const id = miniProfileRoomUserId.value
  if (!id || !showMiniProfileRoomVolume.value) return
  onVol(id, v)
}

function onMiniProfileRoomBlock(key: 'mic' | 'cam' | 'speakers' | 'screen'): void {
  const id = miniProfileRoomUserId.value
  if (!id || !showMiniProfileRoomAdminActions.value) return
  void toggleBlock(id, key)
}

function onMiniProfileRoomKick(): void {
  const id = miniProfileRoomUserId.value
  if (!id || !showMiniProfileRoomAdminActions.value) return
  void kickUser(id)
}

watch(
  [() => route.name, roomTabTitle],
  ([name, title]) => {
    if (name !== 'room') return
    setPageTitle(title, { syncAppleTitle: true })
  },
  { immediate: true }
)

const getIdleGridStyle = (cols: number, rows: number) => {
  const key = `${cols}x${rows}`
  const cached = IDLE_GRID_STYLE_CACHE.get(key)
  if (cached) return cached
  const next = Object.freeze({
    gridTemplateColumns: `repeat(${cols}, 1fr)`,
    gridTemplateRows: `repeat(${rows}, 1fr)`,
  })
  IDLE_GRID_STYLE_CACHE.set(key, next)
  return next
}
const getSeatTileStyle = (pos: number) => {
  const cached = SEAT_TILE_STYLE_CACHE.get(pos)
  if (cached) return cached
  const col = GAME_COLUMN_INDEX[pos] ?? 1
  const row = GAME_ROW_INDEX[pos] ?? 1
  const next = Object.freeze({
    gridColumn: `${col} / span 2`,
    gridRow: `${row} / span 2`,
  })
  SEAT_TILE_STYLE_CACHE.set(pos, next)
  return next
}
const gridStyle = computed(() => {
  if (gamePhase.value !== 'idle') {
    return GAME_GRID_STYLE
  }
  const limit = roomUserLimit.value
  const isTwoSeatRoom = Number.isFinite(limit) && limit === 2
  const count = sortedPeerIds.value.length
  const cols = count <= 2 ? (isTwoSeatRoom ? 2 : 3) : count <= 6 ? 3 : 4
  const rows = count <= 2 ? (isTwoSeatRoom ? 1 : 2) : count <= 6 ? 2 : 3
  return getIdleGridStyle(cols, rows)
})

const tileGridStyle = (id: string) => {
  if (gamePhase.value === 'idle') return EMPTY_STYLE
  const pos = seatsByUser[id]
  if (!pos) return EMPTY_STYLE
  return getSeatTileStyle(pos)
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

function statusPatch(patch: any): Partial<StatusState> {
  const out: Partial<StatusState> = {}
  if (!patch || typeof patch !== 'object') return out
  if (!isEmpty((patch as any).mic)) out.mic = norm01((patch as any).mic, 0)
  if (!isEmpty((patch as any).cam)) out.cam = norm01((patch as any).cam, 0)
  if (!isEmpty((patch as any).speakers)) out.speakers = norm01((patch as any).speakers, 0)
  if (!isEmpty((patch as any).visibility)) out.visibility = norm01((patch as any).visibility, 0)
  if (!isEmpty((patch as any).ready)) out.ready = norm01((patch as any).ready, 0)
  if (!isEmpty((patch as any).mirror)) out.mirror = norm01((patch as any).mirror, 0)
  return out
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
  const applied = rtc.setUserVolume(id, next)
  if (applied !== next) {
    clearVolumeSnap(id)
    volUi[id] = applied
  }
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
    const current = volumeFor(uid)
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
function moderationRol(id: string): string { return moderationRolesByUser.get(id) || rol(id) }
function profileRol(id: string): string { return profileRolesByUser.get(id) || rol(id) }
const myRole = computed(() => rol(localId.value))

function normRole(value: string): string {
  return String(value || '').trim().toLowerCase()
}

function actionRol(id: string): string {
  const roomRole = normRole(rol(id))
  const moderationRole = normRole(moderationRol(id))
  const profileRole = normRole(profileRol(id))
  if (moderationRole === 'admin' || profileRole === 'admin') return 'admin'
  if (roomRole === 'host') return 'host'
  if (moderationRole === 'moder' || profileRole === 'moder') return 'moder'
  if (roomRole === 'head') return 'head'
  return 'user'
}

function canUseRoomAdminActions(): boolean {
  const id = localId.value
  if (!id) return false
  if (adminSpectator.value) return isAdminUser.value
  return positionByUser.has(id) || rolesByUser.has(id)
}

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
  if (kind === 'cam') {
    if (st && st.cam !== undefined) return st.cam === 1
    if (!st) return true
    return rtc.hasRemoteCameraTrack(id)
  }
  if (kind === 'mic') {
    return st && st.mic !== undefined ? st.mic === 1 : true
  }
  if (kind === 'speakers') return st && st.speakers !== undefined ? st.speakers === 1 : true
  if (kind === 'visibility') return st && st.visibility !== undefined ? st.visibility === 1 : true
  return st && st[kind] !== undefined ? st[kind] === 1 : true
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
    const id = localId.value
    if (!id) return
    const cur = statusByUser.get(id) ?? {}
    statusByUser.set(id, { ...cur, ready: v ? 1 : 0 })
  }
})
const isReady = (id: string) => (statusByUser.get(id)?.ready ?? 0) === 1

async function ensureReadyAllowed(): Promise<boolean> {
  if (userStore.suspendActive) {
    void alertDialog('Вам временно запрещено участие в играх')
    return false
  }
  return true
}

async function toggleReady() {
  if (!canUseReadyToggle.value) return
  if (!(await ensureReadyAllowed())) return
  const want = !readyOn.value
  readyOn.value = want
  try {
    await publishState({ ready: want })
  } catch {}
}

function canModerate(targetId: string): boolean {
  if (targetId === localId.value) return false
  if (gamePhase.value !== 'idle') return false
  if (!canUseRoomAdminActions()) return false
  const me = adminSpectator.value && isAdminUser.value ? 'admin' : actionRol(localId.value)
  const trg = actionRol(targetId)
  if (me === trg) return false
  if (me === 'admin') return trg !== 'admin'
  if (me === 'host') return trg === 'moder' || trg === 'user'
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
    title: 'Выгнать пользователя',
    text: 'Вы уверены, что хотите выгнать пользователя?',
    confirmText: 'Подтвердить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  const resp = await sendAck('kick', { user_id: Number(targetId) })
  if (!ensureOk(resp, { 403: 'Недостаточно прав', 404: 'Пользователь не в комнате' }, 'Сеть/таймаут при удалении')) return
}

function applyPeerState(uid: string, patch: any) {
  const nextPatch = statusPatch(patch)
  if (Object.keys(nextPatch).length === 0) return
  const cur = statusByUser.get(uid) ?? {}
  statusByUser.set(uid, { ...cur, ...nextPatch })
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
  moderationRolesByUser.delete(id)
  profileRolesByUser.delete(id)
  nameByUser.delete(id)
  avatarByUser.delete(id)
  themeColorByUser.delete(id)
  themeIconByUser.delete(id)
  videoRefMemo.delete(id)
  screenRefMemo.delete(id)
  offlineInGame.delete(id)
  clearVolumeSnap(id)
  clearVolumeSnap(rtc.screenKey(id))
  delete volUi[id]
  delete volUi[rtc.screenKey(id)]
  if (screenOwnerId.value === id) setScreenOwner('')
}

function clearScreenVolume(id: string | null | undefined) {
  if (!id) return
  clearVolumeSnap(rtc.screenKey(id))
  delete volUi[rtc.screenKey(id)]
}

function setScreenOwner(id: string, quality?: unknown) {
  const prev = screenOwnerId.value
  screenOwnerId.value = id
  screenQuality.value = id
    ? normalizeScreenQuality(quality, id === prev ? screenQuality.value : 'low')
    : 'low'
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
    socket.value?.io.on('reconnect',         () => {
      netReconnecting.value = false
      clearRoomDisconnectFailClosedTimer()
    })
  } catch {}

socket.value?.on('connect', async () => {
  netReconnecting.value = false
  clearRoomDisconnectFailClosedTimer()
  if (!leaving.value) {
    rtc.setVideoSubscriptionsForAll(false)
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
    if (!leaving.value) {
      netReconnecting.value = true
      if (shouldDeferRoomDisconnectFailClosed()) clearRoomDisconnectFailClosedTimer()
      else armRoomDisconnectFailClosedTimer()
    }
  })

  socket.value.on('force_logout', async (p: any) => {
    const reason = String(p?.reason || '')
    try { await onLeave() } finally { await auth.localSignOut?.() }
    if (reason === 'replaced') {
      void alertDialog('Сессия завершена: вход выполнен с другого устройства')
    } else if (reason === 'account_deleted') {
      void alertDialog('Сессия завершена: аккаунт удалён')
    } else {
      void alertDialog('Сессия завершена, войдите снова')
    }
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
    if (p?.moderation_role) moderationRolesByUser.set(id, String(p.moderation_role))
    else if (p?.role) moderationRolesByUser.set(id, String(p.role))
    const profileRole = typeof p?.profile_role === 'string' ? p.profile_role : p?.base_role
    applyProfileRole(id, { role: profileRole })
    if (p?.blocks) applyBlocks(id, p.blocks)
    const av = p?.avatar_name
    if (typeof av === 'string' && av.trim() !== '') avatarByUser.set(id, av)
    else avatarByUser.delete(id)
    const un = p?.username
    if (typeof un === 'string' && un.trim() !== '') nameByUser.set(id, String(un))
    else nameByUser.delete(id)
    applyProfileTheme(id, p)
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

  socket.value.on('profile_theme_sync', (p: any) => {
    const id = String(p?.user_id || '')
    if (!id) return
    ensurePeer(id)
    applyProfileTheme(id, p)
  })

  socket.value.on('role_sync', (p: any) => {
    const id = String(p?.user_id || '')
    if (!id) return
    ensurePeer(id)
    applyRoomRoleSync(id, p)
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
        setScreenOwner('')
      }
    }
  })

  function roomKickAlertText(p: any): string {
    const role = String(p?.by?.role || '').trim().toLowerCase()
    const baseRole = String(p?.by?.base_role || '').trim().toLowerCase()
    if (role === 'host') return 'Вы были кикнуты владельцем комнаты'
    if (role === 'admin' || baseRole === 'admin') return 'Вы были кикнуты администратором'
    return 'Вас кикнули из комнаты'
  }

  socket.value.on('force_leave', async (p:any) => {
    const reason = String(p?.reason || '')
    try { await onLeave() } catch {}
    if (reason === 'admin_spectator_game_start') {
      return
    } else if (reason === 'admin_kick_all') {
      void alertDialog('Упс, кажется пришло обновление! Перезагрузка серверов займет ~5 минут')
    } else if (reason === 'room_kick') {
      void alertDialog(roomKickAlertText(p))
    } else if (reason === 'sanction_timeout') {
      void alertDialog('Вам выдан таймаут: вы кикнуты из комнаты')
    } else if (reason === 'sanction_ban') {
      void alertDialog('Ваш аккаунт забанен: вы кикнуты из комнаты')
    } else if (reason === 'room_deleted') {
      void alertDialog('Комната была удалена администратором')
    } else if (reason === 'single_timeout') {
      const minutes = Number(p?.minutes || 0)
      if (Number.isFinite(minutes) && minutes > 0) {
        void alertDialog(`Вы были автоматически кикнуты т.к. последние ${minutes} минут вы находились в комнате один`)
      } else {
        void alertDialog('Вы были автоматически кикнуты т.к. длительное время вы находились в комнате один')
      }
    }
  })

  socket.value.on('screen_owner', (p: any) => {
    setScreenOwner(p?.user_id ? String(p.user_id) : '', p?.quality)
  })

  socket.value.on('room_game_updated', (p: any) => {
    const roomId = Number(p?.room_id || 0)
    if (roomId && roomId !== rid) return
    applyRoomGameSnapshot(p?.game ?? p)
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
    }
    statusByUser.forEach((st, uid) => {
      statusByUser.set(uid, { ...st, ready: 0 as 0 })
    })
    enforceMinGameVolumes()
    void enforceInitialGameControls()
  })

  socket.value?.on('game_limits', (p: any) => {
    const roomId = Number(p?.room_id || 0)
    if (roomId && roomId !== rid) return
    game.handleGameLimits(p)
  })

  socket.value?.on('game_finished', (p: any) => {
    game.handleGameFinished(p)
    if (myGameRole.value === 'player') void restoreAfterGameEnd()
  })

  socket.value?.on('game_ended', async (p: any) => {
    const reason = String(p?.reason || '')
    const spectatorBeforeEnd = isSpectatorInGame.value
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
    if (spectatorBeforeEnd) {
      await onLeave()
      return
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
    }
    syncBgmPlayback({ forceStop: true })
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
      showTransientToast('Вам подмигнули!', `${seat}й игрок подмигнул`)
    } else {
      showTransientToast('Вам подмигнули!', 'Игрок подмигнул вам')
    }
  })
  socket.value.on('game_wink_spotted', (p: any) => {
    const fromSeat = Number(p?.from_seat || 0)
    const toSeat = Number(p?.to_seat || 0)
    if (fromSeat > 0 && toSeat > 0) {
      showTransientToast('Вы наблюдательны!', `Вы заметили как ${fromSeat}й подмигнул ${toSeat}му`)
    } else {
      showTransientToast('Вы наблюдательны!', 'Вы заметили подмигивание')
    }
  })
  socket.value.on('game_knocked', (p: any) => {
    const seat = Number(p?.from_seat || 0)
    const count = Number(p?.count || 0)
    if (seat > 0 && count > 0) {
      showTransientToast('Вам отстучали!', `${seat}й игрок отстучал ${count}`)
    } else if (seat > 0) {
      showTransientToast('Вам отстучали!', `${seat}й игрок отстучал`)
    } else {
      showTransientToast('Вам отстучали!', 'Игрок отстучал вам')
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
    if ((p as any)?.best_move?.active) rtc.forceStopBgm()
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

  socket.value.on('game_vote_presence_break', (p: any) => {
    const id = String((p as any)?.user_id || '')
    if (!id) return
    const candidateId = String((p as any)?.candidate_uid || '')
    game.maybeAskRevoteOnDisconnect(id, sendAckGame, candidateId)
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
    return await sendAck('join', {
      room_id: rid,
      state: { ...local },
      admin_spectator: adminSpectatorRequested.value,
    })
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
  if (!adminSpectator.value) {
    if (gamePhase.value === 'idle') return
    if (amIAlive.value) return
  }
  if (!localId.value) return
  const isSpectator = isSpectatorLike.value
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
    setScreenOwner('')
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

function clampLocalVisibilityForCurrentPhase(): void {
  const phase = gamePhase.value
  if (phase === 'idle') return
  const target = gameReturnTargets(phase)
  const nextVisibility = target.visibility && !blockedSelf.value.visibility
  if (local.visibility !== nextVisibility) {
    local.visibility = nextVisibility
  }
}

function applyJoinAck(j: any) {
  adminSpectator.value = !!j?.admin_spectator
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
    const id = String(uid)
    const next = statusPatch(st)
    if (Object.keys(next).length) statusByUser.set(id, next)
  }

  const ids = new Set<string>(rtc.peerIds.value)
  Object.keys(j.snapshot || {}).forEach(uid => ids.add(String(uid)))
  Object.keys(j.positions || {}).forEach(uid => ids.add(String(uid)))
  rtc.peerIds.value = [...ids]

  blockByUser.clear()
  for (const [uid, bl] of Object.entries((j.blocked || {}) as Record<string, any>)) {
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

  moderationRolesByUser.clear()
  for (const [uid, r] of Object.entries(j.moderation_roles || j.roles || {})) {
    moderationRolesByUser.set(String(uid), String(r || 'user'))
  }

  profileRolesByUser.clear()
  const prof = j.profiles || {}
  for (const [uid, m] of Object.entries(prof)) {
    const id = String(uid)
    const mm = m as any
    if (typeof mm?.avatar_name === 'string' && mm.avatar_name.trim() !== '') avatarByUser.set(id, mm.avatar_name)
    else avatarByUser.delete(id)
    if (typeof mm?.username === 'string' && mm.username.trim() !== '') nameByUser.set(id, String(mm.username))
    else nameByUser.delete(id)
    applyProfileTheme(id, mm)
    applyProfileRole(id, mm)
  }

  if (j.self_pref) applySelfPref(j.self_pref)
  setScreenOwner(j.screen_owner ? String(j.screen_owner) : '', j.screen_quality)
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
  }
  syncBgmPlayback({ forceStop: true })
  clampLocalVisibilityForCurrentPhase()
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
  if (adminSpectator.value && (k === 'mic' || k === 'cam')) return
  if (pending[k]) return
  if (blockedSelf.value[k]) return
  if ((k === 'mic' || k === 'cam') && gamePhase.value !== 'idle' && isSpectatorInGame.value) return
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
  if (adminSpectator.value) return
  if (pendingScreen.value) return
  const wantEnable = !isMyScreen.value
  if (wantEnable && !canStartStreams.value) {
    void alertDialog('Запуск трансляций отключен')
    return
  }
  const confirmPayload = {
    title: wantEnable ? 'Запуск трансляции' : 'Остановка трансляции',
    text: wantEnable
      ? 'Вы уверены, что хотите запустить трансляцию экрана?'
      : 'Вы уверены, что хотите остановить трансляцию экрана?',
    confirmText: wantEnable ? 'Запустить' : 'Остановить',
    cancelText: 'Отмена',
  }
  let requestedScreenQuality: ScreenShareQuality = 'low'
  let confirmed: boolean
  if (wantEnable) {
    const hasSubscription = userStore.subscriptionActive
    const result = await confirmDialogWithRadio({
      ...confirmPayload,
      radioOptions: SCREEN_QUALITY_OPTIONS.map(option => ({
        ...option,
        disabled: !hasSubscription && option.value !== 'low',
        tooltip: !hasSubscription && option.value !== 'low'
          ? SCREEN_QUALITY_HINT
          : undefined,
      })),
      radioDefault: hasSubscription ? 'high' : 'low',
    })
    confirmed = result.ok
    requestedScreenQuality = hasSubscription
      ? normalizeScreenQuality(result.radioValue, 'medium')
      : 'low'
  } else {
    confirmed = await confirmDialog(confirmPayload)
  }
  if (!confirmed) return
  pendingScreen.value = true
  try {
    if (wantEnable) {
      const resp = await sendAck('screen', { on: true, quality: requestedScreenQuality })
      if (!resp || !resp.ok) {
        if (resp?.status === 409 && resp?.owner) setScreenOwner(String(resp.owner), resp?.quality)
        else if (resp?.status === 403 && resp?.error === 'streams_start_disabled') void alertDialog('Запуск трансляций отключен')
        else if (resp?.status === 403 && resp?.error === 'blocked') void alertDialog('Стрим запрещён администратором')
        else void alertDialog('Не удалось запустить трансляцию')
        return
      }
      const nextScreenQuality = normalizeScreenQuality(resp?.quality, requestedScreenQuality)
      const ok = await rtc.startScreenShare({ audio: true, quality: nextScreenQuality })
      if (ok) {
        setScreenOwner(localId.value, nextScreenQuality)
        return
      }
      if (!ok) {
        await sendAck('screen', { on: false, canceled: true })
        setScreenOwner('')
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
      ? 'Начать паузу? Игроки не смогут видеть друг друга и брать фолы. Пауза завершится автоматически через 2 минуты.'
      : 'Завершить паузу?',
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

function joinFailureMessage(j: any): string {
  const st = Number(j?.status || 0)
  const code = String(j?.error || '')
  if (st === 403 && code === 'room_owner_blacklisted_requester') return 'Вход запрещен: Вы находитесь в ЧС у владельца комнаты'
  if (st === 403 && code === 'hidden_room') return 'Комната скрыта, вход доступен только по приглашению'
  if (!j) return 'Таймаут сети при входе в комнату'
  if (st === 404) return 'Комната не найдена'
  if (st === 410) return 'Комната закрыта'
  if (st === 409 && code === 'active_alive_game_conflict') return 'Вы живой игрок в другой активной игре'
  if (st === 409 && code === 'admin_spectator_unavailable') return 'Игра уже началась'
  if (st === 409 && code === 'game_in_progress') return 'В комнате нет мест для зрителей'
  if (st === 409 && code === 'spectators_full') return 'В комнате нет мест для зрителей'
  if (st === 409) return 'Комната заполнена'
  if (st === 429) {
    const retryAfter = Number(j?.retry_after || 0)
    if (Number.isFinite(retryAfter) && retryAfter > 0) {
      return `Слишком много попыток входа. Повторите через ${Math.ceil(retryAfter)} сек`
    }
    return 'Слишком много попыток входа. Повторите чуть позже'
  }
  if (st === 400 && code === 'bad_room_id') return 'Некорректный идентификатор комнаты'
  if (st >= 500 || code === 'internal') return 'Сервис комнаты временно недоступен. Попробуйте снова'
  if (st > 0 || code) return `Ошибка входа в комнату (${st || 'no_status'}${code ? `, ${code}` : ''})`
  return 'Ошибка входа в комнату'
}

async function handleJoinFailure(j: any) {
  if (leaving.value) return
  if (j?.status === 403 && j?.error === 'rooms_entry_disabled') {
    void alertDialog('Вход в комнату заблокирован')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  if (j?.status === 403 && j?.error === 'user_timeout') {
    void alertDialog('Вам выдан таймаут — вход в комнату недоступен')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  if (j?.status === 403 && j?.error === 'not_verified') {
    void alertDialog('Для входа в комнату требуется верификация')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  if (j?.status === 403 && j?.error === 'user_banned') {
    void alertDialog('Аккаунт забанен — вход в комнату недоступен')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  if (j?.status === 403 && j?.error === 'room_owner_blacklisted_requester') {
    void alertDialog('Вход запрещен: Вы находитесь в ЧС у владельца комнаты')
    if (j?.hidden) await router.replace({ name: 'home' })
    else await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  if (j?.status === 403 && j?.error === 'hidden_room') {
    void alertDialog('Комната скрыта, вход доступен только по приглашению')
    await router.replace({ name: 'home' })
    return
  }
  if (j?.status === 403 && j?.error === 'private_room') {
    if (j?.hidden) {
      void alertDialog('Комната скрыта, вход доступен только по приглашению')
      await router.replace({ name: 'home' })
      return
    }
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
  if (j?.status === 409 && j?.error === 'active_alive_game_conflict') {
    void alertDialog('Вы живой игрок в другой активной игре')
    const activeRoomId = Number(j?.room_id || 0)
    if (Number.isFinite(activeRoomId) && activeRoomId > 0 && activeRoomId !== rid) {
      await router.replace(`/room/${activeRoomId}`)
    } else {
      await router.replace({ name: 'home', query: { focus: String(rid) } })
    }
    return
  }
  if (j?.status === 409 && j?.error === 'admin_spectator_unavailable') {
    void alertDialog('Игра уже началась')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  if (j?.status === 409 && (j?.error === 'game_in_progress' || j?.error === 'spectators_full')) {
    void alertDialog('В комнате нет мест для зрителей')
    await router.replace({ name: 'home', query: { focus: String(rid) } })
    return
  }
  void alertDialog(joinFailureMessage(j))
  await router.replace('/')
}

async function onLeave(goHome = true) {
  if (leaving.value) return
  leaving.value = true
  try {
      document.removeEventListener('click', onDocClick)
      document.removeEventListener('visibilitychange', onBackgroundVisibility)
      window.removeEventListener('pagehide', onBackgroundVisibility)
      window.removeEventListener('pageshow', handleForegroundSignal)
      window.removeEventListener('focus', handleForegroundSignal)
      window.removeEventListener('keydown', onHotkey)
  } catch {}
  clearRoomDisconnectFailClosedTimer()
  clearForegroundMediaRecoveryTimers()
  try {
    await stopScreenBeforeLeave()
    const s = socket.value
    socket.value = null
    if (s) {
      if (s.connected) {
        try { await s.timeout(800).emitWithAck('leave', { room_id: rid }) } catch {}
      }
      disposeAuthedSocket(s)
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
    setScreenOwner('')
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
      scheduleForegroundMediaRecovery()
      return
    }
  }
  if (phase !== 'idle') {
    await applyGameReturnState()
  }
  scheduleForegroundMediaRecovery()
}

function clearForegroundMediaRecoveryTimers(): void {
  if (foregroundMediaRetryShortId != null) {
    window.clearTimeout(foregroundMediaRetryShortId)
    foregroundMediaRetryShortId = null
  }
  if (foregroundMediaRetryLongId != null) {
    window.clearTimeout(foregroundMediaRetryLongId)
    foregroundMediaRetryLongId = null
  }
}

async function reassertForegroundMediaTracks(): Promise<void> {
  if (!IS_MOBILE || leaving.value || backgrounded.value) return
  if (!rtc.lk.value) return
  if (local.cam && desiredMedia.cam && !blockedSelf.value.cam) {
    try { await rtc.enable('videoinput') } catch {}
  }
  if (local.mic && desiredMedia.mic && !blockedSelf.value.mic) {
    try { await rtc.enable('audioinput') } catch {}
  }
}

function scheduleForegroundMediaRecovery(): void {
  clearForegroundMediaRecoveryTimers()
  void reassertForegroundMediaTracks()
  foregroundMediaRetryShortId = window.setTimeout(() => {
    foregroundMediaRetryShortId = null
    void reassertForegroundMediaTracks()
  }, 400)
  foregroundMediaRetryLongId = window.setTimeout(() => {
    foregroundMediaRetryLongId = null
    void reassertForegroundMediaTracks()
  }, 1400)
}

function handleForegroundSignal() {
  if (!IS_MOBILE) return
  if (leaving.value) return
  if (!backgrounded.value) return
  local.visibility = false
  rtc.setVideoSubscriptionsForAll(false)
  backgrounded.value = false
  if (netReconnecting.value && !socket.value?.connected) {
    armRoomDisconnectFailClosedTimer()
  }
  void restoreAfterBackgroundFromServer()
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

function onBackgroundVisibility(e?: Event) {
  const type = (e as any)?.type
  const hidden = document.visibilityState === 'hidden' || type === 'pagehide'
  if (hidden) rtc.flushVolumePrefs()
  if (!IS_MOBILE) return
  if (leaving.value) return
  if (hidden) {
    if (isSpectatorInGame.value) {
      void onLeave()
      return
    }
    void applyBackgroundMute()
  } else {
    handleForegroundSignal()
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

watch(canViewGameSettings, (ok) => {
  if (!ok && gameParamsOpen.value) gameParamsOpen.value = false
})

watch(() => [gamePhase.value, amIAlive.value, isSpectatorLike.value, adminSpectator.value, localId.value], () => {
  void enforceNoPublishWhenInactive()
}, { immediate: true })

let speechAudioKickId: number | null = null
let speechAudioRetryShortId: number | null = null
let speechAudioRetryLongId: number | null = null
function clearSpeechAudioKickTimer(): void {
  if (speechAudioKickId != null) {
    window.clearTimeout(speechAudioKickId)
    speechAudioKickId = null
  }
}
function clearSpeechAudioRecoveryTimers(): void {
  if (speechAudioRetryShortId != null) {
    window.clearTimeout(speechAudioRetryShortId)
    speechAudioRetryShortId = null
  }
  if (speechAudioRetryLongId != null) {
    window.clearTimeout(speechAudioRetryLongId)
    speechAudioRetryLongId = null
  }
}
async function recoverSpeechAudioPlayback(): Promise<void> {
  if (!IS_MOBILE || leaving.value || backgrounded.value) return
  if (!rtc.lk.value || !hasRemotePeers.value) return
  if (!speakersOn.value || blockedSelf.value.speakers) return
  try { await rtc.startAudio() } catch {}
  try { rtc.setAudioSubscriptionsForAll(true) } catch {}
  try { await rtc.resumeAudio() } catch {}
}
function scheduleSpeechAudioRecovery(): void {
  if (!IS_MOBILE) return
  clearSpeechAudioRecoveryTimers()
  const run = () => { void recoverSpeechAudioPlayback() }
  run()
  speechAudioRetryShortId = window.setTimeout(() => {
    speechAudioRetryShortId = null
    run()
  }, 250)
  speechAudioRetryLongId = window.setTimeout(() => {
    speechAudioRetryLongId = null
    run()
  }, 900)
}
function kickSpeechAudio() {
  if (speechAudioKickId != null) return
  speechAudioKickId = window.setTimeout(() => {
    speechAudioKickId = null
    void recoverSpeechAudioPlayback()
  }, 100)
}

watch(
  () => [gamePhase.value, game.daySpeech.currentId, speakersOn.value, blockedSelf.value.speakers, backgrounded.value],
  ([phase, cur, speakers, speakersBlocked, bg], [_prevPhase, prevCur]) => {
    if (!IS_MOBILE) return
    if (bg || !speakers || speakersBlocked) {
      clearSpeechAudioRecoveryTimers()
      return
    }
    if ((phase !== 'day' && phase !== 'vote') || !cur) return
    if (cur === prevCur || cur === localId.value) return
    scheduleSpeechAudioRecovery()
  }
)

watch(() => [gamePhase.value, game.daySpeech.currentId, game.daySpeech.remainingMs, speakersOn.value, blockedSelf.value.speakers], ([phase, cur, ms]) => {
  if ((phase !== 'day' && phase !== 'vote') || !cur) return
  if (Number(ms ?? 0) > 0) return
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
    rtc.setVideoSubscriptionsForAll(false)

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
          setScreenOwner('')
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

    const hasLsButtonsHigh = rtc.loadLS(rtc.LS.buttonsHigh)
    if (hasLsButtonsHigh == null) {
      rtc.saveLS(rtc.LS.buttonsHigh, '0')
      buttonsHighState.value = false
    } else {
      buttonsHighState.value = hasLsButtonsHigh === '1'
    }

    const hasLsVideoFill = rtc.loadLS(rtc.LS.videoFill)
    if (hasLsVideoFill == null) {
      rtc.saveLS(rtc.LS.videoFill, '1')
      videoFillOnState.value = true
    } else {
      videoFillOnState.value = hasLsVideoFill !== '0'
    }

    document.addEventListener('click', onDocClick)
    window.addEventListener('keydown', onHotkey)
    document.addEventListener('visibilitychange', onBackgroundVisibility, { passive: true })
    window.addEventListener('pagehide', onBackgroundVisibility, { passive: true })
    window.addEventListener('pageshow', handleForegroundSignal, { passive: true })
    window.addEventListener('focus', handleForegroundSignal)
    window.addEventListener('offline', handleOffline)
    window.addEventListener('online', handleOnline)

    uiReady.value = true
  } catch (err) {
    rerr('room onMounted fatal', err)
    try { await rtc.disconnect() } catch {}
    if (!leaving.value) {
      const msg = String((err as any)?.message || '')
      if (msg.includes('connect timeout')) {
        void alertDialog('Таймаут подключения к комнате. Проверьте сеть и попробуйте снова')
      } else {
        void alertDialog('Ошибка входа в комнату')
      }
      await router.replace('/')
    }
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('offline', handleOffline)
  window.removeEventListener('online', handleOnline)
  window.removeEventListener('keydown', onHotkey)
  window.removeEventListener('pageshow', handleForegroundSignal)
  window.removeEventListener('focus', handleForegroundSignal)
  clearSpeechAudioKickTimer()
  clearSpeechAudioRecoveryTimers()
  clearRoomDisconnectFailClosedTimer()
  clearForegroundMediaRecoveryTimers()
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
    flex-direction: column;
    align-items: center;
    justify-content: center;
    inset: 0;
    gap: 16px;
    background-color: $neutral-black;
    pointer-events: none;
    z-index: 1000;
    &.media-gate {
      background-color: rgba($neutral-black, 0.25);
      backdrop-filter: blur(12px);
      pointer-events: auto;
      cursor: pointer;
    }
    .reconnect-overlay__icon {
      --ui-icon-width: 48px;
      --ui-icon-height: 48px;
      --ui-icon-color: #{$neutral-white};
    }
    .reconnect-overlay__text {
      color: $neutral-100;
      font-family: Hauora-Regular;
      font-size: 16px;
      line-height: 22px;
      letter-spacing: -0.32px;
    }
  }
  .grid {
    display: grid;
    width: calc(var(--app-viewport-width) - 20px);
    height: calc(var(--app-viewport-height) - 70px);
    gap: 2px;
  }
  .theater {
    display: grid;
    grid-template-columns: 1fr 328px;
    width: calc(var(--app-viewport-width) - 20px);
    height: calc(var(--app-viewport-height) - 70px);
    gap: 6px;
    .stage {
      position: relative;
      border: 4px solid $green-700;
      border-radius: 24px;
      overflow: hidden;
      video {
        width: 100%;
        height: 100%;
        object-fit: contain;
        background-color: black;
      }
      .screen-quality {
        display: flex;
        position: absolute;
        align-items: center;
        justify-content: center;
        top: 8px;
        right: 8px;
        height: 40px;
        padding: 0 16px;
        gap: 8px;
        border-radius: 12px;
        background-color: $soft-purple-900;
        pointer-events: auto;
        .dot-img {
          --ui-icon-width: 24px;
          --ui-icon-height: 24px;
          --ui-icon-color: #{$green-500};
        }
        .screen-text {
          color: $neutral-100;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 18px;
          letter-spacing: -0.32px;
        }
      }
      .volume {
        display: flex;
        position: absolute;
        align-items: center;
        top: 8px;
        left: 8px;
        padding: 0 16px;
        gap: 8px;
        width: 208px;
        height: 40px;
        border-radius: 12px;
        background-color: $soft-purple-900;
        -webkit-overflow-scrolling: touch;
        transition: background-color 0.25s ease-in-out;
        &:not(:disabled):hover,
        &:not(:disabled):focus-visible,
        &:not(:disabled):active {
          background-color: $soft-purple-800;
        }
        .volume-img {
          --ui-icon-width: 24px;
          --ui-icon-height: 24px;
          --ui-icon-color: #{$neutral-100};
        }
        span {
          min-width: 42px;
          color: $neutral-100;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 16px;
          letter-spacing: -0.32px;
          text-align: right;
        }
      }
    }
    .sidebar {
      display: flex;
      flex-direction: column;
      width: 328px;
      gap: 2px;
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
    width: calc(var(--app-viewport-width) - 20px);
    height: 40px;
    .controls-side {
      display: flex;
      gap: 10px;
      min-width: 320px;
      &.left {
        justify-content: flex-start;
      }
      &.right {
        justify-content: flex-end;
      }
    }
    .controls {
      display: flex;
      gap: 10px;
    }
    &.panel-high {
      gap: 10px;
      justify-content: flex-start;
      .controls-side {
        min-width: 0;
      }
      .controls-side.left {
        order: 2;
      }
      .controls-side.right {
        order: 1;
      }
      .controls {
        order: 0;
        margin-right: auto;
        justify-content: flex-start;
      }
    }
    .btn-text {
      padding: 0 16px;
      width: fit-content;
      color: $neutral-white;
      font-family: Hauora-Regular;
      font-size: 16px;
      line-height: 16px;
      letter-spacing: -0.32px;
    }
    button {
      display: flex;
      position: relative;
      align-items: center;
      justify-content: center;
      padding: 0 16px;
      height: 40px;
      border: none;
      border-radius: 12px;
      background-color: $soft-purple-900;
      cursor: pointer;
      transition: background-color 0.25s ease-in-out;
      .panel-icon {
        --ui-icon-width: 24px;
        --ui-icon-height: 24px;
        --ui-icon-color: #{$neutral-100};
        &.panel-icon-neutral {
          --ui-icon-color: #{$neutral-100};
        }
        &.panel-icon-green {
          --ui-icon-color: #{$green-500};
        }
        &.panel-icon-red {
          --ui-icon-color: #{$red-500};
        }
        &.leave-room-icon {
          transform: scaleX(-1);
        }
      }
      .ready-icon {
        --ui-icon-width: 24px;
        --ui-icon-height: 24px;
        --ui-icon-color: #{$neutral-100};
        &.ready-icon-on {
          --ui-icon-color: #{$green-500};
        }
      }
      .control-state-icon {
        --ui-icon-width: 24px;
        --ui-icon-height: 24px;
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
      .count-total {
        display: flex;
        position: absolute;
        align-items: center;
        justify-content: center;
        top: 3px;
        right: 11px;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background-color: $neutral-500;
        color: $neutral-white;
        font-family: Hauora-Medium;
        font-size: 10px;
        line-height: 8px;
        letter-spacing: -0.4px;
        transition: background-color 0.25s ease-in-out;
        &.unread {
          background-color: $red-500;
        }
      }
      .hot-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        position: absolute;
        bottom: 1.5px;
        right: 1.5px;
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
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      &:not(:disabled):hover,
      &:not(:disabled):focus-visible,
      &:not(:disabled):active {
        background-color: $soft-purple-800;
      }
    }
  }
  .role-overlay {
    display: grid;
    position: fixed;
    box-sizing: border-box;
    grid-template-columns: repeat(5, minmax(0, calc((var(--app-viewport-width) - 193px) / 5)));
    grid-template-rows: repeat(2, minmax(0, calc((var(--app-viewport-height) - 121px) / 2)));
    align-items: center;
    justify-content: center;
    inset: 0;
    gap: 24px;
    padding: 48px;
    background-color: $neutral-black;
    perspective: 1000px;
    z-index: 900;
    .role-card {
      display: block;
      position: relative;
      justify-self: center;
      padding: 0;
      height: 90%;
      aspect-ratio: 4 / 4.7;
      border: none;
      background: transparent;
      cursor: pointer;
      transition: transform 0.15s ease-in-out, opacity 0.15s ease-in-out;
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
        transform: scale(1.075);
      }
      &:disabled {
        opacity: 0.5;
        cursor: default;
      }
      .role-card-inner {
        position: relative;
        width: 100%;
        height: 100%;
        transform-style: preserve-3d;
        transition: transform 0.5s ease-in-out;
        .role-card-face {
          position: absolute;
          inset: 0;
          backface-visibility: hidden;
          overflow: hidden;
          img {
            display: block;
            width: 100%;
            height: 100%;
            object-fit: fill;
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
  .knock-overlay {
    display: flex;
    position: fixed;
    align-items: center;
    justify-content: center;
    inset: 0;
    background-color: rgba($neutral-800, 0.2);
    backdrop-filter: blur(12px);
    z-index: 900;
    .knock-modal {
      display: flex;
      flex-direction: column;
      padding: 24px;
      gap: 32px;
      width: 606px;
      border-radius: 24px;
      background-color: $neutral-100;
      .knock-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        span {
          color: $neutral-black;
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        .close-btn {
          padding: 0;
          width: 24px;
          height: 24px;
          border: none;
          background: none;
          cursor: pointer;
          .close-icon {
            --ui-icon-width: 24px;
            --ui-icon-height: 24px;
            --ui-icon-color: #{$neutral-black};
          }
          &:not(:disabled):hover,
          &:not(:disabled):focus-visible,
          &:not(:disabled):active {
            .close-icon {
              --ui-icon-color: #{$green-500};
            }
          }
        }
      }
      .knock-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(50px, 1fr));
        gap: 10px;
        .knock-btn {
          padding: 0 16px;
          height: 48px;
          border: none;
          border-radius: 999px;
          background-color: $neutral-white;
          color: $neutral-500;
          font-family: Hauora-Regular;
          font-size: 18px;
          line-height: 20px;
          letter-spacing: -0.36px;
          cursor: pointer;
          transition: color 0.25s ease-in-out;
          &:disabled {
            opacity: 0.5;
            cursor: default;
          }
          &:not(:disabled):hover,
          &:not(:disabled):focus-visible,
          &:not(:disabled):active {
            color: $neutral-black;
          }
        }
      }
    }
  }
  .host-blur-overlay {
    display: flex;
    position: fixed;
    align-items: center;
    justify-content: center;
    inset: 0;
    z-index: 850;
    background-color: rgba($neutral-black, 0.4);
    backdrop-filter: blur(25px);
    pointer-events: fill;
    .pause-block {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 178px;
      height: 178px;
      border-radius: 24px;
      background-color: $neutral-100;
      .pause-img {
        --ui-icon-width: 100px;
        --ui-icon-height: 100px;
        --ui-icon-color: #{$soft-purple-600};
      }
      .pause-text {
        color: $neutral-black;
        font-family: Hauora-Regular;
        font-size: 16px;
        line-height: 22px;
        letter-spacing: -0.32px;
      }
    }
  }
  .host-blur-overlay.host-blur-overlay-head {
    backdrop-filter: none !important;
    pointer-events: none;
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
  transition: opacity 0.5s ease-in-out;
}
.host-blur-enter-from,
.host-blur-leave-to {
  opacity: 0;
}
.host-blur-enter-to,
.host-blur-leave-from {
  opacity: 1;
}
.role-overlay-fade-enter-active,
.role-overlay-fade-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.role-overlay-fade-enter-from,
.role-overlay-fade-leave-to {
  opacity: 0;
}
.role-overlay-fade-enter-to,
.role-overlay-fade-leave-from {
  opacity: 1;
}

@media (max-width: 1000px) {
  .room {
    padding: 0 10px;
  }
  .room .panel {
    height: 60px;
  }
  .room .panel button {
    padding: 0 24px;
    height: 60px;
  }
  .room .panel button .panel-icon {
    --ui-icon-width: 30px;
    --ui-icon-height: 30px;
  }
  .room .panel button .count-total {
    top: 8px;
    width: 18px;
    height: 18px;
    font-size: 12px;
  }
}

</style>
