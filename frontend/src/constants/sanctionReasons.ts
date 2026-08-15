export type SanctionBadgeKey = 'ban' | 'tm1' | 'tm2' | 'tm3' | 'tm4' | 'ot1' | 'ot2' | 'ot3' | 'ot4'

export type SanctionRule = {
  text: string
  badge: SanctionBadgeKey | null
}

export type RulesSection = {
  id: string
  title: string
  rules: SanctionRule[]
}

export type SanctionBadge = {
  code: string
  backgroundColor: string
  textColor: string
  notation?: string
}

export const SANCTION_BADGES: Record<SanctionBadgeKey, SanctionBadge> = {
  ban: { code: 'БАН', backgroundColor: 'var(--sanction-ban-background)', textColor: '#ffffff' },
  tm1: { code: 'ТМ1', notation: '6ч–24ч', backgroundColor: 'var(--sanction-timeout-background)', textColor: '#ffffff' },
  tm2: { code: 'ТМ2', notation: '1д–3д', backgroundColor: 'var(--sanction-timeout-background)', textColor: '#ffffff' },
  tm3: { code: 'ТМ3', notation: '3д–7д', backgroundColor: 'var(--sanction-timeout-background)', textColor: '#ffffff' },
  tm4: { code: 'ТМ4', notation: '1д–…', backgroundColor: 'var(--sanction-timeout-background)', textColor: '#ffffff' },
  ot1: { code: 'ОТ1', notation: '6ч–24ч', backgroundColor: 'var(--sanction-suspend-background)', textColor: '#ffffff' },
  ot2: { code: 'ОТ2', notation: '1д–3д', backgroundColor: 'var(--sanction-suspend-background)', textColor: '#ffffff' },
  ot3: { code: 'ОТ3', notation: '3д–7д', backgroundColor: 'var(--sanction-suspend-background)', textColor: '#ffffff' },
  ot4: { code: 'ОТ4', notation: '7д–…', backgroundColor: 'var(--sanction-suspend-background)', textColor: '#ffffff' },
}

export const SUSPEND_SANCTION_BADGES = [
  SANCTION_BADGES.ot1,
  SANCTION_BADGES.ot2,
  SANCTION_BADGES.ot3,
  SANCTION_BADGES.ot4,
] as const

export const TIMEOUT_SANCTION_BADGES = [
  SANCTION_BADGES.tm1,
  SANCTION_BADGES.tm2,
  SANCTION_BADGES.tm3,
  SANCTION_BADGES.tm4,
] as const

export function getSanctionBadge(badgeKey: SanctionBadgeKey | null | undefined): SanctionBadge | undefined {
  return badgeKey ? SANCTION_BADGES[badgeKey] : undefined
}
