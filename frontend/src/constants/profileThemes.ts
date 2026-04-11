export const PROFILE_THEME_DEFAULT = 'terracotta' as const

export const PROFILE_THEME_OPTIONS = [
  { key: 'violet', title: 'Фиолетовый', bg: 'rgba(100, 40, 200, 0.6)', hover: 'rgba(100, 40, 200, 0.75)' },
  { key: 'mulberry', title: 'Тутовый', bg: 'rgba(200, 40, 100, 0.6)', hover: 'rgba(200, 40, 100, 0.75)' },
  { key: 'garnet', title: 'Гранатовый', bg: 'rgba(180, 40, 40, 0.6)', hover: 'rgb(180, 40, 40, 0.75)' },
  { key: 'terracotta', title: 'Терракотовый', bg: 'rgba(180, 120, 40, 0.6)', hover: 'rgba(180, 120, 40, 0.75)' },
  { key: 'amber', title: 'Янтарный', bg: 'rgba(200, 180, 40, 0.6)', hover: 'rgb(200, 180, 40, 0.75)' },
  { key: 'olive', title: 'Оливковый', bg: 'rgba(100, 160, 40, 0.6)', hover: 'rgb(100, 160, 40, 0.75)' },
  { key: 'emerald', title: 'Изумрудный', bg: 'rgba(40, 160, 120, 0.6)', hover: 'rgb(40, 160, 120, 0.75)' },
  { key: 'lagoon', title: 'Лагунный', bg: 'rgba(40, 140, 180, 0.6)', hover: 'rgba(40, 140, 180, 0.75)' },
  { key: 'azure', title: 'Лазурный', bg: 'rgba(40, 80, 180, 0.6)', hover: 'rgba(40, 80, 180, 0.75)' },
  { key: 'midnight', title: 'Полуночный', bg: 'rgba(40, 40, 140, 0.6)', hover: 'rgba(40, 40, 140, 0.75)' },
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
  }
}

export function buildProfileThemeBgStyle(value: unknown): Record<string, string> {
  const option = getProfileThemeOption(value)
  if (!option) return {}
  return {
    '--user-theme-bg': option.bg,
  }
}
