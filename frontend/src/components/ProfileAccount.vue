<template>
  <section class="block-account">
    <div class="account-verif-password">
      <div class="account-verif">
        <div class="account">
          <div class="account-div">
            <div class="account-header">
              <span class="title">Аккаунт</span>
              <span class="hint">Удаление произойдет навсегда без возможности его восстановления.</span>
            </div>
            <UiButton
              variant="red"
              size="middle"
              :icon="iconDelete"
              :text="deleteBusy ? '...' : 'Удалить аккаунт'"
              @click="deleteAccount"
              :disabled="deleteBusy || isDeleteAccountForbiddenSelf"
            />
          </div>
          <div class="profile-dates" aria-label="Даты профиля">
            <div class="date-row">
              <span class="date-title">Дата регистрации</span>
              <span class="date-time">{{ registeredAtLabel }}</span>
            </div>
            <div class="date-row">
              <span class="date-title">Последняя игра</span>
              <span class="date-time">{{ lastGameAtLabel }}</span>
            </div>
            <div class="date-row">
              <span class="date-title">Был в сети</span>
              <span class="date-time">{{ lastOnlineLabel }}</span>
            </div>
          </div>
        </div>

        <div class="verif">
          <img class="verif-icon" :src="iconTickCircle" alt="" aria-hidden="true" />
          <div class="verif-div">
            <span class="title">Верификация</span>
            <span v-if="telegramVerified" class="hint">Если отвязать TG-аккаунт верификация будет снята.</span>
            <span v-if="!telegramVerified" class="hint">В чате с ботом сначала введите никнейм, затем пароль. После успешной верификации ограничения будут сняты.</span>
          </div>
          <UiButton
            v-if="telegramVerified"
            variant="red"
            :text="unlinkTgBusy ? '...' : 'Отвязать TG-аккаунт'"
            @click="unlinkTelegram"
            :disabled="unlinkTgBusy"
          />
          <UiButton
            v-if="!telegramVerified && botName"
            variant="green"
            text="Пройти верификацию"
            :href="botLink"
            target="_blank"
            rel="noopener noreferrer"
          />
        </div>
      </div>

      <div class="password">
        <div class="password-header">
          <span class="password-title">Пароль</span>
          <span class="password-temp">Замените временный пароль</span>
<!--          <span v-if="passwordTemp" class="password-temp">Замените временный пароль</span>-->
        </div>
        <span class="hint">
          Сбросить пароль можно через
          <a v-if="botName" :href="botLink" target="_blank" rel="noopener noreferrer">TG-бота</a>
        </span>
        <div class="password-div">
          <span class="password-text">Текущий пароль</span>
          <UiInput
            id="profile-pass-current"
            v-model="pwd.current"
            type="password"
            password-toggle
            autocomplete="current-password"
            minlength="8"
            maxlength="32"
            label="Введите текущий пароль"
            :invalid="currentPasswordInvalid"
            :aria-invalid="currentPasswordInvalid"
            aria-describedby="profile-pass-current-hint"
          >
            <template #meta>
              <span id="profile-pass-current-hint">{{ pwd.current.length }}/{{ PASSWORD_MAX }}</span>
            </template>
          </UiInput>
        </div>
        <div class="password-div">
          <span class="password-text">Новый пароль</span>
          <UiInput
            id="profile-pass-new"
            v-model="pwd.next"
            type="password"
            password-toggle
            autocomplete="new-password"
            minlength="8"
            maxlength="32"
            label="Введите новый пароль"
            :invalid="newPasswordInvalid"
            :aria-invalid="newPasswordInvalid"
            aria-describedby="profile-pass-new-hint"
          >
            <template #meta>
              <span id="profile-pass-new-hint">{{ pwd.next.length }}/{{ PASSWORD_MAX }}</span>
            </template>
          </UiInput>
        </div>
        <div class="password-div">
          <span class="password-text">Повторите пароль</span>
          <UiInput
            id="profile-pass-confirm"
            v-model="pwd.confirm"
            type="password"
            password-toggle
            autocomplete="new-password"
            minlength="8"
            maxlength="32"
            label="Повторите новый пароль"
            :invalid="confirmPasswordInvalid"
            :aria-invalid="confirmPasswordInvalid"
            aria-describedby="profile-pass-confirm-hint"
          >
            <template #meta>
              <span id="profile-pass-confirm-hint">{{ pwd.confirm.length }}/{{ PASSWORD_MAX }}</span>
            </template>
          </UiInput>
        </div>
        <UiButton
          class="password-btn"
          variant="green"
          size="middle"
          :text="pwdBusy ? '...' : 'Сменить пароль'"
          @click="changePassword"
          :disabled="pwdBusy || !canChangePassword"
        />
      </div>
    </div>

    <div class="params">
      <span class="title">Настройки</span>
      <div class="params-div">
        <UiSwitch
          class="profile-switch"
          :model-value="tgInvitesEnabled"
          label="Уведомления в TG о приглашениях в комнату"
          off-label="Запретить"
          on-label="Разрешить"
          size="low"
          :width="256"
          :disabled="tgInvitesTogglePending || !telegramVerified"
          @update:modelValue="onToggleTgInvites"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { api } from '@/services/axios'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { useAuthStore, useUserStore } from '@/store'

