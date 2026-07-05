<template>
  <div class="history-details">
    <div class="slots-grid">
      <article v-for="slot in orderedSlots" :key="slot.slot" :class="['slot-card', slotCardRoleClass(slot.role)]">
        <div class="slot-top">
          <span class="slot-num-label">{{ slotLabel(slot.slot) }}</span>
          <button class="slot-player" type="button" :disabled="!canOpenSlotMiniProfile(slot)" @click.stop="openSlotMiniProfile(slot)">
            <img v-minio-img="{ key: slot.avatar_name ? `avatars/${slot.avatar_name}` : '', placeholder: defaultAvatar }" alt="avatar" />
            <span>{{ slot.username || 'Пусто' }}</span>
          </button>
        </div>

        <img v-if="slot.role" class="slot-role-icon" :src="roleIcon(slot.role)" alt="role" />

        <div v-if="slot.leave_day && slot.leave_reason" class="slot-leave">
          <span>{{ leaveMomentLabel(slot.leave_day, slot.leave_reason) }}</span>
          <img class="leave-reason-icon" :src="displayLeaveReasonIcon(slot)" :alt="displayLeaveReasonAlt(slot)" />
          <img v-if="isVoteThenFoul(slot)" class="leave-reason-icon leave-reason-icon-extra" :src="iconLeaveFoul" alt="Удален по фолам после голосования" />
          <span v-if="slot.leave_reason === 'foul' && slot.leave_ppk" class="ppk-mark">ППК</span>
          <span v-if="showVoteValues(slot)" class="vote-values">
            <template v-for="voterSlot in slot.voted_by_slots" :key="`${slot.slot}-vote-${voterSlot}`">
              <span class="vote-chip">{{ voterSlot }}</span>
            </template>
          </span>
        </div>

        <div v-if="slot.best_move_slots.length > 0" class="slot-extra slot-extra-best-move">
          <span class="slot-extra-label">Лучший ход:</span>
          <span class="best-move-values">
            <template v-for="targetSlot in slot.best_move_slots" :key="`${slot.slot}-best-move-${targetSlot}`">
              <span class="best-move-chip">{{ targetSlot }}</span>
            </template>
          </span>
        </div>

        <div v-if="slot.farewell.length > 0" class="slot-extra slot-extra-farewell">
          <span class="slot-extra-label">Завещание:</span>
          <span class="farewell-values">
            <template v-for="pick in slot.farewell" :key="`${slot.slot}-${pick.slot}-${pick.verdict}`">
              <span class="farewell-chip" :class="pick.verdict">{{ pick.slot }}</span>
            </template>
          </span>
        </div>

        <div v-if="slot.night_checks.length > 0" class="slot-extra slot-extra-night-checks">
          <span class="slot-extra-label">Проверки:</span>
          <span class="night-check-values">
            <template v-for="check in slot.night_checks" :key="`${slot.slot}-check-${check.slot}-${check.verdict}`">
              <span class="night-check-chip" :class="check.verdict">{{ check.slot }}</span>
            </template>
          </span>
        </div>

        <div class="slot-metrics">
          <span>Баллы: {{ formatMetric(slot.points) }} ({{ formatMetric(slot.mmr)}} MMR)</span>
        </div>
      </article>
    </div>

    <MiniProfile
      v-model:open="miniProfileOpen"
      :user-id="miniProfileUserId"
      :initial-profile="miniProfileInitial"
      :stats-url="miniProfileStatsUrl"
      :show-stats-button="true"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import { canOpenMiniProfileTarget, normalizeMiniProfileRole, normalizeMiniProfileUserId } from '@/services/miniProfile'
import { useUserStore } from '@/store'
import MiniProfile from '@/components/MiniProfile.vue'
import defaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconRoleCitizen from '@/assets/svg/iconRoleCitizen.svg'
import iconRoleMafia from '@/assets/svg/iconRoleMafia.svg'
import iconRoleDon from '@/assets/svg/iconRoleDon.svg'
import iconRoleSheriff from '@/assets/svg/iconRoleSheriff.svg'
import iconLeaveVote from '@/assets/svg/iconLike.svg'
import iconLeaveFoul from '@/assets/svg/iconJudgeHummer.svg'
import iconLeaveNight from '@/assets/svg/iconKill.svg'
import iconLeaveSuicide from '@/assets/svg/iconDead.svg'

