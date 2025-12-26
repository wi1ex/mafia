import { computed, reactive, ref, type Ref, watch } from 'vue'
import { confirmDialog, alertDialog } from '@/services/confirm'
import { useSettingsStore } from '@/store'

import iconRoleCitizen from '@/assets/images/roleCitizen.png'
import iconRoleMafia from '@/assets/images/roleMafia.png'
import iconRoleDon from '@/assets/images/roleDon.png'
import iconRoleSheriff from '@/assets/images/roleSheriff.png'
import iconCardBack from '@/assets/images/cardBack.png'
import iconCardCitizen from '@/assets/images/cardCitizen.png'
import iconCardMafia from '@/assets/images/cardMafia.png'
import iconCardDon from '@/assets/images/cardDon.png'
import iconCardSheriff from '@/assets/images/cardSheriff.png'

import iconSlotHead from '@/assets/svg/slotHead.svg'
import iconSlot1 from '@/assets/svg/slot1.svg'
import iconSlot2 from '@/assets/svg/slot2.svg'
import iconSlot3 from '@/assets/svg/slot3.svg'
import iconSlot4 from '@/assets/svg/slot4.svg'
import iconSlot5 from '@/assets/svg/slot5.svg'
import iconSlot6 from '@/assets/svg/slot6.svg'
import iconSlot7 from '@/assets/svg/slot7.svg'
import iconSlot8 from '@/assets/svg/slot8.svg'
import iconSlot9 from '@/assets/svg/slot9.svg'
import iconSlot0 from '@/assets/svg/slot10.svg'

export type GamePhase = 'idle' | 'roles_pick' | 'mafia_talk_start' | 'mafia_talk_end' | 'day' | 'vote' | 'night'
export type GameRoleKind = 'citizen' | 'mafia' | 'don' | 'sheriff'
export type GameResult = 'red' | 'black' | 'draw' | ''

export type Ack = {
  ok: boolean
  status?: number
  error?: string
  [k: string]: any
} | null

export type SendAckFn = (event: string, payload: any, timeoutMs?: number) => Promise<Ack>
export type FarewellVerdict = 'citizen' | 'mafia'

export const GAME_COLUMN_INDEX: Record<number, number> = {
  1: 5, 2: 7, 3: 7, 4: 7, 5: 5, 6: 3, 7: 1, 8: 1, 9: 1, 10: 3, 11: 4,
}

export const GAME_ROW_INDEX: Record<number, number> = {
  1: 1, 2: 1, 3: 3, 4: 5, 5: 5, 6: 5, 7: 5, 8: 3, 9: 1, 10: 1, 11: 3,
}

export const ROLE_CARD_IMAGES = [
  iconCardBack,
  iconCardCitizen,
  iconCardMafia,
  iconCardDon,
  iconCardSheriff,
]

export const ROLE_IMAGES: Record<GameRoleKind, string> = {
  citizen: iconCardCitizen,
  mafia: iconCardMafia,
  don: iconCardDon,
  sheriff: iconCardSheriff,
}

const ROLE_BADGE_ICONS: Record<GameRoleKind, string> = {
  citizen: iconRoleCitizen,
  mafia: iconRoleMafia,
  don: iconRoleDon,
  sheriff: iconRoleSheriff,
}

const ALL_ROLE_CARDS = Array.from({ length: 10 }, (_, i) => i + 1)

