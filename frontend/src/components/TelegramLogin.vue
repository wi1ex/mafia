<template>
  <div>
    <div v-if="!auth.pending" id="tg-login"></div>

    <div v-else class="form">
      <div class="title">Завершите профиль</div>
      <input v-model="nick" @blur="onCheck" placeholder="Ник (уникальный)"/>
      <div v-if="ok!==null" class="hint">{{ ok ? 'ник свободен' : 'ник занят' }}</div>
      <input v-model="name" placeholder="Имя"/>
      <button :disabled="!nick || !name || ok===false" @click="onSave">Сохранить</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/store'

const BOT = import.meta.env.VITE_TG_BOT_NAME
const SIZE: 'large' | 'medium' | 'small' = 'large'

const auth = useAuthStore()
const nick = ref('')
const name = ref('')
const ok = ref<boolean|null>(null)

async function onCheck(){ ok.value = await auth.checkNickname(nick.value) }
async function onSave(){ await auth.completeProfile(nick.value, name.value) }

onMounted(() => {
  ;(window as any).telegramAuthCallback = async (user:any) => { await auth.signInWithTelegram(user) }
  const s = document.createElement('script')
  s.async = true
  s.src = 'https://telegram.org/js/telegram-widget.js?19'
  s.setAttribute('data-telegram-login', BOT)
  s.setAttribute('data-size', SIZE)
  s.setAttribute('data-userpic', 'false')
  s.setAttribute('data-onauth', 'telegramAuthCallback(user)')
  document.getElementById('tg-login')?.appendChild(s)
})
</script>

<style lang="scss" scoped>
.form{margin-top:12px;display:flex;flex-direction:column;gap:8px}
.title{color:var(--fg)}
input{padding:8px;border-radius:8px;border:1px solid #334155;color:#e5e7eb;background:#0b0f14}
button{padding:8px 12px;border-radius:8px;background:var(--color-primary);border:none;cursor:pointer}
.hint{font-size:12px;color:var(--muted)}
</style>
