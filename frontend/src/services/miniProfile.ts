import { useSettingsStore } from '@/store/modules/setting'
import { useUserStore } from '@/store/modules/user'

export type MiniProfileOpenGuardInput = {
  targetId: unknown
  viewerId?: unknown
  viewerRole?: unknown
  targetRole?: unknown
  targetDeletedAt?: unknown
  allowDeleted?: boolean
  verificationRestrictions?: unknown
  viewerTelegramVerified?: unknown
}

export function normalizeMiniProfileUserId(value: unknown): number {
  const userId = Number(value ?? 0)
  if (!Number.isFinite(userId) || userId <= 0) return 0
  return Math.trunc(userId)
}

export function normalizeMiniProfileRole(value: unknown): string {
  return typeof value === 'string' ? value.trim().toLowerCase() : ''
}

export function isMiniProfileAdminTargetRole(value: unknown): boolean {
  return normalizeMiniProfileRole(value) === 'admin'
}

export function hasMiniProfileDeletedAt(value: unknown): boolean {
  if (value == null) return false
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') return value.trim() !== ''
  return true
}

export function isMiniProfilePrivilegedViewer(role: unknown, adminMode = false): boolean {
  const normalizedRole = normalizeMiniProfileRole(role)
  return adminMode || normalizedRole === 'admin' || normalizedRole === 'moder'
}

function isViewerBlockedByVerification(input: MiniProfileOpenGuardInput): boolean {
  if ('verificationRestrictions' in input || 'viewerTelegramVerified' in input) {
    return Boolean(input.verificationRestrictions) && !Boolean(input.viewerTelegramVerified)
  }

  try {
    const settings = useSettingsStore()
    const user = useUserStore()
    return Boolean(settings.verificationRestrictions && !user.telegramVerified)
  } catch {
    return false
  }
}

export function canOpenMiniProfileTarget(input: MiniProfileOpenGuardInput): boolean {
  const targetId = normalizeMiniProfileUserId(input.targetId)
  if (targetId <= 0) return false
  if (isViewerBlockedByVerification(input)) return false
  if (isMiniProfileAdminTargetRole(input.targetRole) && normalizeMiniProfileRole(input.viewerRole) !== 'admin') return false
  return !(!input.allowDeleted && hasMiniProfileDeletedAt(input.targetDeletedAt))
}
