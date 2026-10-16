export type SanctionBadgeKey = 'ban' | 'tm1' | 'tm2' | 'tm3' | 'tm4' | 'ot1' | 'ot2' | 'ot3' | 'ot4' | 'foul' | 'tech_foul' | 'removal' | 'ppk'

export type TimedSanctionKind = 'timeout' | 'suspend'

export type TimedSanctionBadgeKey = Extract<SanctionBadgeKey, `tm${1 | 2 | 3 | 4}` | `ot${1 | 2 | 3 | 4}`>

export type SanctionRule = {
  text: string
  badges: SanctionBadgeKey[]
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
  duration?: { minHours: number; maxHours: number | null }
}

function timedSanctionBadge(code: string, backgroundColor: string, minHours: number, maxHours: number | null): SanctionBadge {
  const useDays = minHours % 24 === 0 && (maxHours === null || maxHours % 24 === 0)
  const formatHours = (hours: number) => useDays ? `${hours / 24}д` : `${hours}ч`
  return {
    code,
    backgroundColor,
    textColor: '#ffffff',
    notation: `${formatHours(minHours)}–${maxHours === null ? '…' : formatHours(maxHours)}`,
    duration: { minHours, maxHours },
  }
}

export const SANCTION_BADGES: Record<SanctionBadgeKey, SanctionBadge> = {
  ban: { code: 'БАН', backgroundColor: 'var(--sanction-ban-background)', textColor: '#ffffff' },
  tm1: timedSanctionBadge('ТМ1', 'var(--sanction-timeout-background)', 6, 24),
  tm2: timedSanctionBadge('ТМ2', 'var(--sanction-timeout-background)', 24, 72),
  tm3: timedSanctionBadge('ТМ3', 'var(--sanction-timeout-background)', 72, 168),
  tm4: timedSanctionBadge('ТМ4', 'var(--sanction-timeout-background)', 168, null),
  ot1: timedSanctionBadge('ОТ1', 'var(--sanction-suspend-background)', 6, 24),
  ot2: timedSanctionBadge('ОТ2', 'var(--sanction-suspend-background)', 24, 72),
  ot3: timedSanctionBadge('ОТ3', 'var(--sanction-suspend-background)', 72, 168),
  ot4: timedSanctionBadge('ОТ4', 'var(--sanction-suspend-background)', 168, null),
  foul: { code: 'ФОЛ', backgroundColor: 'var(--sanction-foul-background)', textColor: '#ffffff' },
  tech_foul: { code: 'Т.ФОЛ', backgroundColor: 'var(--sanction-tech-foul-background)', textColor: '#ffffff' },
  removal: { code: 'УДЛ', backgroundColor: 'var(--sanction-removal-background)', textColor: '#ffffff' },
  ppk: { code: 'ППК', backgroundColor: 'var(--sanction-ppk-background)', textColor: '#ffffff' },
}

const TIMED_SANCTION_BADGE_KEYS: Record<TimedSanctionKind, readonly TimedSanctionBadgeKey[]> = {
  timeout: ['tm1', 'tm2', 'tm3', 'tm4'],
  suspend: ['ot1', 'ot2', 'ot3', 'ot4'],
}

export function getTimedSanctionBadgeKeys(kind: TimedSanctionKind, badges: readonly SanctionBadgeKey[]): TimedSanctionBadgeKey[] {
  return TIMED_SANCTION_BADGE_KEYS[kind].filter(badgeKey => badges.includes(badgeKey))
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
