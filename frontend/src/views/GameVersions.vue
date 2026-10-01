<template>
  <Teleport to="#desktop-teleport-root">
    <Transition name="game-versions-overlay">
      <div class="game-versions-overlay" role="dialog" aria-modal="true" aria-labelledby="game-versions-title"
           @pointerdown.self="overlayArmed = true" @pointerup.self="overlayArmed && requestCancel()" @pointerleave.self="overlayArmed = false" @pointercancel.self="overlayArmed = false">
        <section class="game-versions-modal" @click.stop>
          <h2 id="game-versions-title" class="game-versions-modal__title">Версии игры</h2>
          <p v-if="validationError" class="game-versions-modal__error" role="alert">{{ validationError }}</p>

          <div class="game-versions-modal__marks">
            <div v-for="rule in markRules" :key="rule.key" class="scoring-mark">
              <label :for="`scoring-mark-${rule.key}`">{{ rule.label }}</label>
              <select :id="`scoring-mark-${rule.key}`" v-model.number="marks[rule.key]" :disabled="saving">
                <option :value="0">Не отмечен</option>
                <option v-for="player in players" :key="player.id" :value="Number(player.id)">
                  {{ player.label }}
                </option>
              </select>
            </div>
          </div>

          <div class="game-versions-modal__list-header">
            <span>Текущие версии: {{ rows.length }} / {{ maxVersions }}</span>
            <UiButton size="low" text="Добавить версию" :disabled="saving || rows.length >= maxVersions" @click="addVersion" />
          </div>

          <div class="game-versions-modal__list">
            <section v-for="(version, versionIndex) in rows" :key="versionIndex" class="version-card" :class="{ 'version-card--empty': !version.claimantId }">
              <div class="version-card__heading">
                <span>Версия {{ versionIndex + 1 }}</span>
                <UiButton v-if="rows.length > 1" variant="white" size="low" text="Удалить версию" :disabled="saving" @click="removeVersion(versionIndex)" />
                <UiButton v-else-if="version.claimantId" variant="white" size="low" text="Отменить вскрытие" :disabled="saving" @click="cancelVersion(versionIndex)" />
              </div>

              <label :for="`game-version-claimant-${versionIndex}`">Вскрылся шерифом</label>
              <select :id="`game-version-claimant-${versionIndex}`" :value="version.claimantId" :disabled="saving" @change="setClaimant(versionIndex, $event)">
                <option value="">Не отмечен</option>
                <option v-for="player in players" :key="player.id" :value="player.id" :disabled="isClaimantUsed(player.id, versionIndex)">
                  {{ player.label }}
                </option>
              </select>

              <template v-if="version.claimantId">
                <div class="version-card__checks-heading">
                  <span>Проверки</span>
                  <UiButton variant="white" size="low" text="Добавить проверку" :disabled="saving || version.checks.length >= maxChecksPerVersion" @click="addCheck(versionIndex)" />
                </div>

                <div v-for="(check, checkIndex) in version.checks" :key="checkIndex" class="version-check">
                  <select :value="check.targetId" :disabled="saving" :aria-label="`Проверяемый игрок в версии ${versionIndex + 1}`"
                          @change="setCheckTarget(versionIndex, checkIndex, $event)">
                    <option value="">Игрок</option>
                    <option v-for="player in players" :key="player.id" :value="player.id" :disabled="player.id === version.claimantId || isCheckTargetUsed(player.id, versionIndex, checkIndex)">
                      {{ player.label }}
                    </option>
                  </select>
                  <select :value="check.verdict" :disabled="saving" :aria-label="`Результат проверки в версии ${versionIndex + 1}`"
                          @change="setCheckVerdict(versionIndex, checkIndex, $event)">
                    <option value="red">Красный</option>
                    <option value="black">Чёрный</option>
                  </select>
                  <UiButton class="version-check__remove" variant="white" size="low" :icon="iconClose" width="40px" :disabled="saving || version.checks.length <= 1"
                            :aria-label="`Удалить проверку ${checkIndex + 1}`" @click="removeCheck(versionIndex, checkIndex)" />
                </div>
              </template>
            </section>
          </div>

          <footer>
            <UiButton variant="white" size="middle" text="Отменить изменения и закрыть" :disabled="saving" @click="requestCancel" />
            <UiButton size="middle" :text="saving ? 'Сохранение…' : 'Сохранить и закрыть'" :disabled="saving" @click="requestSave" />
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import UiButton from '@/components/UiButton.vue'
import iconClose from '@/assets/svg/iconClose.svg'

