<template>
  <div class="params">
    <div class="range">
      <span>Лимит зрителей: {{ local.spectators_limit }}/{{ SPECT_MAX }}</span>
      <UiSlider
        v-model="local.spectators_limit"
        :min="SPECT_MIN"
        :max="SPECT_MAX"
        :step="1"
        aria-label="Лимит зрителей"
        :disabled="disabled"
      />
    </div>

    <ToggleSwitch v-model="isRating" label="Режим:" off-label="Обычный" on-label="Рейтинг" aria-label="Режим: обычный/рейтинг" :disabled="true" />
    <ToggleSwitch v-model="isNoHost" label="Судья:" off-label="Ведущий" on-label="Авто" aria-label="Формат: с ведущим/без ведущего" :disabled="true" />
    <ToggleSwitch v-model="isPlayersNomination" label="Выставления:" off-label="Ведущий" on-label="Игрок" aria-label="Выставления" :disabled="disabled" />
    <ToggleSwitch v-model="local.farewell_wills" label="Завещания:" aria-label="Завещания" :disabled="disabled" />
    <ToggleSwitch v-model="local.wink_knock" label="Подмигивание/Стук:" aria-label="Подмигивание/Стук" :disabled="disabled" />
    <ToggleSwitch v-model="local.break_at_zero" label="Слом в нуле:" aria-label="Слом в нуле" :disabled="disabled" />
    <ToggleSwitch v-model="local.lift_at_zero" label="Подъём в нуле:" aria-label="Подъём в нуле" :disabled="disabled" />
    <ToggleSwitch v-model="local.lift_3x" label="Подъём 3х при 9х:" aria-label="Подъём 3х" :disabled="disabled" />
    <ToggleSwitch v-model="local.music" label="Музыка:" aria-label="Музыка" :disabled="disabled" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ToggleSwitch from '@/components/ToggleSwitch.vue'
import UiSlider from '@/components/UiSlider.vue'

type Game = {
  mode: 'normal' | 'rating'
  format: 'hosted' | 'nohost'
  spectators_limit: number
  nominate_mode: 'head' | 'players'
  break_at_zero: boolean
  lift_at_zero: boolean
  lift_3x: boolean
  wink_knock: boolean
  farewell_wills: boolean
  music: boolean
}

const props = defineProps<{
  modelValue: Game
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: Game): void
}>()

const SPECT_MIN = 0
const SPECT_MAX = 10

const gameDefault: Game = {
  mode: 'normal',
  format: 'hosted',
  spectators_limit: 10,
  nominate_mode: 'players',
  break_at_zero: true,
  lift_at_zero: true,
  lift_3x: true,
  wink_knock: true,
  farewell_wills: true,
  music: true,
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

function normalize(raw: any): Game {
  const merged: Game = { ...gameDefault }
  if (!raw || typeof raw !== 'object') return merged
  if (raw.mode === 'normal' || raw.mode === 'rating') merged.mode = raw.mode
  if (raw.format === 'hosted' || raw.format === 'nohost') merged.format = raw.format
  if (raw.nominate_mode === 'head' || raw.nominate_mode === 'players') merged.nominate_mode = raw.nominate_mode
  const spect = Number(raw.spectators_limit)
  if (Number.isFinite(spect)) merged.spectators_limit = clamp(spect, SPECT_MIN, SPECT_MAX)
  if (typeof raw.break_at_zero === 'boolean') merged.break_at_zero = raw.break_at_zero
  if (typeof raw.lift_at_zero === 'boolean') merged.lift_at_zero = raw.lift_at_zero
  if (typeof raw.lift_3x === 'boolean') merged.lift_3x = raw.lift_3x
  if (typeof raw.wink_knock === 'boolean') merged.wink_knock = raw.wink_knock
  if (typeof raw.farewell_wills === 'boolean') merged.farewell_wills = raw.farewell_wills
  if (typeof raw.music === 'boolean') merged.music = raw.music
  return merged
}

const local = ref<Game>(normalize(props.modelValue))

watch(() => props.modelValue, (val) => {
  local.value = normalize(val)
}, { deep: true })

watch(local, (val) => {
  const normalized = normalize(val)
  if (JSON.stringify(normalized) === JSON.stringify(props.modelValue)) return
  emit('update:modelValue', { ...normalized })
}, { deep: true })

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
</script>

<style scoped lang="scss">
.params {
  display: flex;
  flex-direction: column;
  padding: 10px;
  gap: 15px;
  .range {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
}

@media (max-width: 1280px) {
  .params {
    gap: 10px;
  }
}
</style>
