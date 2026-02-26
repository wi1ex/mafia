<template>
  <div class="history-details">
    <div class="slots-grid">
      <article v-for="slot in orderedSlots" :key="slot.slot" class="slot-card">
        <div class="slot-top">
          <span class="slot-num">Слот {{ slotLabel(slot.slot) }}</span>
        </div>

        <div class="slot-player">
          <img v-minio-img="{ key: slot.avatar_name ? `avatars/${slot.avatar_name}` : '', placeholder: defaultAvatar }" alt="avatar" />
          <span>{{ slot.username || 'Пусто' }}</span>
        </div>

        <div class="slot-role">
          <template v-if="slot.role">
            <img :src="roleIcon(slot.role)" alt="role" />
            <span>{{ roleLabel(slot.role) }}</span>
          </template>
          <span v-else>-</span>
        </div>

        <div class="slot-metrics">
          <span>Баллы: {{ formatMetric(slot.points) }} ({{ formatMetric(slot.mmr)}} MMR)</span>
        </div>

        <div v-if="slot.leave_day && slot.leave_reason" class="slot-leave">
          <span>{{ leaveMomentLabel(slot.leave_day, slot.leave_reason) }} - {{ leaveReasonLabel(slot.leave_reason) }}</span>
          <span v-if="slot.leave_reason === 'vote' && slot.voted_by_slots.length > 0"> {{ slot.voted_by_slots.join(', ') }}</span>
        </div>

        <div v-if="slot.best_move_slots.length > 0" class="slot-extra">
          Лучший ход: {{ slot.best_move_slots.join(', ') }}
        </div>

        <div v-if="slot.farewell.length > 0" class="slot-extra slot-extra-farewell">
          <span class="slot-extra-label">Завещание:</span>
          <span class="farewell-values">
            <template v-for="(pick, index) in slot.farewell" :key="`${slot.slot}-${pick.slot}-${pick.verdict}`">
              <span class="farewell-chip" :class="pick.verdict">{{ pick.slot }}</span>
            </template>
          </span>
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

type GameHistoryRole = 'citizen' | 'mafia' | 'don' | 'sheriff'
type LeaveReason = 'vote' | 'foul' | 'suicide' | 'night'
type FarewellVerdict = 'citizen' | 'mafia'

interface GameHistoryFarewellItem {
  slot: number
  verdict: FarewellVerdict
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
}

interface GameHistorySlotView extends Omit<GameHistorySlot, 'voted_by_slots' | 'best_move_slots' | 'farewell'> {
  voted_by_slots: number[]
  best_move_slots: number[]
  farewell: GameHistoryFarewellItem[]
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

const orderedSlots = computed<GameHistorySlotView[]>(() => {
  const copy = Array.isArray(props.slots) ? [...props.slots] : []
  return copy
    .map((slot) => ({
      ...slot,
      voted_by_slots: normalizeSeatList(slot.voted_by_slots),
      best_move_slots: normalizeSeatList(slot.best_move_slots),
      farewell: normalizeFarewell(slot.farewell),
    }))
    .sort((a, b) => a.slot - b.slot)
})

const roleIcons: Record<GameHistoryRole, string> = {
  citizen: iconRoleCitizen,
  mafia: iconRoleMafia,
  don: iconRoleDon,
  sheriff: iconRoleSheriff,
}

function roleIcon(role: GameHistoryRole): string {
  return roleIcons[role]
}

function roleLabel(role: GameHistoryRole): string {
  if (role === 'citizen') return 'Мирный'
  if (role === 'mafia') return 'Мафия'
  if (role === 'don') return 'Дон'
  return 'Шериф'
}

function leaveReasonLabel(reason: LeaveReason): string {
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

function slotLabel(slot: number): string {
  return String(slot).padStart(2, '0')
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
      flex-direction: column;
      gap: 10px;
      min-height: 120px;
      padding: 10px;
      border-radius: 5px;
      background-color: $dark;
      border: 1px solid rgba($grey, 0.25);
      .slot-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        .slot-num {
          color: $fg;
          font-size: 14px;
          font-variant-numeric: tabular-nums;
        }
      }
      .slot-player {
        display: flex;
        align-items: center;
        gap: 5px;
        img {
          width: 25px;
          height: 25px;
          border-radius: 50%;
          object-fit: cover;
        }
        span {
          height: 16px;
          color: $fg;
          font-size: 14px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }
      .slot-role {
        display: flex;
        align-items: center;
        gap: 5px;
        color: $ashy;
        font-size: 12px;
        img {
          width: 16px;
          height: 16px;
        }
      }
      .slot-metrics {
        display: flex;
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
            gap: 5px;
            .farewell-chip {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              min-width: 20px;
              height: 20px;
              border-radius: 5px;
              color: $fg;
              font-size: 12px;
              &.citizen {
                background-color: $red;
              }
              &.mafia {
                background-color: $black;
                border: 1px solid rgba($grey, 0.5);
              }
            }
          }
        }
      }
      .slot-leave {
        color: $orange;
        font-size: 12px;
        line-height: 1.2;
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
