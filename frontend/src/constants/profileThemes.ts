export const PROFILE_THEME_DEFAULT = 'violet' as const

export const PROFILE_THEME_OPTIONS = [
  { key: 'violet', title: 'Фиолетовый', shadow: 'rgba(80, 40, 200, 0.4)', chat: 'rgba(80, 40, 200, 0.6)', bg: 'rgba(80, 40, 200, 0.8)', hover: 'rgba(80, 40, 200, 1)' },
  { key: 'mulberry', title: 'Тутовый', shadow: 'rgba(180, 40, 100, 0.4)', chat: 'rgba(180, 40, 100, 0.6)', bg: 'rgba(180, 40, 100, 0.8)', hover: 'rgba(180, 40, 100, 1)' },
  { key: 'garnet', title: 'Гранатовый', shadow: 'rgba(140, 20, 20, 0.4)', chat: 'rgb(140, 20, 20, 0.6)', bg: 'rgba(140, 20, 20, 0.8)', hover: 'rgb(140, 20, 20, 1)' },
  { key: 'terracotta', title: 'Терракотовый', shadow: 'rgba(180, 120, 40, 0.4)', chat: 'rgba(180, 120, 40, 0.6)', bg: 'rgba(180, 120, 40, 0.8)', hover: 'rgba(180, 120, 40, 1)' },
  { key: 'amber', title: 'Янтарный', shadow: 'rgba(160, 160, 40, 0.4)', chat: 'rgb(160, 160, 40, 0.6)', bg: 'rgba(160, 160, 40, 0.8)', hover: 'rgb(160, 160, 40, 1)' },
  { key: 'olive', title: 'Оливковый', shadow: 'rgba(100, 160, 40, 0.4)', chat: 'rgb(100, 160, 40, 0.6)', bg: 'rgba(100, 160, 40, 0.8)', hover: 'rgb(100, 160, 40, 1)' },
  { key: 'emerald', title: 'Изумрудный', shadow: 'rgba(40, 140, 120, 0.4)', chat: 'rgb(40, 140, 120, 0.6)', bg: 'rgba(40, 140, 120, 0.8)', hover: 'rgb(40, 140, 120, 1)' },
  { key: 'lagoon', title: 'Лагунный', shadow: 'rgba(40, 140, 160, 0.4)', chat: 'rgba(40, 140, 160, 0.6)', bg: 'rgba(40, 140, 160, 0.8)', hover: 'rgba(40, 140, 160, 1)' },
  { key: 'azure', title: 'Лазурный', shadow: 'rgba(40, 80, 180, 0.4)', chat: 'rgba(40, 80, 180, 0.6)', bg: 'rgba(40, 80, 180, 0.8)', hover: 'rgba(40, 80, 180, 1)' },
  { key: 'midnight', title: 'Полуночный', shadow: 'rgba(40, 40, 140, 0.4)', chat: 'rgba(40, 40, 140, 0.6)', bg: 'rgba(40, 40, 140, 0.8)', hover: 'rgba(40, 40, 140, 1)' },
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

export function buildProfileThemeBgStyle(value: unknown): Record<string, string> {
  const option = getProfileThemeOption(value)
  if (!option) return {}
  return {
    '--user-theme-bg': option.bg,
  }
}
