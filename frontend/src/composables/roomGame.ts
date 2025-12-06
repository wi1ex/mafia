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
  const canToggleKnownRoles = computed(() => {
    return gamePhase.value !== 'idle' && myGameRole.value !== 'none'
  })
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
  const daySpeechTimerId = ref<number | null>(null)
  const daySpeechesDone = ref(false)
  const foulActive = reactive(new Set<string>())

  const dayNominees = reactive<string[]>([])
  const nominatedThisSpeechByMe = ref(false)

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
    const isHead = myGameRole.value === 'head'
    if (isSelf) return true
    if (isHead && rolesVisibleForHead.value) return true
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

    daySpeech.openingId = ''
    daySpeech.closingId = ''
    daySpeech.currentId = ''
    daySpeech.remainingMs = 0
    if (daySpeechTimerId.value != null) {
      clearTimeout(daySpeechTimerId.value)
      daySpeechTimerId.value = null
    }
    daySpeechesDone.value = false

    dayNominees.splice(0, dayNominees.length)
    nominatedThisSpeechByMe.value = false
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

    gameFoulsByUser.clear()
    const gf = (join?.game_fouls || {}) as Record<string, any>
    for (const [uid, cnt] of Object.entries(gf)) {
      const n = Number(cnt)
      if (Number.isFinite(n) && n > 0) gameFoulsByUser.set(String(uid), n)
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
    if (phase === 'day' && dy && typeof dy === 'object') {
      daySpeech.openingId = String(dy.opening_uid || '')
      daySpeech.closingId = String(dy.closing_uid || '')
      const rawMs = secondsToMs(dy.deadline)
      daySpeech.currentId = rawMs > 0 ? String(dy.current_uid || '') : ''
      setDaySpeechRemainingMs(rawMs, false)
      daySpeechesDone.value = isTrueLike((dy as any).speeches_done)

      const rawNominees = (dy as any).nominees
      dayNominees.splice(0, dayNominees.length)
      if (Array.isArray(rawNominees)) {
        for (const uid of rawNominees) {
          const s = String(uid)
          if (s) dayNominees.push(s)
        }
      }
      nominatedThisSpeechByMe.value = false
    } else {
      daySpeech.openingId = ''
      daySpeech.closingId = ''
      daySpeech.currentId = ''
      setDaySpeechRemainingMs(0, false)
      daySpeechesDone.value = false

      dayNominees.splice(0, dayNominees.length)
      nominatedThisSpeechByMe.value = false
    }

    const playersCount = gamePlayers.size
    const rolesCount = gameRolesByUser.size
    rolesVisibleForHead.value = playersCount > 0 && rolesCount >= playersCount
    if (phase !== 'idle' && gamePlayers.size === 0) {
      for (const [uid, seat] of Object.entries(seatsByUser)) {
        if (seat && seat !== 11) {
          gamePlayers.add(uid)
          gameAlive.add(uid)
        }
      }
    }

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
    gamePlayers.clear()
    gameAlive.clear()
    for (const [uid, seat] of Object.entries(seatsByUser)) {
      if (seat && seat !== 11) {
        gamePlayers.add(uid)
        gameAlive.add(uid)
      }
    }
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
    const isActiveSpeech = ms > 0 && !!speakerId
    if (isActiveSpeech) {
      daySpeechesDone.value = false
      if (speakerId !== localId.value) nominatedThisSpeechByMe.value = false
    } else if (done || (speakerId && closingId && speakerId === closingId)) {
      daySpeechesDone.value = true
      nominatedThisSpeechByMe.value = false
    }
  }

  function handleGameNomineeAdded(p: any) {
    const orderRaw = p?.order
    dayNominees.splice(0, dayNominees.length)
    if (Array.isArray(orderRaw)) {
      for (const uid of orderRaw) {
        const s = String(uid)
        if (s) dayNominees.push(s)
      }
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
    const fouls = (p?.fouls || {}) as Record<string, any>
    gameFoulsByUser.clear()
    for (const [uid, cnt] of Object.entries(fouls)) {
      const n = Number(cnt)
      if (Number.isFinite(n) && n > 0) gameFoulsByUser.set(String(uid), n)
    }
  }

  watch(() => [rolePick.activeUserId, localId.value, myGameRoleKind.value, gamePhase.value], () => { syncRoleOverlayWithTurn() })

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
    if (to === 'mafia_talk_start') {
      const mt = p?.mafia_talk_start
      const ms = secondsToMs(mt?.deadline)
      setMafiaTalkRemainingMs(ms, true)
    } else {
      setMafiaTalkRemainingMs(0, true)
    }

    if (to === 'day') {
      const dy = p?.day
      daySpeech.openingId = String(dy?.opening_uid || '')
      daySpeech.closingId = String(dy?.closing_uid || '')
      daySpeech.currentId = ''
      setDaySpeechRemainingMs(0, true)
      daySpeechesDone.value = false

      dayNominees.splice(0, dayNominees.length)
      nominatedThisSpeechByMe.value = false
    } else {
      daySpeech.openingId = ''
      daySpeech.closingId = ''
      daySpeech.currentId = ''
      setDaySpeechRemainingMs(0, true)
      daySpeechesDone.value = false

      dayNominees.splice(0, dayNominees.length)
      nominatedThisSpeechByMe.value = false
    }
  }

  function canNominateTarget(id: string): boolean {
    const me = localId.value
    if (!me) return false
    if (gamePhase.value !== 'day') return false
    if (daySpeech.currentId !== me) return false
    if (daySpeech.remainingMs <= 0) return false
    if (!amIAlive.value) return false
    if (!gamePlayers.has(id)) return false
    if (!gameAlive.has(id)) return false
    if (dayNominees.includes(id)) return false
    return !nominatedThisSpeechByMe.value
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
    dayNominees.splice(0, dayNominees.length)
    if (Array.isArray(orderRaw)) {
      for (const uid of orderRaw) {
        const s = String(uid)
        if (s) dayNominees.push(s)
      }
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
    const mySeat = seatsByUser[me]
    const isHead = mySeat === 11
    const myRoleKind = gameRolesByUser.get(me) as GameRoleKind | undefined
    if (isHead) return true
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
    myGameRoleKind,
    amIAlive,
    takenCardSet,
    roleCardsToRender,
    gameFoulsByUser,
    daySpeechesDone,
    nomineeSeatNumbers,

    isGameHead,
    isDead,
    seatIndex,
    seatIconForUser,
    canClickCard,
    roleIconForTile,
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
  }
}
