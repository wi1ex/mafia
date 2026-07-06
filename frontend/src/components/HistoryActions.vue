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
                  <select
                    :id="`game-history-result-${gameId}`"
                    :value="selectedResult"
                    aria-label="Выбрать исход игры"
                    :disabled="loading || savingResult || savingPpk || savingFoulRemovals"
                    @change="selectResult"
                  >
                    <option v-for="option in RESULT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                  </select>
                  <span v-if="savingResult" class="editor-status">Сохраняем...</span>
                  <span v-else-if="saveError" class="editor-status editor-status--error">{{ saveError }}</span>
                </div>

                <div class="editor">
                  <label :for="`game-history-ppk-${gameId}`">ППК</label>
                  <select
                    :id="`game-history-ppk-${gameId}`"
                    :value="selectedPpkUserId ?? ''"
                    aria-label="Выбрать ППК"
                    :disabled="ppkSelectDisabled"
                    @change="selectPpk"
                  >
                    <option v-for="option in ppkOptions" :key="option.key" :value="option.value ?? ''">{{ option.label }}</option>
                  </select>
                  <span v-if="savingPpk" class="editor-status">Сохраняем...</span>
                  <span v-else-if="ppkSaveError" class="editor-status editor-status--error">{{ ppkSaveError }}</span>
                  <span v-else-if="ppkHint" class="editor-status">{{ ppkHint }}</span>
                </div>
              </div>

              <div class="foul-removal-editor">
                <div class="foul-removal-head">
                  <span>Удаление по фолам</span>
                  <small v-if="savingFoulRemovals">Сохраняем...</small>
                  <small v-else-if="foulRemovalSaveError" class="editor-status--error">{{ foulRemovalSaveError }}</small>
                  <small v-else-if="foulRemovalHint">{{ foulRemovalHint }}</small>
                </div>
                <div v-if="foulRemovalPlayerOptions.length > 0" class="foul-removal-grid">
                  <label v-for="option in foulRemovalPlayerOptions" :key="option.key" class="foul-removal-option">
                    <input
                      type="checkbox"
                      :checked="isFoulRemovalChecked(option.value)"
                      :disabled="foulRemovalControlsDisabled"
                      @change="toggleFoulRemoval($event, option.value)"
                    />
                    <span>{{ option.label }}</span>
                  </label>
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
import { computed, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { formatLocalDateTime } from '@/services/datetime'
import { useUserStore } from '@/store'

import iconClose from '@/assets/svg/iconClose.svg'

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

interface AdminGameFoulRemovalsResponse {
  id: number
  number: number
  removed_user_ids?: number[] | null
  ppk_target_user_id?: number | null
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
  (e: 'foul-removals-updated', payload: { gameId: number; removedUserIds: number[]; previousRemovedUserIds: number[]; ppkUserId: number | null; previousPpkUserId: number | null }): void
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
const selectedPpkUserId = ref<number | null>(null)
const savedPpkUserId = ref<number | null>(null)
const savingPpk = ref(false)
const ppkSaveError = ref('')
const selectedFoulRemovalUserIds = ref<number[]>([])
const savedFoulRemovalUserIds = ref<number[]>([])
const savingFoulRemovals = ref(false)
const foulRemovalSaveError = ref('')

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
  buildPpkOptions()
))
const ppkSelectDisabled = computed(() => {
  if (loading.value || savingResult.value || savingPpk.value || savingFoulRemovals.value) return true
  return ppkOptions.value.length <= 1 && selectedPpkUserId.value === null
})
const ppkHint = computed(() => {
  if (savingPpk.value || ppkSaveError.value) return ''
  if (props.detailsLoading) return 'Загружаем игроков...'
  if (ppkOptions.value.length <= 1 && selectedPpkUserId.value === null) return 'В этой игре нет удалений по фолам'
  return ''
})

