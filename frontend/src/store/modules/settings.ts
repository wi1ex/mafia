import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/services/axios'

export interface PublicSettings {
  registration_enabled: boolean
  rooms_can_create: boolean
  games_can_start: boolean
}

export const useSettingsStore = defineStore('settings', () => {
  const registrationEnabled = ref(true)
  const roomsCanCreate = ref(true)
  const gamesCanStart = ref(true)
  const ready = ref(false)

  function applyPublic(data: PublicSettings) {
    registrationEnabled.value = Boolean(data.registration_enabled)
    roomsCanCreate.value = Boolean(data.rooms_can_create)
    gamesCanStart.value = Boolean(data.games_can_start)
  }

  async function fetchPublic(): Promise<void> {
    try {
      const { data } = await api.get<PublicSettings>('/admin/settings/public', { __skipAuth: true })
      applyPublic(data)
    } finally {
      ready.value = true
    }
  }

  return {
    registrationEnabled,
    roomsCanCreate,
    gamesCanStart,
    ready,

    fetchPublic,
    applyPublic,
  }
})