export function useRoomGame(localId: Ref<string>, roomId?: Ref<string | number>) {
  const settings = useSettingsStore()
  const gamePhase = ref<GamePhase>('idle')
  const initialMinReady = Number(settings.gameMinReadyPlayers)
  const minReadyToStart = ref<number>(
    Number.isFinite(initialMinReady) && initialMinReady > 0 ? initialMinReady : 4,
  )
  const seatsByUser = reactive<Record<string, number>>({})
  const gamePlayers = reactive(new Set<string>())
  const gameAlive = reactive(new Set<string>())
  const offlineInGame = reactive(new Set<string>())
  const gameRolesByUser = reactive(new Map<string, GameRoleKind>())
  const gameFoulsByUser = reactive(new Map<string, number>())
  const rolesVisibleForHead = ref(false)
  const knownRolesVisible = ref(true)
  const gameResult = ref<GameResult>('')
  const gameFinished = computed(() => gameResult.value !== '')
  const dayNumber = ref(0)
  const canToggleKnownRoles = computed(() => {
    return !gameFinished.value && gamePhase.value !== 'idle' && myGameRole.value !== 'none'
  })
  if (typeof window !== 'undefined') {
    try {
      const raw = window.localStorage.getItem('roomRolesVisible')
      if (raw === '0' || raw === '1') knownRolesVisible.value = raw === '1'
    } catch {}
  }

  const rolePick = reactive({
    activeUserId: '',
    order: [] as string[],
    picked: new Set<string>(),
    takenCards: [] as number[],
    remainingMs: 0,
  })
  const roleOverlayTimerId = ref<number | null>(null)
  const roleOverlayMode = ref<'hidden' | 'pick' | 'reveal'>('hidden')
  const roleOverlayCard = ref<number | null>(null)
  const pickingRole = ref(false)
  const startingGame = ref(false)
  const endingGame = ref(false)
  const mafiaTalk = reactive({
    remainingMs: 0,
  })
  const mafiaTalkTimerId = ref<number | null>(null)
  const daySpeech = reactive({
    openingId: '',
    closingId: '',
    currentId: '',
    remainingMs: 0,
  })
  const currentFarewellSpeech = ref(false)
  const activeFarewellSpeakerId = ref('')
  const activeFarewellAllowed = ref(true)
  const farewellLimits = reactive(new Map<string, number>())
  const farewellWills = reactive(new Map<string, Map<string, FarewellVerdict>>())
  const bestMove = reactive({
    uid: '',
    active: false,
    targets: [] as string[],
  })
  const vote = reactive({
    currentId: '',
    remainingMs: 0,
    done: false,
  })
  const revotePromptCandidate = ref('')
  const voteTimerId = ref<number | null>(null)
  const votedUsers = reactive(new Set<string>())
  const votedThisRound = reactive(new Set<string>())
  const voteStartedForCurrent = ref(false)
  const daySpeechTimerId = ref<number | null>(null)
  const daySpeechesDone = ref(false)
  const foulActive = reactive(new Set<string>())
  const dayNominees = reactive<string[]>([])
  const nominatedThisSpeechByMe = ref(false)
  const voteResultLeaders = reactive<string[]>([])
  const voteResultShown = ref(false)
  const voteAborted = ref(false)
  const voteLeaderSpeechesDone = ref(false)
  const voteLeaderKilled = ref(false)
  const voteLiftState = ref<'none' | 'ready' | 'prepared' | 'voting' | 'passed' | 'failed'>('none')
  const voteBlocked = ref(false)
  const deathReasonByUser = reactive(new Map<string, string>())

  const night = reactive({
    stage: 'sleep' as 'sleep' | 'shoot' | 'shoot_done' | 'checks' | 'checks_done',
    remainingMs: 0,
    killOk: false,
    killUid: '',
    hasResult: false,
  })
  const nightResultClearedDay = ref(0)
  const nightTimerId = ref<number | null>(null)
  const roomKey = () => String(roomId?.value ?? '')
  const loadNightResultCleared = () => {
    if (typeof window === 'undefined') return 0
    try {
      const raw = window.sessionStorage.getItem(`nightResultCleared:${roomKey()}`)
      const n = Number(raw || 0)
      return Number.isFinite(n) && n > 0 ? n : 0
    } catch {
      return 0
    }
  }
  const persistNightResultCleared = (day: number) => {
    if (typeof window === 'undefined') return
    try { window.sessionStorage.setItem(`nightResultCleared:${roomKey()}`, String(day)) } catch {}
  }
  nightResultClearedDay.value = loadNightResultCleared()
  const myNightShotTarget = ref<string>('')
  const myNightCheckTarget = ref<string>('')
  const nightKnownByMe = reactive(new Map<string, GameRoleKind>())
  const nightCheckedByMe = reactive(new Set<string>())
  const headNightPicks = reactive(new Map<string, number>())

  const nomineeSeatNumbers = computed<number[]>(() => {
    const list = Array.isArray(dayNominees) ? dayNominees : []
    return list.map(uid => seatIndex(uid)).filter((s): s is number => s != null)
  })

  const myGameRoleKind = computed<GameRoleKind | null>(() => {
    const id = localId.value
    if (!id) return null
    return gameRolesByUser.get(id) ?? null
  })

  const myGameRole = computed<'head' | 'player' | 'none'>(() => {
    const id = localId.value
    if (!id) return 'none'
    const seat = seatsByUser[id]
    if (!seat) return 'none'
    return seat === 11 ? 'head' : 'player'
  })

  const isHead = computed(() => myGameRole.value === 'head')

  const amIAlive = computed(() => {
    if (gamePhase.value === 'idle') return true
    const id = localId.value
    if (!id) return false
    const seat = seatsByUser[id]
    if (!seat) return false
    if (seat === 11) return true
    return gameAlive.has(id)
  })

  const takenCardSet = computed(() => new Set(rolePick.takenCards))
  const roleCardsToRender = computed(() => ALL_ROLE_CARDS)

  const currentNomineeSeat = computed<number | null>(() => {
    if (!vote.currentId) return null
    return seatIndex(vote.currentId)
  })

  const headUserId = computed(() => {
    for (const [uid, seat] of Object.entries(seatsByUser)) {
      if (seat === 11) return uid
    }
    return ''
  })

  const mafiaTalkRemainingMs = computed(() => mafiaTalk.remainingMs)

  const offlineAliveSeatNumbers = computed<number[]>(() => {
    const result: number[] = []
    for (const uid of gameAlive) {
      if (!offlineInGame.has(uid)) continue
      const seat = seatsByUser[uid]
      if (Number.isFinite(seat) && seat && seat !== 11) result.push(seat)
    }
    result.sort((a, b) => a - b)
    return result
  })
  const hasOfflineAlivePlayers = computed(() => offlineAliveSeatNumbers.value.length > 0)

  const headPickKind = computed<'shoot' | 'check' | ''>(() => {
    if (!isHead.value) return ''
    if (gamePhase.value !== 'night') return ''
    const st = String(night.stage || '')
    if (st.startsWith('checks')) return 'check'
    if (st.startsWith('shoot')) return 'shoot'
    return ''
  })

  const allRolesPicked = computed(() => {
    const order = rolePick.order
    if (!Array.isArray(order) || order.length === 0) return false
    return order.every(id => rolePick.picked.has(id))
  })

  const gameResultLabel = computed(() => {
    if (gameResult.value === 'black') return 'Победа мафии!'
    if (gameResult.value === 'red') return 'Победа мирных!'
    if (gameResult.value === 'draw') return 'Ничья'
    return ''
  })

  const phaseLabel = computed(() => {
    if (gameResultLabel.value) return gameResultLabel.value
    if (gamePhase.value === 'roles_pick') return allRolesPicked.value ? '' : 'Выбор ролей'
    if (gamePhase.value === 'mafia_talk_start') return 'Договорка мафии'
    if (gamePhase.value === 'night') {
      if (night.stage === 'shoot') return 'Отстрелы мафии'
      if (night.stage === 'checks') return 'Проверки дона и шерифа'
      return ''
    }
    if (gamePhase.value === 'day') {
      if (night.hasResult) {
        if (night.killOk && night.killUid) {
          const seat = seatIndex(night.killUid)
          return `Убит ${seat ?? ''}`
        }
        return 'Несострел'
      }
    }
    return ''
  })

  const FINISH_SPEECH_DELAY_MS = 1000
  const finishSpeechUnlocked = ref(false)
  let finishSpeechTimer: number | null = null
  function resetFinishSpeechDelay() {
    finishSpeechUnlocked.value = false
    if (finishSpeechTimer !== null) {
      clearTimeout(finishSpeechTimer)
      finishSpeechTimer = null
    }
  }
  function scheduleFinishSpeechUnlock() {
    resetFinishSpeechDelay()
    if (gamePhase.value !== 'day' && gamePhase.value !== 'vote') return
    if (!daySpeech.currentId || daySpeech.remainingMs <= 0) return
    finishSpeechTimer = window.setTimeout(() => {
      if ((gamePhase.value === 'day' || gamePhase.value === 'vote') && !!daySpeech.currentId && daySpeech.remainingMs > 0) {
        finishSpeechUnlocked.value = true
      }
      finishSpeechTimer = null
    }, FINISH_SPEECH_DELAY_MS)
  }
  
  const PASS_SPEECH_DELAY_MS = 1000
  const passSpeechUnlocked = ref(false)
  let passSpeechTimer: number | null = null
  function resetPassSpeechDelay() {
    passSpeechUnlocked.value = false
    if (passSpeechTimer !== null) {
      clearTimeout(passSpeechTimer)
      passSpeechTimer = null
    }
  }
  function schedulePassSpeechUnlock() {
    resetPassSpeechDelay()
    if (!isHead.value) return
    if (gamePhase.value !== 'day') return
    if (daySpeechesDone.value) return
    if (daySpeech.currentId && daySpeech.remainingMs > 0) return
    passSpeechTimer = window.setTimeout(() => {
      if (isHead.value && gamePhase.value === 'day' && !daySpeechesDone.value && !(daySpeech.currentId && daySpeech.remainingMs > 0)) {
        passSpeechUnlocked.value = true
      }
      passSpeechTimer = null
    }, PASS_SPEECH_DELAY_MS)
  }

  const START_MAFIA_TALK_DELAY_MS = 3000
  const startMafiaTalkUnlocked = ref(false)
  let startMafiaTalkTimer: number | null = null
  function resetStartMafiaTalkDelay() {
    startMafiaTalkUnlocked.value = false
    if (startMafiaTalkTimer !== null) {
      clearTimeout(startMafiaTalkTimer)
      startMafiaTalkTimer = null
    }
  }
  function scheduleStartMafiaTalkUnlock() {
    resetStartMafiaTalkDelay()
    if (typeof window === 'undefined') return
    if (!isHead.value) return
    if (gamePhase.value !== 'roles_pick') return
    if (!rolesVisibleForHead.value) return
    startMafiaTalkTimer = window.setTimeout(() => {
      if (isHead.value && gamePhase.value === 'roles_pick' && rolesVisibleForHead.value) {
        startMafiaTalkUnlocked.value = true
      }
      startMafiaTalkTimer = null
    }, START_MAFIA_TALK_DELAY_MS)
  }

  const LEADER_SPEECH_DELAY_MS = 1000
  const leaderSpeechUnlocked = ref(false)
  let leaderSpeechTimer: number | null = null
  function resetLeaderSpeechDelay() {
    leaderSpeechUnlocked.value = false
    if (leaderSpeechTimer !== null) {
      clearTimeout(leaderSpeechTimer)
      leaderSpeechTimer = null
    }
  }
  function leaderSpeechEligibleNow(): boolean {
    if (!isHead.value) return false
    if (gamePhase.value !== 'vote') return false
    const liftPassed = voteLiftState.value === 'passed'
    if (!liftPassed && !vote.done) return false
    if (!voteResultShown.value) return false
    if (voteAborted.value) return false
    if (voteLeaderKilled.value) return false
    if (['ready', 'prepared', 'voting', 'failed'].includes(voteLiftState.value)) return false
    if (voteResultLeaders.length === 0) return false
    if (voteLeaderSpeechesDone.value) return false
    return daySpeech.remainingMs <= 0
  }
  function scheduleLeaderSpeechUnlock() {
    resetLeaderSpeechDelay()
    if (typeof window === 'undefined') return
    if (!leaderSpeechEligibleNow()) return
    leaderSpeechTimer = window.setTimeout(() => {
      if (leaderSpeechEligibleNow()) leaderSpeechUnlocked.value = true
      leaderSpeechTimer = null
    }, LEADER_SPEECH_DELAY_MS)
  }

  const DAY_BUTTON_DELAY_MS = 1000
  const startDayUnlocked = ref(false)
  let startDayTimer: number | null = null
  function resetStartDayDelay() {
    startDayUnlocked.value = false
    if (startDayTimer !== null) {
      clearTimeout(startDayTimer)
      startDayTimer = null
    }
  }
  function canShowStartDayNow(): boolean {
    return gamePhase.value === 'mafia_talk_end' && isHead.value
  }
  function scheduleStartDayUnlock() {
    resetStartDayDelay()
    if (typeof window === 'undefined') return
    if (!canShowStartDayNow()) return
    startDayTimer = window.setTimeout(() => {
      if (canShowStartDayNow()) startDayUnlocked.value = true
      startDayTimer = null
    }, DAY_BUTTON_DELAY_MS)
  }

  const dayFromNightUnlocked = ref(false)
  let dayFromNightTimer: number | null = null
  function resetDayFromNightDelay() {
    dayFromNightUnlocked.value = false
    if (dayFromNightTimer !== null) {
      clearTimeout(dayFromNightTimer)
      dayFromNightTimer = null
    }
  }
  function canShowDayFromNightNow(): boolean {
    return gamePhase.value === 'night'
      && isHead.value
      && night.stage === 'checks_done'
      && (!bestMove.uid || bestMove.active)
  }
  function scheduleDayFromNightUnlock() {
    resetDayFromNightDelay()
    if (typeof window === 'undefined') return
    if (!canShowDayFromNightNow()) return
    dayFromNightTimer = window.setTimeout(() => {
      if (canShowDayFromNightNow()) dayFromNightUnlocked.value = true
      dayFromNightTimer = null
    }, DAY_BUTTON_DELAY_MS)
  }

  const canStartDay = computed(() => canShowStartDayNow() && startDayUnlocked.value)

  const isCurrentSpeaker = computed(() => {
    return (
      (gamePhase.value === 'day' || gamePhase.value === 'vote') &&
      daySpeech.currentId === localId.value &&
      daySpeech.remainingMs > 0
    )
  })

  const canFinishSpeechHead = computed(() => {
    if (!isHead.value) return false
    if (gamePhase.value !== 'day' && gamePhase.value !== 'vote') return false
    if (!daySpeech.currentId) return false
    if (!finishSpeechUnlocked.value) return false
    return daySpeech.remainingMs > 0
  })

  const canPassSpeechHead = computed(() => {
    if (!isHead.value) return false
    if (gamePhase.value !== 'day') return false
    if (daySpeechesDone.value) return false
    if (!passSpeechUnlocked.value) return false
    return !(daySpeech.currentId && daySpeech.remainingMs > 0)
  })

  const canFinishSpeechSelf = computed(() => {
    const me = localId.value
    if (!me) return false
    if (!amIAlive.value) return false
    if (gamePhase.value !== 'day' && gamePhase.value !== 'vote') return false
    if (daySpeech.currentId !== me) return false
    if (!finishSpeechUnlocked.value) return false
    return daySpeech.remainingMs > 0
  })

  const canTakeFoulSelf = computed(() => {
    return (
      (gamePhase.value === 'day' || gamePhase.value === 'vote') &&
      myGameRole.value === 'player' &&
      amIAlive.value &&
      !isCurrentSpeaker.value
    )
  })

  const canStartVote = computed(() => {
    if (!isHead.value) return false
    if (gamePhase.value !== 'day') return false
    if (voteBlocked.value) return false
    if (!daySpeechesDone.value) return false
    const cnt = nomineeSeatNumbers.value.length
    if (cnt <= 0) return false
    return !(dayNumber.value === 1 && cnt === 1)
  })

  const canHeadVoteControl = computed(() => {
    if (voteLiftState.value !== 'none') return false
    return gamePhase.value === 'vote' && isHead.value && !vote.done && vote.remainingMs === 0
  })

  const canPrepareVoteLift = computed(() => {
    return isHead.value && gamePhase.value === 'vote' && voteResultShown.value && voteLiftState.value === 'ready'
  })

  const canStartVoteLift = computed(() => {
    return isHead.value && gamePhase.value === 'vote' && voteLiftState.value === 'prepared'
  })

  const isLiftVoting = computed(() => voteLiftState.value === 'voting')
  const liftHighlightNominees = computed(() => ['prepared', 'voting', 'passed'].includes(voteLiftState.value))

  const canHeadNightShootControl = computed(() => {
    return gamePhase.value === 'night' && isHead.value && night.stage === 'sleep'
  })

  const canHeadNightCheckControl = computed(() => {
    return gamePhase.value === 'night' && isHead.value && night.stage === 'shoot_done'
  })

  const bestMovePending = computed(() => !!bestMove.uid && !bestMove.active)
  const bestMoveSeat = computed(() => (bestMove.uid ? seatIndex(bestMove.uid) : null))
  const canHeadBestMoveControl = computed(() => {
    return gamePhase.value === 'night' && isHead.value && night.stage === 'checks_done' && bestMovePending.value
  })

  const canHeadDayFromNightControl = computed(() => {
    return canShowDayFromNightNow() && dayFromNightUnlocked.value
  })

  const canStartDayFromNight = computed(() => {
    return canShowDayFromNightNow()
  })

  const canHeadGoToMafiaTalkControl = computed(() => {
    return (
      gamePhase.value === 'roles_pick' &&
      isHead.value &&
      rolesVisibleForHead.value &&
      startMafiaTalkUnlocked.value
    )
  })

  const canHeadFinishMafiaTalkControl = computed(() => {
    return gamePhase.value === 'mafia_talk_start' && isHead.value && mafiaTalkRemainingMs.value <= 0
  })

  const canHeadFinishVoteControl = computed(() => {
    if (gamePhase.value !== 'vote' || !isHead.value) return false
    if (voteResultShown.value) return false
    if (voteBlocked.value) return false
    if (voteLiftState.value === 'voting') {
      return vote.done || vote.remainingMs <= 0
    }
    if (voteLiftState.value !== 'none') return false
    return vote.done
  })

  const canStartLeaderSpeech = computed(() => {
    if (!leaderSpeechUnlocked.value) return false
    return leaderSpeechEligibleNow()
  })

  const canRestartVoteForLeaders = computed(() => {
    if (!isHead.value) return false
    if (gamePhase.value !== 'vote') return false
    if (!vote.done) return false
    if (!voteResultShown.value) return false
    if (voteAborted.value) return false
    if (voteLiftState.value !== 'none') return false
    if (voteResultLeaders.length <= 1) return false
    return voteLeaderSpeechesDone.value
  })

  const noNomineesAfterDay = computed(() => {
    return (
      isHead.value &&
      gamePhase.value === 'day' &&
      daySpeechesDone.value &&
      nomineeSeatNumbers.value.length === 0
    )
  })

  const singleNomineeFirstDay = computed(() => {
    return (
      isHead.value &&
      gamePhase.value === 'day' &&
      daySpeechesDone.value &&
      dayNumber.value === 1 &&
      nomineeSeatNumbers.value.length === 1
    )
  })

  const canShowNightAfterVote = computed(() => {
    if (!isHead.value) return false
    if (gamePhase.value !== 'vote') return false
    if (voteLiftState.value === 'failed') return true
    if (!vote.done) return false
    if (!voteLeaderSpeechesDone.value) return false
    if (voteAborted.value || voteResultLeaders.length <= 1) return true
    return voteLeaderKilled.value
  })

  const canShowNight = computed(() => {
    return canShowNightAfterVote.value || singleNomineeFirstDay.value || noNomineesAfterDay.value
  })

  function setNightRemainingMs(ms: number, changed: boolean) {
    setTimerWithLatency(night, ms, nightTimerId, changed)
  }

  function canPressVoteButton(): boolean {
    if (gameFinished.value) return false
    const me = localId.value
    if (!me) return false
    if (gamePhase.value !== 'vote') return false
    if (voteLiftState.value !== 'none' && voteLiftState.value !== 'voting') return false
    if (vote.done) return false
    if (vote.remainingMs <= 0) return false
    if (!amIAlive.value) return false
    if (myGameRole.value !== 'player') return false
    return !votedUsers.has(me)
  }

  function setVoteRemainingMs(ms: number, changed: boolean) {
    setTimerWithLatency(vote, ms, voteTimerId, changed)
  }

  function toggleKnownRolesVisibility(): void {
    knownRolesVisible.value = !knownRolesVisible.value
  }

  function ensureKnownRolesVisible(): void {
    if (myGameRoleKind.value === 'don' || myGameRoleKind.value === 'sheriff') {
      knownRolesVisible.value = true
    }
  }

  const LATENCY_MS = 1500
  function withLatency(rawMs: number): number {
    if (!rawMs || rawMs <= 0) return 0
    return Math.max(rawMs - LATENCY_MS, 0)
  }
  function secondsToMs(sec: any): number {
    const n = Number(sec || 0)
    return n > 0 ? n * 1000 : 0
  }
  function isTrueLike(v: any): boolean {
    return v === true || v === 1 || v === '1'
  }
  function setTimerWithLatency(target: { remainingMs: number }, ms: number, timerRef: Ref<number | null>, changed: boolean, onFinish?: () => void) {
    const safe = !changed ? withLatency(ms) : ms
    target.remainingMs = safe
    if (timerRef.value != null) {
      clearTimeout(timerRef.value)
      timerRef.value = null
    }
    if (safe > 0) {
      timerRef.value = window.setTimeout(() => {
        target.remainingMs = 0
        timerRef.value = null
        if (onFinish) onFinish()
      }, safe)
    } else { if (onFinish) onFinish() }
  }
  
  function replaceIds(target: string[], raw: any, filter?: (id: string) => boolean) {
    target.splice(0, target.length)
    if (!Array.isArray(raw)) return
    for (const uid of raw) {
      const s = String(uid)
      if (!s) continue
      if (filter && !filter(s)) continue
      target.push(s)
    }
  }

  function resetDaySpeechState(changed: boolean) {
    daySpeech.openingId = ''
    daySpeech.closingId = ''
    daySpeech.currentId = ''
    setDaySpeechRemainingMs(0, changed)
    daySpeechesDone.value = false
    currentFarewellSpeech.value = false
    activeFarewellSpeakerId.value = ''
    activeFarewellAllowed.value = true
  }

  function resetVoteState(changed: boolean) {
    vote.currentId = ''
    setVoteRemainingMs(0, changed)
    vote.done = false
    voteAborted.value = false
    voteBlocked.value = false
    votedUsers.clear()
    votedThisRound.clear()
    voteStartedForCurrent.value = false
    voteResultShown.value = false
    voteLeaderSpeechesDone.value = false
    voteLeaderKilled.value = false
    voteLiftState.value = 'none'
    resetLeaderSpeechDelay()
  }

  function fillPlayersFromSeats() {
    gamePlayers.clear()
    gameAlive.clear()
    for (const [uid, seat] of Object.entries(seatsByUser)) {
      if (seat && seat !== 11) {
        gamePlayers.add(uid)
        gameAlive.add(uid)
      }
    }
  }

  function syncGameFouls(raw: any) {
    gameFoulsByUser.clear()
    const fouls = (raw || {}) as Record<string, any>
    for (const [uid, cnt] of Object.entries(fouls)) {
      const n = Number(cnt)
      if (Number.isFinite(n) && n > 0) gameFoulsByUser.set(String(uid), n)
    }
  }

  function syncFarewellLimits(raw: any) {
    farewellLimits.clear()
    const limits = (raw || {}) as Record<string, any>
    for (const [uid, lim] of Object.entries(limits)) {
      const n = Number(lim)
      if (!Number.isFinite(n) || n < 0) continue
      farewellLimits.set(String(uid), Math.max(0, Math.floor(n)))
    }
  }

  function upsertFarewellForSpeaker(speakerId: string, raw: any) {
    const sid = String(speakerId || '')
    if (!sid) return
    const map = new Map<string, FarewellVerdict>()
    if (raw && typeof raw === 'object') {
      for (const [targetId, verdictRaw] of Object.entries(raw)) {
        const verdict = verdictRaw === 'mafia' ? 'mafia' : verdictRaw === 'citizen' ? 'citizen' : ''
        if (!verdict) continue
        const tid = String(targetId || '')
        if (!tid) continue
        map.set(tid, verdict)
      }
    }
    farewellWills.set(sid, map)
  }

  function syncFarewellWills(raw: any) {
    farewellWills.clear()
    const wills = (raw || {}) as Record<string, any>
    for (const [speakerId, payload] of Object.entries(wills)) {
      upsertFarewellForSpeaker(String(speakerId || ''), payload)
    }
  }

  function resetBestMoveState() {
    bestMove.uid = ''
    bestMove.active = false
    bestMove.targets = []
  }

  function syncBestMove(raw: any) {
    if (!raw || typeof raw !== 'object') {
      resetBestMoveState()
      return
    }
    const uidNum = Number((raw as any).uid || (raw as any).user_id || 0)
    const targetNum = Number((raw as any).target_uid || (raw as any).targetId || 0)
    const uid = uidNum > 0 ? String(uidNum) : ''
    const rawTargets = (raw as any).targets
    const rawTargetsList = Array.isArray(rawTargets) ? rawTargets : []
    const nextTargets: string[] = []
    const seen = new Set<string>()
    for (const item of rawTargetsList) {
      const n = Number(item)
      if (!Number.isFinite(n) || n <= 0) continue
      const id = String(n)
      if (seen.has(id)) continue
      seen.add(id)
      nextTargets.push(id)
    }
    if (!nextTargets.length && targetNum > 0) nextTargets.push(String(targetNum))
    bestMove.uid = uid
    bestMove.active = isTrueLike((raw as any).active) && !!uid
    bestMove.targets = nextTargets
    if (!uid) {
      bestMove.active = false
      bestMove.targets = []
    }
  }

  function isBestMoveMarked(id: string): boolean {
    return bestMove.targets.includes(id)
  }

  function isGameHead(id: string): boolean {
    return seatsByUser[id] === 11
  }

  function isDead(id: string): boolean {
    if (gameFinished.value) return false
    if (gamePhase.value === 'idle') return false
    const seat = seatsByUser[id]
    if (!seat || seat === 11) return false
    return !gameAlive.has(id)
  }

  function deathReason(id: string): string {
    return deathReasonByUser.get(id) || ''
  }

  function seatIndex(id: string): number | null {
    const s = seatsByUser[id]
    return Number.isFinite(s) && s > 0 ? s : null
  }

  function seatIconBySeat(seat: number | null | undefined): string {
    if (!seat) return ''
    switch (seat) {
      case 11: return iconSlotHead
      case 1: return iconSlot1
      case 2: return iconSlot2
      case 3: return iconSlot3
      case 4: return iconSlot4
      case 5: return iconSlot5
      case 6: return iconSlot6
      case 7: return iconSlot7
      case 8: return iconSlot8
      case 9: return iconSlot9
      case 10: return iconSlot0
      default: return ''
    }
  }

  function seatIconForUser(id: string): string {
    if (gamePhase.value === 'idle') return ''
    const s = seatIndex(id)
    return seatIconBySeat(s)
  }

  function roleVisibleOnTile(id: string): boolean {
    const role = gameRolesByUser.get(id)
    if (!role) return false
    const me = localId.value
    if (!me) return false
    if (gameFinished.value) return true
    if (!knownRolesVisible.value) return false
    const myRole = gameRolesByUser.get(me) as GameRoleKind | undefined
    const isSelf = id === me
    if (isSelf) return true
    if (isHead.value && rolesVisibleForHead.value) return true
    if (!myRole) return false
    if (myRole === 'mafia') return role === 'mafia' || role === 'don'
    if (myRole === 'don') return role === 'mafia'
    return false
  }

  function roleIconForTile(id: string): string {
    const role = gameRolesByUser.get(id)
    if (!role) return ''
    if (!roleVisibleOnTile(id)) return ''
    return ROLE_BADGE_ICONS[role] || ''
  }

  const canClickCard = (n: number) =>
    roleOverlayMode.value === 'pick' &&
    !pickingRole.value &&
    !!localId.value &&
    !rolePick.picked.has(localId.value) &&
    !takenCardSet.value.has(n)

  function resetRolesUiState() {
    rolePick.activeUserId = ''
    rolePick.order = []
    rolePick.picked = new Set<string>()
    rolePick.takenCards = []
    rolePick.remainingMs = 0
    roleOverlayMode.value = 'hidden'
    roleOverlayCard.value = null
    gameResult.value = ''
    resetStartMafiaTalkDelay()
    resetLeaderSpeechDelay()
    if (roleOverlayTimerId.value != null) {
      clearTimeout(roleOverlayTimerId.value)
      roleOverlayTimerId.value = null
    }
    gameRolesByUser.clear()
    rolesVisibleForHead.value = false
    gameFoulsByUser.clear()
    farewellLimits.clear()
    farewellWills.clear()
    currentFarewellSpeech.value = false
    activeFarewellSpeakerId.value = ''
    mafiaTalk.remainingMs = 0
    if (mafiaTalkTimerId.value != null) {
      clearTimeout(mafiaTalkTimerId.value)
      mafiaTalkTimerId.value = null
    }
    resetDaySpeechState(false)
    replaceIds(dayNominees, undefined)
    nominatedThisSpeechByMe.value = false
    resetVoteState(false)
    
    night.stage = 'sleep'
    night.remainingMs = 0
    night.killOk = false
    night.killUid = ''
    night.hasResult = false
    if (nightTimerId.value != null) {
      clearTimeout(nightTimerId.value)
      nightTimerId.value = null
    }
    myNightShotTarget.value = ''
    myNightCheckTarget.value = ''
    nightKnownByMe.clear()
    nightCheckedByMe.clear()
    headNightPicks.clear()
  }

  function nightKnownRoleIconForTile(id: string): string {
    if (gamePhase.value === 'idle') return ''
    const me = localId.value
    if (!me) return ''
    if (!knownRolesVisible.value) return ''
    const myRole = gameRolesByUser.get(me)
    if (myRole !== 'don' && myRole !== 'sheriff') return ''
    const rr = nightKnownByMe.get(id)
    if (!rr) return ''
    return ROLE_BADGE_ICONS[rr] || ''
  }

  function effectiveRoleIconForTile(id: string): string {
    if (gameFinished.value) return roleIconForTile(id)
    return nightKnownRoleIconForTile(id) || roleIconForTile(id)
  }

  function farewellLimitForUser(id: string): number {
    const v = farewellLimits.get(id)
    if (v == null) return 0
    return Number.isFinite(v) && v > 0 ? Math.floor(v) : 0
  }

  function farewellSummaryForUser(id: string): { targetId: string, seat: number | null, verdict: FarewellVerdict }[] {
    const map = farewellWills.get(id)
    if (!map) return []
    const out: { targetId: string, seat: number | null, verdict: FarewellVerdict }[] = []
    map.forEach((verdict, targetId) => {
      out.push({ targetId, seat: seatIndex(targetId), verdict })
    })
    out.sort((a, b) => {
      const sa = a.seat ?? 99
      const sb = b.seat ?? 99
      if (sa !== sb) return sa - sb
      return a.targetId.localeCompare(b.targetId)
    })
    return out
  }

  function canMakeFarewellChoice(targetId: string): boolean {
    if (gameFinished.value) return false
    const me = localId.value
    if (!me) return false
    if (!currentFarewellSpeech.value) return false
    if (activeFarewellSpeakerId.value !== me) return false
    if (!activeFarewellAllowed.value) return false
    const seat = seatIndex(targetId)
    if (seat == null || seat === 11) return false
    if (!gameAlive.has(targetId)) return false
    if (targetId === me) return false
    const limit = farewellLimitForUser(me)
    if (limit <= 0) return false
    const map = farewellWills.get(me)
    if (map?.has(targetId)) return false
    return (map?.size ?? 0) < limit
  }

  function canMakeBestMoveChoice(targetId: string): boolean {
    if (gameFinished.value) return false
    const me = localId.value
    if (!me) return false
    if (gamePhase.value !== 'night') return false
    if (!bestMove.active) return false
    if (bestMove.uid !== me) return false
    if (bestMove.targets.length >= 3) return false
    if (bestMove.targets.includes(targetId)) return false
    if (!gamePlayers.has(targetId)) return false
    if (!gameAlive.has(targetId)) return false
    return targetId !== me
  }

  function syncRoleOverlayWithTurn() {
    const me = localId.value
    const uid = rolePick.activeUserId
    if (!me || !uid || gamePhase.value !== 'roles_pick') {
      if (roleOverlayMode.value === 'pick') {
        roleOverlayMode.value = 'hidden'
        roleOverlayCard.value = null
        pickingRole.value = false
      }
      return
    }
    if (uid === me && !myGameRoleKind.value) {
      roleOverlayMode.value = 'pick'
      roleOverlayCard.value = null
      pickingRole.value = false
    } else if (roleOverlayMode.value === 'pick' && uid !== me) {
      roleOverlayMode.value = 'hidden'
      roleOverlayCard.value = null
      pickingRole.value = false
    }
  }

  function fillSeats(source: Record<string, any>) {
    Object.keys(seatsByUser).forEach(k => { delete seatsByUser[k] })
    for (const [uid, seat] of Object.entries(source)) {
      const n = Number(seat)
      if (Number.isFinite(n) && n > 0) seatsByUser[String(uid)] = n
    }
  }

  function normalizeCards(raw: any): number[] {
    const arr = Array.isArray(raw) ? raw : []
    return arr.map((x: any) => Number(x)).filter((n: number) => Number.isFinite(n) && n > 0)
  }

  function applyFromJoinAck(join: any, snapshotIds?: string[]) {
    const gr = join?.game_runtime || {}
    const mr = Number(gr.min_ready)
    syncFarewellWills(join?.farewell_wills ?? (gr as any).farewell_wills)
    syncFarewellLimits(join?.farewell_limits ?? (gr as any).farewell_limits)
    syncBestMove(join?.best_move ?? (gr as any).best_move)
    activeFarewellAllowed.value = true
    if (Number.isFinite(mr) && mr > 0) {
      minReadyToStart.value = mr
    }
    const phase = (gr.phase as GamePhase) || 'idle'
    gamePhase.value = phase
    const rawResult = String((gr as any).result || '')
    if (rawResult === 'red' || rawResult === 'black' || rawResult === 'draw') {
      gameResult.value = rawResult as GameResult
      knownRolesVisible.value = true
    } else {
      gameResult.value = ''
    }
    fillSeats((gr.seats || {}) as Record<string, any>)
    gamePlayers.clear()
    gameAlive.clear()
    const grPlayers = Array.isArray(gr.players) ? gr.players.map((x: any) => String(x)) : []
    const grAlive = Array.isArray(gr.alive) ? gr.alive.map((x: any) => String(x)) : []
    for (const uid of grPlayers) gamePlayers.add(uid)
    for (const uid of grAlive) gameAlive.add(uid)
    gameRolesByUser.clear()
    const grRoles = join?.game_roles || {}
    for (const [uid, role] of Object.entries(grRoles)) {
      gameRolesByUser.set(String(uid), role as GameRoleKind)
    }
    syncGameFouls(join?.game_fouls)
    deathReasonByUser.clear()
    const deathsRaw = join?.game_deaths || {}
    if (deathsRaw && typeof deathsRaw === 'object') {
      for (const [uid, reason] of Object.entries(deathsRaw)) {
        const key = String(uid)
        const val = String(reason || '')
        if (key) deathReasonByUser.set(key, val)
      }
    }
    const rp = (gr as any).roles_pick
    if (phase === 'roles_pick' && rp && typeof rp === 'object') {
      rolePick.activeUserId = String(rp.turn_uid || '')
      rolePick.order = Array.isArray(rp.order) ? rp.order.map((x: any) => String(x)) : []
      rolePick.picked = new Set((rp.picked || []).map((x: any) => String(x)))
      const rawMs = secondsToMs(rp.deadline)
      rolePick.remainingMs = withLatency(rawMs)
      rolePick.takenCards = normalizeCards(rp.taken_cards)
    } else {
      rolePick.activeUserId = ''
      rolePick.order = []
      rolePick.picked = new Set<string>()
      rolePick.remainingMs = 0
      rolePick.takenCards = []
    }
    const mt = (gr as any).mafia_talk_start
    if (phase === 'mafia_talk_start' && mt && typeof mt === 'object') {
      const rawMs = secondsToMs(mt.deadline)
      setMafiaTalkRemainingMs(rawMs, false)
    } else {
      setMafiaTalkRemainingMs(0, false)
    }

    const dy = (gr as any).day
    const vt = (gr as any).vote
    const nt = (gr as any).night

    if (phase === 'day' && dy && typeof dy === 'object') {
      const num = Number((dy as any).number || 0)
      dayNumber.value = Number.isFinite(num) && num > 0 ? num : 0
      const cleared = loadNightResultCleared()
      if (cleared > nightResultClearedDay.value) nightResultClearedDay.value = cleared
      daySpeech.openingId = String(dy.opening_uid || '')
      daySpeech.closingId = String(dy.closing_uid || '')
      const rawMs = secondsToMs(dy.deadline)
      daySpeech.currentId = rawMs > 0 ? String(dy.current_uid || '') : ''
      setDaySpeechRemainingMs(rawMs, false)
      daySpeechesDone.value = isTrueLike((dy as any).speeches_done)
      const preludeSection = (dy as any).prelude
      const preludeActive = !!(preludeSection && typeof preludeSection === 'object' && isTrueLike((preludeSection as any).active))
      const preludeUid = String((preludeSection as any)?.uid || '')
      const farewellSection = (dy as any).farewell
      if (farewellSection && typeof farewellSection === 'object' && daySpeech.currentId) {
        const lim = Number((farewellSection as any).limit)
        if (Number.isFinite(lim) && lim >= 0) farewellLimits.set(daySpeech.currentId, Math.floor(lim))
        upsertFarewellForSpeaker(daySpeech.currentId, (farewellSection as any).wills)
        if ('allowed' in (farewellSection as any)) {
          activeFarewellAllowed.value = isTrueLike((farewellSection as any).allowed)
        }
      }
      const farewellActive = !!(daySpeech.currentId && daySpeech.remainingMs > 0 && ((preludeActive && preludeUid && daySpeech.currentId === preludeUid) || farewellSection))
      currentFarewellSpeech.value = farewellActive
      activeFarewellSpeakerId.value = farewellActive ? daySpeech.currentId : ''
      replaceIds(dayNominees, (dy as any).nominees)
      nominatedThisSpeechByMe.value = isTrueLike((dy as any).nominated_this_speech)

      const lastNight = (dy as any).night ?? nt
      const hasNightPayload = !!lastNight && typeof lastNight === 'object' && ('kill_ok' in lastNight || 'kill_uid' in lastNight)
      const hadNight = hasNightPayload && dayNumber.value > 1
      if (hadNight) {
        night.killOk = isTrueLike((lastNight as any).kill_ok)
        night.killUid = String((lastNight as any).kill_uid || '')
        night.hasResult = true
      } else {
        night.killOk = false
        night.killUid = ''
        night.hasResult = false
      }
      if (daySpeech.currentId || daySpeechesDone.value || nightResultClearedDay.value >= dayNumber.value) {
        night.killOk = false
        night.killUid = ''
        night.hasResult = false
        if (nightResultClearedDay.value < dayNumber.value && (daySpeech.currentId || daySpeechesDone.value)) {
          nightResultClearedDay.value = dayNumber.value
          persistNightResultCleared(dayNumber.value)
        }
      }
    } else if (phase === 'vote' && vt && typeof vt === 'object') {
      resetDaySpeechState(false)
      daySpeechesDone.value = true
      replaceIds(dayNominees, (vt as any).nominees)

      const rawMs = secondsToMs((vt as any).deadline)
      setVoteRemainingMs(rawMs, false)

      const done = isTrueLike((vt as any).done)
      const aborted = isTrueLike((vt as any).aborted)
      const resultsReady = isTrueLike((vt as any).results_ready)
      const liftStateRaw = String((vt as any).lift_state || '')
      vote.done = done
      voteAborted.value = aborted
      voteResultShown.value = resultsReady
      voteStartedForCurrent.value = isTrueLike((vt as any).started)
      voteLiftState.value = liftStateRaw ? (liftStateRaw as typeof voteLiftState.value) : 'none'

      votedUsers.clear()
      votedThisRound.clear()

      const curIdRaw  = String((vt as any).current_uid || '')
      if (aborted || resultsReady) {
        vote.currentId = ''
        voteStartedForCurrent.value = false
      } else {
        vote.currentId = curIdRaw
        const votedRaw = (vt as any).voted
        if (Array.isArray(votedRaw)) {
          for (const uid of votedRaw) {
            const s = String(uid)
            if (s) votedUsers.add(s)
          }
        }
        const votedCurRaw = (vt as any).voted_for_current
        if (Array.isArray(votedCurRaw) && curIdRaw) {
          for (const uid of votedCurRaw) {
            const s = String(uid)
            if (s) votedThisRound.add(s)
          }
        }
      }
      
      nominatedThisSpeechByMe.value = false
      const leadersRaw = (vt as any).leaders
      if (Array.isArray(leadersRaw)) replaceIds(voteResultLeaders, leadersRaw)
      else replaceIds(voteResultLeaders, undefined)

      const speech = (vt as any).speech
      if (speech && typeof speech === 'object') {
        const spId = String((speech as any).speaker_uid || '')
        const spMs = secondsToMs((speech as any).deadline)
        daySpeech.openingId = spId
        daySpeech.closingId = spId
        daySpeech.currentId = spMs > 0 && spId ? spId : ''
        setDaySpeechRemainingMs(spMs, false)
        daySpeechesDone.value = false
        voteLeaderSpeechesDone.value = false
        voteLeaderKilled.value = false
        const kind = String((speech as any).kind || '')
        const farewellSection = (vt as any).farewell
        if (kind === 'farewell' && spId) {
          if (farewellSection && typeof farewellSection === 'object') {
            const lim = Number((farewellSection as any).limit)
            if (Number.isFinite(lim) && lim >= 0) farewellLimits.set(spId, Math.floor(lim))
            upsertFarewellForSpeaker(spId, (farewellSection as any).wills)
            if ('allowed' in (farewellSection as any)) {
              activeFarewellAllowed.value = isTrueLike((farewellSection as any).allowed)
            } else {
              activeFarewellAllowed.value = true
            }
          }
          const active = spMs > 0 && !!spId
          currentFarewellSpeech.value = active
          activeFarewellSpeakerId.value = active ? spId : ''
        } else {
          currentFarewellSpeech.value = false
          activeFarewellSpeakerId.value = ''
          activeFarewellAllowed.value = true
        }
      } else {
        setDaySpeechRemainingMs(0, false)
        daySpeech.currentId = ''
        const done = isTrueLike((vt as any).speeches_done)
        daySpeechesDone.value = done
        voteLeaderSpeechesDone.value = done
        voteLeaderKilled.value = false
        currentFarewellSpeech.value = false
        activeFarewellSpeakerId.value = ''
        activeFarewellAllowed.value = true
      }
      voteResultShown.value = isTrueLike((vt as any).results_ready)
    } else if (phase === 'night' && nt && typeof nt === 'object') {
      night.stage = String((nt as any).stage || 'sleep') as any
      const ms = secondsToMs((nt as any).deadline)
      setNightRemainingMs(ms, false)
      myNightShotTarget.value = ''
      myNightCheckTarget.value = ''
      headNightPicks.clear()
      const headPicksRaw = (nt as any).head_picks
      if (headPicksRaw && typeof headPicksRaw === 'object') {
        for (const [uid, seat] of Object.entries(headPicksRaw.picks || {})) {
          const n = Number(seat)
          if (Number.isFinite(n) && n > 0) headNightPicks.set(String(uid), n)
        }
      }
      nightCheckedByMe.clear()
      nightKnownByMe.clear()
      const checkedRaw = (nt as any).checked
      if (Array.isArray(checkedRaw)) {
        for (const u of checkedRaw) {
          const s = String(u)
          if (s) nightCheckedByMe.add(s)
        }
      }
      const knownRaw = (nt as any).known
      if (knownRaw && typeof knownRaw === 'object') {
        for (const [u, rr] of Object.entries(knownRaw)) {
          const role = String(rr) as GameRoleKind
          nightKnownByMe.set(String(u), role)
        }
      }
    } else {
      resetDaySpeechState(false)
      replaceIds(dayNominees, undefined)
      nominatedThisSpeechByMe.value = false
      resetVoteState(false)
      setNightRemainingMs(0, false)
      night.stage = 'sleep'
    }
    const playersCount = gamePlayers.size
    const rolesCount = gameRolesByUser.size
    rolesVisibleForHead.value = playersCount > 0 && rolesCount >= playersCount
    if (phase !== 'idle' && gamePlayers.size === 0) fillPlayersFromSeats()
    offlineInGame.clear()
    if (phase !== 'idle') {
      const snapshotSet = new Set<string>(snapshotIds ?? [])
      const seatIds = Object.keys(seatsByUser)
      const allInGameIds = new Set<string>([...grPlayers, ...seatIds].map(String))
      for (const uid of allInGameIds) {
        if (!snapshotSet.has(uid)) offlineInGame.add(uid)
      }
    }
  }

  function handleGameStarted(payload: any) {
    resetRolesUiState()
    resetBestMoveState()
    offlineInGame.clear()
    deathReasonByUser.clear()
    gamePhase.value = (payload?.phase as GamePhase) || 'roles_pick'
    if (payload?.min_ready != null) {
      const v = Number(payload.min_ready)
      if (Number.isFinite(v) && v > 0) minReadyToStart.value = v
    }
    fillSeats((payload?.seats || {}) as Record<string, any>)
    fillPlayersFromSeats()
  }

  function handleGameFinished(payload: any) {
    const result = String(payload?.result || '')
    if (result === 'red' || result === 'black' || result === 'draw') {
      gameResult.value = result as GameResult
      knownRolesVisible.value = true
      farewellWills.clear()
      farewellLimits.clear()
      currentFarewellSpeech.value = false
      activeFarewellSpeakerId.value = ''
      activeFarewellAllowed.value = true
    } else {
      gameResult.value = ''
    }

    const roles = payload?.roles
    if (roles && typeof roles === 'object') {
      gameRolesByUser.clear()
      for (const [uid, role] of Object.entries(roles)) {
        gameRolesByUser.set(String(uid), role as GameRoleKind)
      }
      rolesVisibleForHead.value = true
    }
  }

  function handleGameEnded(_payload: any): 'head' | 'player' | 'none' {
    const roleBeforeEnd = myGameRole.value
    resetRolesUiState()
    resetBestMoveState()
    gamePhase.value = 'idle'
    Object.keys(seatsByUser).forEach((k) => { delete seatsByUser[k] })
    gamePlayers.clear()
    gameAlive.clear()
    offlineInGame.clear()
    gameFoulsByUser.clear()
    deathReasonByUser.clear()
    revotePromptCandidate.value = ''
    return roleBeforeEnd
  }

  function handleGamePlayerLeft(p: any) {
    const uid = String(p?.user_id ?? '')
    if (!uid) return
    gameAlive.delete(uid)
    gameFoulsByUser.delete(uid)
    if (p?.reason) deathReasonByUser.set(uid, String(p.reason))
  }

  function handleGameRolesTurn(p: any) {
    rolePick.activeUserId = String(p?.user_id || '')
    rolePick.order = Array.isArray(p?.order) ? p.order.map((x: any) => String(x)) : []
    rolePick.picked = new Set((p?.picked || []).map((x: any) => String(x)))
    const remainingSec = Number(p?.deadline || 0)
    rolePick.remainingMs = remainingSec > 0 ? remainingSec * 1000 : 0
    rolePick.takenCards = normalizeCards(p?.taken_cards)
    syncRoleOverlayWithTurn()
  }

  function handleGameRolesPicked(p: any) {
    const uid = String(p?.user_id || '')
    if (!uid) return
    rolePick.picked.add(uid)
    const remaining = rolePick.order.filter(id => !rolePick.picked.has(id))
    if (
      remaining.length === 0 &&
      rolePick.activeUserId === uid &&
      roleOverlayMode.value !== 'pick'
    ) {
      rolePick.activeUserId = ''
      rolePick.remainingMs = 0
    }
  }

  const ROLE_REVEAL_MS = 3000
  function handleGameRoleAssigned(p: any) {
    const uid = String(p?.user_id || '')
    const role = String(p?.role || '')
    if (!uid || !role) return
    gameRolesByUser.set(uid, role as GameRoleKind)
    if (uid === localId.value) {
      knownRolesVisible.value = true
      roleOverlayMode.value = 'reveal'
      roleOverlayCard.value = Number(p?.card || 0) || null
      if (roleOverlayTimerId.value != null) {
        clearTimeout(roleOverlayTimerId.value)
      }
      roleOverlayTimerId.value = window.setTimeout(() => {
        roleOverlayMode.value = 'hidden'
        roleOverlayTimerId.value = null
      }, ROLE_REVEAL_MS)
    }
  }

  function handleGameRolesReveal(p: any) {
    const roles = (p?.roles || {}) as Record<string, string>
    for (const [uid, role] of Object.entries(roles)) {
      gameRolesByUser.set(String(uid), role as GameRoleKind)
    }
    if (myGameRole.value === 'head') rolesVisibleForHead.value = true
  }

  function handleGameDaySpeech(p: any) {
    const openingId = String(p?.opening_uid || '')
    const closingId = String(p?.closing_uid || '')
    const speakerId = String(p?.speaker_uid || '')
    const ms = secondsToMs(p?.deadline)
    activeFarewellAllowed.value = true
    const farewellSection = (p as any)?.farewell
    if (farewellSection && typeof farewellSection === 'object' && speakerId) {
      const lim = Number((farewellSection as any).limit)
      if (Number.isFinite(lim) && lim >= 0) farewellLimits.set(speakerId, Math.floor(lim))
      upsertFarewellForSpeaker(speakerId, (farewellSection as any).wills)
      if ('allowed' in (farewellSection as any)) {
        activeFarewellAllowed.value = isTrueLike((farewellSection as any).allowed)
      } else {
        activeFarewellAllowed.value = true
      }
    }
    if ('vote_blocked' in (p as any)) {
      const blocked = isTrueLike((p as any).vote_blocked)
      voteBlocked.value = blocked
      if (blocked) {
        replaceIds(dayNominees, [])
        nominatedThisSpeechByMe.value = false
      }
    }

    daySpeech.openingId = openingId
    daySpeech.closingId = closingId
    daySpeech.currentId = ms > 0 ? speakerId : ''
    setDaySpeechRemainingMs(ms, true)

    const done = isTrueLike((p as any)?.speeches_done)
    const killed = isTrueLike((p as any)?.killed)
    const voteSpeechKind = String((p as any)?.vote_speech_kind || '')
    const isActiveSpeech = ms > 0 && !!speakerId

    const nightPayload = (p as any)?.night
    if (nightPayload && typeof nightPayload === 'object') {
      night.killOk = isTrueLike((nightPayload as any).kill_ok)
      night.killUid = String((nightPayload as any).kill_uid || '')
      night.hasResult = night.killOk && !!night.killUid
    } else if (isTrueLike((p as any)?.prelude)) {
      night.killOk = false
      night.killUid = ''
      night.hasResult = false
    }

    const isFarewellSpeech = isActiveSpeech && (isTrueLike((p as any)?.prelude) || killed || voteSpeechKind === 'farewell' || !!farewellSection)
    currentFarewellSpeech.value = isFarewellSpeech
    activeFarewellSpeakerId.value = isFarewellSpeech ? speakerId : ''
    if (!isFarewellSpeech) activeFarewellAllowed.value = true
    if (isActiveSpeech && night.hasResult) {
      night.hasResult = false
      night.killOk = false
      night.killUid = ''
      nightResultClearedDay.value = dayNumber.value
      persistNightResultCleared(dayNumber.value)
    }

    if (isActiveSpeech) {
      daySpeechesDone.value = false
      if (speakerId !== localId.value) nominatedThisSpeechByMe.value = false
    } else if (done || (speakerId && closingId && speakerId === closingId)) {
      daySpeechesDone.value = true
      nominatedThisSpeechByMe.value = false
    }

    if (gamePhase.value === 'vote') {
      if (isActiveSpeech) {
        voteLeaderSpeechesDone.value = false
        voteLeaderKilled.value = false
      } else if (done) {
        voteLeaderSpeechesDone.value = true
        voteLeaderKilled.value = killed
      } else if (killed && voteLiftState.value !== 'passed') {
        voteLeaderSpeechesDone.value = true
        voteLeaderKilled.value = true
      } else if (speakerId && closingId && speakerId === closingId) {
        voteLeaderSpeechesDone.value = true
      }
    }
  }

  function handleGameNomineeAdded(p: any) {
    const orderRaw = p?.order
    replaceIds(dayNominees, orderRaw)
  }

  function handleGameFarewellUpdate(p: any) {
    const speakerId = String(p?.speaker_uid || '')
    if (!speakerId) return
    const limRaw = (p as any)?.limit
    if (limRaw != null) {
      const lim = Number(limRaw)
      if (Number.isFinite(lim) && lim >= 0) farewellLimits.set(speakerId, Math.floor(lim))
    }
    if ((p as any)?.wills) {
      upsertFarewellForSpeaker(speakerId, (p as any).wills)
    }
  }

  function handleGameBestMoveUpdate(p: any) {
    const payload = (p as any)?.best_move
    if (payload && typeof payload === 'object') {
      if (isTrueLike((payload as any).active)) headNightPicks.clear()
      syncBestMove(payload)
    }
  }

  function handleGameFoul(p: any) {
    const uid = String(p?.user_id || '')
    if (!uid) return
    foulActive.add(uid)
    const ms = secondsToMs(p?.duration)
    if (ms <= 0) return
    window.setTimeout(() => {
      foulActive.delete(uid)
    }, ms)
  }

  function handleGameFouls(p: any) {
    syncGameFouls(p?.fouls)
  }

  function handleGameVoteState(p: any) {
    const vt = p?.vote
    if (!vt || typeof vt !== 'object') return
    const prevId = vote.currentId
    const newId = String(vt.current_uid || '')
    const ms = secondsToMs(vt.deadline)
    const liftStateRaw = String((vt as any).lift_state || '')
    voteLiftState.value = liftStateRaw ? (liftStateRaw as typeof voteLiftState.value) : 'none'
    vote.currentId = newId
    setVoteRemainingMs(ms, true)
    vote.done = isTrueLike(vt.done)
    voteAborted.value = isTrueLike((vt as any).aborted)
    if ('blocked' in (vt as any)) {
      voteBlocked.value = isTrueLike((vt as any).blocked)
    } else if (gamePhase.value === 'vote') {
      voteBlocked.value = false
    }
    voteResultShown.value = isTrueLike((vt as any).results_ready)
    const isRestart = isTrueLike((vt as any).restart)
    const cleared = Array.isArray((vt as any).cleared_voters) ? (vt as any).cleared_voters.map((x: any) => String(x)) : []
    if (!newId) {
      voteStartedForCurrent.value = false
      revotePromptCandidate.value = ''
    } else if (newId !== prevId) {
      voteStartedForCurrent.value = ms > 0
      votedThisRound.clear()
      if (revotePromptCandidate.value && revotePromptCandidate.value !== newId) revotePromptCandidate.value = ''
    } else {
      voteStartedForCurrent.value = ms > 0
    }
    if (isRestart) {
      voteStartedForCurrent.value = false
      for (const uid of cleared) {
        votedUsers.delete(uid)
        votedThisRound.delete(uid)
      }
    }
    replaceIds(dayNominees, vt.nominees)
  }

  function handleGameVoteAborted(_p: any) {
    voteAborted.value = true
    vote.done = true
    const blocked = isTrueLike((_p as any)?.blocked)
    if (blocked) voteBlocked.value = true
    setVoteRemainingMs(0, true)
    votedUsers.clear()
    votedThisRound.clear()

    vote.currentId = ''
    revotePromptCandidate.value = ''
    voteStartedForCurrent.value = false
    voteLiftState.value = 'none'
    voteLeaderSpeechesDone.value = true
    voteLeaderKilled.value = false
    replaceIds(voteResultLeaders, [])
    nominatedThisSpeechByMe.value = false
    const nomineesRaw = (_p as any)?.nominees
    if (Array.isArray(nomineesRaw)) replaceIds(dayNominees, nomineesRaw)
    else if (blocked) replaceIds(dayNominees, [])
  }

  function handleGameVoted(p: any) {
    const uid = String(p?.user_id || '')
    const target = String(p?.target_id ?? '')
    const lift = isTrueLike((p as any)?.lift)
    if (!uid || (!target && !lift)) return
    votedUsers.add(uid)
    if (lift || target === vote.currentId) {
      votedThisRound.add(uid)
    }
  }

  function handleGameVoteResult(p: any) {
    voteAborted.value = false
    voteResultShown.value = true
    vote.done = true
    if ('blocked' in (p as any)) {
      voteBlocked.value = isTrueLike((p as any).blocked)
    } else {
      voteBlocked.value = false
    }
    const speechesDone = isTrueLike((p as any)?.speeches_done)
    voteLeaderSpeechesDone.value = speechesDone
    voteLeaderKilled.value = false
    votedUsers.clear()
    votedThisRound.clear()

    vote.currentId = ''
    revotePromptCandidate.value = ''
    voteStartedForCurrent.value = false
    setVoteRemainingMs(0, true)

    const liftStateRaw = String((p as any)?.lift_state || '')
    const liftResult = liftStateRaw ? (liftStateRaw as typeof voteLiftState.value) : 'none'
    voteLiftState.value = liftResult

    const leadersRaw = p?.leaders
    if (liftResult === 'failed') {
      voteLeaderSpeechesDone.value = true
      replaceIds(voteResultLeaders, [])
    } else if (speechesDone && (!leadersRaw || (Array.isArray(leadersRaw) && leadersRaw.length === 0))) {
      voteLeaderSpeechesDone.value = true
      replaceIds(voteResultLeaders, [])
    } else {
      replaceIds(voteResultLeaders, leadersRaw)
    }

    const nomineesRaw = p?.nominees
    if (liftResult === 'failed' || voteLeaderSpeechesDone.value) replaceIds(dayNominees, [])
    else replaceIds(dayNominees, nomineesRaw, s => voteResultLeaders.includes(s))
  }

  async function finishVote(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_vote_finish', {})
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 400 && code === 'bad_phase') {
         void alertDialog('Сейчас не фаза голосования')
      } else if (st === 403 && code === 'forbidden') {
         void alertDialog('Только ведущий может завершать голосование')
      } else if (st === 409 && code === 'vote_not_done') {
         void alertDialog('Голосование еще не завершено')
      } else if (st === 409 && code === 'no_nominees') {
         void alertDialog('Никто не выставлен')
      } else if (st === 409 && code === 'no_leaders') {
         void alertDialog('Нет лидеров голосования')
      } else {
         void alertDialog('Не удалось завершить голосование')
      }
      return
    }
    voteResultShown.value = true
    votedUsers.clear()
    votedThisRound.clear()
  }

  async function prepareVoteLift(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_vote_lift_prepare', {})
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 400 && code === 'bad_phase')  void alertDialog('Сейчас нельзя продолжить голосование')
      else if (st === 403 && code === 'forbidden')  void alertDialog('Только ведущий может продолжить')
      else if (st === 409 && code === 'lift_not_ready')  void alertDialog('Продолжение недоступно')
      else if (st === 409 && code === 'vote_not_ready')  void alertDialog('Результаты голосования ещё не готовы')
      else  void alertDialog('Не удалось продолжить голосование')
      return
    }
  }

  async function startVoteLift(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_vote_lift_start', {})
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 400 && code === 'bad_phase')  void alertDialog('Сейчас нельзя начать голосование за подъём')
      else if (st === 403 && code === 'forbidden')  void alertDialog('Только ведущий может начать голосование за подъём')
      else if (st === 409 && code === 'lift_not_ready')  void alertDialog('Голосование за подъём недоступно')
      else if (st === 409 && code === 'no_nominees')  void alertDialog('Нет кандидатов для голосования')
      else  void alertDialog('Не удалось начать голосование за подъём')
      return
    }
    voteResultShown.value = false
    votedUsers.clear()
    votedThisRound.clear()
  }

  watch(() => [rolePick.activeUserId, localId.value, myGameRoleKind.value, gamePhase.value], () => { syncRoleOverlayWithTurn() })

  watch(knownRolesVisible, (val) => {
    if (typeof window === 'undefined') return
    try { window.localStorage.setItem('roomRolesVisible', val ? '1' : '0') } catch {}
  })

  watch(() => [gamePhase.value, daySpeech.currentId, daySpeech.remainingMs], (_v, _ov, onCleanup) => {
      scheduleFinishSpeechUnlock()
      onCleanup(() => resetFinishSpeechDelay())
  }, { immediate: true })

  watch(() => [isHead.value, gamePhase.value, daySpeechesDone.value, daySpeech.currentId, daySpeech.remainingMs], (_v, _ov, onCleanup) => {
      schedulePassSpeechUnlock()
      onCleanup(() => resetPassSpeechDelay())
  }, { immediate: true })

  watch(() => [isHead.value, gamePhase.value, rolesVisibleForHead.value], (_v, _ov, onCleanup) => {
      scheduleStartMafiaTalkUnlock()
      onCleanup(() => resetStartMafiaTalkDelay())
  }, { immediate: true })

  watch(() => [isHead.value, gamePhase.value], (_v, _ov, onCleanup) => {
      scheduleStartDayUnlock()
      onCleanup(() => resetStartDayDelay())
  }, { immediate: true })

  watch(() => [isHead.value, gamePhase.value, night.stage, bestMove.uid, bestMove.active], (_v, _ov, onCleanup) => {
      scheduleDayFromNightUnlock()
      onCleanup(() => resetDayFromNightDelay())
  }, { immediate: true })

  watch(() => [
    isHead.value,
    gamePhase.value,
    vote.done,
    voteResultShown.value,
    voteAborted.value,
    voteLeaderKilled.value,
    voteLiftState.value,
    voteResultLeaders.length,
    voteLeaderSpeechesDone.value,
    daySpeech.currentId,
    daySpeech.remainingMs,
  ], (_v, _ov, onCleanup) => {
      scheduleLeaderSpeechUnlock()
      onCleanup(() => resetLeaderSpeechDelay())
  }, { immediate: true })

  watch(() => settings.gameMinReadyPlayers, (value) => {
      const v = Number(value)
      if (Number.isFinite(v) && v > 0 && gamePhase.value === 'idle') minReadyToStart.value = v
  })

  async function goToMafiaTalk(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_phase_next', { from: 'roles_pick', to: 'mafia_talk_start' })
    if (!resp?.ok) {
       void alertDialog('Не удалось перейти к договорке')
      return
    }
  }

  function setMafiaTalkRemainingMs(ms: number, changed: boolean) {
    setTimerWithLatency(mafiaTalk, ms, mafiaTalkTimerId, changed)
  }

  function setDaySpeechRemainingMs(ms: number, changed: boolean) {
    setTimerWithLatency(daySpeech, ms, daySpeechTimerId, changed, () => {
      daySpeech.currentId = ''
      currentFarewellSpeech.value = false
      activeFarewellSpeakerId.value = ''
    })
  }

  function handleGamePhaseChange(p: any) {
    const to = String(p?.to || '') as GamePhase
    gamePhase.value = to
    if (to !== 'vote') {
      voteLeaderSpeechesDone.value = false
      voteLeaderKilled.value = false
    }
    if (to === 'mafia_talk_start') {
      const mt = p?.mafia_talk_start
      const ms = secondsToMs(mt?.deadline)
      setMafiaTalkRemainingMs(ms, true)
    } else {
      setMafiaTalkRemainingMs(0, true)
    }
    if (to === 'night') {
      resetDaySpeechState(true)
      resetVoteState(true)
      resetBestMoveState()
      const nt = p?.night
      night.stage = String(nt?.stage || 'sleep') as any
      setNightRemainingMs(secondsToMs(nt?.deadline), true)
      night.hasResult = false
      myNightShotTarget.value = ''
      myNightCheckTarget.value = ''
      headNightPicks.clear()

      const checkedRaw = (nt as any)?.checked
      if (Array.isArray(checkedRaw)) {
        nightCheckedByMe.clear()
        for (const u of checkedRaw) nightCheckedByMe.add(String(u))
      }
      const knownRaw = (nt as any)?.known
      if (knownRaw && typeof knownRaw === 'object') {
        nightKnownByMe.clear()
        for (const [u, rr] of Object.entries(knownRaw)) nightKnownByMe.set(String(u), String(rr) as GameRoleKind)
      }
      return
    }
    if (to === 'day') {
      const dy = p?.day
      const num = Number(dy?.number || 0)
      dayNumber.value = Number.isFinite(num) && num > 0 ? num : 0
      resetDaySpeechState(true)
      daySpeech.openingId = String(dy?.opening_uid || '')
      daySpeech.closingId = String(dy?.closing_uid || '')
      const ms = secondsToMs(dy?.deadline)
      daySpeech.currentId = ms > 0 ? String(dy?.current_uid || '') : ''
      setDaySpeechRemainingMs(ms, true)

      replaceIds(dayNominees, undefined)
      nominatedThisSpeechByMe.value = false
      const n = (p as any)?.night
      night.killOk = isTrueLike(n?.kill_ok)
      night.killUid = String(n?.kill_uid || '')
      night.hasResult = String((p as any)?.from || '') === 'night'
      headNightPicks.clear()
    } else if (to === 'vote') {
      const vt = p?.vote
      resetDaySpeechState(true)
      daySpeechesDone.value = true
      replaceIds(voteResultLeaders, undefined)
      voteResultShown.value = false
      voteLeaderSpeechesDone.value = false
      voteLeaderKilled.value = false
      replaceIds(dayNominees, vt?.nominees)
      vote.currentId = String(vt?.current_uid || '')
      const ms = secondsToMs(vt?.deadline)
      setVoteRemainingMs(ms, true)
      vote.done = isTrueLike(vt?.done)
      votedUsers.clear()
      votedThisRound.clear()
      nominatedThisSpeechByMe.value = false
      voteStartedForCurrent.value = ms > 0
    } else {
      resetDaySpeechState(true)
      replaceIds(dayNominees, undefined)
      nominatedThisSpeechByMe.value = false
      resetVoteState(true)
      dayNumber.value = 0
    }
  }

  function isNightVictimFarewellSpeech(me: string): boolean {
    return (
      gamePhase.value === 'day' &&
      night.hasResult &&
      night.killOk &&
      !!night.killUid &&
      me === night.killUid &&
      daySpeech.currentId === me &&
      daySpeech.remainingMs > 0
    )
  }

  function canNominateTarget(id: string): boolean {
    if (gameFinished.value) return false
    const me = localId.value
    if (!me) return false
    if (currentFarewellSpeech.value) return false
    if (isNightVictimFarewellSpeech(me)) return false
    if (gamePhase.value !== 'day') return false
    if (daySpeech.currentId !== me) return false
    if (daySpeech.remainingMs <= 0) return false
    if (!amIAlive.value) return false
    if (voteBlocked.value) return false
    if (!gamePlayers.has(id)) return false
    if (!gameAlive.has(id)) return false
    if (dayNominees.includes(id)) return false
    return !nominatedThisSpeechByMe.value
  }
  
  function handleGameNightState(p: any) {
    const nt = p?.night
    if (!nt || typeof nt !== 'object') return
    const prevStage = night.stage
    const nextStage = String(nt.stage || 'sleep') as any
    const stageChanged = nextStage !== prevStage
    night.stage = nextStage
    setNightRemainingMs(secondsToMs(nt.deadline), true)
    if ('best_move' in (nt as any)) syncBestMove((nt as any).best_move)
    if (!stageChanged) return
    if (nextStage === 'shoot') {
      myNightShotTarget.value = ''
      headNightPicks.clear()
    } else if (nextStage === 'checks') {
      myNightCheckTarget.value = ''
      headNightPicks.clear()
    }
  }

  function handleGameNightHeadPicks(p: any) {
    const picks = (p?.picks || {}) as Record<string, any>
    headNightPicks.clear()
    for (const [uid, seat] of Object.entries(picks)) {
      const n = Number(seat)
      if (Number.isFinite(n) && n > 0) headNightPicks.set(String(uid), n)
    }
  }

  function handleGameNightReveal(p: any) {
    const tid = String(p?.target_id || '')
    const rr = String(p?.shown_role || '') as GameRoleKind
    if (!tid || !rr) return
    nightKnownByMe.set(tid, rr)
    nightCheckedByMe.add(tid)
  }

  function canShootTarget(targetId: string): boolean {
    if (gameFinished.value) return false
    if (gamePhase.value !== 'night') return false
    if (night.stage !== 'shoot') return false
    if (night.remainingMs <= 0) return false
    if (!amIAlive.value) return false
    const me = localId.value
    if (!me) return false
    const myRole = gameRolesByUser.get(me)
    if (myRole !== 'mafia' && myRole !== 'don') return false
    if (myNightShotTarget.value) return false
    return gamePlayers.has(targetId)
  }

  function canCheckTarget(targetId: string): boolean {
    if (gameFinished.value) return false
    if (gamePhase.value !== 'night') return false
    if (night.stage !== 'checks') return false
    if (night.remainingMs <= 0) return false
    if (!amIAlive.value) return false
    const me = localId.value
    if (!me) return false
    if (targetId === me) return false
    const myRole = gameRolesByUser.get(me)
    if (myRole !== 'don' && myRole !== 'sheriff') return false
    if (myNightCheckTarget.value) return false
    if (!gamePlayers.has(targetId)) return false
    if (nightCheckedByMe.has(targetId)) return false
    if (myRole === 'don') {
      const tr = gameRolesByUser.get(targetId)
      if (tr === 'mafia' || tr === 'don') return false
    }
    return true
  }

  async function shootTarget(targetUserId: string, sendAck: SendAckFn): Promise<void> {
    const uidNum = Number(targetUserId)
    if (!uidNum) return
    const resp = await sendAck('game_night_shoot', { user_id: uidNum })
    if (resp?.ok) myNightShotTarget.value = targetUserId
  }

  async function checkTarget(targetUserId: string, sendAck: SendAckFn): Promise<void> {
    const uidNum = Number(targetUserId)
    if (!uidNum) return
    const resp = await sendAck('game_night_check', { user_id: uidNum })
    if (resp?.ok) {
      myNightCheckTarget.value = targetUserId
      ensureKnownRolesVisible()
    }
  }

  async function startNightShoot(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_night_shoot_start', {})
    if (!resp?.ok)  void alertDialog('Не удалось начать отстрелы мафии')
  }

  async function startNightChecks(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_night_checks_start', {})
    if (!resp?.ok)  void alertDialog('Не удалось начать проверки')
  }

  async function nominateTarget(targetUserId: string, sendAck: SendAckFn): Promise<void> {
    const uidNum = Number(targetUserId)
    if (!uidNum) return
    const resp = await sendAck('game_nominate', { user_id: uidNum })
    if (!resp?.ok) {
      const code = resp?.error
      const st = resp?.status
      if (st === 400 && code === 'bad_phase') {
         void alertDialog('Сейчас не фаза дня')
      } else if (st === 403 && code === 'not_your_speech') {
         void alertDialog('Вы можете выставлять только во время своей речи')
      } else if (st === 403 && code === 'not_alive') {
         void alertDialog('Вы не являетесь живым игроком')
      } else if (st === 400 && code === 'target_not_alive') {
         void alertDialog('Игрок уже выбыл из игры')
      } else if (st === 409 && code === 'already_nominated') {
         void alertDialog('Вы уже выставили игрока в этой речи')
      } else if (st === 409 && code === 'target_already_on_ballot') {
         void alertDialog('Этот игрок уже выставлен')
      } else if (st === 409 && code === 'vote_blocked') {
         void alertDialog('Голосования не будет — нельзя выставлять игроков')
      } else {
         void alertDialog('Не удалось выставить игрока на голосование')
      }
      return
    }
    nominatedThisSpeechByMe.value = true
    const orderRaw = (resp as any).order
    replaceIds(dayNominees, orderRaw)
  }

  async function markFarewellChoice(targetUserId: string, verdict: FarewellVerdict, sendAck: SendAckFn): Promise<void> {
    const uidNum = Number(targetUserId)
    if (!uidNum) return
    const resp = await sendAck('game_farewell_mark', { user_id: uidNum, verdict })
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 409 && code === 'limit_reached') {
         void alertDialog('Лимит завещаний исчерпан')
      } else if (st === 409 && code === 'already_marked') {
         void alertDialog('Вы уже оставили завещание по этому игроку')
      } else if (st === 404 && code === 'target_not_alive') {
         void alertDialog('Игрок уже выбыл и не может быть отмечен')
      } else if (st === 409 && code === 'no_active_speech') {
         void alertDialog('Речь завершена, завещание недоступно')
      } else if (st === 409 && code === 'not_farewell') {
         void alertDialog('Сейчас нельзя оставлять завещание')
      } else {
         void alertDialog('Не удалось сохранить завещание')
      }
      return
    }
    handleGameFarewellUpdate(resp)
  }

  async function startBestMove(sendAck: SendAckFn): Promise<void> {
    if (!isHead.value) return
    const resp = await sendAck('game_best_move_start', {})
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 409 && code === 'best_move_unavailable') {
        void alertDialog('Лучший ход недоступен')
      } else if (st === 409 && code === 'night_not_finished') {
        void alertDialog('Ночь ещё не завершена')
      } else {
        void alertDialog('Не удалось начать лучший ход')
      }
      return
    }
    handleGameBestMoveUpdate(resp)
  }

  async function markBestMoveChoice(targetUserId: string, sendAck: SendAckFn): Promise<void> {
    const uidNum = Number(targetUserId)
    if (!uidNum) return
    const resp = await sendAck('game_best_move_mark', { user_id: uidNum })
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 409 && code === 'limit_reached') {
        void alertDialog('Можно выбрать только 3 кандидатов')
      } else if (st === 409 && code === 'already_marked') {
        void alertDialog('Вы уже отметили этого игрока')
      } else if (st === 404 && code === 'target_not_alive') {
        void alertDialog('Игрок уже выбыл из игры')
      } else if (st === 409 && code === 'best_move_inactive') {
        void alertDialog('Лучший ход пока недоступен')
      } else {
        void alertDialog('Не удалось выбрать лучший ход')
      }
      return
    }
    handleGameBestMoveUpdate(resp)
  }

  async function startVotePhase(sendAck: SendAckFn): Promise<void> {
    if (gamePhase.value === 'day') {
      const resp = await sendAck('game_phase_next', { from: 'day', to: 'vote' })
      if (!resp?.ok) {
        const st = resp?.status
        const code = resp?.error
        if (st === 400 && code === 'speeches_not_done') {
           void alertDialog('Сначала нужно закончить речи')
        } else if (st === 409 && code === 'no_nominees') {
           void alertDialog('Никто не выставлен – можно переходить к ночи')
        } else {
           void alertDialog('Не удалось начать голосование')
        }
      }
      return
    }
    if (gamePhase.value === 'vote') {
      await restartVoteForLeaders(sendAck)
    }
  }

  async function startCurrentCandidateVote(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_vote_control', { action: 'start' })
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 400 && code === 'bad_phase') {
         void alertDialog('Сейчас не фаза голосования')
      } else if (st === 403 && code === 'forbidden') {
         void alertDialog('Только ведущий может управлять голосованием')
      } else if (st === 409 && code === 'vote_already_ended') {
         void alertDialog('Голосование за этого кандидата уже завершено')
      } else if (st === 409 && code === 'vote_done') {
         void alertDialog('Голосование уже завершено')
      } else {
         void alertDialog('Не удалось запустить голосование за кандидата')
      }
    }
  }

  async function restartCurrentVote(sendAck: SendAckFn, targetId?: string): Promise<void> {
    const payload: Record<string, any> = {}
    const t = Number(targetId || vote.currentId || 0)
    if (Number.isFinite(t) && t > 0) payload.user_id = t
    const resp = await sendAck('game_vote_restart_current', payload)
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 400 && code === 'bad_phase') {
         void alertDialog('Сейчас не фаза голосования')
      } else if (st === 403 && code === 'forbidden') {
         void alertDialog('Переголосование может запустить только ведущий')
      } else if (st === 409 && code === 'vote_done') {
         void alertDialog('Голосование уже завершено')
      } else if (st === 409 && code === 'no_current_vote') {
         void alertDialog('Нет активной кандидатуры для голосования')
      } else if (st === 409 && code === 'no_nominees') {
         void alertDialog('Нет кандидатов для голосования')
      } else if (st === 409 && code === 'lift_in_progress') {
         void alertDialog('Идёт голосование за подъём — переголосование недоступно')
      } else {
         void alertDialog('Не удалось перезапустить голосование по текущему кандидату')
      }
      return
    }
    voteStartedForCurrent.value = false
    votedUsers.clear()
    votedThisRound.clear()
  }

  function maybeAskRevoteOnDisconnect(userId: string, sendAck: SendAckFn): void {
    if (!isHead.value) return
    if (gamePhase.value !== 'vote') return
    const cur = vote.currentId
    if (!cur || vote.remainingMs <= 0) return
    if (isDead(userId)) return
    if (votedUsers.has(userId)) return
    const seatLeft = seatIndex(userId)
    if (!seatLeft || seatLeft === 11) return
    if (revotePromptCandidate.value === cur) return
    revotePromptCandidate.value = cur
    const targetSeat = seatIndex(cur)
    const targetLabel = targetSeat != null ? targetSeat : 'кандидата'
    void confirmDialog({
      title: 'Переголосование',
      text: `Игрок ${seatLeft} покидал комнату во время голосования. Переголосовать за ${targetLabel}?`,
      confirmText: 'Переголосовать',
      cancelText: 'Отмена',
    }).then((ok) => {
      if (ok) void restartCurrentVote(sendAck, cur)
    })
  }

  async function goToNextCandidate(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_vote_control', { action: 'next' })
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 409 && code === 'vote_in_progress') {
         void alertDialog('Сначала дождитесь окончания голосования за текущего кандидата')
      } else if (st === 403 && code === 'forbidden') {
         void alertDialog('Только ведущий может управлять голосованием')
      } else {
         void alertDialog('Не удалось перейти к следующему кандидату')
      }
    }
  }

  async function voteForCurrent(sendAck: SendAckFn): Promise<void> {
    if (!canPressVoteButton()) return
    const resp = await sendAck('game_vote', {})
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 400 && code === 'bad_phase') {
         void alertDialog('Сейчас не фаза голосования')
      } else if (st === 403 && code === 'not_alive') {
         void alertDialog('Только живые игроки могут голосовать')
      } else if (st === 409 && code === 'already_voted') {
         void alertDialog('Вы уже проголосовали')
      } else if (st === 409 && (code === 'no_active_vote' || code === 'vote_window_closed')) {
         void alertDialog('Время голосования за этого кандидата вышло')
      } else if (st === 409 && code === 'vote_done') {
         void alertDialog('Голосование уже завершено')
      } else {
         void alertDialog('Не удалось проголосовать')
      }
      return
    }
  }

  async function finishMafiaTalk(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_phase_next', { from: 'mafia_talk_start', to: 'mafia_talk_end' })
    if (!resp?.ok) {
       void alertDialog('Не удалось завершить договорку')
      return
    }
  }

  async function startDay(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_phase_next', { from: 'mafia_talk_end', to: 'day' })
    if (!resp?.ok) {
       void alertDialog('Не удалось начать день')
      return
    }
  }

  async function leaveGame(sendAck: SendAckFn): Promise<void> {
    const ok = await confirmDialog({
      title: 'Покинуть игру',
      text: 'Вы уверены что хотите покинуть игру?',
      confirmText: 'Покинуть',
      cancelText: 'Отмена',
    })
    if (!ok) return
    const resp = await sendAck('game_leave', {})
    if (!resp?.ok) {
      const code = resp?.error
      const st = resp?.status
      const id = localId.value
      if (st === 400 && code === 'no_game') {
         void alertDialog('Игра не запущена')
      } else if (st === 400 && code === 'not_player') {
         void alertDialog('Вы не участвуете в этой игре')
      } else if (st === 400 && code === 'already_dead') {
        if (id) gameAlive.delete(id)
         void alertDialog('Вы уже выбыли из игры')
      } else {
         void alertDialog('Не удалось выйти из игры')
      }
      return
    }
    const id = localId.value
    if (id) gameAlive.delete(id)
  }

  function handleGameStartError(resp: Ack): void {
    const code = resp?.error
    const st = resp?.status
    if (st === 400 && code === 'not_enough_ready') {
       void alertDialog('Недостаточно готовых игроков для запуска игры')
    } else if (st === 403 && code === 'forbidden') {
       void alertDialog('Недостаточно прав для запуска игры')
    } else if (st === 403 && code === 'game_start_disabled') {
       void alertDialog('Запуск игр временно недоступен')
    } else if (st === 409 && code === 'already_in_other_game') {
       void alertDialog('Некоторые пользователи являются живыми игроками в другой комнате')
    } else if (st === 403 && code === 'not_in_room') {
       void alertDialog('Вы не в комнате')
    } else if (st === 409 && code === 'streaming_present') {
       void alertDialog('Остановите трансляции перед запуском игры')
    } else if (st === 409 && code === 'blocked_params') {
       void alertDialog('Снимите блокировки перед запуском игры')
    } else if (st === 409 && code === 'already_started') {
       void alertDialog('Игра уже запущена')
    } else {
       void alertDialog('Не удалось запустить игру')
    }
  }

  async function startGame(sendAck: SendAckFn): Promise<void> {
    if (startingGame.value) return
    startingGame.value = true
    try {
      const check = await sendAck('game_start', { confirm: false })
      if (!check?.ok) {
        handleGameStartError(check)
        return
      }
      const ok = await confirmDialog({
        title: 'Начало игры',
        text: 'Вы уверены что хотите начать игру?',
        confirmText: 'Начать',
        cancelText: 'Отмена',
      })
      if (!ok) return
      const resp = await sendAck('game_start', { confirm: true })
      if (!resp?.ok) {
        handleGameStartError(resp)
        return
      }
    } finally {
      startingGame.value = false
    }
  }

  function handleGameEndError(resp: Ack): void {
    const code = resp?.error
    const st = resp?.status
    if (st === 400 && code === 'no_game') {
       void alertDialog('Игра не запущена')
    } else if (st === 403 && code === 'forbidden') {
       void alertDialog('Недостаточно прав для завершения игры')
    } else {
       void alertDialog('Не удалось завершить игру')
    }
  }

  async function endGame(sendAck: SendAckFn): Promise<void> {
    if (endingGame.value) return
    const ok = await confirmDialog({
      title: 'Завершение игры',
      text: 'Вы уверены что хотите завершить игру?',
      confirmText: 'Завершить',
      cancelText: 'Отмена',
    })
    if (!ok) return
    endingGame.value = true
    try {
      const check = await sendAck('game_end', { confirm: false })
      if (!check?.ok) {
        handleGameEndError(check)
        return
      }
      const resp = await sendAck('game_end', { confirm: true })
      if (!resp?.ok) {
        handleGameEndError(resp)
      }
    } finally {
      endingGame.value = false
    }
  }

  async function pickRoleCard(card: number, sendAck: SendAckFn): Promise<void> {
    if (pickingRole.value) return
    if (card <= 0) return
    pickingRole.value = true
    try {
      const resp = await sendAck('game_roles_pick', { card })
      if (!resp?.ok) {
        const code = resp?.error
        const st = resp?.status
        if (st === 403 && code === 'not_your_turn') {
           void alertDialog('Сейчас ход другого игрока')
        } else if (st === 409 && code === 'card_taken') {
           void alertDialog('Эта карта уже занята')
        } else {
           void alertDialog('Не удалось выбрать роль')
        }
        return
      }
    } finally {
      pickingRole.value = false
    }
  }

  function shouldHighlightMafiaTile(id: string): boolean {
    if (gamePhase.value !== 'mafia_talk_start') return false
    const role = gameRolesByUser.get(id)
    if (!role) return false
    if (role !== 'mafia' && role !== 'don') return false
    const me = localId.value
    if (!me) return false
    const myRoleKind = gameRolesByUser.get(me) as GameRoleKind | undefined
    if (isHead.value) return true
    return myRoleKind === 'mafia' || myRoleKind === 'don'
  }

  async function passSpeech(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_speech_next', {})
    if (!resp?.ok) {
      const code = resp?.error
      const st = resp?.status
      if (st === 409 && code === 'day_speeches_done') {
         void alertDialog('Речи игроков завершены')
        daySpeechesDone.value = true
      } else if (st === 400 && code === 'bad_phase') {
         void alertDialog('Сейчас не фаза дня')
      } else if (st === 403 && code === 'forbidden') {
         void alertDialog('Только ведущий может передавать речь')
      } else {
         void alertDialog('Не удалось передать речь')
      }
    }
  }

  async function takeFoul(sendAck: SendAckFn): Promise<number | null> {
    const resp = await sendAck('game_foul', {})
    if (!resp?.ok) {
      const code = resp?.error
      const st = resp?.status
      if (st === 429 && code === 'too_soon') {
      } else if (st === 400 && code === 'bad_phase') {
         void alertDialog('Сейчас не фаза дня')
      } else if (st === 403 && code === 'not_alive') {
         void alertDialog('Вы не являетесь игроком или уже выбыли')
      } else if (st === 400 && code === 'no_room') {
         void alertDialog('Вы не в комнате')
      } else {
         void alertDialog('Не удалось взять фол')
      }
      return null
    }
    const ms = secondsToMs((resp as any).duration)
    return ms || null
  }

  async function finishSpeech(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_speech_finish', {})
    if (!resp?.ok) {
      const code = resp?.error
      const st = resp?.status
      if (st === 400 && code === 'bad_phase') {
         void alertDialog('Сейчас не фаза дня')
      } else if (st === 400 && code === 'no_speech') {
         void alertDialog('Сейчас никто не говорит')
      } else if (st === 403 && code === 'forbidden') {
         void alertDialog('Завершить речь может только ведущий или текущий игрок')
      } else if (st === 400 && code === 'not_alive') {
         void alertDialog('Игрок уже выбыл из игры')
      } else {
         void alertDialog('Не удалось завершить речь')
      }
    }
  }

  async function giveFoul(targetUserId: string, sendAck: SendAckFn): Promise<void> {
    const uidNum = Number(targetUserId)
    if (!uidNum) return
    const resp = await sendAck('game_foul_set', { user_id: uidNum })
    if (!resp?.ok) {
      const code = resp?.error
      const st = resp?.status
      if (st === 409 && code === 'need_confirm_kill') {
        const ok = await confirmDialog({
          title: 'Удаление игрока',
          text: 'Вы уверены что хотите удалить игрока?',
          confirmText: 'Удалить',
          cancelText: 'Отмена',
        })
        if (!ok) return
        const resp2 = await sendAck('game_foul_set', { user_id: uidNum, confirm_kill: true })
        if (!resp2?.ok) {
           void alertDialog('Не удалось выдать фол')
        }
      } else if (st === 403 && code === 'forbidden') {
         void alertDialog('Фол может выдать только ведущий')
      } else if (st === 404 && code === 'not_alive') {
         void alertDialog('Игрок уже выбыл из игры')
      } else {
         void alertDialog('Не удалось выдать фол')
      }
      return
    }
  }

  async function startLeaderSpeech(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_vote_speech_next', {})
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 400 && code === 'bad_phase') {
         void alertDialog('Сейчас не фаза голосования')
      } else if (st === 403 && code === 'forbidden') {
         void alertDialog('Только ведущий может передавать оправдательную/прощальную речь')
      } else if (st === 409 && code === 'vote_not_done') {
         void alertDialog('Сначала завершите голосование')
      } else if (st === 409 && code === 'speech_in_progress') {
         void alertDialog('Сейчас уже идёт речь игрока')
      } else if (st === 409 && code === 'no_leaders') {
         void alertDialog('Нет лидеров голосования')
      } else if (st === 409 && code === 'no_more_leaders') {
         void alertDialog('Все лидеры уже выступили — можно начинать новое голосование')
        voteLeaderSpeechesDone.value = true
      } else {
         void alertDialog('Не удалось передать речь лидеру')
      }
      return
    }
    voteLeaderSpeechesDone.value = false
  }

  async function restartVoteForLeaders(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_vote_restart', {})
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 400 && code === 'bad_phase') {
         void alertDialog('Сейчас не фаза голосования')
      } else if (st === 403 && code === 'forbidden') {
         void alertDialog('Только ведущий может начинать голосование')
      } else if (st === 409 && code === 'vote_not_done') {
         void alertDialog('Сначала завершите голосование')
      } else if (st === 409 && code === 'speeches_not_done') {
         void alertDialog('Сначала проведите оправдательные речи всех лидеров')
      } else if (st === 409 && code === 'no_nominees') {
         void alertDialog('Нет кандидатов для повторного голосования')
      } else {
         void alertDialog('Не удалось начать повторное голосование')
      }
    } else {
      voteLeaderSpeechesDone.value = false
      voteLeaderKilled.value = false
      voteResultShown.value = false
      replaceIds(voteResultLeaders, undefined)
      voteLiftState.value = 'none'
    }
  }

  async function goToNight(sendAck: SendAckFn): Promise<boolean> {
    if (!isHead.value) return false
    const from = gamePhase.value
    if (from !== 'day' && from !== 'vote') return false
    const resp = await sendAck('game_phase_next', { from, to: 'night' })
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 400 && code === 'bad_phase')  void alertDialog('Сейчас нельзя перейти в ночь')
      else if (st === 403 && code === 'forbidden')  void alertDialog('Только ведущий может начать ночь')
      else if (st === 409 && code === 'speeches_not_done')  void alertDialog('Сначала нужно закончить речи')
      else if (st === 409 && code === 'vote_not_done')  void alertDialog('Сначала завершите голосование')
      else  void alertDialog('Не удалось перейти в ночь')
      return false
    }
    return true
  }

  async function startDayFromNight(sendAck: SendAckFn): Promise<boolean> {
    if (gamePhase.value !== 'night') return false
    const resp = await sendAck('game_phase_next', { from: 'night', to: 'day' })
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 409 && code === 'best_move_required') {
        void alertDialog('Сначала запустите лучший ход')
      } else {
        void alertDialog('Не удалось начать день')
      }
      return false
    }
    return true
  }

  async function headVoteControl(sendAck: SendAckFn): Promise<void> {
    if (voteLiftState.value !== 'none') return
    if (gamePhase.value !== 'vote' || !isHead.value || vote.done) return
    if (!vote.currentId) {
      await startCurrentCandidateVote(sendAck)
      return
    }
    if (!voteStartedForCurrent.value) {
      await startCurrentCandidateVote(sendAck)
      return
    }
    if (vote.remainingMs <= 0) {
      await goToNextCandidate(sendAck)
    }
  }

  return {
    GAME_COLUMN_INDEX,
    GAME_ROW_INDEX,
    ROLE_IMAGES,
    ROLE_CARD_IMAGES,

    gamePhase,
    minReadyToStart,
    seatsByUser,
    headUserId,
    offlineInGame,
    rolesVisibleForHead,
    knownRolesVisible,
    canToggleKnownRoles,
    rolePick,
    roleOverlayMode,
    roleOverlayCard,
    startingGame,
    endingGame,
    mafiaTalk,
    mafiaTalkRemainingMs,
    daySpeech,
    foulActive,
    myGameRole,
    isHead,
    myGameRoleKind,
    amIAlive,
    takenCardSet,
    roleCardsToRender,
    gameFoulsByUser,
    daySpeechesDone,
    nomineeSeatNumbers,
    vote,
    votedUsers,
    votedThisRound,
    currentNomineeSeat,
    voteStartedForCurrent,
    voteResultLeaders,
    voteResultShown,
    gameAlive,
    voteAborted,
    voteLeaderSpeechesDone,
    voteLeaderKilled,
    voteBlocked,
    dayNumber,
    night,
    headNightPicks,
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
    canStartDayFromNight,
    bestMoveSeat,
    canStartLeaderSpeech,
    canRestartVoteForLeaders,
    canShowNight,
    nightKnownByMe,

    farewellSummaryForUser,
    canMakeFarewellChoice,
    canMakeBestMoveChoice,
    isBestMoveMarked,
    effectiveRoleIconForTile,
    canShootTarget,
    canCheckTarget,
    shootTarget,
    checkTarget,
    startNightShoot,
    startNightChecks,
    startBestMove,
    handleGameNightState,
    handleGameNightHeadPicks,
    handleGameNightReveal,
    handleGameVoteResult,
    handleGameVoteAborted,
    canPressVoteButton,
    startVotePhase,
    voteForCurrent,
    finishVote,
    maybeAskRevoteOnDisconnect,
    prepareVoteLift,
    startVoteLift,
    handleGameVoteState,
    handleGameVoted,
    handleGameBestMoveUpdate,
    isGameHead,
    isDead,
    deathReason,
    seatIndex,
    seatIconForUser,
    canClickCard,
    applyFromJoinAck,
    handleGameStarted,
    handleGameFinished,
    handleGameEnded,
    handleGamePlayerLeft,
    handleGameRolesTurn,
    handleGameRolesPicked,
    handleGameRoleAssigned,
    handleGameRolesReveal,
    handleGameDaySpeech,
    handleGameFoul,
    handleGamePhaseChange,
    shouldHighlightMafiaTile,
    goToMafiaTalk,
    finishMafiaTalk,
    startDay,
    leaveGame,
    startGame,
    endGame,
    pickRoleCard,
    passSpeech,
    takeFoul,
    finishSpeech,
    giveFoul,
    handleGameFouls,
    handleGameFarewellUpdate,
    handleGameNomineeAdded,
    canNominateTarget,
    nominateTarget,
    markFarewellChoice,
    markBestMoveChoice,
    toggleKnownRolesVisibility,
    restartVoteForLeaders,
    startLeaderSpeech,
    goToNight,
    startDayFromNight,
    headVoteControl,
  }
}
