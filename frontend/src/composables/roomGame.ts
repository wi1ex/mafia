import { computed, reactive, ref, watch, type Ref } from 'vue'

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

export type GamePhase = 'idle' | 'roles_pick' | 'mafia_talk_start' | 'mafia_talk_end' | 'day' | 'night'
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
const LATENCY_MS = 1500

export function useRoomGame(localId: Ref<string>) {
  const gamePhase = ref<GamePhase>('idle')
  const minReadyToStart = ref<number>(5)
  const seatsByUser = reactive<Record<string, number>>({})
  const gamePlayers = reactive(new Set<string>())
  const gameAlive = reactive(new Set<string>())
  const offlineInGame = reactive(new Set<string>())
  const gameRolesByUser = reactive(new Map<string, GameRoleKind>())
  const rolesVisibleForHead = ref(false)
  const rolePick = reactive({
    activeUserId: '',
    order: [] as string[],
    picked: new Set<string>(),
    takenCards: [] as number[],
    remainingMs: 0,
  })
  const roleOverlayMode = ref<'hidden' | 'pick' | 'reveal'>('hidden')
  const roleOverlayCard = ref<number | null>(null)
  const roleOverlayTimerId = ref<number | null>(null)
  const pickingRole = ref(false)
  const startingGame = ref(false)
  const endingGame = ref(false)
  const mafiaTalk = reactive({
    remainingMs: 0,
  })
  const mafiaTalkTimerId = ref<number | null>(null)

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
    const myRole = gameRolesByUser.get(me)
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

    mafiaTalk.remainingMs = 0
    if (mafiaTalkTimerId.value != null) {
      clearTimeout(mafiaTalkTimerId.value)
      mafiaTalkTimerId.value = null
    }
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

    const rp = (gr as any).roles_pick
    if (phase === 'roles_pick' && rp && typeof rp === 'object') {
      rolePick.activeUserId = String(rp.turn_uid || '')
      rolePick.order = Array.isArray(rp.order) ? rp.order.map((x: any) => String(x)) : []
      rolePick.picked = new Set((rp.picked || []).map((x: any) => String(x)))
      const remainingSec = Number(rp.deadline || 0)
      const rawMs = remainingSec > 0 ? remainingSec * 1000 : 0
      rolePick.remainingMs = Math.max(rawMs - LATENCY_MS, 0)
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
      const remainingSec = Number(mt.deadline || 0)
      const rawMs = remainingSec > 0 ? remainingSec * 1000 : 0
      setMafiaTalkRemainingMs(rawMs)
    } else {
      setMafiaTalkRemainingMs(0)
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
    return roleBeforeEnd
  }

  function handleGamePlayerLeft(p: any) {
    const uid = String(p?.user_id ?? '')
    if (!uid) return
    gameAlive.delete(uid)
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

  function handleGameRolesState(_p: any) {
    // Сейчас флаг p.done не используется.
  }

  watch(() => [rolePick.activeUserId, localId.value, myGameRoleKind.value, gamePhase.value], () => { syncRoleOverlayWithTurn() })

  async function goToMafiaTalk(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_phase_next', { from: 'roles_pick', to: 'mafia_talk_start' })
    if (!resp?.ok) {
      alert('Не удалось перейти к договорке')
      return
    }
  }

  function setMafiaTalkRemainingMs(ms: number) {
    const safe = Math.max(ms - LATENCY_MS, 0)
    mafiaTalk.remainingMs = safe
    if (mafiaTalkTimerId.value != null) {
      clearTimeout(mafiaTalkTimerId.value)
      mafiaTalkTimerId.value = null
    }
    if (safe > 0) {
      mafiaTalkTimerId.value = window.setTimeout(() => {
        mafiaTalk.remainingMs = 0
        mafiaTalkTimerId.value = null
      }, safe)
    }
  }

  function handleGamePhaseChange(p: any) {
    const to = String(p?.to || '') as GamePhase
    gamePhase.value = to
    if (to === 'mafia_talk_start') {
      const mt = p?.mafia_talk_start
      const remainingSec = Number(mt?.deadline || 0)
      const ms = remainingSec > 0 ? remainingSec * 1000 : 0
      setMafiaTalkRemainingMs(ms)
    } else {
      setMafiaTalkRemainingMs(0)
    }
  }

  async function finishMafiaTalk(sendAck: SendAckFn): Promise<void> {
    const resp = await sendAck('game_phase_next', { from: 'mafia_talk_start', to: 'mafia_talk_end' })
    if (!resp?.ok) {
      alert('Не удалось завершить договорку')
      return
    }
  }

  async function leaveGame(sendAck: SendAckFn): Promise<void> {
    if (!confirm('Вы хотите покинуть игровой стол?')) return
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
      alert('Некоторые участники уже играют в другой комнате')
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
    if (!confirm('Завершить текущую игру?')) return
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
          alert('Эта карточка уже занята, обновите окно')
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

  return {
    GAME_COLUMN_INDEX,
    GAME_ROW_INDEX,
    ROLE_IMAGES,
    ROLE_CARD_IMAGES,

    gamePhase,
    minReadyToStart,
    seatsByUser,
    gamePlayers,
    gameAlive,
    offlineInGame,
    gameRolesByUser,
    rolesVisibleForHead,
    rolePick,
    roleOverlayMode,
    roleOverlayCard,
    startingGame,
    endingGame,
    mafiaTalk,
    myGameRole,
    myGameRoleKind,
    amIAlive,
    takenCardSet,
    roleCardsToRender,

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
    handleGameRolesState,
    handleGamePhaseChange,
    shouldHighlightMafiaTile,
    goToMafiaTalk,
    finishMafiaTalk,
    leaveGame,
    startGame,
    endGame,
    pickRoleCard,
  }
}
