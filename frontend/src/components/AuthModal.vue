<template>
  <Transition name="auth-modal">
    <div v-if="open" class="auth-overlay" role="dialog" aria-modal="true" @pointerdown.self="armed = true"
         @pointerup.self="armed && close()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
      <div class="auth-modal">
        <header>
          <span>Вход в аккаунт</span>
          <button @click="close" aria-label="Закрыть">
            <img :src="iconClose" alt="close" />
          </button>
        </header>
        <div class="auth-body">
          <div v-if="canRegister" class="tabs" role="tablist">
            <button class="tab" :class="{ active: activeTab === 'login' }" type="button" role="tab" @click="activeTab = 'login'">Авторизация</button>
            <button class="tab" :class="{ active: activeTab === 'register' }" type="button" role="tab" @click="activeTab = 'register'">Регистрация</button>
          </div>

          <form v-if="activeTab === 'login'" class="form" @submit.prevent="submitLogin">
            <div class="ui-input" :class="{ filled: !!login.username }">
              <input id="auth-login-username" v-model.trim="login.username" maxlength="20" autocomplete="username" placeholder=" " />
              <label for="auth-login-username">Логин</label>
              <div class="underline"><span></span></div>
            </div>
            <div class="ui-input" :class="{ filled: !!login.password }">
              <input id="auth-login-password" v-model="login.password" type="password" autocomplete="current-password" placeholder=" " />
              <label for="auth-login-password">Пароль</label>
              <div class="underline"><span></span></div>
            </div>
            <button class="btn confirm" type="submit" :disabled="loginBusy || !canLogin">
              {{ loginBusy ? '...' : 'Войти' }}
            </button>
            <button class="btn ghost" type="button" @click="openBot">Сбросить пароль</button>
          </form>

          <form v-else class="form" @submit.prevent="submitRegister">
            <div class="ui-input" :class="{ filled: !!reg.username }">
              <input id="auth-reg-username" v-model.trim="reg.username" maxlength="20" autocomplete="username" placeholder=" " />
              <label for="auth-reg-username">Логин</label>
              <div class="underline"><span></span></div>
            </div>
            <div class="ui-input" :class="{ filled: !!reg.password }">
              <input id="auth-reg-password" v-model="reg.password" type="password" autocomplete="new-password" placeholder=" " />
              <label for="auth-reg-password">Пароль</label>
              <div class="underline"><span></span></div>
            </div>
            <div class="ui-input" :class="{ filled: !!reg.passwordConfirm, invalid: reg.passwordConfirm && !passwordsMatch }">
              <input id="auth-reg-password-confirm" v-model="reg.passwordConfirm" type="password" autocomplete="new-password" placeholder=" " />
              <label for="auth-reg-password-confirm">Повторите пароль</label>
              <div class="underline"><span></span></div>
            </div>
            <label class="rules">
              <input type="checkbox" v-model="reg.acceptRules" />
              <span>С <router-link to="/rules" target="_blank">правилами</router-link> ознакомлен и согласен</span>
            </label>
            <button class="btn confirm" type="submit" :disabled="regBusy || !canRegisterSubmit">
              {{ regBusy ? '...' : 'Зарегистрироваться' }}
            </button>
          </form>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useAuthStore, useSettingsStore } from '@/store'
import iconClose from '@/assets/svg/close.svg'

const props = defineProps<{ open: boolean; mode?: 'login' | 'register' }>()
const emit = defineEmits<{ (e: 'update:open', value: boolean): void }>()

const auth = useAuthStore()
const settings = useSettingsStore()

const botName = (import.meta.env.VITE_TG_BOT_NAME as string || '').trim()
const botLink = botName ? `https://t.me/${botName}` : 'https://t.me'

const canRegister = computed(() => Boolean(settings.registrationEnabled))
const activeTab = ref<'login' | 'register'>(props.mode ?? 'login')
const armed = ref(false)
const loginBusy = ref(false)
const regBusy = ref(false)

const login = reactive({ username: '', password: '' })
const reg = reactive({ username: '', password: '', passwordConfirm: '', acceptRules: false })

const canLogin = computed(() => login.username.trim().length >= 2 && login.password.length >= 6)
const passwordsMatch = computed(() => reg.password && reg.password === reg.passwordConfirm)
const canRegisterSubmit = computed(() =>
  canRegister.value &&
  reg.username.trim().length >= 2 &&
  reg.password.length >= 6 &&
  passwordsMatch.value &&
  reg.acceptRules
)

function close() {
  emit('update:open', false)
  armed.value = false
}

function openBot() {
  if (!botLink) return
  window.open(botLink, '_blank', 'noopener,noreferrer')
}

async function submitLogin() {
  if (!canLogin.value || loginBusy.value) return
  loginBusy.value = true
  try {
    await auth.signInWithPassword({ username: login.username.trim(), password: login.password })
    if (auth.isAuthed) close()
  } finally { loginBusy.value = false }
}

