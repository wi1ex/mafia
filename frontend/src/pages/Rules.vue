<template>
  <main class="rules">
    <div class="rules-layout">
      <div class="rules-content">
        <section id="intro" class="hero">
          <div class="hero-content">
            <p class="eyebrow">deceit.games</p>
            <h1>Правила сообщества</h1>
            <p class="lead">
              Мы играем в мафию ради честной конкуренции, живого общения и удовольствия от процесса.
              Эти правила защищают игроков, ведущих и атмосферу комнат.
            </p>
            <div class="tags">
              <span class="pill">Уважение</span>
              <span class="pill">Честная игра</span>
              <span class="pill">Безопасность</span>
            </div>
            <div class="meta">
              <div class="meta-item">
                <span class="label">Версия</span>
                <span class="value">1.0</span>
              </div>
              <div class="meta-item">
                <span class="label">Возраст</span>
                <span class="value">13+</span>
              </div>
            </div>
          </div>
        </section>

        <section class="rules-grid">
          <article id="rule-respect" class="rule-card">
            <h3>1. Уважение и безопасность</h3>
            <p>Мы поддерживаем дружелюбную среду, где комфортно играть каждому.</p>
            <ul>
              <li>Запрещены оскорбления, травля, угрозы и дискриминация.</li>
              <li>Нельзя раскрывать личные данные других игроков без их согласия.</li>
              <li>Давление, шантаж, преследование — недопустимы.</li>
            </ul>
          </article>

          <article id="rule-fair" class="rule-card">
            <h3>2. Честная игра</h3>
            <p>Мафия — игра логики и речи, а не внешних подсказок.</p>
            <ul>
              <li>Нельзя пользоваться подсказками со стороны, стрим-снайпом или связью вне комнаты.</li>
              <li>Запрещены мультиаккаунты и договорные игры.</li>
              <li>После смерти не раскрывайте информацию и не влияйте на ход игры.</li>
            </ul>
          </article>

          <article id="rule-behavior" class="rule-card">
            <h3>3. Поведение в комнате</h3>
            <p>Соблюдайте регламент, чтобы у всех были равные условия.</p>
            <ul>
              <li>Говорите в свой ход, не перебивайте и не спамьте микрофоном.</li>
              <li>Запрещены чрезмерные шумы, намеренный срыв тайминга и троллинг.</li>
              <li>Решения ведущего обязательны, если не противоречат общим правилам.</li>
            </ul>
          </article>

          <article id="rule-profiles" class="rule-card">
            <h3>4. Ники и профили</h3>
            <p>Профиль — часть атмосферы и безопасности.</p>
            <ul>
              <li>Ники и аватары без непристойного контента, насилия и политической агитации.</li>
              <li>Запрещено выдавать себя за других игроков или администрацию.</li>
              <li>Реклама и спам в профиле удаляются.</li>
            </ul>
          </article>

          <article id="rule-streams" class="rule-card">
            <h3>5. Стримы и записи</h3>
            <p>Делитесь контентом ответственно.</p>
            <ul>
              <li>Предупреждайте участников, если ведете запись или трансляцию.</li>
              <li>Не публикуйте приватные данные и личные переписки.</li>
              <li>Запрещены нарезки с унижением или травлей участников.</li>
            </ul>
          </article>

          <article id="rule-moderation" class="rule-card">
            <h3>6. Модерация и санкции</h3>
            <p>Мы действуем быстро и прозрачно, чтобы сохранить порядок.</p>
            <ul>
              <li>Санкции: предупреждение, временный мьют, блокировка комнаты или аккаунта.</li>
              <li>Серьезные нарушения могут привести к моментальному бану.</li>
              <li>Повторные нарушения усиливают наказание.</li>
            </ul>
          </article>
        </section>

        <section id="serious" class="notice">
          <div class="notice-text">
            <h2>Что считается серьезным нарушением</h2>
            <p>
              За эти действия аккаунт может быть заблокирован без предупреждения.
              Мы ценим безопасность игроков и репутацию сообщества.
            </p>
          </div>
          <div class="notice-list">
            <div class="notice-item">Угрозы, ксенофобия, разжигание ненависти</div>
            <div class="notice-item">Доксинг и публикация личной информации</div>
            <div class="notice-item">Сговор, подсказки, стрим-снайпинг</div>
            <div class="notice-item">Мошенничество и попытки доступа к чужим аккаунтам</div>
          </div>
        </section>

        <section id="acceptance" class="footer-card">
          <div class="footer-text">
            <h2>Принятие правил</h2>
            <p>
              Используя сайт и входя в комнаты, вы подтверждаете, что ознакомились с правилами
              и согласны их соблюдать. В спорных ситуациях решения администрации являются финальными.
            </p>
          </div>
          <div class="footer-meta">
            <div class="meta-item">
              <span class="label">Свежая версия</span>
              <span class="value">Всегда доступна на этой странице</span>
            </div>
            <div class="meta-item">
              <span class="label">Совет</span>
              <span class="value">Сохраняйте уважительный тон даже в острой дискуссии</span>
            </div>
          </div>
        </section>
      </div>

      <aside class="rules-toc" aria-label="Содержание страницы">
        <div class="toc-card">
          <span class="toc-title">Содержание</span>
          <nav class="toc-links">
            <a v-for="item in tocLinks" :key="item.id" :href="`#${item.id}`" :class="{ active: activeId === item.id }"
               :aria-current="activeId === item.id ? 'location' : undefined" @click="onTocClick($event, item.id)">
              {{ item.label }}
            </a>
          </nav>
        </div>
      </aside>
    </div>
  </main>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'

