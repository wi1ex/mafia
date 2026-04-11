import iconSub1 from '@/assets/svg/sub_icon1.svg'
import iconSub2 from '@/assets/svg/sub_icon2.svg'
import iconSub3 from '@/assets/svg/sub_icon3.svg'
import iconSub4 from '@/assets/svg/sub_icon4.svg'
import iconSub5 from '@/assets/svg/sub_icon5.svg'
import iconSub6 from '@/assets/svg/sub_icon6.svg'
import iconSub7 from '@/assets/svg/sub_icon7.svg'
import iconSub8 from '@/assets/svg/sub_icon8.svg'
import iconSub9 from '@/assets/svg/sub_icon9.svg'
import iconSub10 from '@/assets/svg/sub_icon10.svg'

export const PROFILE_THEME_ICON_OPTIONS = [
  { key: 'sub_icon1', title: 'Иконка 1', src: iconSub1 },
  { key: 'sub_icon2', title: 'Иконка 2', src: iconSub2 },
  { key: 'sub_icon3', title: 'Иконка 3', src: iconSub3 },
  { key: 'sub_icon4', title: 'Иконка 4', src: iconSub4 },
  { key: 'sub_icon5', title: 'Иконка 5', src: iconSub5 },
  { key: 'sub_icon6', title: 'Иконка 6', src: iconSub6 },
  { key: 'sub_icon7', title: 'Иконка 7', src: iconSub7 },
  { key: 'sub_icon8', title: 'Иконка 8', src: iconSub8 },
  { key: 'sub_icon9', title: 'Иконка 9', src: iconSub9 },
  { key: 'sub_icon10', title: 'Иконка 10', src: iconSub10 },
] as const

export type ProfileThemeIcon = typeof PROFILE_THEME_ICON_OPTIONS[number]['key']
export type ProfileThemeIconOption = typeof PROFILE_THEME_ICON_OPTIONS[number]

const PROFILE_THEME_ICON_MAP = PROFILE_THEME_ICON_OPTIONS.reduce<Record<ProfileThemeIcon, ProfileThemeIconOption>>((acc, item) => {
  acc[item.key] = item
  return acc
}, {} as Record<ProfileThemeIcon, ProfileThemeIconOption>)

export function normalizeProfileThemeIcon(value: unknown): ProfileThemeIcon | null {
  const key = String(value || '').trim().toLowerCase()
  return key in PROFILE_THEME_ICON_MAP ? (key as ProfileThemeIcon) : null
}

export function getProfileThemeIconOption(value: unknown): ProfileThemeIconOption | null {
  const key = normalizeProfileThemeIcon(value)
  return key ? PROFILE_THEME_ICON_MAP[key] : null
}

export function getProfileThemeIconSrc(value: unknown): string | null {
  return getProfileThemeIconOption(value)?.src || null
}
