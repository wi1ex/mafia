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
          <span class="title">Добро пожаловать<br />на платформу deceit.games!</span>

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

          <form class="form" @submit.prevent="submitActiveAuth">
            <UiInput
              :id="authUsernameId"
              v-model.trim="authUsername"
              maxlength="20"
              autocomplete="username"
              label="Никнейм"
              :invalid="authUsernameInvalid"
              :aria-invalid="authUsernameInvalid"
              :aria-describedby="authUsernameHintId"
            >
              <template #meta>
                <span :id="authUsernameHintId">{{ authUsername.length }}/{{ USERNAME_MAX }}</span>
              </template>
            </UiInput>
            <UiInput
              :id="authPasswordId"
              v-model="authPassword"
              type="password"
              password-toggle
              :autocomplete="authPasswordAutocomplete"
              minlength="8"
              maxlength="32"
              label="Пароль"
              :invalid="authPasswordInvalid"
              :aria-invalid="authPasswordInvalid"
              :aria-describedby="authPasswordHintId"
            >
              <template #meta>
                <span :id="authPasswordHintId">{{ authPassword.length }}/{{ PASSWORD_MAX }}</span>
              </template>
            </UiInput>
            <Transition name="auth-field-expand" mode="out-in">
              <div v-if="isRegisterMode" key="register" class="auth-field-expand">
                <div class="auth-register-fields">
                  <UiInput
                    id="auth-reg-password-confirm"
                    v-model="reg.passwordConfirm"
                    type="password"
                    password-toggle
                    autocomplete="new-password"
                    minlength="8"
                    maxlength="32"
                    label="Повторите пароль"
                    :invalid="regPasswordConfirmInvalid"
                    :aria-invalid="regPasswordConfirmInvalid"
                    aria-describedby="auth-reg-password-confirm-hint"
                  >
                    <template #meta>
                      <span id="auth-reg-password-confirm-hint">{{ reg.passwordConfirm.length }}/{{ PASSWORD_MAX }}</span>
                    </template>
                  </UiInput>
                  <UiCheckbox v-model="reg.acceptRules" theme="light">
                    <span>С <router-link to="/rules" target="_blank">правилами платформы</router-link> ознакомлен и согласен</span>
                  </UiCheckbox>
                </div>
              </div>
              <div v-else key="login" class="auth-field-expand">
                <div class="forgot-password">
                  <span>Забыли пароль?</span>
                  <button class="btn-ghost" type="button" @click="openBot">Восстановить</button>
                </div>
              </div>
            </Transition>
            <UiButton
              class="auth-btn"
              type="submit"
              :text="authSubmitText"
              :disabled="authSubmitDisabled"
            />
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
import UiButton from '@/components/UiButton.vue'

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
const isRegisterMode = computed(() => activeTab.value === 'register')
const registrationMode = computed({
  get: () => isRegisterMode.value,
  set: (value: boolean) => {
    activeTab.value = value && canRegister.value ? 'register' : 'login'
  },
})
const armed = ref(false)
const loginBusy = ref(false)
const regBusy = ref(false)

const login = reactive({ username: '', password: '' })
const reg = reactive({ username: '', password: '', passwordConfirm: '', acceptRules: false })

const authUsername = computed({
  get: () => isRegisterMode.value ? reg.username : login.username,
  set: (value: string) => {
    if (isRegisterMode.value) reg.username = value
    else login.username = value
  },
})
const authPassword = computed({
  get: () => isRegisterMode.value ? reg.password : login.password,
  set: (value: string) => {
    if (isRegisterMode.value) reg.password = value
    else login.password = value
  },
})
const authUsernameId = computed(() => isRegisterMode.value ? 'auth-reg-username' : 'auth-login-username')
const authUsernameHintId = computed(() => `${authUsernameId.value}-hint`)
const authPasswordId = computed(() => isRegisterMode.value ? 'auth-reg-password' : 'auth-login-password')
const authPasswordHintId = computed(() => `${authPasswordId.value}-hint`)
const authPasswordAutocomplete = computed(() => isRegisterMode.value ? 'new-password' : 'current-password')

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
const authUsernameInvalid = computed(() => isRegisterMode.value ? regUsernameInvalid.value : loginUsernameInvalid.value)
const authPasswordInvalid = computed(() => isRegisterMode.value ? regPasswordInvalid.value : loginPasswordInvalid.value)
const authSubmitText = computed(() => {
  if (isRegisterMode.value) return regBusy.value ? '...' : 'Зарегистрироваться'
  return loginBusy.value ? '...' : 'Войти в аккаунт'
})
const authSubmitDisabled = computed(() => {
  if (isRegisterMode.value) return regBusy.value || auth.registerCooldownActive || !canRegisterSubmit.value
  return loginBusy.value || auth.loginCooldownActive || !canLogin.value
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

async function submitActiveAuth() {
  if (isRegisterMode.value) {
    await submitRegister()
    return
  }
  await submitLogin()
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
      gap: 40px;
      width: 450px;
      .title {
        text-align: center;
        color: $neutral-white;
        font-family: Involve-Medium;
        font-size: 32px;
        line-height: 36px;
        letter-spacing: -0.64px;
      }
      .form {
        display: flex;
        flex-direction: column;
        gap: 16px;
        .auth-field-expand {
          display: grid;
          margin-top: -16px;
          > * {
            min-height: 0;
            overflow: hidden;
          }
        }
        .auth-register-fields {
          display: flex;
          flex-direction: column;
          padding-top: 16px;
          gap: 16px;
        }
        .forgot-password {
          display: flex;
          justify-self: flex-end;
          align-items: center;
          margin-top: 16px;
          gap: 4px;
          color: $neutral-300;
          font-family: Hauora-Regular;
          font-size: 14px;
          line-height: 18px;
          letter-spacing: -0.28px;
        }
        .auth-switch {
          margin-bottom: 16px;
        }
        .btn-ghost {
          padding: 0;
          border: none;
          background: none;
          color: inherit;
          font: inherit;
          letter-spacing: inherit;
          text-decoration-line: underline;
          text-decoration-color: currentColor;
          text-decoration-thickness: 1px;
          text-underline-offset: 3px;
          cursor: pointer;
          transition: color 0.25s ease-in-out, text-decoration-color 0.25s ease-in-out;
          &:hover,
          &:focus-visible,
          &:active {
            color: $neutral-white;
          }
        }
        .auth-btn {
          align-self: center;
          margin-top: 16px;
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
.auth-field-expand-enter-active,
.auth-field-expand-leave-active {
  overflow: hidden;
  transition: grid-template-rows 0.25s ease-in-out, opacity 0.25s ease-in-out;
}
.auth-field-expand-enter-from,
.auth-field-expand-leave-to {
  grid-template-rows: 0fr;
  opacity: 0;
}
.auth-field-expand-enter-to,
.auth-field-expand-leave-from {
  grid-template-rows: 1fr;
  opacity: 1;
}

</style>
