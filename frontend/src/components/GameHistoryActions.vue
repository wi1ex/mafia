<template>
  <span v-if="isAdmin" class="actions-trigger" @pointerdown.stop @click.stop.prevent="openModal">
    Подробности
  </span>

  <Teleport to="body">
    <Transition name="overlay">
      <div v-if="open" class="overlay" @pointerdown.self="armed = true"
           @pointerup.self="armed && closeModal()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <div class="modal" role="dialog" aria-modal="true" :aria-label="`Подробности игры #${gameNumber}`">
          <header class="modal-header">
            <div class="modal-header-main">
              <span>Подробности игры #{{ gameNumber }}</span>
              <div class="editors">
                <div class="editor">
                  <label :for="`game-history-result-${gameId}`">Исход игры</label>
                  <div ref="resultRoot" class="ui-select" :class="{ open: resultOpen }">
                    <button type="button" :disabled="loading || savingResult || savingPpk" :aria-expanded="resultOpen" aria-label="Выбрать исход игры" @click="toggleResultDd">
                      <span>{{ selectedResultLabel }}</span>
                      <img :src="iconArrowDown" alt="arrow" />
                    </button>
                    <Transition name="menu">
                      <ul v-show="resultOpen" :data-open="resultOpen ? 1 : 0" role="listbox">
                        <li v-for="option in RESULT_OPTIONS" :key="option.value" class="option"
                            :aria-selected="option.value === selectedResult" :class="{ selected: option.value === selectedResult }"
                            @click="selectResult(option.value)">
                          <span>{{ option.label }}</span>
                          <img v-if="option.value === selectedResult" :src="iconReadyGreen" alt="ready" />
                        </li>
                      </ul>
                    </Transition>
                  </div>
                  <span v-if="savingResult" class="editor-status">Сохраняем...</span>
                  <span v-else-if="saveError" class="editor-status editor-status--error">{{ saveError }}</span>
                </div>

                <div class="editor">
                  <label :for="`game-history-ppk-${gameId}`">ППК</label>
                  <div ref="ppkRoot" class="ui-select" :class="{ open: ppkOpen }">
                    <button type="button" :disabled="ppkSelectDisabled" :aria-expanded="ppkOpen" aria-label="Выбрать ППК" @click="togglePpkDd">
                      <span>{{ selectedPpkLabel }}</span>
                      <img :src="iconArrowDown" alt="arrow" />
                    </button>
                    <Transition name="menu">
                      <ul v-show="ppkOpen" :data-open="ppkOpen ? 1 : 0" role="listbox">
                        <li v-for="option in ppkOptions" :key="option.key" class="option"
                            :aria-selected="option.value === selectedPpkUserId" :class="{ selected: option.value === selectedPpkUserId }"
                            @click="selectPpk(option.value)">
                          <span>{{ option.label }}</span>
                          <img v-if="option.value === selectedPpkUserId" :src="iconReadyGreen" alt="ready" />
                        </li>
                      </ul>
                    </Transition>
                  </div>
                  <span v-if="savingPpk" class="editor-status">Сохраняем...</span>
                  <span v-else-if="ppkSaveError" class="editor-status editor-status--error">{{ ppkSaveError }}</span>
                  <span v-else-if="ppkHint" class="editor-status">{{ ppkHint }}</span>
                </div>
              </div>
            </div>
            <button class="icon" type="button" aria-label="Закрыть" @click="closeModal">
              <img :src="iconClose" alt="close" />
            </button>
          </header>

          <div class="modal-body">
            <div v-if="loading" class="state">Загрузка игровых действий...</div>
            <div v-else-if="error" class="state state-error">{{ error }}</div>
            <div v-else-if="items.length === 0" class="state">Игровые действия не найдены</div>

            <div v-else class="actions-list">
              <article v-for="action in items" :key="`${gameId}-${action.order}-${action.type}`" class="action-card">
                <div class="action-head">
                  <div class="action-head-main">
                    <span class="action-order">#{{ action.order }}</span>
                    <span class="action-title">{{ action.title }}</span>
                  </div>
                  <div class="action-head-meta">
                    <span class="action-type">{{ action.type }}</span>
                    <span v-if="action.occurred_at">{{ formatOccurredAt(action.occurred_at) }}</span>
                  </div>
                </div>

                <p class="action-summary">{{ action.summary }}</p>

                <div v-if="action.fields.length > 0" class="action-fields">
                  <div v-for="field in action.fields" :key="`${action.order}-${field.label}`" class="action-field">
                    <span class="field-label">{{ field.label }}</span>
                    <span class="field-value">{{ field.value }}</span>
                  </div>
                </div>
              </article>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { formatLocalDateTime } from '@/services/datetime'
