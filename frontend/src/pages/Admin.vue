<template>
  <section class="admin">
    <header>
      <nav class="tabs" aria-label="Админ" role="tablist">
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'site' }"
                :aria-selected="activeTab === 'site'" @click="activeTab = 'site'">
          Параметры сайта
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'game' }"
                :aria-selected="activeTab === 'game'" @click="activeTab = 'game'">
          Параметры игры
        </button>
      </nav>
      <router-link class="btn nav" :to="{ name: 'home' }" aria-label="На главную">На главную</router-link>
    </header>

    <Transition name="tab-fade" mode="out-in">
      <div :key="activeTab" class="tab-panel">
        <div v-if="loading" class="loading">Загрузка...</div>

        <div v-else-if="activeTab === 'site'">
          <div class="grid">
            <div class="block">
              <h3>Доступ</h3>
              <div class="switch">
                <span>Регистрация</span>
                <label>
                  <input type="checkbox" v-model="site.registration_enabled" :disabled="savingSite" aria-label="Регистрация" />
                  <div class="slider">
                    <span>Нет</span>
                    <span>Да</span>
                  </div>
                </label>
              </div>
              <div class="switch">
                <span>Создание комнат</span>
                <label>
                  <input type="checkbox" v-model="site.rooms_can_create" :disabled="savingSite" aria-label="Создание комнат" />
                  <div class="slider">
                    <span>Нет</span>
                    <span>Да</span>
                  </div>
                </label>
              </div>
              <div class="switch">
                <span>Запуск игр</span>
                <label>
                  <input type="checkbox" v-model="site.games_can_start" :disabled="savingSite" aria-label="Запуск игр" />
                  <div class="slider">
                    <span>Нет</span>
                    <span>Да</span>
                  </div>
                </label>
              </div>
            </div>

            <div class="block">
              <h3>Лимиты комнат</h3>
              <div class="ui-input" :class="{ filled: Number.isFinite(site.rooms_limit_global) }">
                <input id="rooms-limit-global" v-model.number="site.rooms_limit_global" type="number" min="1" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSite" />
                <label for="rooms-limit-global">Общий лимит комнат</label>
                <div class="underline"><span></span></div>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(site.rooms_limit_per_user) }">
                <input id="rooms-limit-user" v-model.number="site.rooms_limit_per_user" type="number" min="1" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSite" />
                <label for="rooms-limit-user">Лимит комнат на пользователя</label>
                <div class="underline"><span></span></div>
              </div>
            </div>
          </div>
          <div class="form-actions">
            <button class="btn dark" :disabled="savingSite" @click="saveSite">Сохранить</button>
          </div>
        </div>

        <div v-else class="grid">
          <div class="block">
            <h3>Роли и ночь</h3>
            <div class="ui-input" :class="{ filled: Number.isFinite(game.game_min_ready_players) }">
              <input id="game-min-ready" v-model.number="game.game_min_ready_players" type="number" min="1" step="1"
                     placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingGame" />
              <label for="game-min-ready">Минимум готовых игроков</label>
              <div class="underline"><span></span></div>
            </div>
            <div class="ui-input" :class="{ filled: Number.isFinite(game.role_pick_seconds) }">
              <input id="role-pick-seconds" v-model.number="game.role_pick_seconds" type="number" min="1" step="1"
                     placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingGame" />
              <label for="role-pick-seconds">Выбор ролей (сек)</label>
              <div class="underline"><span></span></div>
            </div>
            <div class="ui-input" :class="{ filled: Number.isFinite(game.mafia_talk_seconds) }">
              <input id="mafia-talk-seconds" v-model.number="game.mafia_talk_seconds" type="number" min="1" step="1"
                     placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingGame" />
              <label for="mafia-talk-seconds">Обсуждение мафии (сек)</label>
              <div class="underline"><span></span></div>
            </div>
            <div class="ui-input" :class="{ filled: Number.isFinite(game.night_action_seconds) }">
              <input id="night-action-seconds" v-model.number="game.night_action_seconds" type="number" min="1" step="1"
                     placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingGame" />
              <label for="night-action-seconds">Ночные действия (сек)</label>
              <div class="underline"><span></span></div>
            </div>
          </div>

          <div class="block">
            <h3>День и голосование</h3>
            <div class="ui-input" :class="{ filled: Number.isFinite(game.player_talk_seconds) }">
              <input id="player-talk-seconds" v-model.number="game.player_talk_seconds" type="number" min="1" step="1"
                     placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingGame" />
              <label for="player-talk-seconds">Речь игрока (сек)</label>
              <div class="underline"><span></span></div>
            </div>
            <div class="ui-input" :class="{ filled: Number.isFinite(game.player_talk_short_seconds) }">
              <input id="player-talk-short-seconds" v-model.number="game.player_talk_short_seconds" type="number"
                     min="1" step="1" placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingGame" />
              <label for="player-talk-short-seconds">Короткая речь (сек)</label>
              <div class="underline"><span></span></div>
            </div>
            <div class="ui-input" :class="{ filled: Number.isFinite(game.player_foul_seconds) }">
              <input id="player-foul-seconds" v-model.number="game.player_foul_seconds" type="number" min="1" step="1"
                     placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingGame" />
              <label for="player-foul-seconds">Фол (сек)</label>
              <div class="underline"><span></span></div>
            </div>
            <div class="ui-input" :class="{ filled: Number.isFinite(game.vote_seconds) }">
              <input id="vote-seconds" v-model.number="game.vote_seconds" type="number" min="1" step="1"
                     placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingGame" />
              <label for="vote-seconds">Голосование (сек)</label>
              <div class="underline"><span></span></div>
            </div>
          </div>
          <div class="form-actions">
            <button class="btn dark" :disabled="savingGame" @click="saveGame">Сохранить</button>
          </div>
        </div>
      </div>
    </Transition>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { useSettingsStore } from '@/store'

