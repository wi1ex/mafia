<template>
  <div class="history-details">
    <div class="slots-grid">
      <article v-for="slot in orderedSlots" :key="slot.slot" :class="['slot-card', slotCardRoleClass(slot.role)]">
        <div class="slot-top">
          <img class="slot-num-icon" :src="slotIcon(slot.slot)" :alt="`slot-${slot.slot}`" />
          <div class="slot-player">
            <img v-minio-img="{ key: slot.avatar_name ? `avatars/${slot.avatar_name}` : '', placeholder: defaultAvatar }" alt="avatar" />
            <span>{{ slot.username || 'Пусто' }}</span>
          </div>
        </div>

        <img v-if="slot.role" class="slot-role-icon" :src="roleIcon(slot.role)" alt="role" />

        <div v-if="slot.leave_day && slot.leave_reason" class="slot-leave">
          <span>{{ leaveMomentLabel(slot.leave_day, slot.leave_reason) }}</span>
          <img class="leave-reason-icon" :src="leaveReasonIcon(slot.leave_reason)" :alt="leaveReasonAlt(slot.leave_reason)" :title="leaveReasonAlt(slot.leave_reason)" />
          <span v-if="slot.leave_reason === 'vote' && slot.voted_by_slots.length > 0" class="vote-values">
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
            <template v-for="(pick, index) in slot.farewell" :key="`${slot.slot}-${pick.slot}-${pick.verdict}`">
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
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconRoleCitizen from '@/assets/images/roleCitizen.png'
import iconRoleMafia from '@/assets/images/roleMafia.png'
import iconRoleDon from '@/assets/images/roleDon.png'
import iconRoleSheriff from '@/assets/images/roleSheriff.png'
import iconLeaveVote from '@/assets/svg/likeWhite.svg'
import iconLeaveFoul from '@/assets/svg/judge.svg'
import iconLeaveNight from '@/assets/svg/killWhite.svg'
import iconLeaveSuicide from '@/assets/svg/deadPlayer.svg'

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
  role?: GameHistoryRole | null
  points: number
  mmr: number
  leave_day?: number | null
  leave_reason?: LeaveReason | null
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

const props = defineProps<{
  slots: GameHistorySlot[]
}>()

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

const roleIcons: Record<GameHistoryRole, string> = {
  citizen: iconRoleCitizen,
  mafia: iconRoleMafia,
  don: iconRoleDon,
  sheriff: iconRoleSheriff,
}
const slotIcons: Record<number, string> = {
  1: iconSlot1,
  2: iconSlot2,
  3: iconSlot3,
  4: iconSlot4,
  5: iconSlot5,
  6: iconSlot6,
  7: iconSlot7,
  8: iconSlot8,
  9: iconSlot9,
  10: iconSlot10,
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

function slotIcon(slot: number): string {
  return slotIcons[slot] || iconSlot1
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
  border-top: 1px solid $lead;
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
      min-height: 135px;
      border-radius: 5px;
      background-color: $dark;
      border: 1px solid rgba($grey, 0.25);
      &.role-citizen {
        background-color: rgba($red, 0.2);
      }
      &.role-sheriff {
        background-color: rgba($yellow, 0.2);
      }
      &.role-mafia {
        background-color: $dark;
      }
      &.role-don {
        background-color: $bg;
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
        .slot-num-icon {
          width: 25px;
          height: 25px;
          object-fit: contain;
        }
        .slot-player {
          display: flex;
          align-items: center;
          gap: 5px;
          img {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            object-fit: cover;
          }
          span {
            width: 110px;
            height: 14px;
            color: $fg;
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
        color: $ashy;
        font-size: 12px;
        font-variant-numeric: tabular-nums;
      }
      .slot-extra {
        color: $ashy;
        font-size: 12px;
        line-height: 1.2;
        &.slot-extra-best-move {
          display: flex;
          align-items: center;
          gap: 5px;
          .slot-extra-label {
            color: $ashy;
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
              background-color: $orange;
              color: $bg;
              font-size: 10px;
            }
          }
        }
        &.slot-extra-farewell {
          display: flex;
          align-items: center;
          gap: 5px;
          .slot-extra-label {
            color: $ashy;
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
              color: $fg;
              font-size: 10px;
              &.citizen {
                background-color: $red;
              }
              &.mafia {
                background-color: $black;
              }
            }
          }
        }
        &.slot-extra-night-checks {
          display: flex;
          align-items: center;
          gap: 5px;
          .slot-extra-label {
            color: $ashy;
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
              color: $fg;
              font-size: 10px;
              &.citizen {
                background-color: $red;
              }
              &.sheriff {
                background-color: $yellow;
                color: $dark;
              }
              &.mafia {
                background-color: $black;
              }
            }
          }
        }
      }
      .slot-leave {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        color: $orange;
        font-size: 12px;
        line-height: 1.2;
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
            background-color: $ashy;
            color: $bg;
            font-size: 10px;
          }
        }
        .leave-reason-icon {
          width: 20px;
          height: 20px;
          object-fit: contain;
        }
      }
    }
  }
}

@media (max-width: 1280px) {
  .history-details {
    .slots-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
}
</style>
