import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/services/axios'

export interface PublicSettings {
  registration_enabled: boolean
  rooms_can_create: boolean
  rooms_can_enter: boolean
  games_can_start: boolean
  streams_can_start: boolean
  chat_open_enabled: boolean
  chat_messages_enabled: boolean
  verification_restrictions: boolean
  admin_banner_text: string
  admin_banner_link: string
  donation_url: string
  game_min_ready_players: number
  winks_limit: number
  knocks_limit: number
  wink_spot_chance_percent: number
  season_start_game_number: string
  self_speech_finish_enabled: boolean
}

const PUBLIC_SETTINGS_KEYS: readonly (keyof PublicSettings)[] = [
  'registration_enabled',
  'rooms_can_create',
  'rooms_can_enter',
  'games_can_start',
  'streams_can_start',
  'chat_open_enabled',
  'chat_messages_enabled',
  'verification_restrictions',
  'admin_banner_text',
  'admin_banner_link',
  'donation_url',
  'game_min_ready_players',
  'winks_limit',
  'knocks_limit',
  'wink_spot_chance_percent',
  'season_start_game_number',
  'self_speech_finish_enabled',
]

export const useSettingsStore = defineStore('settings', () => {
  const registrationEnabled = ref(true)
  const roomsCanCreate = ref(true)
  const roomsCanEnter = ref(true)
  const gamesCanStart = ref(true)
  const streamsCanStart = ref(true)
  const chatOpenEnabled = ref(true)
  const chatMessagesEnabled = ref(true)
  const verificationRestrictions = ref(true)
  const adminBannerText = ref('0')
  const adminBannerLink = ref('0')
  const donationUrl = ref('')
  const gameMinReadyPlayers = ref(4)
  const winksLimit = ref(0)
  const knocksLimit = ref(0)
  const winkSpotChancePercent = ref(25)
  const seasonStartGameNumber = ref('1')
  const selfSpeechFinishEnabled = ref(true)
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
    chatOpenEnabled.value = Boolean(data.chat_open_enabled)
    chatMessagesEnabled.value = Boolean(data.chat_messages_enabled)
    verificationRestrictions.value = Boolean(data.verification_restrictions)
    adminBannerText.value = String(data.admin_banner_text || '').trim() || '0'
    adminBannerLink.value = String(data.admin_banner_link || '').trim() || '0'
    donationUrl.value = String(data.donation_url || '').trim()
    const minReady = Number(data.game_min_ready_players)
    if (Number.isFinite(minReady) && minReady > 0) gameMinReadyPlayers.value = minReady
    const winks = Number(data.winks_limit)
    if (Number.isFinite(winks) && winks >= 0) winksLimit.value = winks
    const knocks = Number(data.knocks_limit)
    if (Number.isFinite(knocks) && knocks >= 0) knocksLimit.value = knocks
    const winkSpotChance = Number(data.wink_spot_chance_percent)
    if (Number.isFinite(winkSpotChance)) winkSpotChancePercent.value = Math.max(0, Math.min(100, Math.round(winkSpotChance)))
    seasonStartGameNumber.value = normalizeSeasonStart(data.season_start_game_number)
    selfSpeechFinishEnabled.value = Boolean(data.self_speech_finish_enabled)
    ready.value = true
  }

  function isPublicSettingsPayload(payload: unknown): payload is PublicSettings {
    return Boolean(
      payload
      && typeof payload === 'object'
      && PUBLIC_SETTINGS_KEYS.every((key) => key in payload)
    )
  }

  function applyPublicPayload(payload: unknown): boolean {
    if (!isPublicSettingsPayload(payload)) return false
    applyPublic(payload)
    return true
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
    onSettingsEv = (event: CustomEvent<unknown>) => {
      if (applyPublicPayload(event?.detail)) return
      void fetchPublic()
    }
    window.addEventListener('auth-settings_update', onSettingsEv)
    inited = true
  }

  return {
    registrationEnabled,
    roomsCanCreate,
    roomsCanEnter,
    gamesCanStart,
    streamsCanStart,
    chatOpenEnabled,
    chatMessagesEnabled,
    verificationRestrictions,
    adminBannerText,
    adminBannerLink,
    donationUrl,
    gameMinReadyPlayers,
    winksLimit,
    knocksLimit,
    winkSpotChancePercent,
    seasonStartGameNumber,
    selfSpeechFinishEnabled,
    seasonStartGameNumbers,
    ready,

    fetchPublic,
    applyPublic,
    applyPublicPayload,
    ensureWS,
  }
})
