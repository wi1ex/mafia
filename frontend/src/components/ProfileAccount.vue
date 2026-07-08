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
        @update:modelValue="onToggleTgInvites"
      />
      <button v-if="telegramVerified" class="btn danger" @click="unlinkTelegram" :disabled="unlinkTgBusy">
        {{ unlinkTgBusy ? '...' : 'Отвязать TG-аккаунт' }}
      </button>
      <a v-else-if="botName" class="btn confirm" :href="botLink" target="_blank" rel="noopener noreferrer">Пройти верификацию</a>
      <p v-if="telegramVerified" class="hint">Если отвязать TG-аккаунт верификация будет снята и вход в комнаты будет ограничен</p>
      <p v-else class="hint">В чате с ботом сначала введите никнейм, затем пароль. После успешной верификации ограничения на вход в комнаты будут сняты</p>
      <button class="btn danger" @click="deleteAccount" :disabled="deleteBusy || isDeleteAccountForbiddenSelf">{{ deleteBusy ? '...' : 'Удалить аккаунт' }}</button>
      <p class="hint red">Удаление произойдет навсегда без возможности восстановления</p>

      <div v-if="me.has_password" class="password-row">
        <p class="hint text">Пароль</p>
        <p v-if="passwordTemp" class="hint warn">У вас временный пароль — рекомендуем изменить его</p>
        <UiInput class="profile-input" id="profile-pass-current" v-model="pwd.current" type="password" autocomplete="current-password" minlength="8" maxlength="32" label="Текущий пароль"
          :invalid="currentPasswordInvalid" :aria-invalid="currentPasswordInvalid" aria-describedby="profile-pass-current-hint">
          <template #meta>
            <span id="profile-pass-current-hint">{{ pwd.current.length }}/{{ PASSWORD_MAX }}</span>
          </template>
        </UiInput>
        <UiInput class="profile-input" id="profile-pass-new" v-model="pwd.next" type="password" autocomplete="new-password" minlength="8" maxlength="32" label="Новый пароль"
          :invalid="newPasswordInvalid" :aria-invalid="newPasswordInvalid" aria-describedby="profile-pass-new-hint">
          <template #meta>
            <span id="profile-pass-new-hint">{{ pwd.next.length }}/{{ PASSWORD_MAX }}</span>
          </template>
        </UiInput>
        <UiInput class="profile-input" id="profile-pass-confirm" v-model="pwd.confirm" type="password" autocomplete="new-password" minlength="8" maxlength="32" label="Повторите пароль"
          :invalid="confirmPasswordInvalid" :aria-invalid="confirmPasswordInvalid" aria-describedby="profile-pass-confirm-hint">
          <template #meta>
            <span id="profile-pass-confirm-hint">{{ pwd.confirm.length }}/{{ PASSWORD_MAX }}</span>
          </template>
        </UiInput>
        <button class="btn confirm" @click="changePassword" :disabled="pwdBusy || !canChangePassword">
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
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import UiInput from '@/components/UiInput.vue'
import UiSwitch from '@/components/UiSwitch.vue'
import { api } from '@/services/axios'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { useAuthStore, useUserStore } from '@/store'

const PASSWORD_MIN = 8
const PASSWORD_MAX = 32
const PASSWORD_SPACE_RE = /\s/

const userStore = useUserStore()
const auth = useAuthStore()
const { tgInvitesEnabled } = storeToRefs(userStore)
const { setTgInvitesEnabled } = userStore

const me = reactive({
  id: 0,
  role: '',
  registered_at: null as string | null,
  has_password: false,
  protected_user: false,
})
const tgInvitesTogglePending = ref(false)
const pwd = reactive({ current: '', next: '', confirm: '' })
const pwdBusy = ref(false)
const unlinkTgBusy = ref(false)
const deleteBusy = ref(false)
const telegramVerified = computed(() => userStore.telegramVerified)
const passwordTemp = computed(() => userStore.passwordTemp)
const botName = (import.meta.env.VITE_TG_BOT_NAME as string || '').trim()
const botLink = botName ? `https://t.me/${botName}` : 'https://t.me'
let onProfileSync: ((e: Event) => void) | null = null

