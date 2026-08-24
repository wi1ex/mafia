import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/services/axios'
import {
  SANCTION_BADGES,
  type RulesSection,
  type SanctionBadgeKey,
} from '@/constants/sanctionReasons'

export interface PublicSettings {
  registration_enabled: boolean
  rooms_can_create: boolean
  rooms_can_enter: boolean
  games_can_start: boolean
  rating_enabled: boolean
  streams_can_start: boolean
  chat_open_enabled: boolean
  chat_messages_enabled: boolean
  verification_restrictions: boolean
  admin_banner_text: string
  admin_banner_link: string
  home_carousel_banner_key: string | null
  donation_url: string
  rooms_limit_global: number
  spectators_limit: number
  game_min_ready_players: number
  winks_limit: number
  knocks_limit: number
  wink_spot_chance_percent: number
  season_start_game_number: string
  senior_moderator_user_id: number | null
}

export type SanctionReason = {
  value: string
  label: string
}

type SanctionRulesPayload = {
  sections: RulesSection[]
}

const PUBLIC_SETTINGS_KEYS: readonly (keyof PublicSettings)[] = [
  'registration_enabled',
  'rooms_can_create',
  'rooms_can_enter',
  'games_can_start',
  'rating_enabled',
  'streams_can_start',
  'chat_open_enabled',
  'chat_messages_enabled',
  'verification_restrictions',
  'admin_banner_text',
  'admin_banner_link',
  'home_carousel_banner_key',
  'donation_url',
  'rooms_limit_global',
  'spectators_limit',
  'game_min_ready_players',
  'winks_limit',
  'knocks_limit',
  'wink_spot_chance_percent',
  'season_start_game_number',
  'senior_moderator_user_id',
]