import UiInput from '@/components/UiInput.vue'
import UiSwitch from '@/components/UiSwitch.vue'
import UiButton from '@/components/UiButton.vue'

import iconDelete from '@/assets/svg/iconDelete.svg'
import iconTickCircle from '@/assets/svg/iconTickCircle.svg'
import UiTooltip from '@/components/UiTooltip.vue'

const PASSWORD_MIN = 8
const PASSWORD_MAX = 32
const PASSWORD_SPACE_RE = /\s/

const userStore = useUserStore()
const auth = useAuthStore()
const { tgInvitesEnabled, now } = storeToRefs(userStore)
const { setTgInvitesEnabled } = userStore

type ProfileDatesResponse = {
  registered_at?: string | null
  last_visit_at?: string | null
  last_game_at?: string | null
  last_game_id?: number | null
  online?: boolean
}

const me = reactive({
  id: 0,
  role: '',
  registered_at: null as string | null,
  has_password: false,
  protected_user: false,
})
const profileDates = reactive({
  registered_at: null as string | null,
  last_visit_at: null as string | null,
  last_game_at: null as string | null,
  last_game_id: null as number | null,
  online: false,
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
  return role === 'moder'
})
const registeredAtLabel = computed(() => formatDateWithMonthName(profileDates.registered_at || me.registered_at))
const lastGameAtLabel = computed(() => {
  const dateLabel = formatDateOnly(profileDates.last_game_at)
  if (dateLabel === '-') return '-'
  const gameId = Number(profileDates.last_game_id || 0)
  return Number.isFinite(gameId) && gameId > 0 ? `Игра #${Math.trunc(gameId)} от ${dateLabel}` : dateLabel
})
const lastOnlineLabel = computed(() => formatLastOnline(profileDates.last_visit_at, profileDates.online, now.value))
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

function parseDate(value?: string | number | Date | null): Date | null {
  if (!value) return null
  const dt = value instanceof Date ? value : new Date(value)
  return Number.isNaN(dt.getTime()) ? null : dt
}

function pad2(value: number): string {
  return String(value).padStart(2, '0')
}

const RU_MONTHS_GENITIVE = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
]

function formatDateOnly(value?: string | number | Date | null): string {
  const dt = parseDate(value)
  if (!dt) return '-'
  return `${pad2(dt.getDate())}.${pad2(dt.getMonth() + 1)}.${dt.getFullYear()}`
}

function formatDateWithMonthName(value?: string | number | Date | null): string {
  const dt = parseDate(value)
  if (!dt) return '-'
  return `${dt.getDate()} ${RU_MONTHS_GENITIVE[dt.getMonth()]} ${dt.getFullYear()}`
}

function formatLastOnline(value?: string | number | Date | null, online = false, nowMs = Date.now()): string {
  if (online) return 'Онлайн'
  const dt = parseDate(value)
  if (!dt) return '-'
  const diffMs = nowMs - dt.getTime()
  if (diffMs < 0) return 'Только что'
  const totalMinutes = Math.floor(diffMs / 60000)
  const minutesInDay = 24 * 60
  const minutesInMonth = 30 * minutesInDay
  if (totalMinutes < 1) return 'Только что'
  if (totalMinutes < 60) return `${totalMinutes}м назад`
  if (totalMinutes < minutesInDay) {
    const hours = Math.floor(totalMinutes / 60)
    const minutes = totalMinutes % 60
    return `${hours}ч ${minutes}м назад`
  }
  if (totalMinutes < minutesInMonth) return `${Math.floor(totalMinutes / minutesInDay)}д назад`
  return formatDateOnly(dt)
}

function applyMePayload(data: any) {
  me.id = Number(data?.id || 0)
  me.role = data?.role || ''
  me.registered_at = data?.registered_at || null
  me.has_password = Boolean(data?.has_password)
  me.protected_user = Boolean(data?.protected_user)
}

function applyProfileDatesPayload(data: ProfileDatesResponse) {
  profileDates.registered_at = data?.registered_at || null
  profileDates.last_visit_at = data?.last_visit_at || null
  profileDates.last_game_at = data?.last_game_at || null
  profileDates.last_game_id = Number.isFinite(Number(data?.last_game_id)) ? Math.trunc(Number(data.last_game_id)) : null
  profileDates.online = Boolean(data?.online)
}

