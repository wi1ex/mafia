<template>
  <i
    class="ui-icon"
    :style="iconStyle"
    :role="label ? 'img' : undefined"
    :aria-label="label || undefined"
    :aria-hidden="label ? undefined : 'true'"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  icon: string
  label?: string
}>()

const iconUrl = computed(() => {
  const escaped = props.icon.replace(/\\/g, '\\\\').replace(/"/g, '\\"')
  return `url("${escaped}")`
})

const iconStyle = computed<Record<string, string>>(() => ({
  '--ui-icon-url': iconUrl.value,
}))
</script>

<style scoped lang="scss">
.ui-icon {
  display: inline-block;
  flex: 0 0 auto;
  font-style: normal;
  width: var(--ui-icon-width, 24px);
  height: var(--ui-icon-height, 24px);
  background-color: var(--ui-icon-color, currentColor);
  mask-image: var(--ui-icon-url);
  mask-position: center;
  mask-repeat: no-repeat;
  mask-size: contain;
  mask-mode: alpha;
  -webkit-mask-image: var(--ui-icon-url);
  -webkit-mask-position: center;
  -webkit-mask-repeat: no-repeat;
  -webkit-mask-size: contain;
  transition: background-color 0.25s ease-in-out;
}
</style>
