<template>
  <div class="profile-tab-block block-theme">
    <h3>Оформление профиля</h3>
    <div class="theme-row">
      <div class="theme-preview-grid">
        <div class="theme-preview-card" :style="themePreviewStyle">
          <img class="theme-preview-avatar" v-minio-img="{ key: me.avatar_name ? `avatars/${me.avatar_name}` : '', placeholder: iconDefaultAvatar, lazy: false, animated: true }" alt="avatar" />
          <div v-if="themePreviewIconSrcs.length" class="theme-preview-icons" aria-hidden="true">
            <img v-for="badgeSrc in themePreviewIconSrcs" :key="badgeSrc" class="theme-preview-icon" :src="badgeSrc" alt="" />
          </div>
          <span>{{ me.username || 'User' }}</span>
        </div>
      </div>

      <div class="theme-palette">
        <button v-for="item in profileThemeOptions" :key="item.key" class="theme-option" type="button" :class="{ active: selectedProfileThemeColor === item.key }"
                :style="themeOptionStyle(item.key)" :disabled="themeSaveBusy || isBanned" @click="emit('pickProfileTheme', item.key)">
        </button>
      </div>

      <div class="theme-icon-palette">
        <button v-for="item in profileThemeIconOptions" :key="item.key" @click="emit('pickProfileThemeIcon', item.key)"
                class="theme-icon-option" type="button" :class="{ active: selectedProfileThemeIcon === item.key }" :disabled="themeSaveBusy || isBanned || !item.available">
          <img v-if="themeIconSrc(item.key)" :src="themeIconSrc(item.key) || ''" alt="" aria-hidden="true" />
          <span v-else class="theme-icon-none" aria-hidden="true"></span>
        </button>
      </div>

      <button v-if="canEditProfileTheme" class="btn confirm" @click="emit('saveProfileTheme')" :disabled="themeSaveDisabled">
        <img class="btn-img" :src="iconSave" alt="save" />
        {{ themeSaveBusy ? '...' : 'Сохранить' }}
      </button>
      <button v-else type="button" class="btn subscription-btn" @click="emit('openSubscriptionModal')">
        Оформить подписку
      </button>
    </div>
    <p class="hint">{{ profileThemeMessageText }}</p>
  </div>
</template>

<script setup lang="ts">
import type { ProfileThemeColor } from '@/constants/profileThemes'
import type { ProfileThemeIcon } from '@/constants/profileIcons'

type ProfileThemeUser = {
  username: string
  avatar_name: string | null
}

type ProfileThemeOption = {
  key: ProfileThemeColor
}

type ProfileThemeIconOption = {
  key: ProfileThemeIcon
  available: boolean
}

defineProps<{
  me: ProfileThemeUser
  iconDefaultAvatar: string
  iconSave: string
  themePreviewStyle: Record<string, string>
  themePreviewIconSrcs: string[]
  profileThemeOptions: readonly ProfileThemeOption[]
  selectedProfileThemeColor: ProfileThemeColor
  themeOptionStyle: (color: ProfileThemeColor) => Record<string, string>
  profileThemeIconOptions: readonly ProfileThemeIconOption[]
  selectedProfileThemeIcon: ProfileThemeIcon | null
  themeIconSrc: (icon: ProfileThemeIcon) => string | null
  themeSaveBusy: boolean
  isBanned: boolean
  canEditProfileTheme: boolean
  themeSaveDisabled: boolean
  profileThemeMessageText: string
}>()

const emit = defineEmits<{
  (e: 'pickProfileTheme', color: ProfileThemeColor): void
  (e: 'pickProfileThemeIcon', icon: ProfileThemeIcon): void
  (e: 'saveProfileTheme'): void
  (e: 'openSubscriptionModal'): void
}>()
</script>

<style scoped lang="scss">
.block-theme {
  .theme-row {
    display: inline-flex;
    flex-direction: column;
    margin-bottom: 10px;
    .theme-preview-grid {
      display: grid;
      gap: 10px;
      .theme-preview-card {
        display: flex;
        align-items: center;
        padding: 10px 15px;
        gap: 5px;
        width: fit-content;
        border-radius: 15px;
        background-color: var(--user-theme-bg, rgba($neutral-900, 0.75));
        box-shadow: 3px 3px 5px rgba(black, 0.25);
        transition: background-color 0.25s ease-in-out;
        .theme-preview-avatar {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          object-fit: cover;
        }
        .theme-preview-icons {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          flex: 0 0 auto;
          .theme-preview-icon {
            width: 40px;
            height: 40px;
            object-fit: contain;
          }
        }
        span {
          min-width: 0;
          color: $neutral-100;
          font-size: 22px;
          font-family: Hauora-SemiBold;
          line-height: 1.3;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }
    }
    .theme-palette {
      display: inline-grid;
      grid-template-columns: repeat(10, 1fr);
      margin: 15px 0;
      padding: 10px;
      gap: 5px;
      background-color: $neutral-800;
      border-radius: 10px;
      box-shadow: 3px 3px 5px rgba(black, 0.25);
      .theme-option {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        border: 2px solid $neutral-800;
        border-radius: 999px;
        background-color: var(--user-theme-bg, $neutral-800);
        cursor: pointer;
        transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out;
        &:hover:enabled {
          border-color: rgba($neutral-white, 0.5);
        }
        &.active {
          border-color: $neutral-100;
        }
        &:disabled {
          cursor: not-allowed;
        }
      }
    }
    .theme-icon-palette {
      display: inline-grid;
      grid-template-columns: repeat(10, 1fr);
      margin-bottom: 15px;
      padding: 10px;
      gap: 5px;
      background-color: $neutral-800;
      border-radius: 10px;
      box-shadow: 3px 3px 5px rgba(black, 0.25);
      .theme-icon-option {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        border: 2px solid transparent;
        border-radius: 999px;
        background: none;
        cursor: pointer;
        transition: border-color 0.25s ease-in-out;
        img {
          width: 24px;
          height: 24px;
          object-fit: contain;
        }
        .theme-icon-none {
          width: 10px;
          height: 2px;
          border-radius: 2px;
          background-color: rgba($neutral-white, 0.75);
        }
        &:hover:enabled {
          border-color: rgba($neutral-white, 0.5);
        }
        &.active {
          border-color: $neutral-100;
        }
        &:disabled {
          cursor: not-allowed;
        }
      }
    }
  }
}
</style>
