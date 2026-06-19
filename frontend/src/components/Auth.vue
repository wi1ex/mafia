<template>
  <Transition name="auth-modal">
    <div v-if="open" class="auth-overlay" role="dialog" aria-modal="true" @pointerdown.self="armed = true"
         @pointerup.self="armed && close()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
      <div class="auth-logo">
        <video class="auth-logo-video" :src="authLogoVideo" autoplay loop muted playsinline preload="auto" aria-hidden="true" />
      </div>
      <div class="auth-modal">
        <button type="button" class="btn-close" aria-label="Закрыть" @click="close">
          <img :src="iconClose" class="btn-icon" alt="close" aria-hidden="true" />
        </button>

        <div class="auth-body">
          <span class="title">Вход в аккаунт</span>

          <UiSwitch
            v-if="canRegister"
            v-model="registrationMode"
            class="auth-switch"
            off-label="Вход"
            on-label="Регистрация"
            aria-label="Вход / Регистрация"
            :width="450"
            theme="dark"
            without-text
          />

          <form v-if="activeTab === 'login'" class="form" @submit.prevent="submitLogin">
            <UiInput id="auth-login-username" v-model.trim="login.username" maxlength="20" autocomplete="username" label="Никнейм"
              :invalid="loginUsernameInvalid" :aria-invalid="loginUsernameInvalid" aria-describedby="auth-login-username-hint">
              <template #meta>
                <span id="auth-login-username-hint">{{ login.username.length }}/{{ USERNAME_MAX }}</span>
              </template>
            </UiInput>
            <UiInput id="auth-login-password" v-model="login.password" type="password" autocomplete="current-password" minlength="8" maxlength="32" label="Пароль"
              :invalid="loginPasswordInvalid" :aria-invalid="loginPasswordInvalid" aria-describedby="auth-login-password-hint">
              <template #meta>
                <span id="auth-login-password-hint">{{ login.password.length }}/{{ PASSWORD_MAX }}</span>
              </template>
            </UiInput>
            <button class="btn confirm" type="submit" :disabled="loginBusy || auth.loginCooldownActive || !canLogin">
              {{ loginBusy ? '...' : 'Войти в аккаунт' }}
            </button>
            <button class="btn ghost" type="button" @click="openBot">Сбросить пароль</button>
          </form>

          <form v-else class="form" @submit.prevent="submitRegister">
            <UiInput id="auth-reg-username" v-model.trim="reg.username" maxlength="20" autocomplete="username" label="Никнейм"
              :invalid="regUsernameInvalid" :aria-invalid="regUsernameInvalid" aria-describedby="auth-reg-username-hint">
              <template #meta>
                <span id="auth-reg-username-hint">{{ reg.username.length }}/{{ USERNAME_MAX }}</span>
              </template>
            </UiInput>
            <UiInput id="auth-reg-password" v-model="reg.password" type="password" autocomplete="new-password" minlength="8" maxlength="32" label="Пароль"
              :invalid="regPasswordInvalid" :aria-invalid="regPasswordInvalid" aria-describedby="auth-reg-password-hint">
              <template #meta>
                <span id="auth-reg-password-hint">{{ reg.password.length }}/{{ PASSWORD_MAX }}</span>
              </template>
            </UiInput>
            <UiInput id="auth-reg-password-confirm" v-model="reg.passwordConfirm" type="password" autocomplete="new-password" minlength="8" maxlength="32" label="Повторите пароль"
              :invalid="regPasswordConfirmInvalid" :aria-invalid="regPasswordConfirmInvalid" aria-describedby="auth-reg-password-confirm-hint">
              <template #meta>
                <span id="auth-reg-password-confirm-hint">{{ reg.passwordConfirm.length }}/{{ PASSWORD_MAX }}</span>
              </template>
            </UiInput>
            <UiCheckbox v-model="reg.acceptRules">
              <span>С <router-link to="/rules" target="_blank">правилами</router-link> ознакомлен и согласен</span>
            </UiCheckbox>
            <button class="btn confirm" type="submit" :disabled="regBusy || auth.registerCooldownActive || !canRegisterSubmit">
              {{ regBusy ? '...' : 'Зарегистрироваться' }}
            </button>
          </form>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useAuthStore, useSettingsStore } from '@/store'