async function loadMe() {
  const { data } = await api.get('/users/profile_info')
  applyMePayload(data)
  userStore.applyProfile(data)
}

async function loadProfileDates() {
  try {
    const { data } = await api.get<ProfileDatesResponse>('/users/profile_dates')
    applyProfileDatesPayload(data)
  } catch {}
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
  void loadProfileDates()
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
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  .account-verif-password {
    display: flex;
    gap: 10px;
    .account-verif {
      display: flex;
      flex-direction: column;
      gap: 10px;
      width: calc(50% - 5px);
      .account {
        display: flex;
        box-sizing: border-box;
        flex-direction: column;
        padding: 24px;
        gap: 24px;
        height: calc(50% - 5px);
        border-radius: 24px;
        background-color: $soft-purple-900;
        .account-div {
          display: flex;
          justify-content: space-between;
          .account-header {
            display: flex;
            flex-direction: column;
            gap: 16px;
            .title {
              color: $neutral-white;
              font-family: Involve-Medium;
              font-size: 24px;
              line-height: 26px;
              letter-spacing: -0.48px;
            }
            .hint {
              color: $neutral-300;
              font-family: Hauora-Regular;
              font-size: 14px;
              line-height: 14px;
              letter-spacing: -0.28px;
            }
          }
        }
        .profile-dates {
          display: flex;
          flex-direction: column;
          padding: 16px;
          gap: 12px;
          border-radius: 20px;
          background-color: rgba($soft-purple-900, 0.65);
          .date-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            .date-title {
              color: $neutral-300;
              font-family: Hauora-Regular;
              font-size: 16px;
              line-height: 16px;
              letter-spacing: -0.32px;
            }
            .date-time {
              color: $neutral-100;
              font-family: Hauora-Regular;
              font-size: 16px;
              line-height: 16px;
              letter-spacing: -0.32px;
            }
          }
        }
      }
      .verif {
        display: flex;
        box-sizing: border-box;
        position: relative;
        flex-direction: column;
        justify-content: space-between;
        padding: 24px;
        height: calc(50% - 5px);
        border-radius: 24px;
        background: linear-gradient(261deg, $green-700 0%, $soft-purple-800 100%);
        .verif-icon {
          position: absolute;
          top: 24px;
          right: 24px;
          width: 26px;
          height: 26px;
        }
        .verif-div {
          display: flex;
          flex-direction: column;
          margin-bottom: 24px;
          gap: 16px;
          .title {
            color: $neutral-white;
            font-family: Involve-Medium;
            font-size: 24px;
            line-height: 26px;
            letter-spacing: -0.48px;
          }
          .hint {
            max-width: 420px;
            color: $neutral-100;
            font-family: Hauora-Regular;
            font-size: 16px;
            line-height: 22px;
            letter-spacing: -0.32px;
          }
        }
      }
    }
    .password {
      display: flex;
      box-sizing: border-box;
      flex-direction: column;
      padding: 24px;
      gap: 24px;
      width: calc(50% - 5px);
      border-radius: 24px;
      background-color: $soft-purple-900;
      --ui-input-label-bg: #{$soft-purple-900};
      .password-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        height: 32px;
        .password-title {
          color: $neutral-white;
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        .password-temp {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0 16px;
          height: 32px;
          border-radius: 12px;
          background-color: $blue-100;
          color: $blue-500;
          font-family: Hauora-Regular;
          font-size: 14px;
          line-height: 14px;
          letter-spacing: -0.28px;
        }
      }
      .hint {
        color: $neutral-300;
        font-family: Hauora-Regular;
        font-size: 14px;
        line-height: 14px;
        letter-spacing: -0.28px;
        a {
          color: $neutral-white;
        }
      }
      .password-div {
        display: flex;
        flex-direction: column;
        gap: 16px;
        .password-text {
          color: $neutral-white;
          font-family: Hauora-Bold;
          font-size: 16px;
          line-height: 18px;
          letter-spacing: -0.32px;
        }
      }
      .password-btn {
        margin-top: 16px;
      }
    }
  }
  .params {
    display: flex;
    flex-direction: column;
    padding: 24px;
    gap: 24px;
    border-radius: 24px;
    background-color: $soft-purple-900;
    .title {
      color: $neutral-white;
      font-family: Involve-Medium;
      font-size: 24px;
      line-height: 26px;
      letter-spacing: -0.48px;
    }
    .params-div {
      padding: 16px;
      border-radius: 20px;
      background-color: $soft-purple-800;
    }
  }
}

</style>
