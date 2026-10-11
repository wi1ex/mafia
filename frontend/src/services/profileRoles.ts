const HEAD_RATE_ROLE = 'head_rate'

export type ProfileRoleBadge = {
  key: 'player' | 'head_rate' | 'moder' | 'admin'
  label: string
}

export function getProfileRoleBadges(role: unknown, additionalRoles: unknown): ProfileRoleBadge[] {
  const normalizedRole = String(role || '').trim().toLowerCase()
  const normalizedAdditionalRoles = Array.isArray(additionalRoles)
    ? additionalRoles.map((item) => String(item || '').trim().toLowerCase())
    : []
  const badges: ProfileRoleBadge[] = [{ key: 'player', label: 'игрок' }]

  if (normalizedAdditionalRoles.includes(HEAD_RATE_ROLE)) badges.push({ key: 'head_rate', label: 'ведущий' })
  if (normalizedRole === 'moder') badges.push({ key: 'moder', label: 'модератор' })
  if (normalizedRole === 'admin') badges.push({ key: 'admin', label: 'админ' })

  return badges
}

export function getProfileRoleTags(role: unknown, additionalRoles: unknown): string[] {
  return getProfileRoleBadges(role, additionalRoles).map(({ label }) => `#${label}`)
}