import { useUserStore } from '@/store'

import iconClose from '@/assets/svg/close.svg'
import iconReadyGreen from '@/assets/svg/readyGreen.svg'
import iconArrowDown from '@/assets/svg/arrowDown.svg'

interface AdminGameActionField {
  label: string
  value: string
}

interface AdminGameActionItem {
  order: number
  type: string
  occurred_at?: string | null
  title: string
  summary: string
  fields: AdminGameActionField[]
}

type GameHistoryRole = 'citizen' | 'mafia' | 'don' | 'sheriff'
type LeaveReason = 'vote' | 'foul' | 'suicide' | 'night'
type GameResult = 'red' | 'black' | 'draw'

interface GameHistorySlot {
  slot: number
  user_id?: number | null
  username?: string | null
  role?: GameHistoryRole | null
  leave_reason?: LeaveReason | null
  leave_ppk?: boolean | null
}

interface AdminGameActionsResponse {
  id: number
  number: number
  result: GameResult
  ppk_target_user_id?: number | null
  items: AdminGameActionItem[]
}

interface AdminGameResultResponse {
  id: number
  number: number
  result: GameResult
}

interface AdminGamePpkResponse {
  id: number
  number: number
  target_user_id?: number | null
}

const props = defineProps<{
  gameId: number
  gameNumber: number
  gameResult: GameResult
  detailsSlots?: GameHistorySlot[]
  detailsLoading?: boolean
}>()

const emit = defineEmits<{
  (e: 'result-updated', payload: { gameId: number; result: GameResult; previousResult: GameResult }): void
  (e: 'ppk-updated', payload: { gameId: number; userId: number | null; previousUserId: number | null }): void
}>()

const userStore = useUserStore()
const isAdmin = computed(() => userStore.user?.role === 'admin')

const open = ref(false)
const armed = ref(false)
const loading = ref(false)
const error = ref('')
const items = ref<AdminGameActionItem[]>([])
const loaded = ref(false)
const selectedResult = ref<GameResult>(normalizeGameResult(props.gameResult))
const savedResult = ref<GameResult>(normalizeGameResult(props.gameResult))
const savingResult = ref(false)
const saveError = ref('')
const resultOpen = ref(false)
const resultRoot = ref<HTMLElement | null>(null)
const selectedPpkUserId = ref<number | null>(null)
const savedPpkUserId = ref<number | null>(null)
const savingPpk = ref(false)
const ppkSaveError = ref('')
const ppkOpen = ref(false)
const ppkRoot = ref<HTMLElement | null>(null)

let suppressNextDocClick = false

const DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
}

const RESULT_OPTIONS: Array<{ value: GameResult; label: string }> = [
  { value: 'red', label: 'Победа мирных' },
  { value: 'black', label: 'Победа мафии' },
  { value: 'draw', label: 'Ничья' },
]

