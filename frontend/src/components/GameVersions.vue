<template>
  <Teleport to="#desktop-teleport-root">
    <Transition name="game-versions-overlay">
      <div
        class="game-versions-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="game-versions-title"
        @pointerdown.self="overlayArmed = true"
        @pointerup.self="overlayArmed && requestSave()"
        @pointerleave.self="overlayArmed = false"
        @pointercancel.self="overlayArmed = false"
      >
        <section class="game-versions-modal" @click.stop>
          <header>
            <div>
              <h2 id="game-versions-title">Версии</h2>
              <p>Отметьте вскрытия шерифом и озвученные проверки. Сохранение происходит при закрытии окна.</p>
            </div>
            <button class="game-versions-modal__close" type="button" :disabled="saving" aria-label="Сохранить и закрыть" @click="requestSave">×</button>
          </header>

          <p v-if="validationError" class="game-versions-modal__error" role="alert">{{ validationError }}</p>

          <div class="game-versions-modal__list">
            <section v-for="(version, versionIndex) in rows" :key="versionIndex" class="version-card" :class="{ 'version-card--empty': !version.claimantId }">
              <div class="version-card__heading">
                <span>Версия {{ versionIndex + 1 }}</span>
                <button v-if="version.claimantId" type="button" :disabled="saving" @click="cancelVersion(versionIndex)">Отменить вскрытие</button>
              </div>

              <label :for="`game-version-claimant-${versionIndex}`">Вскрылся шерифом</label>
              <select
                :id="`game-version-claimant-${versionIndex}`"
                :value="version.claimantId"
                :disabled="saving"
                @change="setClaimant(versionIndex, $event)"
              >
                <option value="">Не отмечен</option>
                <option v-for="player in players" :key="player.id" :value="player.id" :disabled="isClaimantUsed(player.id, versionIndex)">
                  {{ player.label }}
                </option>
              </select>

              <template v-if="version.claimantId">
                <div class="version-card__checks-heading">
                  <span>Проверки</span>
                  <button type="button" :disabled="saving || version.checks.length >= maxChecksPerVersion" @click="addCheck(versionIndex)">Добавить проверку</button>
                </div>

                <div v-for="(check, checkIndex) in version.checks" :key="checkIndex" class="version-check">
                  <select
                    :value="check.targetId"
                    :disabled="saving"
                    :aria-label="`Проверяемый игрок в версии ${versionIndex + 1}`"
                    @change="setCheckTarget(versionIndex, checkIndex, $event)"
                  >
                    <option value="">Игрок</option>
                    <option
                      v-for="player in players"
                      :key="player.id"
                      :value="player.id"
                      :disabled="player.id === version.claimantId || isCheckTargetUsed(player.id, versionIndex, checkIndex)"
                    >
                      {{ player.label }}
                    </option>
                  </select>
                  <select
                    :value="check.verdict"
                    :disabled="saving"
                    :aria-label="`Результат проверки в версии ${versionIndex + 1}`"
                    @change="setCheckVerdict(versionIndex, checkIndex, $event)"
                  >
                    <option value="red">Красный</option>
                    <option value="black">Чёрный</option>
                  </select>
                  <button
                    class="version-check__remove"
                    type="button"
                    :disabled="saving || version.checks.length <= 1"
                    :aria-label="`Удалить проверку ${checkIndex + 1}`"
                    @click="removeCheck(versionIndex, checkIndex)"
                  >×</button>
                </div>
              </template>
            </section>
          </div>

          <footer>
            <button class="game-versions-modal__save" type="button" :disabled="saving" @click="requestSave">
              {{ saving ? 'Сохранение…' : 'Сохранить и закрыть' }}
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

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

const maxVersions = 5
const maxChecksPerVersion = 10

const props = withDefaults(defineProps<{
  versions?: unknown
  players?: PlayerOption[]
  saving?: boolean
}>(), {
  versions: () => [],
  players: () => [],
  saving: false,
})

const emit = defineEmits<{
  save: [versions: VersionPayload[]]
}>()

const rows = ref<VersionDraft[]>(emptyRows())
const validationError = ref('')
const overlayArmed = ref(false)

function emptyRows(): VersionDraft[] {
  return Array.from({ length: maxVersions }, () => ({ claimantId: '', checks: [] }))
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
  return [...parsed, ...emptyRows()].slice(0, maxVersions)
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
  if (payload) emit('save', payload)
}
</script>

