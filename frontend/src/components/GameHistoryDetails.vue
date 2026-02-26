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
          <span>Баллы: {{ slot.points }}</span>
          <span>MMR: {{ slot.mmr }}</span>
        </div>

        <div v-if="slot.leave_day && slot.leave_reason" class="slot-leave">
          Круг {{ slot.leave_day }} · {{ leaveReasonLabel(slot.leave_reason) }}
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
}

const props = defineProps<{
  slots: GameHistorySlot[]
}>()

const orderedSlots = computed(() => {
  const copy = Array.isArray(props.slots) ? [...props.slots] : []
  return copy.sort((a, b) => a.slot - b.slot)
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
      .slot-leave {
        margin-top: auto;
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