type GameHistoryRole = 'citizen' | 'mafia' | 'don' | 'sheriff'
type LeaveReason = 'vote' | 'foul' | 'suicide' | 'night'
type FarewellVerdict = 'citizen' | 'mafia'
type NightCheckVerdict = 'citizen' | 'mafia' | 'sheriff'

interface GameHistoryFarewellItem {
  slot: number
  verdict: FarewellVerdict
}

interface GameHistoryNightCheckItem {
  slot: number
  verdict: NightCheckVerdict
}

interface GameHistorySlot {
  slot: number
  user_id?: number | null
  username?: string | null
  avatar_name?: string | null
  profile_role?: string | null
  deleted?: boolean | null
  role?: GameHistoryRole | null
  points: number
  mmr: number
  leave_day?: number | null
  leave_reason?: LeaveReason | null
  leave_ppk?: boolean | null
  voted_by_slots?: number[] | null
  best_move_slots?: number[] | null
  farewell?: GameHistoryFarewellItem[] | null
  night_checks?: GameHistoryNightCheckItem[] | null
}

interface GameHistorySlotView extends Omit<GameHistorySlot, 'voted_by_slots' | 'best_move_slots' | 'farewell' | 'night_checks'> {
  voted_by_slots: number[]
  best_move_slots: number[]
  farewell: GameHistoryFarewellItem[]
  night_checks: GameHistoryNightCheckItem[]
}

type GameHistoryMiniProfileInitial = {
  id: number
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  deleted?: boolean | null
}

const props = defineProps<{
  slots: GameHistorySlot[]
}>()

const userStore = useUserStore()
const miniProfileOpen = ref(false)
const miniProfileUserId = ref<number | null>(null)
const miniProfileInitial = ref<GameHistoryMiniProfileInitial | null>(null)
const viewerUserId = computed(() => normalizeMiniProfileUserId(userStore.user?.id))
const viewerRole = computed(() => normalizeMiniProfileRole(userStore.user?.role))
const miniProfileStatsUrl = computed(() => {
  const uid = Number(miniProfileUserId.value || 0)
  if (!Number.isFinite(uid) || uid <= 0) return null
  if (viewerRole.value === 'admin') return `/admin/users/${uid}/stats`
  if (viewerRole.value === 'moder') return `/moderation/users/${uid}/stats`
  return null
})

function normalizeSeatList(raw: unknown): number[] {
  if (!Array.isArray(raw)) return []
  const out: number[] = []
  for (const item of raw) {
    const seat = Number(item)
    if (!Number.isFinite(seat)) continue
    const seatNum = Math.trunc(seat)
    if (seatNum <= 0 || seatNum > 10 || out.includes(seatNum)) continue
    out.push(seatNum)
  }
  return out.sort((a, b) => a - b)
}

function normalizeFarewell(raw: unknown): GameHistoryFarewellItem[] {
  if (!Array.isArray(raw)) return []
  const out: GameHistoryFarewellItem[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const slotRaw = (item as any).slot
    const verdictRaw = String((item as any).verdict || '').trim().toLowerCase()
    if (verdictRaw !== 'citizen' && verdictRaw !== 'mafia') continue
    const seat = Number(slotRaw)
    if (!Number.isFinite(seat)) continue
    const seatNum = Math.trunc(seat)
    if (seatNum <= 0 || seatNum > 10 || out.some((pick) => pick.slot === seatNum)) continue
    out.push({ slot: seatNum, verdict: verdictRaw })
  }
  return out.sort((a, b) => a.slot - b.slot)
}

function normalizeNightChecks(raw: unknown): GameHistoryNightCheckItem[] {
  if (!Array.isArray(raw)) return []
  const out: GameHistoryNightCheckItem[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const slotRaw = (item as any).slot
    const verdictRaw = String((item as any).verdict || '').trim().toLowerCase()
    if (verdictRaw !== 'citizen' && verdictRaw !== 'mafia' && verdictRaw !== 'sheriff') continue
    const seat = Number(slotRaw)
    if (!Number.isFinite(seat)) continue
    const seatNum = Math.trunc(seat)
    if (seatNum <= 0 || seatNum > 10 || out.some((pick) => pick.slot === seatNum)) continue
    out.push({ slot: seatNum, verdict: verdictRaw })
  }
  return out
}