type PlayerOption = {
  id: string
  label: string
}

type VersionCheckDraft = {
  targetId: string
  verdict: 'red' | 'black'
}

type VersionDraft = {
  claimantId: string
  checks: VersionCheckDraft[]
}

type VersionPayload = {
  claimant_id: number
  checks: Array<{ target_id: number, verdict: 'red' | 'black' }>
}

const maxVersions = 6
const markRules = [
  { key: 'vote_break_red_to_red', label: 'Красный сломал в красного/шерифа в нуле' },
  { key: 'vote_break_red_to_black', label: 'Красный сломал в черного и не ушел на след день' },
  { key: 'vote_break_black_to_sheriff', label: 'Черный сломал в шерифа' },
]
const maxChecksPerVersion = 10

const props = withDefaults(defineProps<{
  versions?: unknown
  scoringMarks?: Record<string, number>
  players?: PlayerOption[]
  saving?: boolean
}>(), {
  versions: () => [],
  scoringMarks: () => ({}),
  players: () => [],
  saving: false,
})

const emit = defineEmits<{
  cancel: []
  save: [versions: VersionPayload[], scoringMarks: Record<string, number>]
}>()

const rows = ref<VersionDraft[]>(emptyRows())
const marks = ref<Record<string, number>>({})
watch(() => props.scoringMarks, (value) => {
  marks.value = Object.fromEntries(markRules.map(rule => [rule.key, Number(value[rule.key]) || 0]))
}, { immediate: true })
const validationError = ref('')
const overlayArmed = ref(false)

function emptyRows(): VersionDraft[] {
  return [{ claimantId: '', checks: [] }]
}

function readValue(event: Event): string {
  return String((event.target as HTMLSelectElement | null)?.value || '')
}

function parseVersions(raw: unknown): VersionDraft[] {
  const source = Array.isArray(raw) ? raw : []
  const parsed: VersionDraft[] = []
  for (const item of source.slice(0, maxVersions)) {
    if (!item || typeof item !== 'object') continue
    const record = item as Record<string, unknown>
    const claimantId = String(record.claimant_id || '')
    const rawChecks = Array.isArray(record.checks) ? record.checks : []
    const checks: VersionCheckDraft[] = []
    for (const rawCheck of rawChecks.slice(0, maxChecksPerVersion)) {
      if (!rawCheck || typeof rawCheck !== 'object') continue
      const check = rawCheck as Record<string, unknown>
      const targetId = String(check.target_id || '')
      const verdict = check.verdict === 'black' ? 'black' : check.verdict === 'red' ? 'red' : null
      if (targetId && verdict) checks.push({ targetId, verdict })
    }
    if (claimantId && checks.length) parsed.push({ claimantId, checks })
  }
  return parsed.length ? parsed : emptyRows()
}

function resetRows(raw: unknown): void {
  rows.value = parseVersions(raw)
  validationError.value = ''
}

watch(() => props.versions, resetRows, { immediate: true })

function isClaimantUsed(playerId: string, exceptIndex: number): boolean {
  return rows.value.some((version, index) => index !== exceptIndex && version.claimantId === playerId)
}

function isCheckTargetUsed(playerId: string, versionIndex: number, exceptIndex: number): boolean {
  return rows.value[versionIndex].checks.some((check, index) => index !== exceptIndex && check.targetId === playerId)
}

function setClaimant(versionIndex: number, event: Event): void {
  const claimantId = readValue(event)
  if (claimantId && isClaimantUsed(claimantId, versionIndex)) return
  rows.value[versionIndex] = claimantId
    ? { claimantId, checks: [{ targetId: '', verdict: 'red' }] }
    : { claimantId: '', checks: [] }
  validationError.value = ''
}

function cancelVersion(versionIndex: number): void {
  rows.value[versionIndex] = { claimantId: '', checks: [] }
  validationError.value = ''
}

