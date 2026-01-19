import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

export interface PublicSettings {
  registration_enabled: boolean
  rooms_can_create: boolean
  rooms_can_enter: boolean
  games_can_start: boolean
  streams_can_start: boolean
  game_min_ready_players: number
  winks_limit: number
  knocks_limit: number
}

export const useSettingsStore = defineStore('settings', () => {
  const registrationEnabled = ref(true)
  const roomsCanCreate = ref(true)
  const roomsCanEnter = ref(true)
  const gamesCanStart = ref(true)
  const streamsCanStart = ref(true)
  const gameMinReadyPlayers = ref(4)
  const winksLimit = ref(0)
  const knocksLimit = ref(0)
  const ready = ref(false)
  let inited = false
  let onSettingsEv: ((e: any) => void) | null = null

  function applyPublic(data: PublicSettings) {
    registrationEnabled.value = Boolean(data.registration_enabled)
    roomsCanCreate.value = Boolean(data.rooms_can_create)
    roomsCanEnter.value = Boolean(data.rooms_can_enter)
    gamesCanStart.value = Boolean(data.games_can_start)
    streamsCanStart.value = Boolean(data.streams_can_start)
    const minReady = Number(data.game_min_ready_players)
    if (Number.isFinite(minReady) && minReady > 0) gameMinReadyPlayers.value = minReady
    const winks = Number(data.winks_limit)
    if (Number.isFinite(winks) && winks >= 0) winksLimit.value = winks
    const knocks = Number(data.knocks_limit)
    if (Number.isFinite(knocks) && knocks >= 0) knocksLimit.value = knocks
  }

  async function fetchPublic(): Promise<void> {
    try {
      const { data } = await api.get<PublicSettings>('/admin/settings/public', { __skipAuth: true })
      applyPublic(data)
    } finally {
      ready.value = true
    }
  }

  function ensureWS() {
    if (inited) return
    if (onSettingsEv) window.removeEventListener('auth-settings_update', onSettingsEv)
    onSettingsEv = () => { void fetchPublic() }
    window.addEventListener('auth-settings_update', onSettingsEv)
    inited = true
  }

  return {
    registrationEnabled,
    roomsCanCreate,
    roomsCanEnter,
    gamesCanStart,
    streamsCanStart,
    gameMinReadyPlayers,
    winksLimit,
    knocksLimit,
    ready,

    fetchPublic,
    applyPublic,
    ensureWS,
  }
})
