export const PROFILE_THEME_DEFAULT = 'terracotta' as const

const PROFILE_THEME_GRADIENT = {
  angle: '180deg',
} as const

const PROFILE_THEME_PRESETS = [
  { key: 'onyx', color1: '#777777', color2: '#2D2D2D', adminOnly: true },
  { key: 'plum', color1: '#373737', color2: '#000000' },
  { key: 'mulberry', color1: '#B5397D', color2: '#51133B' },
  { key: 'rose', color1: '#BD2B4D', color2: '#4C1424' },
  { key: 'garnet', color1: '#D01B40', color2: '#4B0C0F' },
  { key: 'ruby', color1: '#C8472A', color2: '#511F17' },
  { key: 'terracotta', color1: '#D06A29', color2: '#653118' },
  { key: 'copper', color1: '#D58926', color2: '#624017' },
  { key: 'gold', color1: '#D0B000', color2: '#5F4E16' },
  { key: 'amber', color1: '#9AB200', color2: '#4A4F14' },
  { key: 'moss', color1: '#70B409', color2: '#334A19' },
  { key: 'olive', color1: '#349D0B', color2: '#1A4116' },
  { key: 'mint', color1: '#2FA169', color2: '#153B2C' },
  { key: 'emerald', color1: '#2F9C8C', color2: '#194844' },
  { key: 'teal', color1: '#00A1BD', color2: '#1E4E54' },
  { key: 'lagoon', color1: '#0091CF', color2: '#132C4C' },
  { key: 'sky', color1: '#4377BD', color2: '#121E4B' },
  { key: 'cobalt', color1: '#2C4AC5', color2: '#0A1748' },
  { key: 'azure', color1: '#6C70DA', color2: '#141B4C' },
  { key: 'midnight', color1: '#825EB7', color2: '#1F1044' },
  { key: 'violet', color1: '#A34BA6', color2: '#381353' },
] as const

type ProfileThemePreset = typeof PROFILE_THEME_PRESETS[number]
export type ProfileThemeColor = ProfileThemePreset['key']
const PROFILE_THEME_ADMIN_HIDDEN_COLORS = new Set<ProfileThemeColor>(['plum'])
type ProfileThemePresetBase = {
  key: ProfileThemeColor
  color1: string
  color2: string
  adminOnly?: boolean
}
export type ProfileThemeOption = ProfileThemePresetBase & { bg: string; hover: string }

function normalizeHexColor(value: string): string {
  const color = String(value || '').trim()
  if (/^#[0-9a-f]{6}$/i.test(color)) return color.toLowerCase()
  const short = color.match(/^#([0-9a-f]{3})$/i)
  if (!short) return color
  const [r, g, b] = short[1].split('')
  return `#${r}${r}${g}${g}${b}${b}`.toLowerCase()
}

function buildProfileThemeGradient(color1: string, color2: string): string {
  return `linear-gradient(${PROFILE_THEME_GRADIENT.angle}, ${normalizeHexColor(color1)} 0%, ${normalizeHexColor(color2)} 100%)`
}

function buildProfileThemeHoverGradient(color1: string, color2: string): string {
  return buildProfileThemeGradient(color2, color1)
}

export const PROFILE_THEME_OPTIONS: readonly ProfileThemeOption[] = PROFILE_THEME_PRESETS.map((item) => ({
  ...item,
  bg: buildProfileThemeGradient(item.color1, item.color2),
  hover: buildProfileThemeHoverGradient(item.color1, item.color2),
}))

const PROFILE_THEME_MAP = PROFILE_THEME_OPTIONS.reduce<Record<ProfileThemeColor, ProfileThemeOption>>((acc, item) => {
  acc[item.key] = item
  return acc
}, {} as Record<ProfileThemeColor, ProfileThemeOption>)
const GRADIENT_BACKGROUND_RE = /\b(?:repeating-)?(?:linear|radial|conic)-gradient\(/i

export function isAdminProfileThemeRole(role: unknown): boolean {
  return String(role || '').trim().toLowerCase() === 'admin'
}

export function getProfileThemeOptions(role?: unknown): readonly ProfileThemeOption[] {
  if (isAdminProfileThemeRole(role)) {
    return PROFILE_THEME_OPTIONS.filter((item) => !PROFILE_THEME_ADMIN_HIDDEN_COLORS.has(item.key))
  }
  return PROFILE_THEME_OPTIONS.filter((item) => !item.adminOnly)
}

function needsDirectBackgroundStyle(bg: string, hover?: string): boolean {
  return GRADIENT_BACKGROUND_RE.test(bg) || GRADIENT_BACKGROUND_RE.test(String(hover || ''))
}

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
  const style: Record<string, string> = {
    '--user-theme-bg': option.bg,
    '--user-theme-bg-hover': option.hover,
  }
  if (needsDirectBackgroundStyle(option.bg, option.hover)) style.background = option.bg
  return style
}

export function buildProfileThemeBgStyle(value: unknown): Record<string, string> {
  const option = getProfileThemeOption(value)
  if (!option) return {}
  const style: Record<string, string> = {
    '--user-theme-bg': option.bg,
  }
  if (needsDirectBackgroundStyle(option.bg)) style.background = option.bg
  return style
}
