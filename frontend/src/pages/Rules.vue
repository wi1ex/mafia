<template>
  <main class="rules" ref="rulesEl">
    <div class="rules-layout">
      <div class="rules-content">
        <section id="intro" class="hero">
          <div class="hero-content">
            <p class="eyebrow">deceit.games</p>
            <h1>Правила сообщества</h1>
            <div class="tags">
              <span class="pill">14+</span>
              <span class="pill">Редакция от 21.01.2026</span>
            </div>
          </div>
        </section>

        <section id="sanctions" class="notice">
          <div class="notice-text">
            <h2>Нотация санкций</h2>
            <p>Конкретный вид санкции, срок и дополнительные меры определяются Администрацией с учётом
              характера нарушения, повторяемости, последствий и иных обстоятельств.</p>
          </div>
          <div class="notice-list">
            <div class="notice-item notice-item--suspend">SUSPEND — временное отстранение от участия в играх.</div>
            <div class="notice-item notice-item--timeout">TIMEOUT — временное ограничение доступа к комнатам.</div>
            <div class="notice-item notice-item--ban">BAN — постоянная блокировка доступа к платформе.</div>
          </div>
        </section>

        <section class="rules-grid">
          <article id="section-1" class="rule-card">
            <h3>1. Принятие правил, регистрация и изменения</h3>
            <ul>
              <li>1.1. Использование платформы deceit.games означает согласие с настоящими Правилами.</li>
              <li>1.2. Новая редакция публикуется на сайте и применяется с даты публикации (или иной указанной даты). Продолжение использования платформы означает согласие с изменениями.</li>
              <li>1.3. Для регистрации и авторизации пользователь использует никнейм и пароль, созданные при регистрации.</li>
              <li>1.4. Для участия в играх требуется верификация через Telegram-бота. Верификация подтверждает привязку Telegram-аккаунта к аккаунту на платформе.</li>
              <li>1.5. Пользователь может отозвать согласие на обработку данных, удалив свой аккаунт в Личном кабинете.</li>
              <li>1.6. При применении санкций доступ к платформе может быть ограничен/заблокирован для соответствующего аккаунта пользователя на основе аккаунта, привязанного к Telegram.</li>
            </ul>
          </article>

          <article id="section-2" class="rule-card">
            <h3>2. Возраст и допустимость использования</h3>
            <ul>
              <li>2.1. Платформа предназначена для пользователей не младше 14 лет. При выявлении нарушения возрастного ограничения доступ может быть запрещён.</li>
              <li>2.2. Если на платформе возможны видео/аудио-трансляции, пользователь подтверждает, что осознаёт риски публичного общения и обязуется соблюдать ограничения по контенту (включая 18+).</li>
              <li>2.3. Несовершеннолетним запрещено публиковать/передавать персональные данные и контент, если это нарушает применимое законодательство или настоящие Правила.</li>
            </ul>
          </article>

          <article id="section-3" class="rule-card">
            <h3>3. Аккаунт и безопасность</h3>
            <ul>
              <li>3.1. Запрещено передавать доступ к своему аккаунту третьим лицам.</li>
              <li>3.2. Запрещён мультиаккаунтинг и обход санкций (вход под другим аккаунтом/устройством/идентификатором для избегания наказания).</li>
              <li>3.3. Запрещена выдача себя за другое лицо, за администрацию платформы или за ведущего/судью в игровых комнатах, а также фальсификация статуса или полномочий.</li>
              <li>3.4. При подозрении на компрометацию аккаунта пользователь обязан уведомить администрацию.</li>
            </ul>
          </article>

          <article id="section-4" class="rule-card">
            <h3>4. Общие правила общения, контента и поведения</h3>
            <h4>4.1. Уважение и запрет токсичности</h4>
            <ul>
              <li>4.1.1. Запрещены оскорбления, унижение, травля, клевета, жесткий троллинг, провокации, шантаж, угрозы, подстрекательство.</li>
              <li>4.1.2. Запрещены пожелания смерти/болезни, призывы к самоубийству/самоповреждению.</li>
              <li>4.1.3. Запрещена дискриминация/разжигание ненависти по полу, гендеру, расе, национальности, языку, возрасту, инвалидности, религии, политическим взглядам.</li>
            </ul>
            <h4>4.2. Приватность и личная жизнь</h4>
            <ul>
              <li>4.2.1. Запрещён доксинг: публикация/угрозы публикации персональных данных без согласия (адреса, телефоны, документы, банковские сведения, переписки и т.п.).</li>
              <li>4.2.2. Запрещены попытки выманивания персональных данных, фишинг, скам.</li>
              <li>4.2.3. Запрещено преследование, навязчивые контакты, сексуальные домогательства.</li>
            </ul>
            <h4>4.3. Запрещённый контент</h4>
            <ul>
              <li>4.3.1. Запрещены порнография, сексуальный контент с участием/образом несовершеннолетних, контент сексуальной эксплуатации.</li>
              <li>4.3.2. Запрещён шок-контент, демонстрация насилия ради эффекта.</li>
              <li>4.3.3. Запрещена пропаганда/сбыт/инструкции по наркотикам и запрещённым веществам.</li>
              <li>4.3.4. Запрещены призывы к насилию/экстремизму, символика и пропаганда запрещённых организаций.</li>
            </ul>
            <h4>4.4. Спам и злоупотребления коммуникацией</h4>
            <ul>
              <li>4.4.1. Запрещён спам, флуд, массовые однотипные сообщения, навязчивая реклама.</li>
              <li>4.4.2. Запрещены бессмысленные жалобы и злоупотребление обращениями к модерации.</li>
            </ul>
            <h4>4.5. Никнеймы, аватары и названия комнат</h4>
            <ul>
              <li>4.5.1. Запрещены никнеймы/аватары/названия комнат, содержащие: мат и грубую вульгарность, оскорбления, дискриминацию/хейт, экстремизм, порнографию, призывы к насилию, рекламу/донат-ссылки без согласования, вводящие в заблуждение обозначения (в т.ч. «модератор», «админ», имитация служебных статусов), а также выдача себя за другого человека.</li>
              <li>4.5.2. Администрация вправе потребовать изменить никнейм/аватар/название комнаты/описание или удалить контент. Отказ выполнить требование рассматривается как нарушение.</li>
            </ul>
          </article>

          <article id="section-5" class="rule-card">
            <h3>5. Камера/микрофон, участие в комнате, запись</h3>
            <ul>
              <li>5.1. Запрещено умышленно создавать помехи участию в комнате (постоянные выключения, демонстративное «затыкание ушей», намеренное скрытие лица при обязательной камере и т.п.), если режим комнаты требует видимость/слышимость.</li>
              <li>5.2. Пользователь понимает, что другие участники могут вести запись экрана/звука для доказательства нарушений, если это не запрещено законом. Администрация может запрашивать такие доказательства при рассмотрении жалоб.</li>
            </ul>
          </article>

          <article id="section-6" class="rule-card">
            <h3>6. Честность, реклама, безопасность</h3>
            <ul>
              <li>6.1. Запрещены попытки взлома, эксплуатация уязвимостей, DDoS, вмешательство в сетевое взаимодействие, обход ограничений.</li>
              <li>6.2. Запрещено использование ботов/скриптов/автоматизации без разрешения.</li>
              <li>6.3. Запрещено целенаправленно препятствовать развитию платформы, дискредитировать администрацию через ложные обвинения, подделывать доказательства.</li>
              <li>6.4. Запрещена подделка скриншотов/логов/видео и иных материалов с целью наказания других пользователей.</li>
              <li>6.5. Запрещена реклама, публикация ссылок на донат/платёжные страницы, сбор средств без согласования с администрацией.</li>
            </ul>
          </article>

          <article id="section-7" class="rule-card">
            <h3>7. Жалобы, доказательства, модерация и апелляции</h3>
            <ul>
              <li>7.1. В игровых комнатах нарушения в рамках игры фиксирует ведущий/судья. Также пользователь может подать жалобу в администрацию.</li>
              <li>7.2. Жалобы по оскорблениям/личным конфликтам могут приниматься от пострадавшей стороны, нарушения приватности/мошенничества/безопасности/запрещённого контента рассматриваются по обращению любого пользователя или по инициативе администрации.</li>
              <li>7.3. Допустимые доказательства: записи экрана, скриншоты, логи комнаты, системные события.</li>
              <li>7.4. Администрация вправе удалять контент, ограничивать доступ к функциям, блокировать комнаты/аккаунты и применять санкции по настоящим Правилам.</li>
              <li>7.5. Апелляции: пользователь вправе подать апелляцию в течение 7 дней, приложив аргументы и доказательства. Решение принимает администрация. Повторные апелляции по тем же фактам могут быть отклонены.</li>
            </ul>
          </article>

          <article id="mafia-rules" class="rule-card">
            <h3>8. Правила для игры «Мафия»</h3>
            <ul>
              <li>8.1. Запрещены подсказки извне, переписка с третьими лицами по игре, просмотр стрима игры, находясь в игре, «слив роли».</li>
              <li>8.2. Запрещено преднамеренное «вскрытие роли» другим игрокам любыми способами.</li>
              <li>8.3. Запрещено влияние на игру через сообщения/статусы «со стороны», скрины, откаты и т.п.</li>
              <li>8.4. Запрещены клятвы/пари/шантаж/подкуп для влияния на голосование или «доказательства роли».</li>
              <li>8.5. Запрещено озвучивать речевую информацию на языке, который очевидно скрывает смысл от ведущего/судьи или большинства игроков.</li>
              <li>8.6. После решающего убийства/голосования, определившего результат игры, меры, связанные с игровым преимуществом, как правило, не применяются, если нарушение уже не могло повлиять на исход (кроме грубых нарушений поведения/безопасности, которые могут наказываться всегда).</li>
              <li>8.7. Ведущему запрещено злоупотреблять правами, требовать оплату за проведение игр (если владелец комнаты это запрещает), применять меры и совершать действия из личной выгоды.</li>
              <li>8.8. Ведущему запрещено раскрывать роли до окончания игры или подсказывать/комментировать так, что это внесет игровую информацию.</li>
            </ul>
          </article>
        </section>
      </div>

      <aside class="rules-toc" aria-label="Содержание страницы">
        <router-link class="btn-home" :to="{ name: 'home' }" aria-label="На главную">На главную</router-link>
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
  { id: 'sanctions', label: 'Нотация санкций' },
  { id: 'section-1', label: '1. Принятие правил, авторизация и изменения' },
  { id: 'section-2', label: '2. Возраст и допустимость использования' },
  { id: 'section-3', label: '3. Аккаунт, безопасность и добросовестность' },
  { id: 'section-4', label: '4. Общие правила общения, контента и поведения' },
  { id: 'section-5', label: '5. Камера/микрофон, участие в комнате, запись' },
  { id: 'section-6', label: '6. Честность, реклама, безопасность' },
  { id: 'section-7', label: '7. Жалобы, доказательства, модерация и апелляции' },
  { id: 'mafia-rules', label: '8. Игровые правила «Мафия»' },
]