type SiteSettings = {
  registration_enabled: boolean
  rooms_can_create: boolean
  games_can_start: boolean
  rooms_limit_global: number
  rooms_limit_per_user: number
}

type GameSettings = {
  game_min_ready_players: number
  role_pick_seconds: number
  mafia_talk_seconds: number
  player_talk_seconds: number
  player_talk_short_seconds: number
  player_foul_seconds: number
  night_action_seconds: number
  vote_seconds: number
}

const activeTab = ref<'site' | 'game'>('site')
const loading = ref(true)
const savingSite = ref(false)
const savingGame = ref(false)

const site = reactive<SiteSettings>({
  registration_enabled: true,
  rooms_can_create: true,
  games_can_start: true,
  rooms_limit_global: 100,
  rooms_limit_per_user: 3,
})

const game = reactive<GameSettings>({
  game_min_ready_players: 5,
  role_pick_seconds: 10,
  mafia_talk_seconds: 3,
  player_talk_seconds: 60,
  player_talk_short_seconds: 30,
  player_foul_seconds: 4,
  night_action_seconds: 10,
  vote_seconds: 3,
})

const settingsStore = useSettingsStore()

async function loadSettings(): Promise<void> {
  loading.value = true
  try {
    const { data } = await api.get('/admin/settings')
    Object.assign(site, data?.site || {})
    Object.assign(game, data?.game || {})
  } catch {
    void alertDialog('Не удалось загрузить настройки')
  } finally {
    loading.value = false
  }
}

async function saveSite(): Promise<void> {
  if (savingSite.value) return
  savingSite.value = true
  try {
    const { data } = await api.patch('/admin/settings/site', site)
    Object.assign(site, data || {})
    settingsStore.applyPublic({
      registration_enabled: site.registration_enabled,
      rooms_can_create: site.rooms_can_create,
      games_can_start: site.games_can_start,
    })
    void alertDialog('Настройки сайта сохранены')
  } catch {
    void alertDialog('Не удалось сохранить настройки сайта')
  } finally {
    savingSite.value = false
  }
}

async function saveGame(): Promise<void> {
  if (savingGame.value) return
  savingGame.value = true
  try {
    const { data } = await api.patch('/admin/settings/game', game)
    Object.assign(game, data || {})
    void alertDialog('Настройки игры сохранены')
  } catch {
    void alertDialog('Не удалось сохранить настройки игры')
  } finally {
    savingGame.value = false
  }
}

onMounted(() => {
  void loadSettings()
})
</script>

