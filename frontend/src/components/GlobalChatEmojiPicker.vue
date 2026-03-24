<template>
  <div ref="root" :class="['emoji-picker', isReactionsMode ? 'emoji-picker--reactions' : 'emoji-picker--composer']" @click.stop>
    <template v-if="isReactionsMode">
      <button v-for="emoji in reactionItems" :key="emoji" class="emoji-button" type="button" @click="selectEmoji(emoji)">
        {{ emoji }}
      </button>
    </template>

    <template v-else>
      <section v-for="section in COMPOSER_SECTIONS" :key="section.title" class="emoji-section">
        <header>{{ section.title }}</header>
        <div class="emoji-grid">
          <button v-for="emoji in section.items" :key="emoji" class="emoji-button" type="button" @click="selectEmoji(emoji)">
            {{ emoji }}
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

type EmojiSectionDef = {
  title: string
  ranges: Array<[number, number]>
}

const EMOJI_RE = /\p{Emoji}/u
const EMOJI_PRESENTATION_RE = /\p{Emoji_Presentation}/u
const EMOJI_COMPONENT_RE = /\p{Emoji_Component}/u
const EMOJI_MODIFIER_RE = /\p{Emoji_Modifier}/u
const EMOJI_MODIFIER_BASE_RE = /\p{Emoji_Modifier_Base}/u
const REGIONAL_INDICATOR_RE = /\p{Regional_Indicator}/u
const EMOJI_VARIATION = '\uFE0F'
const EMOJI_TONES = ['🏻', '🏼', '🏽', '🏾', '🏿']
const KEYCAPS = ['#️⃣', '*️⃣', '0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
const COMPOSER_SECTION_DEFS: EmojiSectionDef[] = [
  {
    title: 'Смайлы',
    ranges: [[0x1F600, 0x1F64F], [0x1F910, 0x1F92F], [0x1F970, 0x1F97A], [0x1FAE0, 0x1FAE8]],
  },
  {
    title: 'Люди и жесты',
    ranges: [
      [0x1F44A, 0x1F64F],
      [0x1F466, 0x1F487],
      [0x1F574, 0x1F57A],
      [0x1F590, 0x1F596],
      [0x1F6B4, 0x1F6CC],
      [0x1F90C, 0x1F9AF],
      [0x1F9B0, 0x1F9B3],
      [0x1F9B5, 0x1F9E6],
      [0x1FAC0, 0x1FACF],
    ],
  },
  {
    title: 'Природа и еда',
    ranges: [[0x1F330, 0x1F37F], [0x1F400, 0x1F43F], [0x1F950, 0x1F96F], [0x1F980, 0x1F9AF]],
  },
  {
    title: 'Предметы и места',
    ranges: [[0x1F380, 0x1F3FF], [0x1F4A0, 0x1F4FF], [0x1F680, 0x1F6FF], [0x1FA70, 0x1FAFF]],
  },
  {
    title: 'Символы',
    ranges: [[0x00A9, 0x00AE], [0x203C, 0x3299], [0x1F300, 0x1F32F], [0x1F5E8, 0x1F5FF], [0x1F7E0, 0x1F7EB]],
  },
  {
    title: 'Флаги',
    ranges: [],
  },
]

function toEmojiChar(codePoint: number): string {
  const base = String.fromCodePoint(codePoint)
  if (!EMOJI_RE.test(base)) return ''
  if (EMOJI_COMPONENT_RE.test(base) || EMOJI_MODIFIER_RE.test(base) || REGIONAL_INDICATOR_RE.test(base)) return ''
  if (EMOJI_PRESENTATION_RE.test(base)) return base
  return codePoint <= 0xFFFF ? `${base}${EMOJI_VARIATION}` : base
}

function pushUnique(target: string[], seen: Set<string>, emoji: string): void {
  const value = String(emoji || '').trim()
  if (!value || seen.has(value)) return
  seen.add(value)
  target.push(value)
}

function buildFlags(): string[] {
  if (typeof Intl === 'undefined' || typeof Intl.DisplayNames !== 'function') return []
  const displayNames = new Intl.DisplayNames(undefined, { type: 'region' })
  const out: string[] = []
  for (let first = 65; first <= 90; first += 1) {
    for (let second = 65; second <= 90; second += 1) {
      const code = `${String.fromCharCode(first)}${String.fromCharCode(second)}`
      const label = displayNames.of(code)
      if (!label || label.toUpperCase() === code) continue
      out.push(String.fromCodePoint(0x1F1E6 + (first - 65), 0x1F1E6 + (second - 65)))
    }
  }
  return out
}

function buildComposerSections(): Array<{ title: string; items: string[] }> {
  const globalSeen = new Set<string>()
  return COMPOSER_SECTION_DEFS.map((section) => {
    const items: string[] = []
    if (section.title === 'Символы') {
      for (const keycap of KEYCAPS) {
        pushUnique(items, globalSeen, keycap)
      }
    }
    if (section.title === 'Флаги') {
      for (const flag of buildFlags()) {
        pushUnique(items, globalSeen, flag)
      }
      return { title: section.title, items }
    }
    for (const [from, to] of section.ranges) {
      for (let codePoint = from; codePoint <= to; codePoint += 1) {
        const emoji = toEmojiChar(codePoint)
        if (!emoji) continue
        pushUnique(items, globalSeen, emoji)
        const base = String.fromCodePoint(codePoint)
        if (EMOJI_MODIFIER_BASE_RE.test(base)) {
          for (const tone of EMOJI_TONES) {
            pushUnique(items, globalSeen, `${emoji}${tone}`)
          }
        }
      }
    }
    return { title: section.title, items }
  }).filter((section) => section.items.length > 0)
}

const COMPOSER_SECTIONS = buildComposerSections()

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
    .emoji-section {
      display: flex;
      flex-direction: column;
      gap: 10px;
      > header {
        color: $ashy;
        font-size: 14px;
        font-family: Manrope-Medium;
        text-transform: uppercase;
      }
      .emoji-grid {
        display: grid;
        grid-template-columns: repeat(8, minmax(0, 1fr));
        gap: 5px;
        .emoji-button {
          border-radius: 5px;
        }
      }
    }
  }
}

@media (max-width: 1280px) {

}

</style>