const orderedSlots = computed<GameHistorySlotView[]>(() => {
  const copy = Array.isArray(props.slots) ? [...props.slots] : []
  return copy
    .map((slot) => ({
      ...slot,
      voted_by_slots: normalizeSeatList(slot.voted_by_slots),
      best_move_slots: normalizeSeatList(slot.best_move_slots),
      farewell: normalizeFarewell(slot.farewell),
      night_checks: normalizeNightChecks(slot.night_checks),
    }))
    .sort((a, b) => a.slot - b.slot)
})

function canOpenSlotMiniProfile(slot: GameHistorySlotView): boolean {
  return canOpenMiniProfileTarget({
    targetId: slot.user_id,
    viewerId: viewerUserId.value,
    viewerRole: viewerRole.value,
    targetRole: slot.profile_role,
    targetDeletedAt: slot.deleted,
  })
}

function openSlotMiniProfile(slot: GameHistorySlotView): void {
  if (!canOpenSlotMiniProfile(slot)) return
  const uid = normalizeMiniProfileUserId(slot.user_id)
  if (uid <= 0) return
  miniProfileUserId.value = uid
  miniProfileInitial.value = {
    id: uid,
    username: slot.username || null,
    avatar_name: slot.avatar_name || null,
    role: slot.profile_role || null,
    deleted: Boolean(slot.deleted),
  }
  miniProfileOpen.value = true
}

const roleIcons: Record<GameHistoryRole, string> = {
  citizen: iconRoleCitizen,
  mafia: iconRoleMafia,
  don: iconRoleDon,
  sheriff: iconRoleSheriff,
}
const leaveReasonIcons: Record<LeaveReason, string> = {
  vote: iconLeaveVote,
  foul: iconLeaveFoul,
  suicide: iconLeaveSuicide,
  night: iconLeaveNight,
}

function slotCardRoleClass(role: GameHistoryRole | null | undefined): string {
  if (!role) return ''
  return `role-${role}`
}

function roleIcon(role: GameHistoryRole): string {
  return roleIcons[role]
}

function slotLabel(slot: number): string {
  const normalized = Math.trunc(Number(slot))
  if (normalized === 11) return 'В'
  if (normalized >= 1 && normalized <= 10) return String(normalized)
  return ''
}

function leaveReasonIcon(reason: LeaveReason): string {
  return leaveReasonIcons[reason]
}

function leaveReasonAlt(reason: LeaveReason): string {
  if (reason === 'vote') return 'Заголосован'
  if (reason === 'foul') return 'Удален по фолам'
  if (reason === 'suicide') return 'Суицид'
  return 'Убит'
}

function isVoteThenFoul(slot: GameHistorySlotView): boolean {
  return slot.leave_reason === 'foul' && slot.voted_by_slots.length > 0
}

function showVoteValues(slot: GameHistorySlotView): boolean {
  return slot.voted_by_slots.length > 0 && (slot.leave_reason === 'vote' || isVoteThenFoul(slot))
}

function displayLeaveReasonIcon(slot: GameHistorySlotView): string {
  if (isVoteThenFoul(slot)) return iconLeaveVote
  return slot.leave_reason ? leaveReasonIcon(slot.leave_reason) : iconLeaveVote
}

function displayLeaveReasonAlt(slot: GameHistorySlotView): string {
  if (isVoteThenFoul(slot)) return 'Заголосован, затем удален по фолам'
  return slot.leave_reason ? leaveReasonAlt(slot.leave_reason) : ''
}

function leaveMomentLabel(day: number, reason: LeaveReason): string {
  const normalizedDay = Math.max(0, Math.trunc(day || 0))
  if (reason === 'night') {
    return `Ночь ${Math.max(0, normalizedDay - 1)}`
  }
  return `День ${normalizedDay}`
}

function formatMetric(value: number): string {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  const normalized = Math.trunc(num)
  return normalized === 0 ? '-' : String(normalized)
}
</script>