<style scoped lang="scss">
.game-versions-overlay {
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  padding: 24px;
  background-color: rgba($neutral-black, 0.64);
  backdrop-filter: blur(12px);
  z-index: 1200;
  .game-versions-modal {
    display: flex;
    flex-direction: column;
    width: min(920px, 100%);
    max-height: min(820px, calc(100vh - 48px));
    border: 2px solid $green-700;
    border-radius: 20px;
    background-color: $neutral-900;
    box-shadow: 0 16px 48px rgba($neutral-black, 0.5);
    overflow: hidden;
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      padding: 24px 24px 16px;
      gap: 16px;
      h2 {
        margin: 0;
        color: $neutral-white;
        font-family: Involve-Medium;
        font-size: 24px;
        line-height: 30px;
      }
      p {
        margin: 8px 0 0;
        max-width: 650px;
        color: $neutral-300;
        font-family: Hauora-Regular;
        font-size: 14px;
        line-height: 20px;
      }
    }
    .game-versions-modal__close,
    .version-check__remove {
      display: flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      width: 36px;
      height: 36px;
      padding: 0;
      border: 0;
      border-radius: 10px;
      background-color: $soft-purple-900;
      color: $neutral-100;
      font-size: 25px;
      line-height: 1;
      cursor: pointer;
      &:hover:not(:disabled),
      &:focus-visible:not(:disabled) {
        background-color: $soft-purple-800;
      }
    }
    .game-versions-modal__error {
      margin: 0 24px 12px;
      color: $red-400;
      font-family: Hauora-Regular;
      font-size: 14px;
      line-height: 20px;
    }
    .game-versions-modal__list {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      padding: 4px 24px 24px;
      gap: 12px;
      overflow-y: auto;
    }
    .version-card {
      padding: 16px;
      border: 1px solid $neutral-700;
      border-radius: 14px;
      background-color: $neutral-800;
      &.version-card--empty {
        opacity: 0.86;
      }
      .version-card__heading,
      .version-card__checks-heading {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }
      .version-card__heading {
        margin-bottom: 14px;
        > span {
          color: $neutral-white;
          font-family: Involve-Medium;
          font-size: 16px;
          line-height: 20px;
        }
      }
      .version-card__checks-heading {
        margin-top: 16px;
        > span {
          color: $neutral-200;
          font-family: Hauora-Medium;
          font-size: 14px;
          line-height: 18px;
        }
      }
      label {
        display: block;
        margin-bottom: 6px;
        color: $neutral-300;
        font-family: Hauora-Regular;
        font-size: 13px;
        line-height: 18px;
      }
      select {
        width: 100%;
        height: 40px;
        padding: 0 10px;
        border: 1px solid $green-300;
        border-radius: 10px;
        background-color: $neutral-900;
        color: $neutral-100;
        font-family: Hauora-Regular;
        font-size: 14px;
        line-height: 18px;
      }
      button:not(.version-check__remove) {
        padding: 0;
        border: 0;
        background: transparent;
        color: $green-400;
        font-family: Hauora-Medium;
        font-size: 13px;
        line-height: 18px;
        cursor: pointer;
        &:hover:not(:disabled),
        &:focus-visible:not(:disabled) {
          color: $green-300;
        }
      }
    }
    .version-check {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 112px 36px;
      margin-top: 8px;
      gap: 8px;
    }
    footer {
      display: flex;
      justify-content: flex-end;
      padding: 16px 24px 24px;
      border-top: 1px solid $neutral-700;
      .game-versions-modal__save {
        min-width: 190px;
        height: 40px;
        padding: 0 16px;
        border: 0;
        border-radius: 10px;
        background-color: $green-500;
        color: $neutral-black;
        font-family: Hauora-Medium;
        font-size: 14px;
        cursor: pointer;
        &:hover:not(:disabled),
        &:focus-visible:not(:disabled) {
          background-color: $green-400;
        }
      }
    }
    button:disabled,
    select:disabled {
      cursor: default;
      opacity: 0.5;
    }
  }
}

.game-versions-overlay-enter-active,
.game-versions-overlay-leave-active {
  transition: opacity 0.2s ease;
}
.game-versions-overlay-enter-from,
.game-versions-overlay-leave-to {
  opacity: 0;
}

@media (max-width: 720px) {
  .game-versions-overlay {
    padding: 12px;
    .game-versions-modal {
      max-height: calc(100vh - 24px);
      header,
      .game-versions-modal__list,
      footer {
        padding-left: 16px;
        padding-right: 16px;
      }
      .game-versions-modal__list {
        grid-template-columns: 1fr;
      }
    }
  }
}
</style>