const activeId = ref(tocLinks[0]?.id ?? '')
const lastId = tocLinks[tocLinks.length - 1]?.id ?? ''
const rulesEl = ref<HTMLElement | null>(null)
let rafId = 0
let sectionEls: HTMLElement[] = []
let scrollTarget: HTMLElement | Window | null = null

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

function collectSections() {
  sectionEls = tocLinks
    .map(item => document.getElementById(item.id))
    .filter((el): el is HTMLElement => Boolean(el))
}

function updateActiveFromScroll() {
  if (!sectionEls.length) return
  if (!lastId) return
  const cutoff = 120
  let current = sectionEls[0].id
  const container = rulesEl.value
  if (container) {
    const containerRect = container.getBoundingClientRect()
    for (const el of sectionEls) {
      const top = el.getBoundingClientRect().top - containerRect.top
      if (top - cutoff <= 0) {
        current = el.id
      } else {
        break
      }
    }
    const scrollBottom = container.scrollTop + container.clientHeight
    const scrollHeight = container.scrollHeight
    if (scrollBottom >= scrollHeight - 4) current = lastId
  } else {
    for (const el of sectionEls) {
      if (el.getBoundingClientRect().top - cutoff <= 0) {
        current = el.id
      } else {
        break
      }
    }
    const scrollBottom = window.scrollY + window.innerHeight
    const docHeight = document.documentElement.scrollHeight
    if (scrollBottom >= docHeight - 4) current = lastId
  }
  setActive(current)
}