import UiInput from '@/components/UiInput.vue'
import UiCheckbox from '@/components/UiCheckbox.vue'
import UiSwitch from '@/components/UiSwitch.vue'

import authLogoVideo from '@/assets/video/auth-logo.mp4'
import iconClose from '@/assets/svg/iconClose.svg'

const props = defineProps<{ open: boolean; mode?: 'login' | 'register' }>()
const emit = defineEmits<{ (e: 'update:open', value: boolean): void }>()

const auth = useAuthStore()
const settings = useSettingsStore()

const botName = (import.meta.env.VITE_TG_BOT_NAME as string || '').trim()
const botLink = botName ? `https://t.me/${botName}` : 'https://t.me'
const AUTH_LOGO_VIDEO_PRELOAD_ID = 'auth-logo-video-preload'

const canRegister = computed(() => Boolean(settings.registrationEnabled))
const activeTab = ref<'login' | 'register'>(props.mode ?? 'login')
const registrationMode = computed({
  get: () => activeTab.value === 'register',
  set: (value: boolean) => {
    activeTab.value = value && canRegister.value ? 'register' : 'login'
  },
})
const armed = ref(false)
const loginBusy = ref(false)
const regBusy = ref(false)

const login = reactive({ username: '', password: '' })
const reg = reactive({ username: '', password: '', passwordConfirm: '', acceptRules: false })

const USERNAME_MIN = 2
const USERNAME_MAX = 20
const PASSWORD_MIN = 8
const PASSWORD_MAX = 32
const PASSWORD_SPACE_RE = /\s/

const canLogin = computed(() =>
  login.username.trim().length >= USERNAME_MIN &&
  login.password.length >= PASSWORD_MIN &&
  login.password.length <= PASSWORD_MAX
)
const passwordsMatch = computed(() => reg.password && reg.password === reg.passwordConfirm)
const canRegisterSubmit = computed(() =>
  canRegister.value &&
  reg.username.trim().length >= USERNAME_MIN &&
  reg.password.length >= PASSWORD_MIN &&
  reg.password.length <= PASSWORD_MAX &&
  !hasPasswordWhitespace(reg.password) &&
  !hasPasswordWhitespace(reg.passwordConfirm) &&
  passwordsMatch.value &&
  reg.acceptRules
)

const loginUsernameInvalid = computed(() => {
  const len = login.username.trim().length
  return len > 0 && len < USERNAME_MIN
})
const loginPasswordInvalid = computed(() => {
  const len = login.password.length
  return len > 0 && len < PASSWORD_MIN
})
const regUsernameInvalid = computed(() => {
  const len = reg.username.trim().length
  return len > 0 && len < USERNAME_MIN
})
const regPasswordInvalid = computed(() => {
  const len = reg.password.length
  return len > 0 && (len < PASSWORD_MIN || hasPasswordWhitespace(reg.password))
})
const regPasswordConfirmInvalid = computed(() => {
  const len = reg.passwordConfirm.length
  if (len === 0) return false
  if (hasPasswordWhitespace(reg.passwordConfirm)) return true
  if (len < PASSWORD_MIN) return true
  return reg.password !== reg.passwordConfirm
})

function hasPasswordWhitespace(value: string) {
  return PASSWORD_SPACE_RE.test(value)
}

function preloadAuthLogoVideo() {
  if (document.getElementById(AUTH_LOGO_VIDEO_PRELOAD_ID)) return

  const link = document.createElement('link')
  link.id = AUTH_LOGO_VIDEO_PRELOAD_ID
  link.rel = 'preload'
  link.as = 'video'
  link.type = 'video/mp4'
  link.href = authLogoVideo
  document.head.appendChild(link)
}

function close() {
  emit('update:open', false)
  armed.value = false
}

