<template>
  <div class="seasonal-copy" :class="`seasonal-copy--${slide}`" aria-hidden="true">
    <template v-if="slide === 1">
      <p class="seasonal-copy-title"><span class="seasonal-copy-accent">deceit</span> — место, где игра<br>превращается в общение!</p>
      <p class="seasonal-copy-body">Собирайтесь в комнаты, играйте в мафию<br>и не только, общайтесь, стримьте<br>и проводите время вместе.</p>
    </template>
    <template v-else-if="slide === 2">
      <p class="seasonal-copy-title">Проводите время <span class="seasonal-copy-accent">вместе</span> —<br>от игр до фильмов</p>
      <p class="seasonal-copy-meta">1500+ уникальных пользователей</p>
    </template>
    <p v-else-if="slide === 3" class="seasonal-copy-caption">Следи за своим уровнем<br>игры и <span class="seasonal-copy-accent">становись сильнее!</span></p>
    <p v-else-if="slide === 4" class="seasonal-copy-caption">Пространство для <span class="seasonal-copy-accent">общения</span><br>и новых знакомств!</p>
    <p v-else class="seasonal-copy-caption">Запусти платформу как<br><span class="seasonal-copy-accent">отдельное</span> приложение</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{ slide: 1 | 2 | 3 | 4 | 5 }>()
</script>

<style scoped>
.seasonal-copy {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
}
</style>