const selectedResultLabel = computed(() => RESULT_OPTIONS.find((option) => option.value === selectedResult.value)?.label || '')
const ppkPlayerOptions = computed<Array<{ key: string; value: number; label: string }>>(() => {
  const slots = Array.isArray(props.detailsSlots) ? [...props.detailsSlots] : []
  slots.sort((left, right) => normalizeSlotNumber(left.slot) - normalizeSlotNumber(right.slot))

  const out: Array<{ key: string; value: number; label: string }> = []
  const seen = new Set<number>()
  for (const slot of slots) {
    if (slot.leave_reason !== 'foul') continue
    const userId = normalizeOptionalUserId(slot.user_id)
    if (userId === null || seen.has(userId)) continue
    seen.add(userId)
    out.push({
      key: String(userId),
      value: userId,
      label: formatPpkOptionLabel(slot),
    })
  }
  return out
})
const ppkOptions = computed<Array<{ key: string; value: number | null; label: string }>>(() => (
  [{ key: 'none', value: null, label: 'Без ППК' }, ...ppkPlayerOptions.value]
))
const selectedPpkLabel = computed(() => {
  if (selectedPpkUserId.value === null) return 'Без ППК'
  const fromOptions = ppkOptions.value.find((option) => option.value === selectedPpkUserId.value)
  if (fromOptions) return fromOptions.label
  const slot = findSlotByUserId(selectedPpkUserId.value)
  if (slot) return formatPpkOptionLabel(slot)
  return `user${selectedPpkUserId.value}`
})
const ppkSelectDisabled = computed(() => {
  if (loading.value || savingResult.value || savingPpk.value) return true
  return ppkOptions.value.length <= 1 && selectedPpkUserId.value === null
})
const ppkHint = computed(() => {
  if (savingPpk.value || ppkSaveError.value) return ''
  if (props.detailsLoading) return 'Загружаем игроков...'
  if (ppkOptions.value.length <= 1 && selectedPpkUserId.value === null) return 'В этой игре нет удалений по фолам'
  return ''
})

function normalizeGameResult(raw: unknown): GameResult {
  if (raw === 'red' || raw === 'black' || raw === 'draw') return raw
  return 'draw'
}

function normalizeOptionalUserId(raw: unknown): number | null {
  const value = Number(raw)
  if (!Number.isFinite(value)) return null
  const normalized = Math.trunc(value)
  return normalized > 0 ? normalized : null
}

function normalizeSlotNumber(raw: unknown): number {
  const value = Number(raw)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.trunc(value))
}

function findSlotByUserId(userId: number | null): GameHistorySlot | null {
  if (userId === null) return null
  const slots = Array.isArray(props.detailsSlots) ? props.detailsSlots : []
  for (const slot of slots) {
    if (normalizeOptionalUserId(slot.user_id) === userId) return slot
  }
  return null
}

function formatPpkOptionLabel(slot: GameHistorySlot): string {
  const seat = normalizeSlotNumber(slot.slot)
  const username = String(slot.username || '').trim()
  if (username) return `${seat} · ${username}`
  return `Игрок ${seat}`
}

function applyActionsPayload(data: AdminGameActionsResponse | undefined): void {
  const result = normalizeGameResult(data?.result)
  selectedResult.value = result
  savedResult.value = result
  selectedPpkUserId.value = normalizeOptionalUserId(data?.ppk_target_user_id)
  savedPpkUserId.value = normalizeOptionalUserId(data?.ppk_target_user_id)
  saveError.value = ''
  ppkSaveError.value = ''
  items.value = normalizeItems(data?.items)
}

function closeModal(): void {
  armed.value = false
  closeResultDropdown()
  closePpkDropdown()
  open.value = false
}

function toggleResultDd(): void {
  if (loading.value || savingResult.value || savingPpk.value) return
  closePpkDropdown()
  resultOpen.value = !resultOpen.value
}

function closeResultDropdown(): void {
  resultOpen.value = false
}

function togglePpkDd(): void {
  if (ppkSelectDisabled.value) return
  closeResultDropdown()
  ppkOpen.value = !ppkOpen.value
}

