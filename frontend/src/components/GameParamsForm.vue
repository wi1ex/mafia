<template>
  <div class="params">
    <ToggleSwitch
      v-model="spectatorsEnabled"
      :disabled="spectatorsToggleDisabled"
      :tooltip="spectatorsToggleTooltip"
      label="Зрители:"
      off-label="Откл"
      on-label="Вкл"
      aria-label="Зрители: откл/вкл"
    />
    <ToggleSwitch
      v-model="isRating"
      label="Режим:"
      off-label="Обычный"
      on-label="Рейтинг"
      aria-label="Режим: обычный/рейтинг"
      :disabled="true"
    />
    <ToggleSwitch
      v-model="isNoHost"
      label="Ведущий:"
      off-label="Ведущий"
      on-label="Авто"
      aria-label="Ведущий: с ведущим/авто"
      :disabled="true"
    />
    <ToggleSwitch
      v-model="isPlayersNomination"
      label="Выставления:"
      off-label="Ведущий"
      on-label="Игрок"
      aria-label="Выставления"
      :disabled="disabled"
    />
    <ToggleSwitch
      v-model="local.farewell_wills"
      label="Завещания:"
      aria-label="Завещания"
      :disabled="disabled"
    />
    <ToggleSwitch
      v-model="local.wink_knock"
      label="Подмигивать/Стучать:"
      aria-label="Подмигивать/Стучать"
      :disabled="disabled"
    />
    <ToggleSwitch
      v-model="local.break_at_zero"
      label="Слом в нуле:"
      aria-label="Слом в нуле"
      :disabled="disabled"
    />
    <ToggleSwitch
      v-model="local.lift_at_zero"
      label="Подъём в нуле:"
      aria-label="Подъём в нуле"
      :disabled="disabled"
    />
    <ToggleSwitch
      v-model="local.lift_3x"
      label="Подъём 3х при 9х:"
      aria-label="Подъём 3х при 9х"
      :disabled="disabled"
    />
    <ToggleSwitch
      v-model="local.music"
      label="Музыка:"
      aria-label="Музыка"
      :disabled="disabled"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ToggleSwitch from '@/components/ToggleSwitch.vue'
import {
  normalizeRoomGameParams,
  SPECTATORS_DISABLED_LIMIT,
  SPECTATORS_ENABLED_LIMIT,
  type RoomGameParams,
} from '@/services/gameParams'

const props = defineProps<{
  modelValue: RoomGameParams
  disabled?: boolean
  canDisableSpectators?: boolean
  spectatorsDisabledHint?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: RoomGameParams): void
}>()

const canDisableSpectators = computed(() => props.canDisableSpectators)
const local = ref<RoomGameParams>(normalizeRoomGameParams(props.modelValue, {
  allowDisableSpectators: canDisableSpectators.value,
}))

watch(() => props.modelValue, (val) => {
  local.value = normalizeRoomGameParams(val, {
    allowDisableSpectators: canDisableSpectators.value,
  })
}, { deep: true })

watch(local, (val) => {
  const normalized = normalizeRoomGameParams(val, {
    allowDisableSpectators: canDisableSpectators.value,
  })
  if (JSON.stringify(normalized) === JSON.stringify(props.modelValue)) return
  emit('update:modelValue', { ...normalized })
}, { deep: true })

watch(canDisableSpectators, (allowDisable) => {
  const normalized = normalizeRoomGameParams(local.value, {
    allowDisableSpectators: allowDisable,
  })
  if (JSON.stringify(normalized) === JSON.stringify(local.value)) return
  local.value = normalized
}, { flush: 'sync' })

const isRating = computed<boolean>({
  get: () => local.value.mode === 'rating',
  set: v => { local.value.mode = v ? 'rating' : 'normal' },
})

const isNoHost = computed<boolean>({
  get: () => local.value.format === 'nohost',
  set: v => { local.value.format = v ? 'nohost' : 'hosted' },
})

const isPlayersNomination = computed<boolean>({
  get: () => local.value.nominate_mode === 'players',
  set: v => { local.value.nominate_mode = v ? 'players' : 'head' },
})

const disabled = computed(() => props.disabled)
const spectatorsEnabled = computed<boolean>({
  get: () => local.value.spectators_limit >= SPECTATORS_ENABLED_LIMIT,
  set: (next) => {
    if (!next && !canDisableSpectators.value) return
    local.value.spectators_limit = next ? SPECTATORS_ENABLED_LIMIT : SPECTATORS_DISABLED_LIMIT
  },
})

const spectatorsToggleDisabled = computed(() => Boolean(disabled.value || !canDisableSpectators.value))
const spectatorsToggleTooltip = computed(() => {
  if (disabled.value || canDisableSpectators.value) return undefined
  return props.spectatorsDisabledHint || 'Отключение зрителей доступно пользователям, поддержавшим платформу'
})
</script>

<style scoped lang="scss">
.params {
  display: flex;
  flex-direction: column;
  padding: 10px;
  gap: 15px;
}

@media (max-width: 1280px) {
  .params {
    gap: 10px;
  }
}
</style>