<style scoped lang="scss">
.admin {
  display: flex;
  flex-direction: column;
  margin: 0 10px;
  padding: 10px;
  border-radius: 5px;
  background-color: $dark;
  header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
  }
  .btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 20px;
    gap: 5px;
    height: 40px;
    border: none;
    border-radius: 5px;
    background-color: $fg;
    font-size: 14px;
    color: $bg;
    font-family: Manrope-Medium;
    line-height: 1;
    text-decoration: none;
    cursor: pointer;
    transition: opacity 0.25s ease-in-out, color 0.25s ease-in-out, border-radius 0.25s ease-in-out, background-color 0.25s ease-in-out;
    &:hover {
      background-color: $white;
    }
    &.nav {
      font-size: 16px;
      border-radius: 5px 5px 0 0;
    }
    &.dark {
      background-color: $lead;
      color: $fg;
      &:hover {
        background-color: rgba($grey, 0.5);
      }
    }
    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }
  .tabs {
    display: flex;
    align-items: flex-end;
    width: 66%;
    height: 30px;
    .tab {
      width: 240px;
      height: 30px;
      border: none;
      border-radius: 5px 5px 0 0;
      background-color: $graphite;
      color: $fg;
      font-size: 18px;
      font-family: Manrope-Medium;
      line-height: 1;
      cursor: pointer;
      transition: opacity 0.25s ease-in-out, height 0.25s ease-in-out, background-color 0.25s ease-in-out;
      &.active {
        height: 40px;
        background-color: $lead;
      }
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
  }
}

.tab-panel {
  margin-top: 10px;
}

.loading {
  padding: 20px;
  color: $fg;
  font-family: Manrope-Medium;
}

.grid {
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr 1fr;
}

.block {
  border: 3px solid $lead;
  border-radius: 5px;
  padding: 15px;
  h3 {
    margin: 0 0 20px;
    font-size: 20px;
    color: $fg;
  }
  .ui-input + .ui-input {
    margin-top: 12px;
  }
  .switch + .switch {
    margin-top: 12px;
  }
}

.form-actions {
  margin-top: 15px;
  display: flex;
  justify-content: flex-end;
}
.grid .form-actions {
  grid-column: 1 / -1;
}

.ui-input {
  display: block;
  position: relative;
  width: 100%;
  box-shadow: 3px 3px 5px rgba($black, 0.25);
  input {
    width: calc(100% - 22px);
    padding: 20px 10px 5px;
    border: 1px solid $lead;
    border-radius: 5px 5px 0 0;
    background-color: $graphite;
    color: $fg;
    font-size: 16px;
    font-family: Manrope-Medium;
    line-height: 1;
    outline: none;
    transition: border-color 0.25s ease-in-out, background-color 0.25s ease-in-out;
  }
  input::placeholder {
    color: transparent;
  }
  label {
    position: absolute;
    top: 50%;
    left: 12px;
    color: $fg;
    transform: translateY(-50%);
    pointer-events: none;
    transition: all 0.25s ease-in-out;
  }
  .underline {
    position: absolute;
    left: 0;
    right: 0;
    bottom: -3px;
    height: 3px;
    border-radius: 0 0 3px 3px;
    overflow: hidden;
    span {
      position: absolute;
      left: 0;
      bottom: 0;
      height: 3px;
      width: 0;
      background-color: $fg;
      transition: width 0.25s ease-in-out;
    }
  }
  .underline::before {
    content: "";
    position: absolute;
    inset: 0;
    background-color: $lead;
    transition: background-color 0.25s ease-in-out;
  }
}

.ui-input:focus-within label,
.ui-input input:not(:placeholder-shown) + label,
.ui-input.filled label {
  top: 5px;
  left: 10px;
  transform: none;
  font-size: 12px;
  color: $grey;
}

.switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  label {
    position: relative;
    width: 170px;
    height: 25px;
    box-shadow: 3px 3px 5px rgba($black, 0.25);
    input {
      position: absolute;
      opacity: 0;
      width: 0;
      height: 0;
    }
    .slider {
      display: flex;
      align-items: center;
      justify-content: space-around;
      position: absolute;
      inset: 0;
      cursor: pointer;
      border: 1px solid $lead;
      border-radius: 5px;
      background-color: $graphite;
      span {
        position: relative;
        width: 100%;
        color: $fg;
        font-size: 14px;
        text-align: center;
        z-index: 2;
      }
    }
    .slider::before {
      content: "";
      position: absolute;
      left: 0;
      width: 50%;
      height: 100%;
      border-radius: 5px;
      background-color: $lead;
      transition: transform 0.25s ease-in-out;
    }
    input:checked + .slider::before {
      transform: translateX(100%);
    }
  }
}

.tab-fade-enter-active,
.tab-fade-leave-active {
  transition: opacity 0.2s ease-in-out;
}
.tab-fade-enter-from,
.tab-fade-leave-to {
  opacity: 0;
}

@media (max-width: 1280px) {
  .admin .tabs {
    width: 100%;
    flex-wrap: wrap;
    gap: 6px;
    height: auto;
    .tab {
      width: 100%;
      height: 36px;
      border-radius: 5px;
      &.active {
        height: 36px;
      }
    }
  }
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
