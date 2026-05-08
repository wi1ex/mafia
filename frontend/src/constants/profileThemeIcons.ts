import adminProfileThemeIconSrc from '@/assets/svg/sub_admin_icon.svg'
import moderProfileThemeIconSrc from '@/assets/svg/sub_moder_icon.svg'

const PROFILE_THEME_ICON_ASSET_MODULES = import.meta.glob('@/assets/svg/sub_icon*.svg', { eager: true, query: '?url', import: 'default' })

const PROFILE_THEME_ICON_ASSETS = Object.entries(PROFILE_THEME_ICON_ASSET_MODULES).reduce<Record<string, string>>((acc, [path, src]) => {
  const match = path.match(/sub_icon\d+\.svg$/)
  if (!match) return acc
  acc[match[0].replace('.svg', '')] = String(src || '')
  return acc
}, {})

export const PROFILE_THEME_ICON_NONE = 'none'
export const PROFILE_THEME_ICON_KEYS = [
  'sub_icon1',
  'sub_icon2',
  'sub_icon3',
  'sub_icon4',
  'sub_icon5',
  'sub_icon6',
  'sub_icon7',
  'sub_icon8',
  'sub_icon9',
  'sub_icon10',
  'sub_icon11',
  'sub_icon12',
  'sub_icon13',
  'sub_icon14',
  'sub_icon15',
  'sub_icon16',
  'sub_icon17',
  'sub_icon18',
  'sub_icon19',
  'sub_icon20',
  'sub_icon21',
  'sub_icon22',
  'sub_icon23',
  'sub_icon24',
  'sub_icon25',
  'sub_icon26',
  'sub_icon27',
  'sub_icon28',
  'sub_icon29',
  'sub_icon30',
  'sub_icon31',
  'sub_icon32',
  'sub_icon33',
  'sub_icon34',
  'sub_icon35',
  'sub_icon36',
  'sub_icon37',
  'sub_icon38',
  'sub_icon39',
] as const

export type ProfileThemeAssetIcon = typeof PROFILE_THEME_ICON_KEYS[number]
export type ProfileThemeIcon = typeof PROFILE_THEME_ICON_NONE | ProfileThemeAssetIcon

export interface ProfileThemeIconOption {
  key: ProfileThemeIcon
  title: string
  src: string | null
  available: boolean
}

const FALLBACK_PROFILE_THEME_ICON_SRC = PROFILE_THEME_ICON_ASSETS.sub_icon1 || ''

const PROFILE_THEME_ASSET_ICON_OPTIONS: readonly ProfileThemeIconOption[] = PROFILE_THEME_ICON_KEYS.map((key, index) => {
  const src = PROFILE_THEME_ICON_ASSETS[key] || FALLBACK_PROFILE_THEME_ICON_SRC
  return {
    key,
    title: `Иконка ${index + 1}`,
    src,
    available: Boolean(PROFILE_THEME_ICON_ASSETS[key]),
  }
})

export const PROFILE_THEME_ICON_OPTIONS: readonly ProfileThemeIconOption[] = [
  {
    key: PROFILE_THEME_ICON_NONE,
    title: 'Без иконки',
    src: null,
    available: true,
  },
  ...PROFILE_THEME_ASSET_ICON_OPTIONS,
]

const PROFILE_THEME_ICON_MAP = PROFILE_THEME_ICON_OPTIONS.reduce<Record<ProfileThemeIcon, ProfileThemeIconOption>>((acc, item) => {
  acc[item.key] = item
  return acc
}, {} as Record<ProfileThemeIcon, ProfileThemeIconOption>)

export function normalizeProfileThemeIcon(value: unknown): ProfileThemeIcon {
  const key = String(value || '').trim().toLowerCase()
  return key in PROFILE_THEME_ICON_MAP ? (key as ProfileThemeIcon) : PROFILE_THEME_ICON_NONE
}

export function getProfileThemeIconOption(value: unknown): ProfileThemeIconOption | null {
  const key = normalizeProfileThemeIcon(value)
  return PROFILE_THEME_ICON_MAP[key] || null
}

export function getProfileThemeIconSrc(value: unknown): string | null {
  return getProfileThemeIconOption(value)?.src || null
}

export function isModeratorProfileThemeRole(role: unknown): boolean {
  return String(role || '').trim().toLowerCase() === 'moder'
}

export function isAdminProfileThemeRole(role: unknown): boolean {
  return String(role || '').trim().toLowerCase() === 'admin'
}

export interface ProfileThemeBadgeOptions {
  hideAdminBadge?: boolean
  hideModeratorBadge?: boolean
}

export function getProfileThemeBadgeSources(value: unknown, role?: unknown, options: ProfileThemeBadgeOptions = {}): string[] {
  const badges: string[] = []
  const themeIconSrc = getProfileThemeIconSrc(value)
  if (themeIconSrc) badges.push(themeIconSrc)
  if (!options.hideAdminBadge && isAdminProfileThemeRole(role) && adminProfileThemeIconSrc) badges.push(adminProfileThemeIconSrc)
  if (!options.hideModeratorBadge && isModeratorProfileThemeRole(role) && moderProfileThemeIconSrc) badges.push(moderProfileThemeIconSrc)
  return badges
}