function onScroll() {
  if (rafId) return
  rafId = window.requestAnimationFrame(() => {
    rafId = 0
    updateActiveFromScroll()
  })
}

onMounted(() => {
  collectSections()
  if (window.location.hash) {
    history.replaceState(null, '', `${window.location.pathname}${window.location.search}`)
  }
  if (rulesEl.value) {
    rulesEl.value.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  } else {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }
  setActive(tocLinks[0]?.id ?? '')
  updateActiveFromScroll()
  scrollTarget = rulesEl.value ?? window
  scrollTarget.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', onScroll)
})

onBeforeUnmount(() => {
  if (rafId) window.cancelAnimationFrame(rafId)
  rafId = 0
  sectionEls = []
  if (scrollTarget) scrollTarget.removeEventListener('scroll', onScroll)
  scrollTarget = null
  window.removeEventListener('resize', onScroll)
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
    display: flex;
    position: sticky;
    flex-direction: column;
    align-self: start;
    top: 0;
    gap: 10px;
    .btn-home {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 40px;
      border-radius: 10px;
      background-color: $fg;
      color: $bg;
      text-decoration: none;
      cursor: pointer;
      transition: background-color 0.25s ease-in-out;
      &:hover {
        background-color: $white;
      }
    }
    .toc-card {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 20px;
      border-radius: 10px;
      background-color: $graphite;
      border: 1px solid $grey;
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
      gap: 5px;
      a {
        padding: 5px 20px;
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
          box-shadow: inset 10px 0 0 $orange;
        }
      }
    }
  }
  .hero {
    position: relative;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
    padding: 20px;
    border-radius: 10px;
    background: linear-gradient(to right, $lead, $dark);
    border: 1px solid $grey;
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
      gap: 10px;
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
      .tags {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        .pill {
          padding: 5px 15px;
          border-radius: 50px;
          border: 1px solid $grey;
          background-color: $dark;
          font-size: 12px;
          letter-spacing: 1px;
          text-transform: uppercase;
        }
      }
    }
  }
  .rules-grid {
    display: grid;
    grid-template-columns: repeat(1, minmax(0, 1fr));
    gap: 15px;
    .rule-card {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 20px;
      border-radius: 10px;
      background-color: $graphite;
      border: 1px solid $grey;
      animation: liftIn 0.25s ease-out both;
      h3 {
        margin: 0;
        font-size: 18px;
        color: $fg;
      }
      h4 {
        margin: 5px 0 0;
        font-size: 15px;
        color: $fg;
      }
      p {
        margin: 0;
        color: $ashy;
      }
      ul {
        margin: 0;
        padding-left: 20px;
        display: grid;
        gap: 5px;
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
    gap: 20px;
    padding: 20px;
    border-radius: 10px;
    background: linear-gradient(to right, $graphite, $lead);
    border: 1px solid $grey;
    animation: liftIn 0.25s ease-out both;
    .notice-text {
      h2 {
        margin: 0 0 10px;
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
        padding: 5px 10px;
        border-radius: 10px;
        background-color: $dark;
        border: 1px solid $grey;
        font-size: 14px;
        color: $fg;
      }
      .notice-item--suspend {
        border-color: $yellow;
      }
      .notice-item--timeout {
        border-color: $orange;
      }
      .notice-item--ban {
        border-color: $red;
      }
    }
  }
}

@keyframes liftIn {
  from {
    opacity: 0;
    transform: translateY(10px);
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