type TocItem = {
  id: string
  label: string
}

const tocLinks: TocItem[] = [
  { id: 'intro', label: 'Введение' },
  { id: 'rule-respect', label: '1. Уважение и безопасность' },
  { id: 'rule-fair', label: '2. Честная игра' },
  { id: 'rule-behavior', label: '3. Поведение в комнате' },
  { id: 'rule-profiles', label: '4. Ники и профили' },
  { id: 'rule-streams', label: '5. Стримы и записи' },
  { id: 'rule-moderation', label: '6. Модерация и санкции' },
  { id: 'serious', label: 'Серьезные нарушения' },
  { id: 'acceptance', label: 'Принятие правил' },
]

const activeId = ref(tocLinks[0]?.id ?? '')
let observer: IntersectionObserver | null = null

function setActive(id: string) {
  if (id && activeId.value !== id) activeId.value = id
}

function onTocClick(event: MouseEvent, id: string) {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  const el = document.getElementById(id)
  if (!el) return
  event.preventDefault()
  setActive(id)
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  el.scrollIntoView({ behavior: prefersReduced ? 'auto' : 'smooth', block: 'start' })
  history.replaceState(null, '', `#${id}`)
}

function observeSections() {
  const targets = tocLinks.map(item => document.getElementById(item.id)).filter((el): el is HTMLElement => Boolean(el))
  if (!targets.length) return

  observer = new IntersectionObserver((entries) => {
    const visible = entries.filter(entry => entry.isIntersecting)
    if (!visible.length) return
    visible.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
    const top = visible[0].target as HTMLElement
    setActive(top.id)
  }, {
    rootMargin: '-30% 0px -60% 0px',
    threshold: 0,
  })

  targets.forEach(el => observer?.observe(el))
}

onMounted(() => {
  observeSections()
  const hash = window.location.hash.replace('#', '')
  if (hash && tocLinks.some(item => item.id === hash)) {
    const el = document.getElementById(hash)
    if (el) {
      el.scrollIntoView({ behavior: 'auto', block: 'start' })
      setActive(hash)
    }
  }
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
})
</script>

