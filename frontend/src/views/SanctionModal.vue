<template>
  <Teleport to="#desktop-teleport-root">
    <Transition name="overlay">
      <div v-if="open" class="overlay" :style="{ zIndex }" @pointerdown.stop.self="armed = true" @pointerup.stop.self="armed && close()"
           @pointerleave.stop.self="armed = false" @pointercancel.stop.self="armed = false" @click.stop>
        <div class="modal" role="dialog" aria-modal="true" :aria-label="title" @pointerdown.stop @pointerup.stop @click.stop>
          <header>
            <h2>{{ title }}</h2>
            <UiButton variant="white" size="low" :icon="iconClose" width="40px" aria-label="Закрыть" @click="close" />
          </header>
          <div class="modal-body">
            <div v-if="showReason" class="reason-card">
              <label for="sanction-reason">Причина</label>
              <select id="sanction-reason" v-model="form.reason" :disabled="saving || !availableReasons.length">
                <option v-if="!availableReasons.length" value="" disabled>Нет подходящих пунктов правил</option>
                <option v-for="option in availableReasons" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>
            <div class="div-card">
              <div v-if="timedKind && showReason && restrictRuleDuration" class="reason-card">
                <label for="sanction-type">Тип санкции</label>
                <select id="sanction-type" v-model="selectedBadgeKey" :disabled="saving || availableBadges.length < 2">
                  <option v-if="!availableBadges.length" value="" disabled>Выберите пункт правил</option>
                  <option v-for="badgeKey in availableBadges" :key="badgeKey" :value="badgeKey">
                    {{ SANCTION_BADGES[badgeKey].code }} · {{ SANCTION_BADGES[badgeKey].notation }}
                  </option>
                </select>
              </div>
              <div v-if="showDuration" class="duration-card">
                <h3>Срок</h3>
                <div class="grid">
                  <UiInput id="sanction-months" v-model.number="form.months" type="number" min="0" max="240" step="1" autocomplete="off" label="Месяцы" size="low" :invalid="Boolean(durationError)" :aria-describedby="durationDescriptionIds" />
                  <UiInput id="sanction-days" v-model.number="form.days" type="number" min="0" max="31" step="1" autocomplete="off" label="Дни" size="low" :invalid="Boolean(durationError)" :aria-describedby="durationDescriptionIds" />
                  <UiInput id="sanction-hours" v-model.number="form.hours" type="number" min="0" max="23" step="1" autocomplete="off" label="Часы" size="low" :invalid="Boolean(durationError)" :aria-describedby="durationDescriptionIds" />
                </div>
                <p v-if="ruleDurationHint" id="sanction-rule-duration-hint" class="duration-hint">{{ ruleDurationHint }}</p>
                <p v-if="durationHint" id="sanction-duration-hint" class="duration-hint">{{ durationHint }}</p>
                <p v-if="durationError" id="sanction-duration-error" class="duration-error" role="alert">{{ durationError }}</p>
              </div>
            </div>
            <div v-if="showDescription" class="description-card">
              <h3>Служебное описание</h3>
              <p id="sanction-description-hint">Пользователь не увидит этот текст</p>
              <UiInput
                id="sanction-description"
                v-model="form.description"
                as="textarea"
                rows="5"
                maxlength="2048"
                label="Описание"
                size="low"
                aria-describedby="sanction-description-hint"
                class="sanction-description-textarea"
              />
            </div>
          </div>
          <div class="modal-actions">
            <UiButton variant="white" size="middle" text="Отмена" @click="close" />
            <UiButton size="middle" :text="saving ? 'Сохранение…' : saveLabel" :disabled="!canSubmit" @click="save" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { SANCTION_BADGES, getTimedSanctionBadgeKeys, type SanctionBadgeKey, type TimedSanctionBadgeKey, type TimedSanctionKind } from '@/constants/sanctionReasons'

import UiInput from '@/components/UiInput.vue'
import UiButton from '@/components/UiButton.vue'

import iconClose from '@/assets/svg/iconClose.svg'

const props = withDefaults(defineProps<{
  open: boolean
  title: string
  saving: boolean
  canSave: boolean
  showDuration?: boolean
  showReason?: boolean
  showDescription?: boolean
  saveLabel?: string
  durationHint?: string
  restrictRuleDuration?: boolean
  issuanceKind?: TimedSanctionKind | 'ban'
  zIndex?: number
  reasons: { value: string; label: string; badges?: SanctionBadgeKey[] }[]
  form: {
    months: number
    days: number
    hours: number
    reason: string
    description: string
  }
}>(), {
  showDuration: true,
  showReason: true,
  showDescription: true,
  saveLabel: 'Применить',
  durationHint: '',
  restrictRuleDuration: true,
  zIndex: 1000,
})

const emit = defineEmits<{
  'update:open': [boolean]
  'save': []
}>()