function addVersion(): void {
  if (rows.value.length >= maxVersions) return
  rows.value.push({ claimantId: '', checks: [] })
  validationError.value = ''
}

function removeVersion(versionIndex: number): void {
  if (rows.value.length <= 1) return
  rows.value.splice(versionIndex, 1)
  validationError.value = ''
}

function addCheck(versionIndex: number): void {
  const version = rows.value[versionIndex]
  if (!version || version.checks.length >= maxChecksPerVersion) return
  version.checks.push({ targetId: '', verdict: 'red' })
  validationError.value = ''
}

function removeCheck(versionIndex: number, checkIndex: number): void {
  const version = rows.value[versionIndex]
  if (!version || version.checks.length <= 1) return
  version.checks.splice(checkIndex, 1)
  validationError.value = ''
}

function setCheckTarget(versionIndex: number, checkIndex: number, event: Event): void {
  const targetId = readValue(event)
  const version = rows.value[versionIndex]
  if (!version || !version.checks[checkIndex]) return
  if (targetId && (targetId === version.claimantId || isCheckTargetUsed(targetId, versionIndex, checkIndex))) return
  version.checks[checkIndex].targetId = targetId
  validationError.value = ''
}

function setCheckVerdict(versionIndex: number, checkIndex: number, event: Event): void {
  const version = rows.value[versionIndex]
  if (!version || !version.checks[checkIndex]) return
  version.checks[checkIndex].verdict = readValue(event) === 'black' ? 'black' : 'red'
  validationError.value = ''
}

function buildPayload(): VersionPayload[] | null {
  const payload: VersionPayload[] = []
  for (const [versionIndex, version] of rows.value.entries()) {
    if (!version.claimantId) continue
    if (!version.checks.length) {
      validationError.value = `В версии ${versionIndex + 1} должна быть хотя бы одна проверка.`
      return null
    }
    const claimantId = Number(version.claimantId)
    const targetIds = new Set<string>()
    const checks: VersionPayload['checks'] = []
    for (const check of version.checks) {
      const targetId = Number(check.targetId)
      if (!Number.isInteger(targetId) || targetId <= 0) {
        validationError.value = `Выберите игрока для каждой проверки версии ${versionIndex + 1}.`
        return null
      }
      if (targetId === claimantId || targetIds.has(check.targetId)) {
        validationError.value = `Проверки версии ${versionIndex + 1} не должны повторяться или указывать на вскрывшегося игрока.`
        return null
      }
      targetIds.add(check.targetId)
      checks.push({ target_id: targetId, verdict: check.verdict })
    }
    if (!Number.isInteger(claimantId) || claimantId <= 0) {
      validationError.value = `Выберите игрока во вскрытии версии ${versionIndex + 1}.`
      return null
    }
    payload.push({ claimant_id: claimantId, checks })
  }
  validationError.value = ''
  return payload
}

function requestSave(): void {
  overlayArmed.value = false
  if (props.saving) return
  const payload = buildPayload()
  if (payload) emit('save', payload, { ...marks.value })
}

function requestCancel(): void {
  overlayArmed.value = false
  if (props.saving) return
  emit('cancel')
}
</script>

