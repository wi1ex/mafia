const HEAD_RATE_ROLE = 'head_rate'

export function getProfileRoleTags(role: unknown, additionalRoles: unknown): string[] {
  const normalizedRole = String(role || '').trim().toLowerCase()
  const normalizedAdditionalRoles = Array.isArray(additionalRoles)
    ? additionalRoles.map((item) => String(item || '').trim().toLowerCase())
    : []
  const tags = ['#игрок']

  if (normalizedAdditionalRoles.includes(HEAD_RATE_ROLE)) tags.push('#ведущий')
  if (normalizedRole === 'moder') tags.push('#модератор')
  if (normalizedRole === 'admin') tags.push('#админ')

  return tags
}