function closePpkDropdown(): void {
  ppkOpen.value = false
}

function selectResult(value: GameResult): void {
  closeResultDropdown()
  if (savingResult.value || savingPpk.value || value === selectedResult.value) return
  selectedResult.value = value
  void onResultChange()
}

function selectPpk(value: number | null): void {
  closePpkDropdown()
  if (savingResult.value || savingPpk.value || value === selectedPpkUserId.value) return
  selectedPpkUserId.value = value
  void onPpkChange()
}

function normalizeItems(raw: unknown): AdminGameActionItem[] {
  if (!Array.isArray(raw)) return []
  const out: AdminGameActionItem[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const fieldsRaw = Array.isArray((item as any).fields) ? (item as any).fields : []
    const fields: AdminGameActionField[] = []
    for (const field of fieldsRaw) {
      if (!field || typeof field !== 'object') continue
      const label = String((field as any).label || '').trim()
      const value = String((field as any).value || '').trim()
      if (!label || !value) continue
      fields.push({ label, value })
    }
    out.push({
      order: Math.max(1, Number((item as any).order) || 0),
      type: String((item as any).type || '').trim() || 'unknown',
      occurred_at: (item as any).occurred_at ? String((item as any).occurred_at) : null,
      title: String((item as any).title || '').trim() || 'Событие',
      summary: String((item as any).summary || '').trim(),
      fields,
    })
  }
  return out.sort((a, b) => a.order - b.order)
}

async function fetchActionsPayload(): Promise<AdminGameActionsResponse> {
  const { data } = await api.get<AdminGameActionsResponse>(`/admin/games/${props.gameId}/actions`)
  return data
}

async function loadActions(force = false): Promise<void> {
  if (loading.value || (loaded.value && !force)) return
  loading.value = true
  error.value = ''
  try {
    const data = await fetchActionsPayload()
    applyActionsPayload(data)
    loaded.value = true
  } catch (e: any) {
    const status = Number(e?.response?.status || 0)
    error.value = status === 404 ? 'Игра не найдена' : 'Не удалось загрузить игровые действия'
  } finally {
    loading.value = false
  }
}

async function refreshActionsQuietly(): Promise<void> {
  try {
    const data = await fetchActionsPayload()
    applyActionsPayload(data)
    loaded.value = true
  } catch {}
}

function openModal(): void {
  if (!isAdmin.value) return
  armed.value = false
  saveError.value = ''
  ppkSaveError.value = ''
  closeResultDropdown()
  closePpkDropdown()
  open.value = true
  void loadActions()
}

async function onResultChange(): Promise<void> {
  const nextResult = normalizeGameResult(selectedResult.value)
  const previousResult = savedResult.value
  saveError.value = ''
  if (savingResult.value || savingPpk.value || nextResult === previousResult) return

  savingResult.value = true
  try {
    const { data } = await api.patch<AdminGameResultResponse>(`/admin/games/${props.gameId}/result`, {
      result: nextResult,
    })
    const actualResult = normalizeGameResult(data?.result)
    selectedResult.value = actualResult
    savedResult.value = actualResult
    emit('result-updated', {
      gameId: props.gameId,
      result: actualResult,
      previousResult,
    })
  } catch (e: any) {
    selectedResult.value = previousResult
    const status = Number(e?.response?.status || 0)
    saveError.value = status === 404 ? 'Игра не найдена' : 'Не удалось изменить результат'
  } finally {
    savingResult.value = false
  }
}

