<template>
  <div ref="root" :class="['emoji-picker', isReactionsMode ? 'emoji-picker--reactions' : 'emoji-picker--composer']" @click.stop>
    <template v-if="isReactionsMode">
      <button v-for="emoji in reactionItems" :key="emoji" class="emoji-button" type="button" @click="selectEmoji(emoji)">
        {{ emoji }}
      </button>
    </template>

    <div v-else class="emoji-grid emoji-grid--composer">
      <button v-for="emoji in COMPOSER_ITEMS" :key="emoji" class="emoji-button" type="button" @click="selectEmoji(emoji)">
        {{ emoji }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { GLOBAL_CHAT_COMPOSER_EMOJIS } from '@/constants/globalChatComposerEmojis'

const COMPOSER_ITEMS = GLOBAL_CHAT_COMPOSER_EMOJIS

const props = withDefaults(defineProps<{
  mode?: 'composer' | 'reactions'
  reactions?: string[]
}>(), {
  mode: 'composer',
  reactions: () => [],
})

const emit = defineEmits<{
  select: [emoji: string]
  close: []
}>()

const root = ref<HTMLElement | null>(null)
const isReactionsMode = computed(() => props.mode === 'reactions')
const reactionItems = computed(() => props.reactions.filter((item, index, list) => Boolean(item) && list.indexOf(item) === index))

function selectEmoji(emoji: string): void {
  emit('select', emoji)
  if (isReactionsMode.value) {
    emit('close')
  }
}

function onDocumentPointerDown(event: PointerEvent): void {
  const target = event.target as Node | null
  if (!target || root.value?.contains(target)) return
  emit('close')
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
})
</script>

<style scoped lang="scss">
.emoji-picker {
  display: flex;
  position: absolute;
  transform-origin: bottom right;
  background-color: $lead;
  box-shadow: 0 15px 30px rgba($black, 0.5);
  overflow: hidden;
  z-index: 10;
  .emoji-button {
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
    font-size: 18px;
    transition: transform 0.25s ease-in-out;
    cursor: pointer;
    &:hover {
      transform: translateY(-3px);
    }
  }
  &--reactions {
    bottom: calc(100% + 5px);
    right: 0;
    padding: 5px;
    border-radius: 999px;
    > .emoji-button {
      padding: 0;
      width: 30px;
      height: 30px;
    }
  }
  &--composer {
    flex-direction: column;
    bottom: calc(100% + 10px);
    right: 10px;
    padding: 10px;
    width: 250px;
    height: 200px;
    border-radius: 5px;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-width: none;
    .emoji-grid--composer {
      display: grid;
      grid-template-columns: repeat(8, minmax(0, 1fr));
      gap: 5px;
    }
  }
}

@media (max-width: 1280px) {

}

</style>
