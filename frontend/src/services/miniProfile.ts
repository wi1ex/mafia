export type MiniProfileOpenGuardInput = {
  targetId: unknown
  viewerId?: unknown
  targetRole?: unknown
  targetDeletedAt?: unknown
  allowDeleted?: boolean
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

export function canOpenMiniProfileTarget(input: MiniProfileOpenGuardInput): boolean {
  const targetId = normalizeMiniProfileUserId(input.targetId)
  const viewerId = normalizeMiniProfileUserId(input.viewerId)
  if (targetId <= 0) return false
  if (viewerId > 0 && targetId === viewerId) return false
  if (isMiniProfileAdminTargetRole(input.targetRole)) return false
  return !(!input.allowDeleted && hasMiniProfileDeletedAt(input.targetDeletedAt))
}
