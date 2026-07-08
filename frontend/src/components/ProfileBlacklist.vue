<template>
  <div class="profile-tab-block block-blacklist">
    <div class="blacklist-head">
      <h3>Черный список</h3>
    </div>
    <div class="blacklist-rules">
      <p>Игроки из ЧС не смогут отправлять Вам заявки в друзья и заявки на вход в Ваши приватные комнаты.</p>
      <p>При добавлении в ЧС текущая дружба, входящая заявка или исходящая заявка с этим игроком удаляется.</p>
      <p>Вы не будете получать уведомления, если игрок из ЧС отметит Вас в чате или поставит реакцию на Ваше сообщение.</p>
    </div>
    <div v-if="blacklistLoading" class="blacklist-empty">Загрузка…</div>
    <div v-else-if="blacklistError" class="blacklist-empty danger">{{ blacklistError }}</div>
    <div v-else-if="blacklistItems.length === 0" class="blacklist-empty">В ЧС пока никого нет</div>
    <div v-else class="blacklist-list">
      <article v-for="item in blacklistItems" :key="item.id" class="blacklist-card">
        <div class="blacklist-user">
          <img class="blacklist-avatar" v-minio-img="{ key: blacklistAvatarKey(item), placeholder: iconDefaultAvatar, lazy: true, animated: true }" alt="avatar" />
          <div class="blacklist-main">
            <span>{{ item.username || `user${item.id}` }}</span>
            <small>Добавлен: {{ formatLocalDateTime(item.created_at || '') }}</small>
          </div>
        </div>
        <button class="btn danger blacklist-remove" type="button" :disabled="blacklistRemoving[item.id]" @click="emit('removeFromBlacklist', item)">
          {{ blacklistRemoving[item.id] ? '...' : 'Удалить из ЧС' }}
        </button>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BlacklistItem } from '@/store'

defineProps<{
  blacklistLoading: boolean
  blacklistError: string
  blacklistItems: BlacklistItem[]
  blacklistRemoving: Record<number, boolean>
  iconDefaultAvatar: string
  blacklistAvatarKey: (item: BlacklistItem) => string
  formatLocalDateTime: (value: string, options?: Intl.DateTimeFormatOptions) => string
}>()

const emit = defineEmits<{
  (e: 'removeFromBlacklist', item: BlacklistItem): void
}>()
</script>

<style scoped lang="scss">
.block-blacklist {
  .blacklist-head {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
  }
  .blacklist-rules {
    display: grid;
    gap: 6px;
    margin-top: 10px;
    padding: 12px;
    border: 3px solid $neutral-700;
    border-radius: 5px;
    background-color: rgba(black, 0.08);
    p {
      margin: 0;
      color: $neutral-300;
      font-size: 14px;
      line-height: 1.35;
    }
  }
  .blacklist-empty {
    padding: 20px 0;
    color: $neutral-300;
    &.danger {
      color: $red-500;
    }
  }
  .blacklist-list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 10px;
    margin-top: 10px;
    .blacklist-card {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px;
      border: 3px solid $neutral-700;
      border-radius: 5px;
      background-color: rgba(black, 0.12);
      .blacklist-user {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
        .blacklist-avatar {
          flex: 0 0 auto;
          width: 48px;
          height: 48px;
          border-radius: 50%;
          object-fit: cover;
          background-color: black;
        }
        .blacklist-main {
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 0;
          span {
            color: $neutral-100;
            font-family: Hauora-SemiBold;
            font-size: 16px;
            line-height: 1.2;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          small {
            color: $neutral-300;
            font-size: 12px;
            line-height: 1.2;
          }
        }
      }
      .blacklist-remove {
        flex: 0 0 auto;
        max-width: none;
        min-width: 130px;
      }
    }
  }
}
</style>
