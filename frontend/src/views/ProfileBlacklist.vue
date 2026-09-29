<template>
  <section class="block-blacklist">
    <div class="blacklist-head">
      <div>
        <span class="section-title">Черный список</span>
        <span class="section-hint">Пользователи, от которых вы не хотите получать заявки и уведомления</span>
      </div>
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
        <button class="blacklist-user" type="button" :disabled="!canOpenMiniProfile(item)" :aria-label="`Открыть профиль ${item.username || `user${item.id}`}`" @click="openMiniProfile(item)">
          <img class="blacklist-avatar" v-minio-img="{ key: blacklistAvatarKey(item), placeholder: iconDefaultAvatar, lazy: true, animated: true }" alt="avatar" />
          <div class="blacklist-main">
            <span>{{ item.username || `user${item.id}` }}</span>
            <small>Добавлен: {{ formatLocalDateTime(item.created_at || '') }}</small>
          </div>
        </button>
        <UiButton
          class="blacklist-remove"
          variant="red"
          size="middle"
          :icon="iconDelete"
          :text="blacklistRemoving[item.id] ? '...' : 'Удалить из ЧС'"
          :disabled="blacklistRemoving[item.id]"
          @click="removeFromBlacklistProfile(item)"
        />
      </article>
    </div>
  </section>
  <MiniProfile
    v-model:open="miniProfileOpen"
    :user-id="miniProfileUserId"
    :initial-profile="miniProfileInitial"
    :show-stats-button="true"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useFriendsStore, useUserStore, type BlacklistItem } from '@/store'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { formatLocalDateTime } from '@/services/datetime'
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId } from '@/services/miniProfile'
import UiButton from '@/components/UiButton.vue'
import MiniProfile from '@/views/MiniProfile.vue'

import iconDefaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconDelete from '@/assets/svg/iconDelete.svg'

const friendsStore = useFriendsStore()
const userStore = useUserStore()
const { subscriptionActive } = storeToRefs(userStore)
const blacklistLoading = ref(false)
const blacklistError = ref('')
const blacklistRemoving = reactive<Record<number, boolean>>({})
const miniProfileOpen = ref(false)
const miniProfileUserId = ref<number | null>(null)
const miniProfileInitial = ref<BlacklistItem | null>(null)
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

function canOpenMiniProfile(item: BlacklistItem): boolean {
  return canOpenMiniProfileTarget({
    targetId: item.id,
    viewerId: userStore.user?.id,
    viewerRole: userStore.user?.role,
    targetRole: item.role,
  })
}

function openMiniProfile(item: BlacklistItem): void {
  if (!canOpenMiniProfile(item)) return
  miniProfileUserId.value = normalizeMiniProfileUserId(item.id)
  miniProfileInitial.value = item
  miniProfileOpen.value = true
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
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  padding: 24px;
  border-radius: 24px;
  background-color: $soft-purple-900;
  .section-title,
  .section-hint {
    display: block;
  }
  .section-title {
    color: $neutral-white;
    font-family: Involve-Medium;
    font-size: 24px;
    line-height: 26px;
  }
  .section-hint {
    margin-top: 12px;
    color: $neutral-300;
    font-size: 14px;
  }
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
    border: 1px solid $soft-purple-800;
    border-radius: 20px;
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
      border: 1px solid $soft-purple-800;
      border-radius: 20px;
      background-color: $soft-purple-800;
      .blacklist-user {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
        padding: 0;
        border: none;
        border-radius: 12px;
        background: transparent;
        text-align: left;
        cursor: pointer;
        &:disabled {
          cursor: default;
        }
        &:focus-visible {
          outline: 2px solid $green-500;
          outline-offset: 4px;
        }
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