async function onPpkChange(): Promise<void> {
  const nextUserId = selectedPpkUserId.value
  const previousUserId = savedPpkUserId.value
  ppkSaveError.value = ''
  if (savingResult.value || savingPpk.value || nextUserId === previousUserId) return

  savingPpk.value = true
  try {
    const { data } = await api.patch<AdminGamePpkResponse>(`/admin/games/${props.gameId}/ppk`, {
      target_user_id: nextUserId,
    })
    const actualUserId = normalizeOptionalUserId(data?.target_user_id)
    selectedPpkUserId.value = actualUserId
    savedPpkUserId.value = actualUserId
    emit('ppk-updated', {
      gameId: props.gameId,
      userId: actualUserId,
      previousUserId,
    })
    void refreshActionsQuietly()
  } catch (e: any) {
    selectedPpkUserId.value = previousUserId
    const status = Number(e?.response?.status || 0)
    const code = String(e?.response?.data?.detail || '')
    if (status === 404) {
      ppkSaveError.value = 'Игра не найдена'
    } else if (status === 409 && code === 'ppk_target_not_foul_removed') {
      ppkSaveError.value = 'ППК можно переназначить только игроку, удалённому по фолам'
    } else {
      ppkSaveError.value = 'Не удалось изменить ППК'
    }
  } finally {
    savingPpk.value = false
  }
}

function formatOccurredAt(value: string): string {
  return formatLocalDateTime(value, DATE_OPTIONS)
}

function onDocPointerDown(ev: PointerEvent): void {
  const target = ev.target as Node | null
  const clickedOutsideResult = resultOpen.value && resultRoot.value && target && !resultRoot.value.contains(target)
  const clickedOutsidePpk = ppkOpen.value && ppkRoot.value && target && !ppkRoot.value.contains(target)
  if (!clickedOutsideResult && !clickedOutsidePpk) return
  closeResultDropdown()
  closePpkDropdown()
  suppressNextDocClick = true
  ev.stopPropagation?.()
}

function onDocClickCapture(ev: MouseEvent): void {
  if (!suppressNextDocClick) return
  ev.stopPropagation()
  suppressNextDocClick = false
}

watch(
  () => props.gameResult,
  (value) => {
    const normalized = normalizeGameResult(value)
    if (savingResult.value) return
    selectedResult.value = normalized
    savedResult.value = normalized
    saveError.value = ''
  },
)

watch(open, (value) => {
  if (!value) {
    closeResultDropdown()
    closePpkDropdown()
  }
})

onMounted(() => {
  document.addEventListener('pointerdown', onDocPointerDown, { capture: true })
  document.addEventListener('click', onDocClickCapture, { capture: true })
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocPointerDown, { capture: true } as AddEventListenerOptions)
  document.removeEventListener('click', onDocClickCapture, { capture: true } as AddEventListenerOptions)
})
</script>