<style scoped lang="scss">
.rules {
  width: 60%;
  margin: 20px auto;
  line-height: 1.5;
  overflow: auto;
  scrollbar-width: none;
  [id] {
    scroll-margin-top: 90px;
  }
  .rules-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 300px;
    gap: 20px;
    align-items: start;
  }
  .rules-content {
    display: flex;
    flex-direction: column;
    gap: 20px;
    min-width: 0;
  }
  .rules-toc {
    position: sticky;
    top: 0;
    align-self: start;
    .toc-card {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 16px;
      border-radius: 10px;
      background-color: $graphite;
      border: 1px solid $grey;
      box-shadow: 0 12px 24px rgba($black, 0.25);
    }
    .toc-title {
      font-size: 12px;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: $ashy;
    }
    .toc-links {
      display: flex;
      flex-direction: column;
      gap: 6px;
      a {
        padding: 5px 15px;
        border-radius: 5px;
        border: 1px solid transparent;
        background-color: $dark;
        color: $fg;
        font-size: 14px;
        text-decoration: none;
        transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out, color 0.25s ease-in-out;
        &:hover {
          background-color: $lead;
          border-color: $grey;
          color: $white;
        }
        &.active {
          background-color: $lead;
          border-color: $orange;
          color: $white;
          box-shadow: inset 8px 0 0 $orange;
        }
      }
    }
  }
  .hero {
    position: relative;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
    padding: 24px;
    border-radius: 12px;
    background: linear-gradient(to right, $lead, $dark);
    border: 1px solid $grey;
    box-shadow: 0 18px 35px rgba($black, 0.25);
    overflow: hidden;
    animation: liftIn 0.25s ease-out both;
    &::before,
    &::after {
      content: '';
      position: absolute;
      border-radius: 50%;
      filter: blur(0);
      opacity: 0.5;
    }
    &::before {
      width: 320px;
      height: 320px;
      top: -160px;
      left: -120px;
      background: radial-gradient(circle, $orange, transparent 50%);
    }
    &::after {
      width: 400px;
      height: 400px;
      bottom: -200px;
      right: -130px;
      background: radial-gradient(circle, $green, transparent 50%);
    }
    .hero-content {
      position: relative;
      z-index: 1;
      display: flex;
      flex-direction: column;
      gap: 12px;
      .eyebrow {
        margin: 0;
        font-size: 12px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: $ashy;
      }
      h1 {
        margin: 0;
        font-size: 35px;
        letter-spacing: 1px;
      }
      .lead {
        margin: 0;
        color: $fg;
        max-width: 550px;
      }
      .tags {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        .pill {
          padding: 4px 12px;
          border-radius: 50px;
          border: 1px solid $grey;
          background-color: $dark;
          font-size: 12px;
          letter-spacing: 1px;
          text-transform: uppercase;
        }
      }
      .meta {
        display: flex;
        flex-wrap: wrap;
        gap: 12px 16px;
        .meta-item {
          display: flex;
          flex-direction: column;
          gap: 4px;
          padding: 8px 10px;
          border-radius: 8px;
          background-color: $graphite;
          border: 1px solid $grey;
          min-width: 100px;
          .label {
            font-size: 12px;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: $ashy;
          }
          .value {
            font-size: 14px;
            color: $fg;
          }
        }
      }
    }
  }
  .rules-grid {
    display: grid;
    grid-template-columns: repeat(1, minmax(0, 1fr));
    gap: 16px;
    .rule-card {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 18px;
      border-radius: 10px;
      background-color: $graphite;
      border: 1px solid $grey;
      box-shadow: 0 10px 22px rgba($black, 0.25);
      animation: liftIn 0.25s ease-out both;
      h3 {
        margin: 0;
        font-size: 18px;
        color: $fg;
      }
      p {
        margin: 0;
        color: $ashy;
      }
      ul {
        margin: 0;
        padding-left: 18px;
        display: grid;
        gap: 6px;
        li {
          color: $fg;
        }
      }
      &:nth-child(2) { animation-delay: 0.15s; }
      &:nth-child(3) { animation-delay: 0.25s; }
      &:nth-child(4) { animation-delay: 0.15s; }
      &:nth-child(5) { animation-delay: 0.25s; }
      &:nth-child(6) { animation-delay: 0.15s; }
    }
  }
  .notice {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 18px;
    padding: 20px;
    border-radius: 12px;
    background: linear-gradient(to right, $graphite, $lead);
    border: 1px solid $orange;
    box-shadow: 0 16px 30px rgba($black, 0.25);
    animation: liftIn 0.25s ease-out both;
    .notice-text {
      h2 {
        margin: 0 0 8px;
        font-size: 20px;
      }
      p {
        margin: 0;
        color: $ashy;
      }
    }
    .notice-list {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      .notice-item {
        padding: 10px 12px;
        border-radius: 8px;
        background-color: $dark;
        border: 1px solid $grey;
        font-size: 14px;
        color: $fg;
      }
    }
  }
  .footer-card {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    align-items: center;
    justify-content: space-between;
    padding: 20px 20px 400px;
    border-radius: 12px;
    background-color: $graphite;
    border: 1px solid $grey;
    box-shadow: 0 12px 24px rgba($black, 0.25);
    animation: liftIn 0.25s ease-out both;
    .footer-text {
      max-width: 600px;
      h2 {
        margin: 0 0 8px;
        font-size: 20px;
      }
      p {
        margin: 0;
        color: $ashy;
      }
    }
    .footer-meta {
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-width: 240px;
      .meta-item {
        display: flex;
        flex-direction: column;
        gap: 4px;
        padding: 8px 10px;
        border-radius: 8px;
        background-color: $graphite;
        border: 1px solid $grey;
        .label {
          font-size: 12px;
          letter-spacing: 1px;
          text-transform: uppercase;
          color: $ashy;
        }
        .value {
          font-size: 14px;
          color: $fg;
        }
      }
    }
  }
}

@keyframes liftIn {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1280px) {
  .rules {
    .rules-layout {
      grid-template-columns: 1fr;
    }
    .rules-toc {
      display: none;
    }
    .hero {
      grid-template-columns: 1fr;
    }
    .rules-grid {
      grid-template-columns: 1fr;
    }
    .notice {
      grid-template-columns: 1fr;
    }
    .notice-list {
      grid-template-columns: 1fr;
    }
  }
}
</style>
