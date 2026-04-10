export const PROFILE_THEME_DEFAULT = 'violet' as const

export const PROFILE_THEME_OPTIONS = [
  { key: 'violet', title: 'Фиолетовый', bg: '#6641ec', hover: '#7554f0', shadow: 'rgba(102, 65, 236, 0.4)' },
  { key: 'mulberry', title: 'Тутовый', bg: '#8a315d', hover: '#9d4471', shadow: 'rgba(138, 49, 93, 0.4)' },
  { key: 'garnet', title: 'Гранатовый', bg: '#962f3f', hover: '#aa4253', shadow: 'rgba(150, 47, 63, 0.4)' },
  { key: 'terracotta', title: 'Терракотовый', bg: '#9d4b36', hover: '#af5f49', shadow: 'rgba(157, 75, 54, 0.4)' },
  { key: 'amber', title: 'Янтарный', bg: '#986319', hover: '#98651b', shadow: 'rgba(152, 99, 25, 0.4)' },
  { key: 'olive', title: 'Оливковый', bg: '#65722f', hover: '#697936', shadow: 'rgba(101, 114, 47, 0.4)' },
  { key: 'emerald', title: 'Изумрудный', bg: '#287655', hover: '#30795a', shadow: 'rgba(40, 118, 85, 0.4)' },
  { key: 'lagoon', title: 'Лагунный', bg: '#1f6376', hover: '#34798c', shadow: 'rgba(31, 99, 118, 0.4)' },
  { key: 'azure', title: 'Лазурный', bg: '#2c679f', hover: '#3972aa', shadow: 'rgba(44, 103, 159, 0.4)' },
  { key: 'midnight', title: 'Полуночный', bg: '#3a477e', hover: '#4d5b95', shadow: 'rgba(58, 71, 126, 0.4)' },
] as const

export type ProfileThemeColor = typeof PROFILE_THEME_OPTIONS[number]['key']
export type ProfileThemeOption = typeof PROFILE_THEME_OPTIONS[number]

const PROFILE_THEME_MAP = PROFILE_THEME_OPTIONS.reduce<Record<ProfileThemeColor, ProfileThemeOption>>((acc, item) => {
  acc[item.key] = item
  return acc
}, {} as Record<ProfileThemeColor, ProfileThemeOption>)

export function normalizeProfileThemeColor(value: unknown): ProfileThemeColor | null {
  const key = String(value || '').trim().toLowerCase()
  return key in PROFILE_THEME_MAP ? (key as ProfileThemeColor) : null
}

export function resolveProfileThemeColor(value: unknown): ProfileThemeColor {
  return normalizeProfileThemeColor(value) ?? PROFILE_THEME_DEFAULT
}

export function getProfileThemeOption(value: unknown): ProfileThemeOption | null {
  const key = normalizeProfileThemeColor(value)
  return key ? PROFILE_THEME_MAP[key] : null
}

export function buildProfileThemeStyle(value: unknown): Record<string, string> {
  const option = getProfileThemeOption(value)
  if (!option) return {}
  return {
    '--user-theme-bg': option.bg,
    '--user-theme-bg-hover': option.hover,
    '--user-theme-shadow': option.shadow,
  }
}
