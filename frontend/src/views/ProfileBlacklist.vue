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
        <button class="btn danger blacklist-remove" type="button" :disabled="blacklistRemoving[item.id]" @click="removeFromBlacklistProfile(item)">
          {{ blacklistRemoving[item.id] ? '...' : 'Удалить из ЧС' }}
        </button>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useFriendsStore, useUserStore, type BlacklistItem } from '@/store'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { formatLocalDateTime } from '@/services/datetime'

import iconDefaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'

const friendsStore = useFriendsStore()
const userStore = useUserStore()
const { subscriptionActive } = storeToRefs(userStore)
const blacklistLoading = ref(false)
const blacklistError = ref('')
const blacklistRemoving = reactive<Record<number, boolean>>({})
const blacklistItems = computed<BlacklistItem[]>(() => (
  Array.isArray(friendsStore.blacklist) ? friendsStore.blacklist : []
))

async function loadBlacklist(): Promise<void> {
  if (blacklistLoading.value) return
  blacklistLoading.value = true
  blacklistError.value = ''
  try {
    await friendsStore.fetchBlacklist()
  } catch (e: any) {
    const detail = String(e?.response?.data?.detail || '').trim()
    if (detail === 'subscription_required') {
      blacklistError.value = ''
      return
    }
    blacklistError.value = 'Не удалось загрузить черный список'
  } finally {
    blacklistLoading.value = false
  }
}

function blacklistAvatarKey(item: BlacklistItem): string {
  const name = String(item.avatar_name || '').trim()
  if (!name) return ''
  return name.startsWith('avatars/') ? name : `avatars/${name}`
}

async function removeFromBlacklistProfile(item: BlacklistItem): Promise<void> {
  const uid = Number(item?.id || 0)
  if (!Number.isFinite(uid) || uid <= 0 || blacklistRemoving[Math.trunc(uid)]) return
  const userLabel = item.username || `user${Math.trunc(uid)}`
  const ok = await confirmDialog({
    title: 'Удалить из Черного списка',
    text: `Вы уверены, что хотите удалить пользователя ${userLabel} из ЧС?`,
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  const id = Math.trunc(uid)
  blacklistRemoving[id] = true
  try {
    await friendsStore.removeFromBlacklist(id)
  } catch (e: any) {
    const detail = String(e?.response?.data?.detail || '').trim()
    if (detail === 'subscription_required') {
      void userStore.fetchMe().catch(() => {})
      void alertDialog('Черный список доступен только при активной подписке')
    } else {
      void alertDialog('Не удалось удалить пользователя из ЧС')
    }
  } finally {
    delete blacklistRemoving[id]
  }
}

watch(subscriptionActive, () => {
  void loadBlacklist()
})

onMounted(() => {
  friendsStore.ensureWS()
  void loadBlacklist()
})
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
