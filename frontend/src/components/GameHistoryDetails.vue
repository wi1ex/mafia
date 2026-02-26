<template>
  <div class="history-details">
    <ul class="slots">
      <li v-for="slot in orderedSlots" :key="slot.slot" class="slot">
        <span class="slot-num">{{ slotLabel(slot.slot) }}</span>

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

        <span class="slot-points">{{ slot.points }}</span>
      </li>
    </ul>
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

interface GameHistorySlot {
  slot: number
  user_id?: number | null
  username?: string | null
  avatar_name?: string | null
  role?: GameHistoryRole | null
  points: number
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

function slotLabel(slot: number): string {
  return String(slot).padStart(2, '0')
}
</script>

<style scoped lang="scss">
.history-details {
  padding: 10px;
  border-top: 1px solid $lead;
}
.slots {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  gap: 6px;
  list-style: none;
}
.slot {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) 160px 50px;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-radius: 5px;
  background-color: $dark;
  color: $ashy;
}
.slot-num,
.slot-points {
  color: $fg;
  font-variant-numeric: tabular-nums;
}
.slot-player,
.slot-role {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  img {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    object-fit: cover;
  }
  span {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

@media (max-width: 128px) {
  .slot {
    grid-template-columns: 32px minmax(0, 1fr);
    grid-template-areas: 'num player' 'role points';
  }
  .slot-num {
    grid-area: num;
  }
  .slot-player {
    grid-area: player;
  }
  .slot-role {
    grid-area: role;
  }
  .slot-points {
    grid-area: points;
    justify-self: end;
  }
}

</style>
