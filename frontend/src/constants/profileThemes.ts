export const PROFILE_THEME_DEFAULT = 'terracotta' as const

const PROFILE_THEME_GRADIENT = {
  angle: '180deg',
  hoverOverlay: 'linear-gradient(180deg, rgba(255, 255, 255, 0.16) 0%, rgba(255, 255, 255, 0.10) 100%)',
} as const

const PROFILE_THEME_PRESETS = [
  { key: 'mulberry', title: 'Фуксиевый', color1: '#C72787', color2: '#51133B' },
  { key: 'rose', title: 'Малиновый', color1: '#BD2B4D', color2: '#4C1424' },
  { key: 'garnet', title: 'Гранатовый', color1: '#BB1717', color2: '#4B0C0F' },
  { key: 'ruby', title: 'Киноварный', color1: '#C8472A', color2: '#511F17' },
  { key: 'terracotta', title: 'Терракотовый', color1: '#DC6728', color2: '#653118' },
  { key: 'copper', title: 'Медный', color1: '#D58926', color2: '#624017' },
  { key: 'gold', title: 'Золотой', color1: '#CDAA25', color2: '#5F4E16' },
  { key: 'amber', title: 'Лаймовый', color1: '#B4C422', color2: '#4A4F14' },
  { key: 'moss', title: 'Моховой', color1: '#71A82E', color2: '#334A19' },
  { key: 'olive', title: 'Травяной', color1: '#38A028', color2: '#1A4116' },
  { key: 'mint', title: 'Мятный', color1: '#2FA169', color2: '#153B2C' },
  { key: 'emerald', title: 'Изумрудный', color1: '#2F9C8C', color2: '#194844' },
  { key: 'teal', title: 'Бирюзовый', color1: '#2B8083', color2: '#153539' },
  { key: 'lagoon', title: 'Лагунный', color1: '#289AB3', color2: '#143F4C' },
  { key: 'sky', title: 'Синий', color1: '#2669B5', color2: '#132C4C' },
  { key: 'cobalt', title: 'Кобальтовый', color1: '#2647B4', color2: '#121E4B' },
  { key: 'azure', title: 'Индиго', color1: '#223192', color2: '#141B4C' },
  { key: 'midnight', title: 'Полуночный', color1: '#4420A0', color2: '#1F1044' },
  { key: 'violet', title: 'Фиолетовый', color1: '#8828C8', color2: '#381353' },
  { key: 'plum', title: 'Сливовый', color1: '#702782', color2: '#34143E' },
  { key: 'onyx', title: 'Ониксовый', color1: '#707173', color2: '#2F2F32', adminOnly: true },
] as const

type ProfileThemePreset = typeof PROFILE_THEME_PRESETS[number]
export type ProfileThemeColor = ProfileThemePreset['key']
type ProfileThemePresetBase = {
  key: ProfileThemeColor
  title: string
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
  return `${PROFILE_THEME_GRADIENT.hoverOverlay}, ${buildProfileThemeGradient(color1, color2)}`
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
  if (isAdminProfileThemeRole(role)) return PROFILE_THEME_OPTIONS
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
