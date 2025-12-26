import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

export interface PublicSettings {
  registration_enabled: boolean
  rooms_can_create: boolean
  games_can_start: boolean
  game_min_ready_players: number
}

export const useSettingsStore = defineStore('settings', () => {
  const registrationEnabled = ref(true)
  const roomsCanCreate = ref(true)
  const gamesCanStart = ref(true)
  const gameMinReadyPlayers = ref(4)
  const ready = ref(false)

  function applyPublic(data: PublicSettings) {
    registrationEnabled.value = Boolean(data.registration_enabled)
    roomsCanCreate.value = Boolean(data.rooms_can_create)
    gamesCanStart.value = Boolean(data.games_can_start)
    const minReady = Number(data.game_min_ready_players)
    if (Number.isFinite(minReady) && minReady > 0) gameMinReadyPlayers.value = minReady
  }

  async function fetchPublic(): Promise<void> {
    try {
      const { data } = await api.get<PublicSettings>('/admin/settings/public', { __skipAuth: true })
      applyPublic(data)
    } finally {
      ready.value = true
    }
  }

  return {
    registrationEnabled,
    roomsCanCreate,
    gamesCanStart,
    gameMinReadyPlayers,
    ready,

    fetchPublic,
    applyPublic,
  }
})