<style scoped lang="scss">
.actions-trigger {
  display: inline-flex;
  align-items: center;
  color: $orange;
  font-size: 12px;
  line-height: 1;
  text-decoration: underline;
  cursor: pointer;
  transition: opacity 0.25s ease-in-out;
}
.overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba($black, 0.25);
  backdrop-filter: blur(5px);
  z-index: 1100;
  .modal {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: min(980px, calc(100% - 30px));
    max-height: calc(100vh - 40px);
    padding: 10px;
    border-radius: 5px;
    background-color: $graphite;
    box-sizing: border-box;
    .modal-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
      .modal-header-main {
        display: flex;
        flex-direction: column;
        gap: 10px;
        min-width: 0;
        span {
          color: $fg;
          font-size: 18px;
          font-family: Manrope-Medium;
        }
      }
      .editors {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        .editor {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 5px;
          width: min(320px, 100%);
          label {
            color: $grey;
            font-size: 13px;
            line-height: 1.2;
          }
          .ui-select {
            position: relative;
            width: 100%;
            box-shadow: 3px 3px 5px rgba($black, 0.25);
            button {
              display: flex;
              align-items: center;
              justify-content: space-between;
              width: 100%;
              height: 30px;
              border: 1px solid $lead;
              border-radius: 5px;
              background-color: $dark;
              padding: 0 10px;
              cursor: pointer;
              transition: background-color 0.25s ease-in-out;
              &:hover {
                background-color: $graphite;
              }
              &:disabled {
                opacity: 0.65;
                cursor: not-allowed;
              }
              span {
                height: 16px;
                color: $fg;
                font-size: 14px;
                font-family: Manrope-Medium;
                line-height: 1;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
              }
              img {
                width: 15px;
                height: 15px;
              }
            }
            ul {
              position: absolute;
              z-index: 30;
              bottom: 0;
              margin: 0;
              padding: 0;
              width: calc(100% - 2px);
              border: 1px solid $lead;
              border-radius: 5px;
              background-color: $graphite;
              transform-origin: bottom;
              list-style: none;
              &[data-open="0"] {
                pointer-events: none;
              }
              .option {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                padding: 10px;
                cursor: pointer;
                transition: background-color 0.25s ease-in-out;
                &:hover {
                  background-color: $lead;
                }
                span {
                  height: 16px;
                  color: $fg;
                  font-size: 14px;
                  white-space: nowrap;
                  overflow: hidden;
                  text-overflow: ellipsis;
                }
                img {
                  width: 15px;
                  height: 15px;
                }
              }
              .option.selected {
                background-color: $lead;
              }
            }
          }
          .editor-status {
            color: $ashy;
            font-size: 12px;
            line-height: 1.2;
            &.editor-status--error {
              color: $orange;
            }
          }
        }
      }
      .icon {
        flex: 0 0 auto;
        width: 25px;
        height: 25px;
        border: none;
        background: none;
        cursor: pointer;
        img {
          width: 20px;
          height: 20px;
        }
      }
    }
    .modal-body {
      overflow: auto;
      .state {
        padding: 30px 10px;
        color: $ashy;
        text-align: center;
        &.state-error {
          color: $orange;
        }
      }
      .actions-list {
        display: flex;
        flex-direction: column;
        gap: 10px;
        .action-card {
          display: flex;
          flex-direction: column;
          gap: 10px;
          padding: 10px;
          border: 1px solid rgba($grey, 0.25);
          border-radius: 5px;
          background-color: rgba($lead, 0.75);
          .action-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 10px;
            .action-head-main {
              display: flex;
              align-items: center;
              flex-wrap: wrap;
              gap: 10px;
              .action-order {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 30px;
                height: 25px;
                padding: 0 5px;
                border-radius: 5px;
                background-color: $fg;
                color: $bg;
                font-size: 12px;
                font-family: Manrope-SemiBold;
              }
              .action-title {
                color: $fg;
                font-size: 16px;
                font-family: Manrope-SemiBold;
              }
            }
            .action-head-meta {
              display: flex;
              flex-direction: column;
              align-items: flex-end;
              gap: 5px;
              color: $ashy;
              font-size: 12px;
              text-align: right;
              .action-type {
                color: $orange;
                text-transform: lowercase;
              }
            }
          }
          .action-summary {
            margin: 0;
            color: $fg;
            font-size: 14px;
            line-height: 1.2;
          }
          .action-fields {
            display: grid;
            grid-template-columns: repeat(7, minmax(0, 1fr));
            gap: 5px 10px;
            .action-field {
              display: flex;
              flex-direction: column;
              gap: 5px;
              padding: 10px;
              border-radius: 5px;
              background-color: rgba($dark, 0.5);
              .field-label {
                color: $grey;
                font-size: 12px;
                line-height: 1.2;
              }
              .field-value {
                color: $fg;
                font-size: 14px;
                line-height: 1.2;
                word-break: break-word;
                white-space: pre-wrap;
              }
            }
          }
        }
      }
    }
  }
}

.overlay-enter-active,
.overlay-leave-active {
  transition: opacity 0.25s ease-in-out;
}

.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}

.menu-enter-active,
.menu-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
  will-change: opacity, transform;
}

.menu-enter-from,
.menu-leave-to {
  opacity: 0;
  transform: translateY(30px);
}
</style>