async function submitRegister() {
  if (!canRegisterSubmit.value || regBusy.value) return
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
</script>

<style scoped lang="scss">
.auth-overlay {
  position: fixed;
  display: flex;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($black, 0.25);
  backdrop-filter: blur(5px);
  z-index: 1000;
  .auth-modal {
    display: flex;
    flex-direction: column;
    width: 400px;
    border-radius: 5px;
    background-color: $dark;
    transform: translateY(0);
    transition: transform 0.25s ease-in-out;
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 5px 10px;
      border-radius: 5px;
      background-color: $graphite;
      box-shadow: 0 3px 5px rgba($black, 0.25);
      span {
        font-size: 18px;
        font-weight: bold;
      }
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        width: 25px;
        height: 30px;
        border: none;
        background: none;
        cursor: pointer;
        img {
          width: 25px;
          height: 25px;
        }
      }
    }
    .auth-body {
      display: flex;
      flex-direction: column;
      gap: 0;
      padding: 10px 10px 0;
      background-color: $dark;
      color: $fg;
      .tabs {
        display: flex;
        align-items: flex-end;
        width: 100%;
        height: 40px;
        .tab {
          width: 50%;
          height: 30px;
          border: none;
          border-radius: 5px 5px 0 0;
          background-color: $graphite;
          color: $fg;
          font-size: 16px;
          font-family: Manrope-Medium;
          line-height: 1;
          cursor: pointer;
          transition: height 0.25s ease-in-out, background-color 0.25s ease-in-out;
          &.active {
            height: 40px;
            background-color: $lead;
          }
          &:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
        }
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
      .ui-input {
        display: block;
        position: relative;
        width: 100%;
        box-shadow: 3px 3px 5px rgba($black, 0.25);
        input {
          width: calc(100% - 22px);
          padding: 20px 10px 5px;
          border: 1px solid $lead;
          border-radius: 5px 5px 0 0;
          background-color: $graphite;
          color: $fg;
          font-size: 16px;
          font-family: Manrope-Medium;
          line-height: 1;
          outline: none;
          transition: border-color 0.25s ease-in-out, background-color 0.25s ease-in-out;
        }
        input::placeholder {
          color: transparent;
        }
        label {
          position: absolute;
          top: 50%;
          left: 12px;
          color: $fg;
          transform: translateY(-50%);
          pointer-events: none;
          transition: all 0.25s ease-in-out;
        }
        .underline {
          position: absolute;
          left: 0;
          right: 0;
          bottom: -3px;
          height: 3px;
          border-radius: 0 0 3px 3px;
          overflow: hidden;
          span {
            position: absolute;
            left: 0;
            bottom: 0;
            height: 3px;
            width: 0;
            background-color: $fg;
            transition: width 0.25s ease-in-out;
          }
        }
        .underline::before {
          content: "";
          position: absolute;
          inset: 0;
          background-color: $lead;
          transition: background-color 0.25s ease-in-out;
        }
        &.invalid input {
          border-color: rgba($red, 0.75);
        }
        &.invalid label {
          color: $red;
        }
        &.invalid .underline::before {
          background-color: rgba($red, 0.75);
        }
      }
      .ui-input:focus-within label,
      .ui-input input:not(:placeholder-shown) + label,
      .ui-input.filled label {
        top: 5px;
        left: 10px;
        transform: none;
        font-size: 12px;
        color: $grey;
      }
      .rules {
        display: flex;
        align-items: center;
        gap: 5px;
        font-size: 14px;
        a {
          color: $fg;
        }
      }
      .btn.confirm {
        height: 40px;
        font-size: 16px;
      }
      .btn.ghost {
        height: 40px;
        border: none;
        background-color: $lead;
        color: $fg;
        font-size: 14px;
        cursor: pointer;
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
.auth-modal-enter-from .auth-modal,
.auth-modal-leave-to .auth-modal {
  transform: translateY(-30px);
}

@media (max-width: 1280px) {
  .auth-overlay {
    .auth-modal {
      header {
        span {
          font-size: 16px;
        }
        button {
          width: 20px;
          height: 20px;
          img {
            width: 16px;
            height: 16px;
          }
        }
      }
      .auth-body {
        padding: 5px 5px 0;
        .tabs {
          height: 30px;
          .tab {
            height: 20px;
            font-size: 14px;
            &.active {
              height: 30px;
            }
          }
        }
        .form {
          margin-bottom: 5px;
          padding: 5px;
          gap: 10px;
          height: 245px;
        }
        .btn.confirm {
          height: 30px;
          font-size: 14px;
        }
        .btn.ghost {
          height: 30px;
          font-size: 12px;
        }
      }
    }
  }
}
</style>