const armed = ref(false)
const selectedBadgeKey = ref<TimedSanctionBadgeKey | ''>('')
const timedKind = computed(() => (
  props.issuanceKind === 'timeout' || props.issuanceKind === 'suspend' ? props.issuanceKind : null
))
const availableReasons = computed(() => {
  const kind = timedKind.value
  return kind
    ? props.reasons.filter(reason => getTimedSanctionBadgeKeys(kind, reason.badges || []).length > 0)
    : props.reasons
})
const availableBadges = computed(() => {
  const kind = timedKind.value
  const reason = availableReasons.value.find(reason => reason.value === props.form.reason)
  return kind && reason ? getTimedSanctionBadgeKeys(kind, reason.badges || []) : []
})
const selectedBadge = computed(() => (
  selectedBadgeKey.value && availableBadges.value.includes(selectedBadgeKey.value)
    ? SANCTION_BADGES[selectedBadgeKey.value]
    : null
))
const durationHours = computed(() => {
  const parts = [props.form.months, props.form.days, props.form.hours].map(Number)
  const limits = [240, 31, 23]
  if (!parts.every((value, index) => Number.isInteger(value) && value >= 0 && value <= limits[index]!)) return null
  return parts[0]! * 30 * 24 + parts[1]! * 24 + parts[2]!
})
const ruleDurationValid = computed(() => {
  if (!timedKind.value || !props.restrictRuleDuration) return true
  const range = selectedBadge.value?.duration
  const hours = durationHours.value
  return Boolean(range && hours !== null && hours >= range.minHours && (range.maxHours === null || hours <= range.maxHours))
})
const ruleDurationHint = computed(() => (
  props.restrictRuleDuration && selectedBadge.value ? `Допустимый срок для ${selectedBadge.value.code}: ${selectedBadge.value.notation}.` : ''
))
const durationError = computed(() => {
  if (!timedKind.value) return ''
  if (durationHours.value === null) return 'Укажите срок целыми неотрицательными числами: месяцы — до 240, дни — до 31, часы — до 23.'
  if (durationHours.value > 0 && selectedBadge.value && !ruleDurationValid.value) {
    return `Срок не соответствует диапазону ${selectedBadge.value.code}.`
  }
  return ''
})
const durationDescriptionIds = computed(() => [
  ruleDurationHint.value ? 'sanction-rule-duration-hint' : '',
  props.durationHint ? 'sanction-duration-hint' : '',
  durationError.value ? 'sanction-duration-error' : '',
].filter(Boolean).join(' ') || undefined)
const canSubmit = computed(() => !props.saving && props.canSave && ruleDurationValid.value)

watch([() => props.open, timedKind, availableReasons], ([open, kind, reasons]) => {
  if (open && kind && !reasons.some(reason => reason.value === props.form.reason)) {
    props.form.reason = reasons[0]?.value ?? ''
  }
}, { immediate: true })

watch([() => props.open, availableBadges], ([open, badges]) => {
  if (!open) selectedBadgeKey.value = ''
  else if (!selectedBadgeKey.value || !badges.includes(selectedBadgeKey.value)) selectedBadgeKey.value = badges[0] ?? ''
}, { immediate: true })

function save(): void {
  if (canSubmit.value) emit('save')
}

function close() {
  emit('update:open', false)
}
</script>

<style scoped lang="scss">
.overlay {
  display: flex;
  position: fixed;
  inset: 0;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 40px;
  background-color: rgba($neutral-black, 0.6);
  backdrop-filter: blur(12px);
  z-index: 1000;
  .modal {
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    max-width: 600px;
    padding: 12px 16px;
    gap: 12px;
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
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
      h2 {
        min-width: 0;
        margin: 0;
        color: $neutral-white;
        font-family: Involve-Medium;
        font-weight: 500;
        font-size: 24px;
        line-height: 26px;
        letter-spacing: -0.48px;
      }
    }
    .modal-body {
      display: grid;
      min-width: 0;
      gap: 10px;
      --ui-input-label-bg: #{$soft-purple-800};
      .div-card {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        background-color: $soft-purple-800;
        border-radius: 20px;
      }
      .duration-card {
        display: flex;
        flex-direction: column;
        min-width: 0;
        padding: 10px 20px;
        gap: 10px;
        border-radius: 20px;
        background-color: $soft-purple-800;
        h3 {
          margin: 0;
          color: $neutral-white;
          font-family: Involve-Medium;
          font-weight: 500;
          font-size: 20px;
          line-height: 24px;
          letter-spacing: -0.4px;
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
          :deep(input) {
            box-sizing: content-box;
          }
        }
        .duration-hint {
          margin: 0;
          color: $yellow-500;
          font-size: 14px;
          line-height: 20px;
        }
        .duration-error {
          margin: 0;
          color: $red-300;
          font-size: 14px;
          line-height: 20px;
        }
      }
      .reason-card {
        display: flex;
        flex-direction: column;
        min-width: 0;
        padding: 10px 20px;
        gap: 10px;
        border-radius: 20px;
        background-color: $soft-purple-800;
        label {
          color: $neutral-white;
          font-family: Involve-Medium;
          font-size: 20px;
          line-height: 24px;
          letter-spacing: -0.4px;
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
          text-overflow: ellipsis;
          color-scheme: dark;
          cursor: pointer;
          &:hover {
            border-color: $green-500;
          }
          &:focus-visible {
            outline: 2px solid $green-500;
            outline-offset: 3px;
          }
          option {
            background-color: $soft-purple-900;
            color: $neutral-100;
          }
        }
      }
      .description-card {
        display: flex;
        flex-direction: column;
        min-width: 0;
        padding: 10px 20px;
        gap: 10px;
        border-radius: 20px;
        background-color: $soft-purple-800;
        h3 {
          margin: 0;
          color: $neutral-white;
          font-family: Involve-Medium;
          font-weight: 500;
          font-size: 20px;
          line-height: 24px;
          letter-spacing: -0.4px;
        }
        p {
          margin: -10px 0 0;
          color: $neutral-300;
          font-size: 14px;
          line-height: 20px;
        }
        .sanction-description-textarea {
          :deep(textarea) {
            box-sizing: content-box;
            min-height: 100px;
          }
        }
      }
    }
    .modal-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 10px;
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