function openBot() {
  if (!botLink) return
  window.open(botLink, '_blank', 'noopener,noreferrer')
}

async function submitLogin() {
  if (!canLogin.value || loginBusy.value || auth.loginCooldownActive) return
  loginBusy.value = true
  try {
    await auth.signInWithPassword({ username: login.username.trim(), password: login.password })
    if (auth.isAuthed) close()
  } finally { loginBusy.value = false }
}

async function submitRegister() {
  if (!canRegisterSubmit.value || regBusy.value || auth.registerCooldownActive) return
  regBusy.value = true
  try {
    await auth.registerWithPassword({
      username: reg.username.trim(),
      password: reg.password,
      accept_rules: reg.acceptRules,
    })
    if (auth.isAuthed) close()
  } finally { regBusy.value = false }
}

watch(() => props.mode, (mode) => {
  if (mode) activeTab.value = mode
})

watch(() => props.open, (open) => {
  if (open && props.mode) activeTab.value = props.mode
})

onMounted(() => {
  window.setTimeout(preloadAuthLogoVideo, 500)
})
</script>

<style scoped lang="scss">
.auth-overlay {
  position: fixed;
  display: flex;
  inset: 0;
  padding: 40px;
  background-color: $neutral-black;
  z-index: 1000;
  .auth-logo {
    display: flex;
    width: 50%;
    border-radius: 24px;
    overflow: hidden;
    .auth-logo-video {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
  }
  .auth-modal {
    display: flex;
    position: relative;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 50%;
    overflow: hidden;
    .btn-close {
      display: flex;
      position: absolute;
      align-items: center;
      justify-content: center;
      top: 0;
      right: 0;
      padding: 0;
      width: 40px;
      height: 40px;
      border: none;
      border-radius: 12px;
      background: linear-gradient(261deg, $soft-purple-800 0%, $green-700 100%);
      cursor: pointer;
      overflow: hidden;
      isolation: isolate;
      &::after {
        content: '';
        position: absolute;
        inset: 0;
        border-radius: inherit;
        background: linear-gradient(261deg, $green-700 0%, $soft-purple-800 100%);
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.25s ease-in-out;
        z-index: 0;
      }
      &:hover,
      &:focus-visible,
      &:active {
        &::after {
          opacity: 1;
        }
      }
      .btn-icon {
        position: relative;
        z-index: 2;
        width: 24px;
        height: 24px;
      }
    }
    .auth-body {
      display: flex;
      flex-direction: column;
      gap: 0;
      padding: 10px 10px 0;
      background-color: $dark;
      color: $fg;
      .title {
        font-size: 18px;
        font-weight: bold;
      }
      .auth-switch {
        margin: 20px 0 10px;
      }
      .form {
        display: flex;
        flex-direction: column;
        margin-bottom: 10px;
        padding: 10px;
        gap: 15px;
        height: 266px;
        border-top: 3px solid $lead;
        border-left: 3px solid $lead;
        border-right: 3px solid $lead;
        border-bottom: 3px solid $lead;
        border-radius: 0 0 5px 5px;
      }
      .btn.confirm {
        padding: 0;
        height: 40px;
        border: none;
        border-radius: 5px;
        background-color: $fg;
        color: $bg;
        font-size: 18px;
        font-family: Manrope-Medium;
        line-height: 1;
        cursor: pointer;
        transition: opacity 0.25s ease-in-out, background-color 0.25s ease-in-out;
        &:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        &:hover {
          background-color: $white;
        }
      }
      .btn.ghost {
        padding: 0;
        height: 40px;
        border: none;
        border-radius: 5px;
        background-color: $lead;
        color: $fg;
        font-size: 16px;
        font-family: Manrope-Medium;
        line-height: 1;
        cursor: pointer;
        transition: opacity 0.25s ease-in-out, background-color 0.25s ease-in-out;
        &:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        &:hover {
          background-color: $grey;
        }
      }
    }
  }
}

.auth-modal-enter-active,
.auth-modal-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.auth-modal-enter-from,
.auth-modal-leave-to {
  opacity: 0;
}

</style>
