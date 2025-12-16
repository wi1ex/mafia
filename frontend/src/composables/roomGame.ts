import { computed, reactive, ref, type Ref, watch } from 'vue'

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

export type Ack = {
  ok: boolean
  status?: number
  error?: string
  [k: string]: any
} | null

export type SendAckFn = (event: string, payload: any, timeoutMs?: number) => Promise<Ack>

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

export function useRoomGame(localId: Ref<string>) {
  const gamePhase = ref<GamePhase>('idle')
  const minReadyToStart = ref<number>(5)
  const seatsByUser = reactive<Record<string, number>>({})
  const gamePlayers = reactive(new Set<string>())
  const gameAlive = reactive(new Set<string>())
  const offlineInGame = reactive(new Set<string>())
  const gameRolesByUser = reactive(new Map<string, GameRoleKind>())
  const gameFoulsByUser = reactive(new Map<string, number>())
  const rolesVisibleForHead = ref(false)
  const knownRolesVisible = ref(true)
  const dayNumber = ref(0)
  const canToggleKnownRoles = computed(() => {
    return gamePhase.value !== 'idle' && myGameRole.value !== 'none'
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
  const vote = reactive({
    currentId: '',
    remainingMs: 0,
    done: false,
  })
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

  const night = reactive({
    stage: 'sleep' as 'sleep' | 'shoot' | 'shoot_done' | 'checks' | 'checks_done',
    remainingMs: 0,
    killOk: false,
    killUid: '',
    hasResult: false,
  })
  const nightTimerId = ref<number | null>(null)
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

  function setNightRemainingMs(ms: number, changed: boolean) {
    setTimerWithLatency(night, ms, nightTimerId, changed)
  }

  function canPressVoteButton(): boolean {
    const me = localId.value
    if (!me) return false
    if (gamePhase.value !== 'vote') return false
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
  }

  function resetVoteState(changed: boolean) {
    vote.currentId = ''
    setVoteRemainingMs(0, changed)
    vote.done = false
    voteAborted.value = false
    votedUsers.clear()
    votedThisRound.clear()
    voteStartedForCurrent.value = false
    voteResultShown.value = false
    voteLeaderSpeechesDone.value = false
    voteLeaderKilled.value = false
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

  function isGameHead(id: string): boolean {
    return seatsByUser[id] === 11
  }

  function isDead(id: string): boolean {
    if (gamePhase.value === 'idle') return false
    const seat = seatsByUser[id]
    if (!seat || seat === 11) return false
    return !gameAlive.has(id)
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
    if (roleOverlayTimerId.value != null) {
      clearTimeout(roleOverlayTimerId.value)
      roleOverlayTimerId.value = null
    }
    gameRolesByUser.clear()
    rolesVisibleForHead.value = false
    gameFoulsByUser.clear()
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
    return nightKnownRoleIconForTile(id) || roleIconForTile(id)
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
    if (Number.isFinite(mr) && mr > 0) {
      minReadyToStart.value = mr
    }
    const phase = (gr.phase as GamePhase) || 'idle'
    gamePhase.value = phase
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
      daySpeech.openingId = String(dy.opening_uid || '')
      daySpeech.closingId = String(dy.closing_uid || '')
      const rawMs = secondsToMs(dy.deadline)
      daySpeech.currentId = rawMs > 0 ? String(dy.current_uid || '') : ''
      setDaySpeechRemainingMs(rawMs, false)
      daySpeechesDone.value = isTrueLike((dy as any).speeches_done)
      const preludeSection = (dy as any).prelude
      const preludeActive = !!(preludeSection && typeof preludeSection === 'object' && isTrueLike((preludeSection as any).active))
      currentFarewellSpeech.value = preludeActive || false
      replaceIds(dayNominees, (dy as any).nominees)
      nominatedThisSpeechByMe.value = isTrueLike((dy as any).nominated_this_speech)

      const lastNight = (dy as any).night ?? nt
      const hasNightPayload = !!lastNight && typeof lastNight === 'object' && ('kill_ok' in lastNight || 'kill_uid' in lastNight)
      if (hasNightPayload) {
        night.killOk = isTrueLike((lastNight as any).kill_ok)
        night.killUid = String((lastNight as any).kill_uid || '')
        night.hasResult = true
      } else {
        night.killOk = false
        night.killUid = ''
        night.hasResult = false
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
      vote.done = done
      voteAborted.value = aborted
      voteResultShown.value = resultsReady
      voteStartedForCurrent.value = isTrueLike((vt as any).started)

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
      } else {
        setDaySpeechRemainingMs(0, false)
        daySpeech.currentId = ''
        const done = isTrueLike((vt as any).speeches_done)
        daySpeechesDone.value = done
        voteLeaderSpeechesDone.value = done
        voteLeaderKilled.value = false
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
    offlineInGame.clear()
    gamePhase.value = (payload?.phase as GamePhase) || 'roles_pick'
    if (payload?.min_ready != null) {
      const v = Number(payload.min_ready)
      if (Number.isFinite(v) && v > 0) minReadyToStart.value = v
    }
    fillSeats((payload?.seats || {}) as Record<string, any>)
    fillPlayersFromSeats()
  }

  function handleGameEnded(_payload: any): 'head' | 'player' | 'none' {
    const roleBeforeEnd = myGameRole.value
    resetRolesUiState()
    gamePhase.value = 'idle'
    Object.keys(seatsByUser).forEach((k) => { delete seatsByUser[k] })
    gamePlayers.clear()
    gameAlive.clear()
    offlineInGame.clear()
    gameFoulsByUser.clear()
    return roleBeforeEnd
  }

  function handleGamePlayerLeft(p: any) {
    const uid = String(p?.user_id ?? '')
    if (!uid) return
    gameAlive.delete(uid)
    gameFoulsByUser.delete(uid)
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
      }, 5000)
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

    daySpeech.openingId = openingId
    daySpeech.closingId = closingId
    daySpeech.currentId = ms > 0 ? speakerId : ''
    setDaySpeechRemainingMs(ms, true)

    const done = isTrueLike((p as any)?.speeches_done)
    const killed = isTrueLike((p as any)?.killed)
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

    currentFarewellSpeech.value = isActiveSpeech && (isTrueLike((p as any)?.prelude) || killed)
    if (isActiveSpeech && night.hasResult) {
      night.hasResult = false
      night.killOk = false
      night.killUid = ''
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
      } else if (done || killed || (speakerId && closingId && speakerId === closingId)) {
        voteLeaderSpeechesDone.value = true
        if (killed) voteLeaderKilled.value = true
      }
    }
  }

  function handleGameNomineeAdded(p: any) {
    const orderRaw = p?.order
    replaceIds(dayNominees, orderRaw)
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
    vote.currentId = newId
    setVoteRemainingMs(ms, true)
    vote.done = isTrueLike(vt.done)
    voteAborted.value = isTrueLike((vt as any).aborted)
    if (!newId) {
      voteStartedForCurrent.value = false
    } else if (newId !== prevId) {
      voteStartedForCurrent.value = ms > 0
      votedThisRound.clear()
    } else if (ms > 0) {
      voteStartedForCurrent.value = true
    }
    replaceIds(dayNominees, vt.nominees)
  }

  function handleGameVoteAborted(_p: any) {
    voteAborted.value = true
    vote.done = true
    setVoteRemainingMs(0, true)
    votedUsers.clear()
    votedThisRound.clear()

    vote.currentId = ''
    voteStartedForCurrent.value = false
  }

  function handleGameVoted(p: any) {
    const uid = String(p?.user_id || '')
    const target = String(p?.target_id || '')
    if (!uid || !target) return
    votedUsers.add(uid)
    if (target === vote.currentId) {
      votedThisRound.add(uid)
    }
  }

  function handleGameVoteResult(p: any) {
    voteAborted.value = false
    voteResultShown.value = true
    voteLeaderSpeechesDone.value = false
    voteLeaderKilled.value = false
    votedUsers.clear()
    votedThisRound.clear()

    vote.currentId = ''
    voteStartedForCurrent.value = false
    setVoteRemainingMs(0, true)

    const leadersRaw = p?.leaders
    replaceIds(voteResultLeaders, leadersRaw)

    const nomineesRaw = p?.nominees
    replaceIds(dayNominees, nomineesRaw, s => voteResultLeaders.includes(s))
  }

  async function finishVote(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_vote_finish', {})
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 400 && code === 'bad_phase') {
        alert('Сейчас не фаза голосования')
      } else if (st === 403 && code === 'forbidden') {
        alert('Только ведущий может завершать голосование')
      } else if (st === 409 && code === 'vote_not_done') {
        alert('Голосование еще не завершено')
      } else if (st === 409 && code === 'no_nominees') {
        alert('Никто не выставлен')
      } else if (st === 409 && code === 'no_leaders') {
        alert('Нет лидеров голосования')
      } else {
        alert('Не удалось завершить голосование')
      }
      return
    }
    voteResultShown.value = true
    votedUsers.clear()
    votedThisRound.clear()
  }

  watch(() => [rolePick.activeUserId, localId.value, myGameRoleKind.value, gamePhase.value], () => { syncRoleOverlayWithTurn() })

  watch(knownRolesVisible, (val) => {
    if (typeof window === 'undefined') return
    try { window.localStorage.setItem('roomRolesVisible', val ? '1' : '0') } catch {}
  })

  async function goToMafiaTalk(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_phase_next', { from: 'roles_pick', to: 'mafia_talk_start' })
    if (!resp?.ok) {
      alert('Не удалось перейти к договорке')
      return
    }
  }

  function setMafiaTalkRemainingMs(ms: number, changed: boolean) {
    setTimerWithLatency(mafiaTalk, ms, mafiaTalkTimerId, changed)
  }

  function setDaySpeechRemainingMs(ms: number, changed: boolean) {
    setTimerWithLatency(daySpeech, ms, daySpeechTimerId, changed, () => { daySpeech.currentId = '' })
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
    const me = localId.value
    if (!me) return false
    if (currentFarewellSpeech.value) return false
    if (isNightVictimFarewellSpeech(me)) return false
    if (gamePhase.value !== 'day') return false
    if (daySpeech.currentId !== me) return false
    if (daySpeech.remainingMs <= 0) return false
    if (!amIAlive.value) return false
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
    if (resp?.ok) myNightCheckTarget.value = targetUserId
  }

  async function startNightShoot(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_night_shoot_start', {})
    if (!resp?.ok) alert('Не удалось начать отстрел мафии')
  }

  async function startNightChecks(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_night_checks_start', {})
    if (!resp?.ok) alert('Не удалось начать проверки')
  }

  async function nominateTarget(targetUserId: string, sendAck: SendAckFn): Promise<void> {
    const uidNum = Number(targetUserId)
    if (!uidNum) return
    const resp = await sendAck('game_nominate', { user_id: uidNum })
    if (!resp?.ok) {
      const code = resp?.error
      const st = resp?.status
      if (st === 400 && code === 'bad_phase') {
        alert('Сейчас не фаза дня')
      } else if (st === 403 && code === 'not_your_speech') {
        alert('Вы можете выставлять только во время своей речи')
      } else if (st === 403 && code === 'not_alive') {
        alert('Вы не являетесь живым игроком')
      } else if (st === 400 && code === 'target_not_alive') {
        alert('Игрок уже выбыл из игры')
      } else if (st === 409 && code === 'already_nominated') {
        alert('Вы уже выставили игрока в этой речи')
      } else if (st === 409 && code === 'target_already_on_ballot') {
        alert('Этот игрок уже выставлен')
      } else {
        alert('Не удалось выставить игрока на голосование')
      }
      return
    }
    nominatedThisSpeechByMe.value = true
    const orderRaw = (resp as any).order
    replaceIds(dayNominees, orderRaw)
  }

  async function startVotePhase(sendAck: SendAckFn): Promise<void> {
    if (gamePhase.value === 'day') {
      const resp = await sendAck('game_phase_next', { from: 'day', to: 'vote' })
      if (!resp?.ok) {
        const st = resp?.status
        const code = resp?.error
        if (st === 400 && code === 'speeches_not_done') {
          alert('Сначала нужно закончить речи')
        } else if (st === 409 && code === 'no_nominees') {
          alert('Никто не выставлен – можно переходить к ночи')
        } else {
          alert('Не удалось начать голосование')
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
        alert('Сейчас не фаза голосования')
      } else if (st === 403 && code === 'forbidden') {
        alert('Только ведущий может управлять голосованием')
      } else if (st === 409 && code === 'vote_already_ended') {
        alert('Голосование за этого кандидата уже завершено')
      } else if (st === 409 && code === 'vote_done') {
        alert('Голосование уже завершено')
      } else {
        alert('Не удалось запустить голосование за кандидата')
      }
    }
  }

  async function goToNextCandidate(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_vote_control', { action: 'next' })
    if (!resp?.ok) {
      const st = resp?.status
      const code = resp?.error
      if (st === 409 && code === 'vote_in_progress') {
        alert('Сначала дождитесь окончания голосования за текущего кандидата')
      } else if (st === 403 && code === 'forbidden') {
        alert('Только ведущий может управлять голосованием')
      } else {
        alert('Не удалось перейти к следующему кандидату')
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
        alert('Сейчас не фаза голосования')
      } else if (st === 403 && code === 'not_alive') {
        alert('Только живые игроки могут голосовать')
      } else if (st === 409 && code === 'already_voted') {
        alert('Вы уже проголосовали')
      } else if (st === 409 && (code === 'no_active_vote' || code === 'vote_window_closed')) {
        alert('Время голосования за этого кандидата вышло')
      } else if (st === 409 && code === 'vote_done') {
        alert('Голосование уже завершено')
      } else {
        alert('Не удалось проголосовать')
      }
      return
    }
  }

  async function finishMafiaTalk(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_phase_next', { from: 'mafia_talk_start', to: 'mafia_talk_end' })
    if (!resp?.ok) {
      alert('Не удалось завершить договорку')
      return
    }
  }

  async function startDay(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_phase_next', { from: 'mafia_talk_end', to: 'day' })
    if (!resp?.ok) {
      alert('Не удалось начать день')
      return
    }
  }

  async function leaveGame(sendAck: SendAckFn): Promise<void> {
    if (!confirm('Покинуть игру?')) return
    const resp = await sendAck('game_leave', {})
    if (!resp?.ok) {
      const code = resp?.error
      const st = resp?.status
      const id = localId.value
      if (st === 400 && code === 'no_game') {
        alert('Игра не запущена')
      } else if (st === 400 && code === 'not_player') {
        alert('Вы не участвуете в этой игре')
      } else if (st === 400 && code === 'already_dead') {
        if (id) gameAlive.delete(id)
        alert('Вы уже выбыли из игры')
      } else {
        alert('Не удалось выйти из игры')
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
      alert('Недостаточно готовых игроков для запуска игры')
    } else if (st === 403 && code === 'forbidden') {
      alert('Недостаточно прав для запуска игры')
    } else if (st === 409 && code === 'already_in_other_game') {
      alert('Некоторые пользователи являются живыми игроками в другой комнате')
    } else if (st === 403 && code === 'not_in_room') {
      alert('Вы не в комнате')
    } else if (st === 409 && code === 'streaming_present') {
      alert('Остановите трансляции перед запуском игры')
    } else if (st === 409 && code === 'blocked_params') {
      alert('Снимите блокировки перед запуском игры')
    } else if (st === 409 && code === 'already_started') {
      alert('Игра уже запущена')
    } else {
      alert('Не удалось запустить игру')
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
      if (!confirm('Начать игру?')) return
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
      alert('Игра не запущена')
    } else if (st === 403 && code === 'forbidden') {
      alert('Недостаточно прав для завершения игры')
    } else {
      alert('Не удалось завершить игру')
    }
  }

  async function endGame(sendAck: SendAckFn): Promise<void> {
    if (endingGame.value) return
    if (!confirm('Завершить игру?')) return
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
          alert('Сейчас ход другого игрока')
        } else if (st === 409 && code === 'card_taken') {
          alert('Эта карта уже занята')
        } else {
          alert('Не удалось выбрать роль')
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
        alert('Речи игроков завершены')
        daySpeechesDone.value = true
      } else if (st === 400 && code === 'bad_phase') {
        alert('Сейчас не фаза дня')
      } else if (st === 403 && code === 'forbidden') {
        alert('Только ведущий может передавать речь')
      } else {
        alert('Не удалось передать речь')
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
        alert('Сейчас не фаза дня')
      } else if (st === 403 && code === 'not_alive') {
        alert('Вы не являетесь игроком или уже выбыли')
      } else if (st === 400 && code === 'no_room') {
        alert('Вы не в комнате')
      } else {
        alert('Не удалось взять фол')
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
        alert('Сейчас не фаза дня')
      } else if (st === 400 && code === 'no_speech') {
        alert('Сейчас никто не говорит')
      } else if (st === 403 && code === 'forbidden') {
        alert('Завершить речь может только ведущий или текущий игрок')
      } else if (st === 400 && code === 'not_alive') {
        alert('Игрок уже выбыл из игры')
      } else {
        alert('Не удалось завершить речь')
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
        const ok = confirm('Удалить игрока?')
        if (!ok) return
        const resp2 = await sendAck('game_foul_set', { user_id: uidNum, confirm_kill: true })
        if (!resp2?.ok) {
          alert('Не удалось выдать фол')
        }
      } else if (st === 403 && code === 'forbidden') {
        alert('Фол может выдать только ведущий')
      } else if (st === 404 && code === 'not_alive') {
        alert('Игрок уже выбыл из игры')
      } else {
        alert('Не удалось выдать фол')
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
        alert('Сейчас не фаза голосования')
      } else if (st === 403 && code === 'forbidden') {
        alert('Только ведущий может передавать оправдательную/прощальную речь')
      } else if (st === 409 && code === 'vote_not_done') {
        alert('Сначала завершите голосование')
      } else if (st === 409 && code === 'speech_in_progress') {
        alert('Сейчас уже идёт речь игрока')
      } else if (st === 409 && code === 'no_leaders') {
        alert('Нет лидеров голосования')
      } else if (st === 409 && code === 'no_more_leaders') {
        alert('Все лидеры уже выступили — можно начинать новое голосование')
        voteLeaderSpeechesDone.value = true
      } else {
        alert('Не удалось передать речь лидеру')
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
        alert('Сейчас не фаза голосования')
      } else if (st === 403 && code === 'forbidden') {
        alert('Только ведущий может начинать голосование')
      } else if (st === 409 && code === 'vote_not_done') {
        alert('Сначала завершите голосование')
      } else if (st === 409 && code === 'speeches_not_done') {
        alert('Сначала проведите оправдательные речи всех лидеров')
      } else if (st === 409 && code === 'no_nominees') {
        alert('Нет кандидатов для повторного голосования')
      } else {
        alert('Не удалось начать повторное голосование')
      }
    } else {
      voteLeaderSpeechesDone.value = false
      voteLeaderKilled.value = false
      voteResultShown.value = false
      replaceIds(voteResultLeaders, undefined)
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
    dayNumber,
    night,
    headNightPicks,
    nightKnownByMe,

    effectiveRoleIconForTile,
    canShootTarget,
    canCheckTarget,
    shootTarget,
    checkTarget,
    startNightShoot,
    startNightChecks,
    handleGameNightState,
    handleGameNightHeadPicks,
    handleGameNightReveal,
    handleGameVoteResult,
    handleGameVoteAborted,
    canPressVoteButton,
    startVotePhase,
    startCurrentCandidateVote,
    goToNextCandidate,
    voteForCurrent,
    finishVote,
    handleGameVoteState,
    handleGameVoted,
    isGameHead,
    isDead,
    seatIndex,
    seatIconForUser,
    canClickCard,
    applyFromJoinAck,
    handleGameStarted,
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
    handleGameNomineeAdded,
    canNominateTarget,
    nominateTarget,
    toggleKnownRolesVisibility,
    restartVoteForLeaders,
    startLeaderSpeech,
  }
}
