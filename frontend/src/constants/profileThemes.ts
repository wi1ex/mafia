export const PROFILE_THEME_DEFAULT = 'terracotta' as const

const PROFILE_THEME_GRADIENT = {
  topGlowAlpha: '50',
  topGlowFade: '200%',
  cornerGlowAlpha: '1a',
  cornerGlowFade: '200%',
  angle: '170deg',
  surfaceColor: '#0f0f0f',
  hoverSurfaceColor: '#151515',
  hoverTopGlowAlpha: '50',
} as const

const PROFILE_THEME_PRESETS = [
  { key: 'mulberry', title: 'Тутовый', accent: '#c82864' },
  { key: 'garnet', title: 'Гранатовый', accent: '#b42828' },
  { key: 'terracotta', title: 'Терракотовый', accent: '#dc8c28' },
  { key: 'amber', title: 'Янтарный', accent: '#dcc828' },
  { key: 'olive', title: 'Оливковый', accent: '#64a028' },
  { key: 'emerald', title: 'Изумрудный', accent: '#28a08c' },
  { key: 'lagoon', title: 'Лагунный', accent: '#288cb4' },
  { key: 'azure', title: 'Лазурный', accent: '#2850b4' },
  { key: 'midnight', title: 'Полуночный', accent: '#28288c' },
  { key: 'violet', title: 'Фиолетовый', accent: '#6428c8' },
  { key: 'onyx', title: 'Ониксовый', accent: '#787878', adminOnly: true },
] as const

type ProfileThemePreset = typeof PROFILE_THEME_PRESETS[number]
export type ProfileThemeColor = ProfileThemePreset['key']
type ProfileThemePresetBase = {
  key: ProfileThemeColor
  title: string
  accent: string
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

function withAlpha(color: string, alphaHex: string): string {
  const normalized = normalizeHexColor(color)
  return /^#[0-9a-f]{6}$/i.test(normalized) ? `${normalized}${alphaHex}` : normalized
}

function buildProfileThemeGradient(accent: string, glowAlpha: string, surfaceColor: string): string {
  const normalizedAccent = normalizeHexColor(accent)
  return [
    `radial-gradient(circle at top, ${withAlpha(normalizedAccent, glowAlpha)}, #0000 ${PROFILE_THEME_GRADIENT.topGlowFade})`,
    `radial-gradient(circle at 100% 100%, ${withAlpha('#ffffff', PROFILE_THEME_GRADIENT.cornerGlowAlpha)}, #0000 ${PROFILE_THEME_GRADIENT.cornerGlowFade})`,
    `linear-gradient(${PROFILE_THEME_GRADIENT.angle}, ${normalizedAccent}, ${surfaceColor})`,
  ].join(', ')
}

export const PROFILE_THEME_OPTIONS: readonly ProfileThemeOption[] = PROFILE_THEME_PRESETS.map((item) => ({
  ...item,
  bg: buildProfileThemeGradient(item.accent, PROFILE_THEME_GRADIENT.topGlowAlpha, PROFILE_THEME_GRADIENT.surfaceColor),
  hover: buildProfileThemeGradient(item.accent, PROFILE_THEME_GRADIENT.hoverTopGlowAlpha, PROFILE_THEME_GRADIENT.hoverSurfaceColor),
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
