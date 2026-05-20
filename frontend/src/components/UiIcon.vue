<template>
  <span
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
  --ui-icon-size: 24px;
  --ui-icon-width: var(--ui-icon-size);
  --ui-icon-height: var(--ui-icon-size);
  --ui-icon-color: currentColor;
  --ui-icon-state-color: var(--ui-icon-color);
  --ui-icon-hover-color: var(--ui-icon-state-color);
  --ui-icon-focus-color: var(--ui-icon-state-color);
  --ui-icon-active-color: var(--ui-icon-state-color);
  display: inline-block;
  flex: 0 0 auto;
  width: var(--ui-icon-width);
  height: var(--ui-icon-height);
  background-color: var(--ui-icon-color);
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

.ui-icon:hover,
:global(button:not(:disabled):hover) .ui-icon,
:global(a:hover) .ui-icon,
:global([role='button']:hover) .ui-icon {
  background-color: var(--ui-icon-hover-color);
}

.ui-icon:focus-visible,
:global(button:not(:disabled):focus-visible) .ui-icon,
:global(a:focus-visible) .ui-icon,
:global([role='button']:focus-visible) .ui-icon {
  background-color: var(--ui-icon-focus-color);
}

.ui-icon:active,
:global(button:not(:disabled):active) .ui-icon,
:global(a:active) .ui-icon,
:global([role='button']:active) .ui-icon {
  background-color: var(--ui-icon-active-color);
}

</style>