<style scoped lang="scss">
.game-versions-overlay {
  display: flex;
  position: fixed;
  inset: 0;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 40px;
  background-color: rgba($neutral-black, 0.6);
  backdrop-filter: blur(12px);
  z-index: 1200;
  .game-versions-modal {
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    padding: 24px;
    gap: 24px;
    width: 100%;
    max-width: 1500px;
    max-height: 100%;
    min-height: 0;
    border-radius: 24px;
    background-color: $soft-purple-900;
    color: $neutral-100;
    font-family: Hauora-Regular;
    line-height: 1.4;
    overflow: auto;
    overscroll-behavior: contain;
    scrollbar-width: thin;
    scrollbar-color: $soft-purple-700 transparent;
    > * {
      flex-shrink: 0;
    }
    .game-versions-modal__title {
      margin: 0;
      color: $neutral-white;
      font-family: Involve-Medium;
      font-weight: 500;
      font-size: 24px;
      line-height: 26px;
      letter-spacing: -0.48px;
    }
    .game-versions-modal__error {
      margin: 0;
      padding: 16px;
      border-radius: 16px;
      background-color: rgba($red-500, 0.12);
      color: $red-300;
      font-size: 14px;
      line-height: 20px;
    }
    .game-versions-modal__marks {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      padding: 16px;
      gap: 16px;
      border-radius: 20px;
      background-color: $soft-purple-800;
      .scoring-mark {
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-width: 0;
        gap: 12px;
        label {
          color: $neutral-300;
          font-size: 14px;
          line-height: 20px;
        }
        select {
          box-sizing: border-box;
          width: 100%;
          min-width: 0;
          height: 40px;
          padding: 0 12px;
          border: 1px solid $green-200;
          border-radius: 12px;
          background-color: $soft-purple-800;
          color: $neutral-100;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 20px;
          color-scheme: dark;
          cursor: pointer;
          &:not(:disabled):hover {
            border-color: $green-500;
          }
          &:focus-visible {
            outline: 2px solid $green-500;
            outline-offset: 3px;
          }
          &:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
          option {
            background-color: $soft-purple-900;
            color: $neutral-100;
          }
        }
      }
    }
    .game-versions-modal__list-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      > span {
        color: $neutral-300;
        font-size: 16px;
        line-height: 20px;
      }
    }
    .game-versions-modal__list {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      align-items: start;
      gap: 10px;
      .version-card {
        display: flex;
        flex-direction: column;
        padding: 16px;
        gap: 12px;
        min-width: 0;
        border-radius: 20px;
        background-color: $soft-purple-800;
        .version-card__heading {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 4px;
          gap: 12px;
          > span {
            color: $neutral-white;
            font-family: Involve-Medium;
            font-size: 20px;
            line-height: 24px;
            letter-spacing: -0.4px;
          }
        }
        > label {
          color: $neutral-300;
          font-size: 14px;
          line-height: 20px;
        }
        > select {
          box-sizing: border-box;
          width: 100%;
          min-width: 0;
          height: 40px;
          padding: 0 12px;
          border: 1px solid $green-200;
          border-radius: 12px;
          background-color: $soft-purple-800;
          color: $neutral-100;
          font-family: Hauora-Regular;
          font-size: 16px;
          line-height: 20px;
          color-scheme: dark;
          cursor: pointer;
          &:not(:disabled):hover {
            border-color: $green-500;
          }
          &:focus-visible {
            outline: 2px solid $green-500;
            outline-offset: 3px;
          }
          &:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
          option {
            background-color: $soft-purple-900;
            color: $neutral-100;
          }
        }
        .version-card__checks-heading {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-top: 4px;
          gap: 12px;
          > span {
            color: $neutral-100;
            font-family: Hauora-Medium;
            font-size: 16px;
            line-height: 20px;
          }
        }
        .version-check {
          display: grid;
          grid-template-columns: minmax(0, 1fr) 112px 40px;
          align-items: center;
          gap: 8px;
          select {
            box-sizing: border-box;
            width: 100%;
            min-width: 0;
            height: 40px;
            padding: 0 12px;
            border: 1px solid $green-200;
            border-radius: 12px;
            background-color: $soft-purple-800;
            color: $neutral-100;
            font-family: Hauora-Regular;
            font-size: 16px;
            line-height: 20px;
            color-scheme: dark;
            cursor: pointer;
            &:not(:disabled):hover {
              border-color: $green-500;
            }
            &:focus-visible {
              outline: 2px solid $green-500;
              outline-offset: 3px;
            }
            &:disabled {
              opacity: 0.5;
              cursor: not-allowed;
            }
            option {
              background-color: $soft-purple-900;
              color: $neutral-100;
            }
          }
          .version-check__remove {
            --ui-button-height: 40px;
            --ui-button-padding-x: 0;
          }
        }
      }
    }
    footer {
      display: flex;
      position: sticky;
      bottom: -24px;
      justify-content: flex-end;
      margin: 0 -24px -24px;
      padding: 24px;
      gap: 12px;
      border-top: 1px solid $soft-purple-800;
      background-color: $soft-purple-900;
      z-index: 1;
    }
  }
}
.game-versions-overlay-enter-active,
.game-versions-overlay-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.game-versions-overlay-enter-from,
.game-versions-overlay-leave-to {
  opacity: 0;
}
</style>
