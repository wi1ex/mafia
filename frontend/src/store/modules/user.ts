import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/services/axios'

export interface UserProfile {
  id: number
  username?: string
  avatar_name?: string | null
  role: string
  telegram_verified?: boolean
  password_temp?: boolean
  protected_user?: boolean
  hotkeys_visible?: boolean
  tg_invites_enabled?: boolean
  timeout_until?: string | null
  suspend_until?: string | null
  ban_active?: boolean
}

export const useUserStore = defineStore('user', () => {
  const user = ref<UserProfile | null>(null)
  const now = ref(Date.now())
  let clock: number | undefined

  async function fetchMe(): Promise<void> {
    const { data } = await api.get<UserProfile>('/users/profile_info')
    user.value = data
  }

  async function updateUiPrefs(payload: { hotkeys_visible?: boolean; tg_invites_enabled?: boolean }): Promise<void> {
    const { data } = await api.patch<{ hotkeys_visible: boolean; tg_invites_enabled: boolean }>('/users/ui_prefs', payload)
    if (!user.value) return
    user.value.hotkeys_visible = data.hotkeys_visible
    user.value.tg_invites_enabled = data.tg_invites_enabled
  }

  function updateStoredRoomTitle(id: number, name: string) {
    const trimmed = (name || '').trim()
    const nick = trimmed || (Number.isFinite(id) ? `user${id}` : 'user')
    const title = `Комната ${nick}`
    try {
      const raw = localStorage.getItem('room:lastRoom')
      const payload = raw ? JSON.parse(raw) as Record<string, unknown> : {}
      payload.title = title
      localStorage.setItem('room:lastRoom', JSON.stringify(payload))
    } catch {}
  }
  function setUsername(name: string) {
    if (!user.value) return
    user.value.username = name
    updateStoredRoomTitle(user.value.id, name)
  }

  function setAvatarName(name: string | null) { if (user.value) user.value.avatar_name = name }

  function setSanctions(payload: { timeout_until?: string | null; suspend_until?: string | null; ban_active?: boolean }) {
    if (!user.value) return
    if ("timeout_until" in payload) user.value.timeout_until = payload.timeout_until ?? null
    if ("suspend_until" in payload) user.value.suspend_until = payload.suspend_until ?? null
    if ("ban_active" in payload) user.value.ban_active = Boolean(payload.ban_active)
  }

  function ensureClock() {
    if (clock) return
    clock = window.setInterval(() => { now.value = Date.now() }, 1000)
  }

  const timeoutUntilMs = computed(() => {
    const raw = user.value?.timeout_until
    if (!raw) return 0
    const ts = Date.parse(raw)
    return Number.isFinite(ts) ? ts : 0
  })
  const suspendUntilMs = computed(() => {
    const raw = user.value?.suspend_until
    if (!raw) return 0
    const ts = Date.parse(raw)
    return Number.isFinite(ts) ? ts : 0
  })
  const timeoutRemainingMs = computed(() => {
    if (!timeoutUntilMs.value) return 0
    return Math.max(0, timeoutUntilMs.value - now.value)
  })
  const suspendRemainingMs = computed(() => {
    if (!suspendUntilMs.value) return 0
    return Math.max(0, suspendUntilMs.value - now.value)
  })
  const timeoutActive = computed(() => timeoutRemainingMs.value > 0)
  const suspendActive = computed(() => suspendRemainingMs.value > 0)
  const banActive = computed(() => Boolean(user.value?.ban_active))
  const telegramVerified = computed(() => Boolean(user.value?.telegram_verified))
  const passwordTemp = computed(() => Boolean(user.value?.password_temp))
  const roomRestricted = computed(() => banActive.value || timeoutActive.value)
  const hotkeysVisible = computed(() => user.value?.hotkeys_visible ?? true)
  const tgInvitesEnabled = computed(() => user.value?.tg_invites_enabled ?? true)

  async function setHotkeysVisible(next: boolean): Promise<void> {
    const prev = user.value?.hotkeys_visible
    if (user.value) user.value.hotkeys_visible = next
    try { await updateUiPrefs({ hotkeys_visible: next }) }
    catch {
      if (user.value && prev !== undefined) user.value.hotkeys_visible = prev
    }
  }

  async function setTgInvitesEnabled(next: boolean): Promise<void> {
    const prev = user.value?.tg_invites_enabled
    if (user.value) user.value.tg_invites_enabled = next
    try { await updateUiPrefs({ tg_invites_enabled: next }) }
    catch {
      if (user.value && prev !== undefined) user.value.tg_invites_enabled = prev
    }
  }

  function clear(): void {
    user.value = null
  }

  return {
    user,
    now,
    timeoutRemainingMs,
    suspendRemainingMs,
    timeoutActive,
    suspendActive,
    banActive,
    telegramVerified,
    passwordTemp,
    roomRestricted,
    hotkeysVisible,
    tgInvitesEnabled,
    fetchMe,
    updateUiPrefs,
    setUsername,
    setAvatarName,
    setSanctions,
    setHotkeysVisible,
    setTgInvitesEnabled,
    ensureClock,
    clear,
  }
})
