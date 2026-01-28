import { defineStore } from 'pinia'
import { ref } from 'vue'

export const HOTKEY_HINTS_LS_KEY = 'ui:hotkeys'

let hotkeysInit = false

export const useUiStore = defineStore('ui', () => {
  const hotkeysVisible = ref(true)

  function initHotkeys(): void {
    if (hotkeysInit) return
    hotkeysInit = true
    if (typeof window === 'undefined') return
    try {
      const raw = window.localStorage.getItem(HOTKEY_HINTS_LS_KEY)
      if (raw === '0' || raw === '1') {
        hotkeysVisible.value = raw === '1'
      } else {
        hotkeysVisible.value = true
        window.localStorage.setItem(HOTKEY_HINTS_LS_KEY, '1')
      }
    } catch {}
    window.addEventListener('storage', (e: StorageEvent) => {
      if (e.key !== HOTKEY_HINTS_LS_KEY) return
      hotkeysVisible.value = e.newValue !== '0'
    })
  }

  function setHotkeysVisible(next: boolean): void {
    hotkeysVisible.value = next
    if (typeof window === 'undefined') return
    try { window.localStorage.setItem(HOTKEY_HINTS_LS_KEY, next ? '1' : '0') } catch {}
  }

  initHotkeys()

  return {
    hotkeysVisible,
    setHotkeysVisible,
  }
})
