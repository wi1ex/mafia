import iconSlot1 from '@/assets/svg/slot1.svg'
import iconSlot2 from '@/assets/svg/slot2.svg'
import iconSlot3 from '@/assets/svg/slot3.svg'
import iconSlot4 from '@/assets/svg/slot4.svg'
import iconSlot5 from '@/assets/svg/slot5.svg'
import iconSlot6 from '@/assets/svg/slot6.svg'
import iconSlot7 from '@/assets/svg/slot7.svg'
import iconSlot8 from '@/assets/svg/slot8.svg'
import iconSlot9 from '@/assets/svg/slot9.svg'
import iconSlot10 from '@/assets/svg/slot10.svg'

export const PROFILE_THEME_ICON_OPTIONS = [
  { key: 'slot1', title: 'Слот 1', src: iconSlot1 },
  { key: 'slot2', title: 'Слот 2', src: iconSlot2 },
  { key: 'slot3', title: 'Слот 3', src: iconSlot3 },
  { key: 'slot4', title: 'Слот 4', src: iconSlot4 },
  { key: 'slot5', title: 'Слот 5', src: iconSlot5 },
  { key: 'slot6', title: 'Слот 6', src: iconSlot6 },
  { key: 'slot7', title: 'Слот 7', src: iconSlot7 },
  { key: 'slot8', title: 'Слот 8', src: iconSlot8 },
  { key: 'slot9', title: 'Слот 9', src: iconSlot9 },
  { key: 'slot10', title: 'Слот 10', src: iconSlot10 },
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
