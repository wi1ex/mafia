<template>
  <div class="profile-tab-block block-account">
    <h3>Аккаунт</h3>
    <div class="verify-row">
      <p class="hint text">Дата регистрации: {{ registrationDateLabel }}</p>
      <UiSwitch
        class="profile-switch"
        :model-value="tgInvitesEnabled"
        label="Уведомления в TG о приглашениях в комнату"
        off-label="Запретить"
        on-label="Разрешить"
        :width="200"
        :disabled="tgInvitesTogglePending || !telegramVerified"
        @update:modelValue="emit('toggleTgInvites', $event)" />
      <button v-if="telegramVerified" class="btn danger" @click="emit('unlinkTelegram')" :disabled="unlinkTgBusy">
        {{ unlinkTgBusy ? '...' : 'Отвязать TG-аккаунт' }}
      </button>
      <a v-else-if="botName" class="btn confirm" :href="botLink" target="_blank" rel="noopener noreferrer">
        Пройти верификацию
      </a>
      <p v-if="telegramVerified" class="hint">Если отвязать TG-аккаунт верификация будет снята и вход в комнаты будет ограничен</p>
      <p v-else class="hint">В чате с ботом сначала введите никнейм, затем пароль. После успешной верификации ограничения на вход в комнаты будут сняты</p>
      <button class="btn danger" @click="emit('deleteAccount')" :disabled="deleteBusy || isDeleteAccountForbiddenSelf">
        {{ deleteBusy ? '...' : 'Удалить аккаунт' }}
      </button>
      <p class="hint red">Удаление произойдет навсегда без возможности восстановления</p>

      <div v-if="me.has_password" class="password-row">
        <p class="hint text">Пароль</p>
        <p v-if="passwordTemp" class="hint warn">У вас временный пароль — рекомендуем изменить его</p>
        <UiInput class="profile-input" id="profile-pass-current" v-model="pwd.current" type="password" autocomplete="current-password" minlength="8" maxlength="32" label="Текущий пароль"
          :invalid="currentPasswordInvalid" :aria-invalid="currentPasswordInvalid" aria-describedby="profile-pass-current-hint">
          <template #meta>
            <span id="profile-pass-current-hint">{{ pwd.current.length }}/{{ passwordMax }}</span>
          </template>
        </UiInput>
        <UiInput class="profile-input" id="profile-pass-new" v-model="pwd.next" type="password" autocomplete="new-password" minlength="8" maxlength="32" label="Новый пароль"
          :invalid="newPasswordInvalid" :aria-invalid="newPasswordInvalid" aria-describedby="profile-pass-new-hint">
          <template #meta>
            <span id="profile-pass-new-hint">{{ pwd.next.length }}/{{ passwordMax }}</span>
          </template>
        </UiInput>
        <UiInput class="profile-input" id="profile-pass-confirm" v-model="pwd.confirm" type="password" autocomplete="new-password" minlength="8" maxlength="32" label="Повторите пароль"
          :invalid="confirmPasswordInvalid" :aria-invalid="confirmPasswordInvalid" aria-describedby="profile-pass-confirm-hint">
          <template #meta>
            <span id="profile-pass-confirm-hint">{{ pwd.confirm.length }}/{{ passwordMax }}</span>
          </template>
        </UiInput>
        <button class="btn confirm" @click="emit('changePassword')" :disabled="pwdBusy || !canChangePassword">
          {{ pwdBusy ? '...' : 'Сменить пароль' }}
        </button>
        <p class="hint">
          Сбросить пароль можно через
          <a v-if="botName" :href="botLink" target="_blank" rel="noopener noreferrer">TG-бота</a>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import UiInput from '@/components/UiInput.vue'
import UiSwitch from '@/components/UiSwitch.vue'

type ProfileAccountUser = {
  has_password: boolean
}

type PasswordForm = {
  current: string
  next: string
  confirm: string
}

defineProps<{
  me: ProfileAccountUser
  registrationDateLabel: string
  tgInvitesEnabled: boolean
  tgInvitesTogglePending: boolean
  telegramVerified: boolean
  unlinkTgBusy: boolean
  botName: string
  botLink: string
  deleteBusy: boolean
  isDeleteAccountForbiddenSelf: boolean
  passwordTemp: boolean
  pwd: PasswordForm
  passwordMax: number
  currentPasswordInvalid: boolean
  newPasswordInvalid: boolean
  confirmPasswordInvalid: boolean
  pwdBusy: boolean
  canChangePassword: boolean
}>()

const emit = defineEmits<{
  (e: 'toggleTgInvites', value: boolean): void
  (e: 'unlinkTelegram'): void
  (e: 'deleteAccount'): void
  (e: 'changePassword'): void
}>()
</script>

<style scoped lang="scss">
.block-account {
  .verify-row {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .password-row {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    margin-top: 5px;
    gap: 10px;
    --ui-input-label-bg: #{$neutral-900};
    :deep(.profile-input) {
      max-width: 320px;
      width: 100%;
    }
  }
}
</style>