<style scoped lang="scss">
.history-details {
  padding: 10px;
  border-top: 1px solid $neutral-700;
  .slots-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 10px;
    .slot-card {
      display: flex;
      position: relative;
      flex-direction: column;
      padding: 10px;
      gap: 5px;
      min-height: 130px;
      border-radius: 5px;
      background-color: $neutral-900;
      border: 1px solid rgba($neutral-500, 0.25);
      &.role-citizen {
        background-color: rgba($red-500, 0.2);
      }
      &.role-sheriff {
        background-color: rgba($yellow-500, 0.2);
      }
      &.role-mafia {
        background-color: $neutral-900;
      }
      &.role-don {
        background-color: $neutral-black;
      }
      .slot-role-icon {
        position: absolute;
        top: 10px;
        right: 10px;
        width: 25px;
        height: 25px;
        z-index: 1;
      }
      .slot-top {
        display: flex;
        align-items: center;
        gap: 5px;
        .slot-num-label {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          flex: 0 0 auto;
          width: 25px;
          height: 25px;
          border-radius: 5px;
          background-color: $neutral-700;
          color: $neutral-100;
          font-family: Hauora-SemiBold;
          font-size: 14px;
          line-height: 18px;
        }
        .slot-player {
          display: flex;
          align-items: center;
          padding: 0;
          gap: 5px;
          min-width: 0;
          border: none;
          background: transparent;
          color: inherit;
          font: inherit;
          text-align: left;
          &:not(:disabled) {
            cursor: pointer;
          }
          &:disabled {
            cursor: default;
            opacity: 1;
          }
          img {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            object-fit: cover;
          }
          span {
            width: 105px;
            height: 14px;
            color: $neutral-100;
            font-size: 12px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
        }
      }
      .slot-metrics {
        display: flex;
        position: absolute;
        left: 10px;
        bottom: 10px;
        flex-direction: column;
        gap: 5px;
        color: $neutral-300;
        font-size: 12px;
        font-variant-numeric: tabular-nums;
      }
      .slot-extra {
        color: $neutral-300;
        font-size: 12px;
        line-height: 1.2;
        &.slot-extra-best-move {
          display: flex;
          align-items: center;
          gap: 5px;
          .slot-extra-label {
            color: $neutral-300;
          }
          .best-move-values {
            display: inline-flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 3px;
            .best-move-chip {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              min-width: 16px;
              height: 16px;
              border-radius: 5px;
              background-color: $orange-500;
              color: $neutral-black;
              font-size: 10px;
            }
          }
        }
        &.slot-extra-farewell {
          display: flex;
          align-items: center;
          gap: 5px;
          .slot-extra-label {
            color: $neutral-300;
          }
          .farewell-values {
            display: inline-flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 3px;
            .farewell-chip {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              min-width: 16px;
              height: 16px;
              border-radius: 5px;
              color: $neutral-100;
              font-size: 10px;
              &.citizen {
                background-color: $red-500;
              }
              &.mafia {
                background-color: black;
              }
            }
          }
        }
        &.slot-extra-night-checks {
          display: flex;
          align-items: center;
          gap: 5px;
          .slot-extra-label {
            color: $neutral-300;
          }
          .night-check-values {
            display: inline-flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 3px;
            .night-check-chip {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              min-width: 16px;
              height: 16px;
              border-radius: 5px;
              color: $neutral-100;
              font-size: 10px;
              &.citizen {
                background-color: $red-500;
              }
              &.sheriff {
                background-color: $yellow-500;
                color: $neutral-900;
              }
              &.mafia {
                background-color: black;
              }
            }
          }
        }
      }
      .slot-leave {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        max-width: calc(100% - 70px);
        color: $orange-500;
        font-size: 12px;
        line-height: 1.2;
        span {
          min-width: fit-content;
        }
        .ppk-mark {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 3px 5px;
          border-radius: 5px;
          background-color: rgba($red-500, 0.75);
          color: $neutral-white;
          font-size: 10px;
          font-family: Hauora-SemiBold;
          line-height: 1.1;
        }
        .vote-values {
          display: inline-flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 3px;
          .vote-chip {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 16px;
            height: 16px;
            border-radius: 5px;
            background-color: $neutral-300;
            color: $neutral-black;
            font-size: 10px;
          }
        }
        .leave-reason-icon {
          width: 20px;
          height: 20px;
          object-fit: contain;
          &.leave-reason-icon-extra {
            width: 20px;
            height: 20px;
          }
        }
      }
    }
  }
}

</style>