export const useSettingsStore = defineStore('settings', () => {
  const registrationEnabled = ref(true)
  const roomsCanCreate = ref(true)
  const roomsCanEnter = ref(true)
  const gamesCanStart = ref(true)
  const ratingEnabled = ref(true)
  const streamsCanStart = ref(true)
  const chatOpenEnabled = ref(true)
  const chatMessagesEnabled = ref(true)
  const verificationRestrictions = ref(true)
  const adminBannerText = ref('0')
  const adminBannerLink = ref('0')
  const homeCarouselBannerKey = ref<string | null>(null)
  const donationUrl = ref('')
  const roomsLimitGlobal = ref(100)
  const spectatorsLimit = ref(10)
  const gameMinReadyPlayers = ref(4)
  const winksLimit = ref(0)
  const knocksLimit = ref(0)
  const winkSpotChancePercent = ref(25)
  const seasonStartGameNumber = ref('1')
  const seniorModeratorUserId = ref<number | null>(null)
  const sanctionRules = ref<RulesSection[]>([])
  const sanctionReasons = computed<SanctionReason[]>(() => sanctionRules.value.flatMap(section => (
    section.rules.map(rule => ({ value: rule.text, label: rule.text }))
  )))
  const defaultSanctionReason = computed(() => sanctionReasons.value[0]?.value ?? '')
  const sanctionRulesReady = ref(false)
  const sanctionRulesLoadFailed = ref(false)
  const seasonStartGameNumbers = computed<number[]>(() => parseSeasonStartNumbers(seasonStartGameNumber.value))
  const ready = ref(false)
  let inited = false
  let onSettingsEv: ((e: any) => void) | null = null
  let onSanctionRulesEv: ((e: any) => void) | null = null

  function isBadgeKey(value: unknown): value is SanctionBadgeKey {
    return typeof value === 'string' && value in SANCTION_BADGES
  }

  function normalizeSanctionRulesPayload(payload: unknown): RulesSection[] | null {
    if (!payload || typeof payload !== 'object' || !Array.isArray((payload as SanctionRulesPayload).sections)) return null
    const sectionIds = new Set<string>()
    const sections: RulesSection[] = []
    for (const rawSection of (payload as SanctionRulesPayload).sections) {
      if (!rawSection || typeof rawSection !== 'object') return null
      const id = String(rawSection.id ?? '').trim()
      const title = String(rawSection.title ?? '').trim()
      if (!id || !title || sectionIds.has(id) || !Array.isArray(rawSection.rules) || rawSection.rules.length === 0) return null
      sectionIds.add(id)
      const rules = rawSection.rules.map(rawRule => {
        const text = String(rawRule?.text ?? '').trim()
        const badge = isBadgeKey(rawRule?.badge) ? rawRule.badge : null
        return { text, badge }
      })
      if (rules.some(rule => !rule.text)) return null
      sections.push({ id, title, rules })
    }
    return sections.length > 0 ? sections : null
  }

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
    ratingEnabled.value = Boolean(data.rating_enabled)
    streamsCanStart.value = Boolean(data.streams_can_start)
    chatOpenEnabled.value = Boolean(data.chat_open_enabled)
    chatMessagesEnabled.value = Boolean(data.chat_messages_enabled)
    verificationRestrictions.value = Boolean(data.verification_restrictions)
    adminBannerText.value = String(data.admin_banner_text || '').trim() || '0'
    adminBannerLink.value = String(data.admin_banner_link || '').trim() || '0'
    const homeCarouselBannerKeyValue = String(data.home_carousel_banner_key || '').trim()
    homeCarouselBannerKey.value = /^home\/carousel-banner\/\d{9,}-[a-f0-9]{32}\.(jpg|png)$/.test(homeCarouselBannerKeyValue)
      ? homeCarouselBannerKeyValue
      : null
    donationUrl.value = String(data.donation_url || '').trim()
    const roomsLimit = Number(data.rooms_limit_global)
    if (Number.isFinite(roomsLimit) && roomsLimit > 0) roomsLimitGlobal.value = Math.trunc(roomsLimit)
    const spectatorsLimitValue = Number(data.spectators_limit)
    if (Number.isFinite(spectatorsLimitValue) && spectatorsLimitValue >= 0) {
      spectatorsLimit.value = Math.trunc(spectatorsLimitValue)
    }
    const minReady = Number(data.game_min_ready_players)
    if (Number.isFinite(minReady) && minReady > 0) gameMinReadyPlayers.value = minReady
    const winks = Number(data.winks_limit)
    if (Number.isFinite(winks) && winks >= 0) winksLimit.value = winks
    const knocks = Number(data.knocks_limit)
    if (Number.isFinite(knocks) && knocks >= 0) knocksLimit.value = knocks
    const winkSpotChance = Number(data.wink_spot_chance_percent)
    if (Number.isFinite(winkSpotChance)) winkSpotChancePercent.value = Math.max(0, Math.min(100, Math.round(winkSpotChance)))
    seasonStartGameNumber.value = normalizeSeasonStart(data.season_start_game_number)
    const seniorModeratorId = Number(data.senior_moderator_user_id)
    seniorModeratorUserId.value = Number.isSafeInteger(seniorModeratorId) && seniorModeratorId > 0
      ? seniorModeratorId
      : null
    ready.value = true
  }

  function applySanctionRulesPayload(payload: unknown): boolean {
    const sections = normalizeSanctionRulesPayload(payload)
    if (!sections) return false
    sanctionRules.value = sections
    sanctionRulesReady.value = true
    sanctionRulesLoadFailed.value = false
    return true
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

  async function fetchSanctionRules(): Promise<void> {
    try {
      const { data } = await api.get<SanctionRulesPayload>('/admin/sanction-rules', { __skipAuth: true })
      if (!applySanctionRulesPayload(data)) throw new Error('invalid_sanction_rules_response')
    } catch (error) {
      sanctionRulesLoadFailed.value = true
      throw error
    } finally {
      sanctionRulesReady.value = true
    }
  }

  function ensureWS() {
    if (inited) return
    if (onSettingsEv) window.removeEventListener('auth-settings_update', onSettingsEv)
    if (onSanctionRulesEv) window.removeEventListener('auth-sanction_rules_update', onSanctionRulesEv)
    onSettingsEv = (event: CustomEvent<unknown>) => {
      if (applyPublicPayload(event?.detail)) return
      void fetchPublic()
    }
    window.addEventListener('auth-settings_update', onSettingsEv)
    onSanctionRulesEv = (event: CustomEvent<unknown>) => {
      if (!applySanctionRulesPayload(event?.detail)) void fetchSanctionRules().catch(() => {})
    }
    window.addEventListener('auth-sanction_rules_update', onSanctionRulesEv)
    inited = true
  }

  return {
    registrationEnabled,
    roomsCanCreate,
    roomsCanEnter,
    gamesCanStart,
    ratingEnabled,
    streamsCanStart,
    chatOpenEnabled,
    chatMessagesEnabled,
    verificationRestrictions,
    adminBannerText,
    adminBannerLink,
    homeCarouselBannerKey,
    donationUrl,
    roomsLimitGlobal,
    spectatorsLimit,
    gameMinReadyPlayers,
    winksLimit,
    knocksLimit,
    winkSpotChancePercent,
    seasonStartGameNumber,
    seniorModeratorUserId,
    sanctionRules,
    sanctionReasons,
    defaultSanctionReason,
    sanctionRulesReady,
    sanctionRulesLoadFailed,
    seasonStartGameNumbers,
    ready,

    fetchPublic,
    applyPublic,
    applyPublicPayload,
    applySanctionRulesPayload,
    ensureWS,
    fetchSanctionRules,
  }
})