const foulRemovalPlayerOptions = computed<Array<{ key: string; value: number; label: string }>>(() => {
  const slots = Array.isArray(props.detailsSlots) ? [...props.detailsSlots] : []
  slots.sort((left, right) => normalizeSlotNumber(left.slot) - normalizeSlotNumber(right.slot))

  const out: Array<{ key: string; value: number; label: string }> = []
  const seen = new Set<number>()
  for (const slot of slots) {
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
const foulRemovalControlsDisabled = computed(() => (
  loading.value || savingResult.value || savingPpk.value || savingFoulRemovals.value || Boolean(props.detailsLoading)
))
const foulRemovalHint = computed(() => {
  if (savingFoulRemovals.value || foulRemovalSaveError.value) return ''
  if (props.detailsLoading) return 'Загружаем игроков...'
  if (foulRemovalPlayerOptions.value.length === 0) return 'Игроки не загружены'
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

function normalizeUserIdList(raw: unknown): number[] {
  if (!Array.isArray(raw)) return []
  const out: number[] = []
  const seen = new Set<number>()
  for (const item of raw) {
    const userId = normalizeOptionalUserId(item)
    if (userId === null || seen.has(userId)) continue
    seen.add(userId)
    out.push(userId)
  }
  return out.sort((left, right) => left - right)
}

function sameUserIdList(left: number[], right: number[]): boolean {
  if (left.length !== right.length) return false
  return left.every((value, index) => value === right[index])
}

function currentFoulRemovalUserIds(): number[] {
  const slots = Array.isArray(props.detailsSlots) ? props.detailsSlots : []
  return normalizeUserIdList(
    slots
      .filter((slot) => slot.leave_reason === 'foul')
      .map((slot) => slot.user_id),
  )
}

function buildPpkOptions(): Array<{ key: string; value: number | null; label: string }> {
  const options: Array<{ key: string; value: number | null; label: string }> = [
    { key: 'none', value: null, label: 'Без ППК' },
    ...ppkPlayerOptions.value,
  ]
  const selected = selectedPpkUserId.value
  if (selected !== null && !options.some((option) => option.value === selected)) {
    const slot = (Array.isArray(props.detailsSlots) ? props.detailsSlots : [])
      .find((item) => normalizeOptionalUserId(item.user_id) === selected)
    options.push({
      key: `current-${selected}`,
      value: selected,
      label: slot ? formatPpkOptionLabel(slot) : `user${selected}`,
    })
  }
  return options
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
  foulRemovalSaveError.value = ''
  items.value = normalizeItems(data?.items)
}

function closeModal(): void {
  armed.value = false
  open.value = false
}

function selectValue(event: Event): string {
  return (event.target as HTMLSelectElement).value
}

function selectResult(event: Event): void {
  const next = normalizeGameResult(selectValue(event))
  if (savingResult.value || savingPpk.value || savingFoulRemovals.value || next === selectedResult.value) return
  selectedResult.value = next
  void onResultChange()
}

function selectPpk(event: Event): void {
  const next = normalizeOptionalUserId(selectValue(event))
  if (savingResult.value || savingPpk.value || savingFoulRemovals.value || next === selectedPpkUserId.value) return
  selectedPpkUserId.value = next
  void onPpkChange()
}

function isFoulRemovalChecked(userId: number): boolean {
  return selectedFoulRemovalUserIds.value.includes(userId)
}

function toggleFoulRemoval(event: Event, userId: number): void {
  const normalizedUserId = normalizeOptionalUserId(userId)
  if (normalizedUserId === null || foulRemovalControlsDisabled.value) return

  const checked = Boolean((event.target as HTMLInputElement).checked)
  const next = new Set(selectedFoulRemovalUserIds.value)
  if (checked) next.add(normalizedUserId)
  else next.delete(normalizedUserId)
  selectedFoulRemovalUserIds.value = normalizeUserIdList([...next])
  void onFoulRemovalsChange()
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
  foulRemovalSaveError.value = ''
  open.value = true
  void loadActions()
}

async function onResultChange(): Promise<void> {
  const nextResult = normalizeGameResult(selectedResult.value)
  const previousResult = savedResult.value
  saveError.value = ''
  if (savingResult.value || savingPpk.value || savingFoulRemovals.value || nextResult === previousResult) return

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
  if (savingResult.value || savingPpk.value || savingFoulRemovals.value || nextUserId === previousUserId) return

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

async function onFoulRemovalsChange(): Promise<void> {
  const nextUserIds = normalizeUserIdList(selectedFoulRemovalUserIds.value)
  const previousUserIds = normalizeUserIdList(savedFoulRemovalUserIds.value)
  foulRemovalSaveError.value = ''
  if (savingResult.value || savingPpk.value || savingFoulRemovals.value || sameUserIdList(nextUserIds, previousUserIds)) return

  const previousPpkUserId = savedPpkUserId.value
  savingFoulRemovals.value = true
  try {
    const { data } = await api.patch<AdminGameFoulRemovalsResponse>(`/admin/games/${props.gameId}/foul-removals`, {
      removed_user_ids: nextUserIds,
    })
    const actualUserIds = normalizeUserIdList(data?.removed_user_ids)
    const actualPpkUserId = normalizeOptionalUserId(data?.ppk_target_user_id)
    selectedFoulRemovalUserIds.value = actualUserIds
    savedFoulRemovalUserIds.value = actualUserIds
    selectedPpkUserId.value = actualPpkUserId
    savedPpkUserId.value = actualPpkUserId
    emit('foul-removals-updated', {
      gameId: props.gameId,
      removedUserIds: actualUserIds,
      previousRemovedUserIds: previousUserIds,
      ppkUserId: actualPpkUserId,
      previousPpkUserId,
    })
    void refreshActionsQuietly()
  } catch (e: any) {
    selectedFoulRemovalUserIds.value = previousUserIds
    const status = Number(e?.response?.status || 0)
    const code = String(e?.response?.data?.detail || '')
    if (status === 404) {
      foulRemovalSaveError.value = 'Игра не найдена'
    } else if (status === 409 && code === 'foul_removal_target_not_player') {
      foulRemovalSaveError.value = 'Игрок не найден в этой игре'
    } else if (status === 409 && code === 'foul_removal_players_not_found') {
      foulRemovalSaveError.value = 'Игроки не найдены'
    } else {
      foulRemovalSaveError.value = 'Не удалось изменить удаления по фолам'
    }
  } finally {
    savingFoulRemovals.value = false
  }
}

function formatOccurredAt(value: string): string {
  return formatLocalDateTime(value, DATE_OPTIONS)
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

watch(
  () => props.detailsSlots,
  () => {
    if (savingFoulRemovals.value) return
    const nextUserIds = currentFoulRemovalUserIds()
    selectedFoulRemovalUserIds.value = nextUserIds
    savedFoulRemovalUserIds.value = nextUserIds
    foulRemovalSaveError.value = ''
  },
  { immediate: true, deep: true },
)

</script>

<style scoped lang="scss">
.actions-trigger {
  display: inline-flex;
  align-items: center;
  color: $orange-500;
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
  background-color: rgba(black, 0.25);
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
    background-color: $neutral-800;
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
          color: $neutral-100;
          font-size: 18px;
          font-family: Hauora-Regular;
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
            color: $neutral-500;
            font-size: 13px;
            line-height: 1.2;
          }
          .editor-status {
            color: $neutral-300;
            font-size: 12px;
            line-height: 1.2;
            &.editor-status--error {
              color: $orange-500;
            }
          }
        }
      }
      .foul-removal-editor {
        display: flex;
        flex-direction: column;
        gap: 8px;
        width: min(520px, 100%);
        .foul-removal-head {
          display: flex;
          align-items: center;
          gap: 8px;
          span {
            color: $neutral-100;
            font-size: 14px;
            font-family: Hauora-SemiBold;
            line-height: 1.2;
          }
          small {
            color: $neutral-300;
            font-size: 12px;
            line-height: 1.2;
            &.editor-status--error {
              color: $orange-500;
            }
          }
        }
        .foul-removal-grid {
          display: grid;
          grid-template-columns: repeat(5, minmax(0, 1fr));
          gap: 6px;
        }
        .foul-removal-option {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          min-width: 0;
          color: $neutral-100;
          font-size: 12px;
          line-height: 1.2;
          cursor: pointer;
          input {
            flex: 0 0 auto;
            width: 14px;
            height: 14px;
            margin: 0;
          }
          span {
            min-width: 0;
            color: inherit;
            font-size: 12px;
            line-height: 1.2;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
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
        color: $neutral-300;
        text-align: center;
        &.state-error {
          color: $orange-500;
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
          border: 1px solid rgba($neutral-500, 0.25);
          border-radius: 5px;
          background-color: rgba($neutral-700, 0.75);
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
                background-color: $neutral-100;
                color: $neutral-black;
                font-size: 12px;
                font-family: Hauora-SemiBold;
              }
              .action-title {
                color: $neutral-100;
                font-size: 16px;
                font-family: Hauora-SemiBold;
              }
            }
            .action-head-meta {
              display: flex;
              flex-direction: column;
              align-items: flex-end;
              gap: 5px;
              color: $neutral-300;
              font-size: 12px;
              text-align: right;
              .action-type {
                color: $orange-500;
                text-transform: lowercase;
              }
            }
          }
          .action-summary {
            margin: 0;
            color: $neutral-100;
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
              background-color: rgba($neutral-900, 0.5);
              .field-label {
                color: $neutral-500;
                font-size: 12px;
                line-height: 1.2;
              }
              .field-value {
                color: $neutral-100;
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

</style>