const isDeleteAccountForbiddenSelf = computed(() => {
  const role = String(me.role || '').trim().toLowerCase()
  return Boolean(me.protected_user) || role === 'admin' || role === 'moder'
})
const registrationDateLabel = computed(() => {
  const raw = me.registered_at
  if (!raw) return '-'
  const dt = new Date(raw)
  if (Number.isNaN(dt.getTime())) return '-'
  return dt.toLocaleDateString('ru-RU')
})
const canChangePassword = computed(() =>
  pwd.current.length >= PASSWORD_MIN &&
  pwd.current.length <= PASSWORD_MAX &&
  pwd.next.length >= PASSWORD_MIN &&
  pwd.next.length <= PASSWORD_MAX &&
  !hasPasswordWhitespace(pwd.next) &&
  pwd.confirm.length >= PASSWORD_MIN &&
  pwd.confirm.length <= PASSWORD_MAX &&
  !hasPasswordWhitespace(pwd.confirm) &&
  pwd.next === pwd.confirm
)
const currentPasswordInvalid = computed(() => {
  const len = pwd.current.length
  return len > 0 && len < PASSWORD_MIN
})
const newPasswordInvalid = computed(() => {
  const len = pwd.next.length
  return len > 0 && (len < PASSWORD_MIN || hasPasswordWhitespace(pwd.next))
})
const confirmPasswordInvalid = computed(() => {
  const len = pwd.confirm.length
  if (len === 0) return false
  if (hasPasswordWhitespace(pwd.confirm)) return true
  if (len < PASSWORD_MIN) return true
  return pwd.next !== pwd.confirm
})

function hasPasswordWhitespace(value: string) {
  return PASSWORD_SPACE_RE.test(value)
}

function applyMePayload(data: any) {
  me.id = Number(data?.id || 0)
  me.role = data?.role || ''
  me.registered_at = data?.registered_at || null
  me.has_password = Boolean(data?.has_password)
  me.protected_user = Boolean(data?.protected_user)
}

async function loadMe() {
  const { data } = await api.get('/users/profile_info')
  applyMePayload(data)
  userStore.applyProfile(data)
}

async function onToggleTgInvites(next: boolean) {
  if (tgInvitesTogglePending.value || !telegramVerified.value) return
  tgInvitesTogglePending.value = true
  try { await setTgInvitesEnabled(next) }
  finally { tgInvitesTogglePending.value = false }
}

async function changePassword() {
  if (!canChangePassword.value || pwdBusy.value) return
  pwdBusy.value = true
  try {
    await api.patch('/users/password', {
      current_password: pwd.current,
      new_password: pwd.next,
    })
    pwd.current = ''
    pwd.next = ''
    pwd.confirm = ''
    await userStore.fetchMe?.()
    void alertDialog('Пароль обновлен')
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 401 && d === 'invalid_credentials') void alertDialog('Текущий пароль неверный')
    else if (st === 403 && d === 'password_not_set') void alertDialog('Пароль не установлен. Восстановите его через TG-бота.')
    else if (st === 403 && d === 'user_deleted') void alertDialog('Аккаунт удален')
    else if (st === 422 && d === 'invalid_password') void alertDialog('Пароль должен быть от 8 до 32 символов и без пробелов')
    else void alertDialog('Не удалось изменить пароль')
  } finally { pwdBusy.value = false }
}

async function unlinkTelegram() {
  if (!telegramVerified.value || unlinkTgBusy.value) return
  const ok = await confirmDialog({
    title: 'Отвязать TG-аккаунт',
    text: 'Вы уверены, что хотите отвязать Telegram-аккаунт? После отвязки верификация будет снята.',
    confirmText: 'Подтвердить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  unlinkTgBusy.value = true
  try {
    await api.post('/users/unverify')
    userStore.setTelegramVerified(false)
    await loadMe()
    void alertDialog('TG-аккаунт отвязан. Верификация снята.')
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 403 && d === 'sanction_active') void alertDialog('Нельзя отвязать TG-аккаунт, пока действует наказание.')
    else if (st === 403 && d === 'user_deleted') void alertDialog('Аккаунт удален')
    else void alertDialog('Не удалось отвязать TG-аккаунт')
  } finally {
    unlinkTgBusy.value = false
  }
}

async function deleteAccount() {
  if (deleteBusy.value || isDeleteAccountForbiddenSelf.value) return
  const ok = await confirmDialog({
    title: 'Удаление аккаунта',
    text: 'Вы уверены, что хотите навсегда удалить аккаунт?',
    confirmText: 'Подтвердить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  deleteBusy.value = true
  try {
    await api.delete('/users/account')
    await auth.logout()
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 403 && (d === 'protected_user' || d === 'staff_self_delete_forbidden')) {
      void alertDialog('Модераторам и администраторам нельзя удалять свой аккаунт')
    } else {
      void alertDialog('Не удалось удалить аккаунт')
    }
  } finally {
    deleteBusy.value = false
  }
}

onMounted(() => {
  void loadMe()
  onProfileSync = (e: Event) => {
    const payload = (e as CustomEvent)?.detail
    if (!payload) return
    applyMePayload(payload)
  }
  window.addEventListener('auth-profile_sync', onProfileSync)
})

onBeforeUnmount(() => {
  if (onProfileSync) window.removeEventListener('auth-profile_sync', onProfileSync)
})
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
