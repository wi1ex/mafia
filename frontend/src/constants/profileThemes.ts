export const PROFILE_THEME_DEFAULT = 'violet' as const

export const PROFILE_THEME_OPTIONS = [
  { key: 'violet', title: 'Фиолетовый', bg: '#6f4df6', hover: '#7f62ff', shadow: 'rgba(111, 77, 246, 0.4)' },
  { key: 'plum', title: 'Сливовый', bg: '#8a3f8f', hover: '#9d53a2', shadow: 'rgba(138, 63, 143, 0.4)' },
  { key: 'ruby', title: 'Рубиновый', bg: '#b13a5b', hover: '#c85071', shadow: 'rgba(177, 58, 91, 0.4)' },
  { key: 'coral', title: 'Коралловый', bg: '#d45b4d', hover: '#e66f61', shadow: 'rgba(212, 91, 77, 0.4)' },
  { key: 'amber', title: 'Янтарный', bg: '#b97a22', hover: '#cf9137', shadow: 'rgba(185, 122, 34, 0.4)' },
  { key: 'olive', title: 'Оливковый', bg: '#74823a', hover: '#86954d', shadow: 'rgba(116, 130, 58, 0.4)' },
  { key: 'emerald', title: 'Изумрудный', bg: '#2f8a67', hover: '#43a17d', shadow: 'rgba(47, 138, 103, 0.4)' },
  { key: 'teal', title: 'Бирюзовый', bg: '#2f7e84', hover: '#439499', shadow: 'rgba(47, 126, 132, 0.4)' },
  { key: 'azure', title: 'Лазурный', bg: '#2f73b4', hover: '#4788c7', shadow: 'rgba(47, 115, 180, 0.4)' },
  { key: 'cobalt', title: 'Кобальтовый', bg: '#3f56b4', hover: '#556bca', shadow: 'rgba(63, 86, 180, 0.4)' },
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
