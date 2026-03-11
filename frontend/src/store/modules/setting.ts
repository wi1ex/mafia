import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/services/axios'

export interface PublicSettings {
  registration_enabled: boolean
  rooms_can_create: boolean
  rooms_can_enter: boolean
  games_can_start: boolean
  streams_can_start: boolean
  verification_restrictions: boolean
  admin_banner_text: string
  admin_banner_link: string
  game_min_ready_players: number
  winks_limit: number
  knocks_limit: number
  wink_spot_chance_percent: number
  season_start_game_number: string
}

export const useSettingsStore = defineStore('settings', () => {
  const registrationEnabled = ref(true)
  const roomsCanCreate = ref(true)
  const roomsCanEnter = ref(true)
  const gamesCanStart = ref(true)
  const streamsCanStart = ref(true)
  const verificationRestrictions = ref(true)
  const adminBannerText = ref('0')
  const adminBannerLink = ref('0')
  const gameMinReadyPlayers = ref(4)
  const winksLimit = ref(0)
  const knocksLimit = ref(0)
  const winkSpotChancePercent = ref(25)
  const seasonStartGameNumber = ref('1')
  const seasonStartGameNumbers = computed<number[]>(() => parseSeasonStartNumbers(seasonStartGameNumber.value))
  const ready = ref(false)
  let inited = false
  let onSettingsEv: ((e: any) => void) | null = null

  function parseSeasonStartNumbers(raw: unknown): number[] {
    const source = String(raw ?? '').trim()
    if (!source) return [1]

    const values: number[] = []
    for (const part of source.split(',')) {
      const token = part.trim()
      if (!token) return [1]
      const value = Number(token)
      if (!Number.isFinite(value)) return [1]
      const normalized = Math.trunc(value)
      if (normalized < 1) return [1]
      values.push(normalized)
    }
    if (values.length === 0) return [1]
    return Array.from(new Set(values)).sort((a, b) => a - b)
  }

  function normalizeSeasonStart(raw: unknown): string {
    return parseSeasonStartNumbers(raw).join(',')
  }

  function applyPublic(data: PublicSettings) {
    registrationEnabled.value = Boolean(data.registration_enabled)
    roomsCanCreate.value = Boolean(data.rooms_can_create)
    roomsCanEnter.value = Boolean(data.rooms_can_enter)
    gamesCanStart.value = Boolean(data.games_can_start)
    streamsCanStart.value = Boolean(data.streams_can_start)
    verificationRestrictions.value = Boolean(data.verification_restrictions)
    adminBannerText.value = String(data.admin_banner_text || '').trim() || '0'
    adminBannerLink.value = String(data.admin_banner_link || '').trim() || '0'
    const minReady = Number(data.game_min_ready_players)
    if (Number.isFinite(minReady) && minReady > 0) gameMinReadyPlayers.value = minReady
    const winks = Number(data.winks_limit)
    if (Number.isFinite(winks) && winks >= 0) winksLimit.value = winks
    const knocks = Number(data.knocks_limit)
    if (Number.isFinite(knocks) && knocks >= 0) knocksLimit.value = knocks
    const winkSpotChance = Number(data.wink_spot_chance_percent)
    if (Number.isFinite(winkSpotChance)) winkSpotChancePercent.value = Math.max(0, Math.min(100, Math.round(winkSpotChance)))
    seasonStartGameNumber.value = normalizeSeasonStart(data.season_start_game_number)
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
    verificationRestrictions,
    adminBannerText,
    adminBannerLink,
    gameMinReadyPlayers,
    winksLimit,
    knocksLimit,
    winkSpotChancePercent,
    seasonStartGameNumber,
    seasonStartGameNumbers,
    ready,

    fetchPublic,
    applyPublic,
    ensureWS,
  }
})
