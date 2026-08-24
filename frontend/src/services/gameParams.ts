export type RoomGameParams = {
  mode: 'normal' | 'rating'
  spectators_limit: number
  nominate_mode: 'head' | 'players'
  tech_fouls: boolean
  break_at_zero: boolean
  lift_at_zero: boolean
  lift_3x: boolean
  first_shot_check: boolean
  wink_knock: boolean
  farewell_wills: boolean
  music: boolean
}

type LegacyRoomGameParams = Partial<RoomGameParams> & {
  lift_2x_at_zero?: boolean
}

export const SPECTATORS_DISABLED_LIMIT = 0
export const SPECTATORS_ENABLED_LIMIT = 10

export const roomGameDefault: RoomGameParams = {
  mode: 'normal',
  spectators_limit: SPECTATORS_ENABLED_LIMIT,
  nominate_mode: 'players',
  tech_fouls: false,
  break_at_zero: true,
  lift_at_zero: true,
  lift_3x: true,
  first_shot_check: true,
  wink_knock: true,
  farewell_wills: true,
  music: true,
}

export function normalizeSpectatorsLimit(
  value: unknown,
): number {
  const parsed = Number(value ?? SPECTATORS_ENABLED_LIMIT)
  if (!Number.isFinite(parsed)) return SPECTATORS_ENABLED_LIMIT
  if (parsed <= 0) {
    return SPECTATORS_DISABLED_LIMIT
  }
  return SPECTATORS_ENABLED_LIMIT
}

export function normalizeRoomGameParams(
  raw: unknown,
): RoomGameParams {
  const merged: RoomGameParams = { ...roomGameDefault }
  if (!raw || typeof raw !== 'object') return merged

  const value = raw as LegacyRoomGameParams
  if (value.mode === 'normal' || value.mode === 'rating') merged.mode = value.mode
  if (value.nominate_mode === 'head' || value.nominate_mode === 'players') merged.nominate_mode = value.nominate_mode

  merged.spectators_limit = normalizeSpectatorsLimit(value.spectators_limit)

  if (typeof value.tech_fouls === 'boolean') merged.tech_fouls = value.tech_fouls
  if (typeof value.break_at_zero === 'boolean') merged.break_at_zero = value.break_at_zero
  const liftAtZero = typeof value.lift_at_zero === 'boolean'
    ? value.lift_at_zero
    : (typeof value.lift_2x_at_zero === 'boolean' ? value.lift_2x_at_zero : undefined)
  if (typeof liftAtZero === 'boolean') merged.lift_at_zero = liftAtZero
  if (typeof value.lift_3x === 'boolean') merged.lift_3x = value.lift_3x
  if (typeof value.first_shot_check === 'boolean') merged.first_shot_check = value.first_shot_check
  if (typeof value.wink_knock === 'boolean') merged.wink_knock = value.wink_knock
  if (typeof value.farewell_wills === 'boolean') merged.farewell_wills = value.farewell_wills
  if (typeof value.music === 'boolean') merged.music = value.music

  if (merged.mode === 'rating') {
    merged.spectators_limit = SPECTATORS_ENABLED_LIMIT
    merged.nominate_mode = 'players'
    merged.tech_fouls = true
    merged.break_at_zero = true
    merged.lift_at_zero = true
    merged.lift_3x = true
    merged.first_shot_check = true
    merged.wink_knock = true
    merged.farewell_wills = true
    merged.music = true
  }

  return merged
}
