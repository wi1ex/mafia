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
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'stats' }"
                :aria-selected="activeTab === 'stats'" @click="activeTab = 'stats'">
          Статистика
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'logs' }"
                :aria-selected="activeTab === 'logs'" @click="activeTab = 'logs'">
          Логи
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'rooms' }"
                :aria-selected="activeTab === 'rooms'" @click="activeTab = 'rooms'">
          Комнаты
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'users' }"
                :aria-selected="activeTab === 'users'" @click="activeTab = 'users'">
          Пользователи
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
            <button class="btn dark" :disabled="savingSite || !isSiteDirty" @click="saveSite">Сохранить</button>
          </div>
        </div>

        <div v-else-if="activeTab === 'game'" class="grid">
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
            <button class="btn dark" :disabled="savingGame || !isGameDirty" @click="saveGame">Сохранить</button>
          </div>
        </div>

        <div v-else-if="activeTab === 'stats'">
          <div class="filters">
            <label class="field">
              <span>Месяц</span>
              <input type="month" v-model="statsMonth" :disabled="statsLoading" />
            </label>
            <button class="btn dark" :disabled="statsLoading" @click="loadStats">Обновить</button>
          </div>

          <div v-if="statsLoading" class="loading">Загрузка...</div>
          <div v-else class="stats">
            <div class="stats-grid">
              <div class="stat-card">
                <span class="label">Пользователи</span>
                <span class="value">{{ stats.total_users }}</span>
              </div>
              <div class="stat-card">
                <span class="label">Комнаты (всего)</span>
                <span class="value">{{ stats.total_rooms }}</span>
              </div>
              <div class="stat-card">
                <span class="label">Минуты комнат</span>
                <span class="value">{{ stats.total_room_minutes }}</span>
              </div>
              <div class="stat-card">
                <span class="label">Минуты трансляций</span>
                <span class="value">{{ stats.total_stream_minutes }}</span>
              </div>
              <div class="stat-card">
                <span class="label">Активные комнаты</span>
                <span class="value">{{ stats.active_rooms }}</span>
              </div>
              <div class="stat-card">
                <span class="label">Пользователи в комнатах</span>
                <span class="value">{{ stats.active_room_users }}</span>
              </div>
              <div class="stat-card">
                <span class="label">Онлайн на сайте</span>
                <span class="value">{{ stats.online_users }}</span>
              </div>
            </div>

            <div class="chart">
              <div v-if="stats.registrations.length === 0" class="muted">Нет данных</div>
              <div v-else class="chart-grid">
                <div v-for="point in stats.registrations" :key="point.date" class="chart-bar">
                  <div class="bar" :style="{ height: registrationHeight(point.count) }" />
                  <span class="bar-label">{{ point.date.slice(-2) }}</span>
                </div>
              </div>
              <div class="chart-legend">Регистрации по дням</div>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'logs'">
          <div class="filters">
            <label class="field">
              <span>Action</span>
              <select v-model="logsAction" :disabled="logsLoading">
                <option value="all">Все</option>
                <option v-for="act in logActions" :key="act" :value="act">{{ act }}</option>
              </select>
            </label>
            <label class="field">
              <span>Ник</span>
              <input type="text" v-model.trim="logsUser" :disabled="logsLoading" placeholder="Ник" />
            </label>
            <label class="field">
              <span>Дата</span>
              <input type="date" v-model="logsDay" :disabled="logsLoading" />
            </label>
            <label class="field">
              <span>Показать</span>
              <select v-model.number="logsLimit" :disabled="logsLoading">
                <option :value="20">20</option>
                <option :value="100">100</option>
              </select>
            </label>
            <button class="btn dark" :disabled="logsLoading" @click="applyLogs">Показать</button>
            <button class="btn" :disabled="logsLoading" @click="resetLogs">Сбросить</button>
          </div>

          <div v-if="logsLoading" class="loading">Загрузка...</div>
          <div v-else>
            <table class="table">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Ник</th>
                  <th>Action</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in logs" :key="row.id">
                  <td>{{ formatDateTime(row.created_at) }}</td>
                  <td>{{ row.username || '-' }}</td>
                  <td>{{ row.action }}</td>
                  <td>{{ row.details }}</td>
                </tr>
                <tr v-if="logs.length === 0">
                  <td colspan="4" class="muted">Нет данных</td>
                </tr>
              </tbody>
            </table>
            <div class="pager">
              <button class="btn" :disabled="logsPage <= 1" @click="prevLogs">Назад</button>
              <span>{{ logsPage }} / {{ logsPages }}</span>
              <button class="btn" :disabled="logsPage >= logsPages" @click="nextLogs">Вперед</button>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'rooms'">
          <div class="filters">
            <label class="field">
              <span>Ник</span>
              <input type="text" v-model.trim="roomsUser" :disabled="roomsLoading" placeholder="Ник" />
            </label>
            <label class="field">
              <span>Трансляции</span>
              <select v-model="roomsStreamOnly" :disabled="roomsLoading">
                <option :value="false">Все</option>
                <option :value="true">Только с трансляцией</option>
              </select>
            </label>
            <label class="field">
              <span>Показать</span>
              <select v-model.number="roomsLimit" :disabled="roomsLoading">
                <option :value="20">20</option>
                <option :value="100">100</option>
              </select>
            </label>
            <button class="btn dark" :disabled="roomsLoading" @click="applyRooms">Показать</button>
            <button class="btn" :disabled="roomsLoading" @click="resetRooms">Сбросить</button>
          </div>

          <div v-if="roomsLoading" class="loading">Загрузка...</div>
          <div v-else>
            <table class="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Название</th>
                  <th>Владелец</th>
                  <th>Приватность</th>
                  <th>Создана</th>
                  <th>Удалена</th>
                  <th>Посетители</th>
                  <th>Мин. стрима</th>
                  <th>Стрим</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rooms" :key="row.id">
                  <td>{{ row.id }}</td>
                  <td>{{ row.title }}</td>
                  <td>{{ row.creator_name }}</td>
                  <td>{{ row.privacy }}</td>
                  <td>{{ formatDateTime(row.created_at) }}</td>
                  <td>{{ row.deleted_at ? formatDateTime(row.deleted_at) : '-' }}</td>
                  <td>{{ row.visitors_count }}</td>
                  <td>{{ row.stream_minutes }}</td>
                  <td>{{ row.has_stream ? 'да' : 'нет' }}</td>
                </tr>
                <tr v-if="rooms.length === 0">
                  <td colspan="9" class="muted">Нет данных</td>
                </tr>
              </tbody>
            </table>
            <div class="pager">
              <button class="btn" :disabled="roomsPage <= 1" @click="prevRooms">Назад</button>
              <span>{{ roomsPage }} / {{ roomsPages }}</span>
              <button class="btn" :disabled="roomsPage >= roomsPages" @click="nextRooms">Вперед</button>
            </div>
          </div>
        </div>

        <div v-else>
          <div class="filters">
            <label class="field">
              <span>Ник</span>
              <input type="text" v-model.trim="usersUser" :disabled="usersLoading" placeholder="Ник" />
            </label>
            <label class="field">
              <span>Показать</span>
              <select v-model.number="usersLimit" :disabled="usersLoading">
                <option :value="20">20</option>
                <option :value="100">100</option>
              </select>
            </label>
            <button class="btn dark" :disabled="usersLoading" @click="applyUsers">Показать</button>
            <button class="btn" :disabled="usersLoading" @click="resetUsers">Сбросить</button>
          </div>

          <div v-if="usersLoading" class="loading">Загрузка...</div>
          <div v-else>
            <table class="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Ник</th>
                  <th>Роль</th>
                  <th>Регистрация</th>
                  <th>Последний вход</th>
                  <th>Комнат создано</th>
                  <th>Мин. в комнатах</th>
                  <th>Мин. стрима</th>
                  <th>Действие</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in users" :key="row.id">
                  <td>{{ row.id }}</td>
                  <td>{{ row.username || '-' }}</td>
                  <td>{{ row.role }}</td>
                  <td>{{ formatDateTime(row.registered_at) }}</td>
                  <td>{{ formatDateTime(row.last_login_at) }}</td>
                  <td>{{ row.rooms_created }}</td>
                  <td>{{ row.room_minutes }}</td>
                  <td>{{ row.stream_minutes }}</td>
                  <td>
                    <button class="btn dark" :disabled="usersRoleBusy[row.id]" @click="toggleUserRole(row)">
                      {{ row.role === 'admin' ? 'Снять админа' : 'Сделать админом' }}
                    </button>
                  </td>
                </tr>
                <tr v-if="users.length === 0">
                  <td colspan="9" class="muted">Нет данных</td>
                </tr>
              </tbody>
            </table>
            <div class="pager">
              <button class="btn" :disabled="usersPage <= 1" @click="prevUsers">Назад</button>
              <span>{{ usersPage }} / {{ usersPages }}</span>
              <button class="btn" :disabled="usersPage >= usersPages" @click="nextUsers">Вперед</button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive, computed } from 'vue'
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

type RegistrationPoint = {
  date: string
  count: number
}

type SiteStats = {
  total_users: number
  registrations: RegistrationPoint[]
  total_rooms: number
  total_room_minutes: number
  total_stream_minutes: number
  active_rooms: number
  active_room_users: number
  online_users: number
}

type LogRow = {
  id: number
  user_id?: number | null
  username?: string | null
  action: string
  details: string
  created_at: string
}

type RoomRow = {
  id: number
  creator: number
  creator_name: string
  title: string
  user_limit: number
  privacy: string
  created_at: string
  deleted_at?: string | null
  visitors_count: number
  stream_minutes: number
  has_stream: boolean
}

type UserRow = {
  id: number
  username?: string | null
  avatar_name?: string | null
  role: string
  registered_at: string
  last_login_at: string
  rooms_created: number
  room_minutes: number
  stream_minutes: number
}

const activeTab = ref<'site' | 'game' | 'stats' | 'logs' | 'rooms' | 'users'>('site')
const loading = ref(true)
const savingSite = ref(false)
const savingGame = ref(false)
const statsLoading = ref(false)
const logsLoading = ref(false)
const roomsLoading = ref(false)
const usersLoading = ref(false)

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
const siteSnapshot = ref('')
const gameSnapshot = ref('')

const statsMonth = ref('')
const stats = reactive<SiteStats>({
  total_users: 0,
  registrations: [],
  total_rooms: 0,
  total_room_minutes: 0,
  total_stream_minutes: 0,
  active_rooms: 0,
  active_room_users: 0,
  online_users: 0,
})

const logActions = ref<string[]>([])
const logs = ref<LogRow[]>([])
const logsTotal = ref(0)
const logsPage = ref(1)
const logsLimit = ref(20)
const logsAction = ref('all')
const logsUser = ref('')
const logsDay = ref('')

const rooms = ref<RoomRow[]>([])
const roomsTotal = ref(0)
const roomsPage = ref(1)
const roomsLimit = ref(20)
const roomsUser = ref('')
const roomsStreamOnly = ref(false)

const users = ref<UserRow[]>([])
const usersTotal = ref(0)
const usersPage = ref(1)
const usersLimit = ref(20)
const usersUser = ref('')
const usersRoleBusy = reactive<Record<number, boolean>>({})

function normalizeInt(value: number): number {
  return Number.isFinite(value) ? value : 0
}

function snapshotSite(): string {
  return JSON.stringify({
    registration_enabled: Boolean(site.registration_enabled),
    rooms_can_create: Boolean(site.rooms_can_create),
    games_can_start: Boolean(site.games_can_start),
    rooms_limit_global: normalizeInt(site.rooms_limit_global),
    rooms_limit_per_user: normalizeInt(site.rooms_limit_per_user),
  })
}

function snapshotGame(): string {
  return JSON.stringify({
    game_min_ready_players: normalizeInt(game.game_min_ready_players),
    role_pick_seconds: normalizeInt(game.role_pick_seconds),
    mafia_talk_seconds: normalizeInt(game.mafia_talk_seconds),
    player_talk_seconds: normalizeInt(game.player_talk_seconds),
    player_talk_short_seconds: normalizeInt(game.player_talk_short_seconds),
    player_foul_seconds: normalizeInt(game.player_foul_seconds),
    night_action_seconds: normalizeInt(game.night_action_seconds),
    vote_seconds: normalizeInt(game.vote_seconds),
  })
}

const isSiteDirty = computed(() => siteSnapshot.value !== snapshotSite())
const isGameDirty = computed(() => gameSnapshot.value !== snapshotGame())
const logsPages = computed(() => Math.max(1, Math.ceil(logsTotal.value / logsLimit.value)))
const roomsPages = computed(() => Math.max(1, Math.ceil(roomsTotal.value / roomsLimit.value)))
const usersPages = computed(() => Math.max(1, Math.ceil(usersTotal.value / usersLimit.value)))
const registrationsMax = computed(() => {
  const vals = stats.registrations.map(p => p.count)
  return Math.max(1, ...vals)
})

function formatDateTime(value?: string | null): string {
  if (!value) return '-'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return '-'
  return dt.toLocaleString()
}

function registrationHeight(count: number): string {
  const max = registrationsMax.value || 1
  const pct = Math.round((count / max) * 100)
  return `${Math.max(2, pct)}%`
}

async function loadSettings(): Promise<void> {
  loading.value = true
  try {
    const { data } = await api.get('/admin/settings')
    Object.assign(site, data?.site || {})
    Object.assign(game, data?.game || {})
    siteSnapshot.value = snapshotSite()
    gameSnapshot.value = snapshotGame()
  } catch {
    void alertDialog('Не удалось загрузить настройки')
    siteSnapshot.value = snapshotSite()
    gameSnapshot.value = snapshotGame()
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
    siteSnapshot.value = snapshotSite()
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
    gameSnapshot.value = snapshotGame()
    void alertDialog('Настройки игры сохранены')
  } catch {
    void alertDialog('Не удалось сохранить настройки игры')
  } finally {
    savingGame.value = false
  }
}

async function loadStats(): Promise<void> {
  if (statsLoading.value) return
  statsLoading.value = true
  try {
    const params = { month: statsMonth.value || undefined }
    const { data } = await api.get('/admin/stats', { params })
    Object.assign(stats, {
      total_users: data?.total_users ?? 0,
      registrations: Array.isArray(data?.registrations) ? data.registrations : [],
      total_rooms: data?.total_rooms ?? 0,
      total_room_minutes: data?.total_room_minutes ?? 0,
      total_stream_minutes: data?.total_stream_minutes ?? 0,
      active_rooms: data?.active_rooms ?? 0,
      active_room_users: data?.active_room_users ?? 0,
      online_users: data?.online_users ?? 0,
    })
  } catch {
    void alertDialog('Не удалось загрузить статистику')
  } finally {
    statsLoading.value = false
  }
}

async function loadLogActions(): Promise<void> {
  try {
    const { data } = await api.get('/admin/logs/actions')
    logActions.value = Array.isArray(data?.actions) ? data.actions : []
  } catch {
    logActions.value = []
  }
}

async function loadLogs(): Promise<void> {
  if (logsLoading.value) return
  logsLoading.value = true
  try {
    const params: Record<string, any> = {
      page: logsPage.value,
      limit: logsLimit.value,
      action: logsAction.value,
    }
    if (logsUser.value) params.username = logsUser.value
    if (logsDay.value) params.day = logsDay.value
    const { data } = await api.get('/admin/logs', { params })
    logs.value = Array.isArray(data?.items) ? data.items : []
    logsTotal.value = Number.isFinite(data?.total) ? data.total : 0
  } catch {
    void alertDialog('Не удалось загрузить логи')
  } finally {
    logsLoading.value = false
  }
}

async function loadRooms(): Promise<void> {
  if (roomsLoading.value) return
  roomsLoading.value = true
  try {
    const params: Record<string, any> = {
      page: roomsPage.value,
      limit: roomsLimit.value,
      stream_only: roomsStreamOnly.value || undefined,
    }
    if (roomsUser.value) params.username = roomsUser.value
    const { data } = await api.get('/admin/rooms', { params })
    rooms.value = Array.isArray(data?.items) ? data.items : []
    roomsTotal.value = Number.isFinite(data?.total) ? data.total : 0
  } catch {
    void alertDialog('Не удалось загрузить комнаты')
  } finally {
    roomsLoading.value = false
  }
}

async function loadUsers(): Promise<void> {
  if (usersLoading.value) return
  usersLoading.value = true
  try {
    const params: Record<string, any> = {
      page: usersPage.value,
      limit: usersLimit.value,
    }
    if (usersUser.value) params.username = usersUser.value
    const { data } = await api.get('/admin/users', { params })
    users.value = Array.isArray(data?.items) ? data.items : []
    usersTotal.value = Number.isFinite(data?.total) ? data.total : 0
  } catch {
    void alertDialog('Не удалось загрузить пользователей')
  } finally {
    usersLoading.value = false
  }
}

function applyLogs(): void {
  logsPage.value = 1
  void loadLogs()
}

function resetLogs(): void {
  logsAction.value = 'all'
  logsUser.value = ''
  logsDay.value = ''
  logsLimit.value = 20
  logsPage.value = 1
  void loadLogs()
}

function nextLogs(): void {
  if (logsPage.value >= logsPages.value) return
  logsPage.value += 1
  void loadLogs()
}

function prevLogs(): void {
  if (logsPage.value <= 1) return
  logsPage.value -= 1
  void loadLogs()
}

function applyRooms(): void {
  roomsPage.value = 1
  void loadRooms()
}

function resetRooms(): void {
  roomsUser.value = ''
  roomsStreamOnly.value = false
  roomsLimit.value = 20
  roomsPage.value = 1
  void loadRooms()
}

function nextRooms(): void {
  if (roomsPage.value >= roomsPages.value) return
  roomsPage.value += 1
  void loadRooms()
}

function prevRooms(): void {
  if (roomsPage.value <= 1) return
  roomsPage.value -= 1
  void loadRooms()
}

function applyUsers(): void {
  usersPage.value = 1
  void loadUsers()
}

function resetUsers(): void {
  usersUser.value = ''
  usersLimit.value = 20
  usersPage.value = 1
  void loadUsers()
}

function nextUsers(): void {
  if (usersPage.value >= usersPages.value) return
  usersPage.value += 1
  void loadUsers()
}

function prevUsers(): void {
  if (usersPage.value <= 1) return
  usersPage.value -= 1
  void loadUsers()
}

async function toggleUserRole(row: UserRow): Promise<void> {
  if (usersRoleBusy[row.id]) return
  const targetRole = row.role === 'admin' ? 'user' : 'admin'
  usersRoleBusy[row.id] = true
  try {
    const { data } = await api.patch(`/admin/users/${row.id}/role`, { role: targetRole })
    row.role = data?.role || targetRole
  } catch {
    void alertDialog('Не удалось обновить роль пользователя')
  } finally {
    usersRoleBusy[row.id] = false
  }
}

onMounted(() => {
  const now = new Date()
  statsMonth.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  void loadSettings()
  void loadStats()
  void loadLogActions()
  void loadLogs()
  void loadRooms()
  void loadUsers()
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
    flex-wrap: wrap;
    gap: 10px;
    .tabs {
      display: flex;
      align-items: flex-end;
      flex: 1 1 600px;
      flex-wrap: wrap;
      gap: 5px;
      height: auto;
      .tab {
        width: 220px;
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
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
  .tab-panel {
    margin-top: 10px;
    .loading {
      padding: 20px;
      color: $fg;
      font-family: Manrope-Medium;
    }
    .grid {
      display: grid;
      gap: 10px;
      grid-template-columns: 1fr 1fr;
      .block {
        border: 3px solid $lead;
        border-radius: 5px;
        padding: 15px;
        h3 {
          margin: 0 0 20px;
          font-size: 20px;
          color: $fg;
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
            &::before {
              content: "";
              position: absolute;
              inset: 0;
              background-color: $lead;
              transition: background-color 0.25s ease-in-out;
            }
          }
          &:focus-within label,
          input:not(:placeholder-shown) + label,
          &.filled label {
            top: 5px;
            left: 10px;
            transform: none;
            font-size: 12px;
            color: $grey;
          }
        }
        .ui-input + .ui-input {
          margin-top: 12px;
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
              &::before {
                content: "";
                position: absolute;
                left: 0;
                width: 50%;
                height: 100%;
                border-radius: 5px;
                background-color: $lead;
                transition: transform 0.25s ease-in-out;
              }
            }
            input:checked + .slider::before {
              transform: translateX(100%);
            }
          }
        }
        .switch + .switch {
          margin-top: 12px;
        }
      }
      .form-actions {
        grid-column: 1 / -1;
      }
    }
    .form-actions {
      margin-top: 15px;
      display: flex;
      justify-content: flex-end;
    }
    .filters {
      display: flex;
      flex-wrap: wrap;
      align-items: flex-end;
      gap: 10px;
      margin-bottom: 10px;
      .field {
        display: flex;
        flex-direction: column;
        gap: 5px;
        min-width: 160px;
        span {
          font-size: 14px;
          color: $grey;
        }
        input,
        select {
          height: 35px;
          padding: 0 10px;
          border: 1px solid $lead;
          border-radius: 5px;
          background-color: $graphite;
          color: $fg;
          font-size: 14px;
          font-family: Manrope-Medium;
          outline: none;
        }
      }
    }
    .stats {
      display: flex;
      flex-direction: column;
      gap: 15px;
      .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 10px;
        .stat-card {
          display: flex;
          flex-direction: column;
          gap: 5px;
          padding: 10px;
          border: 1px solid $lead;
          border-radius: 5px;
          background-color: $graphite;
          .label {
            font-size: 12px;
            color: $grey;
          }
          .value {
            font-size: 20px;
            color: $fg;
          }
        }
      }
      .chart {
        padding: 10px;
        border: 1px solid $lead;
        border-radius: 5px;
        background-color: $graphite;
        .chart-grid {
          display: flex;
          align-items: flex-end;
          gap: 5px;
          height: 180px;
          overflow-x: auto;
          padding: 5px 3px;
          .chart-bar {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-end;
            gap: 5px;
            width: 15px;
            flex: 0 0 15px;
            .bar {
              width: 100%;
              background-color: $lead;
              border-radius: 3px 3px 0 0;
              transition: height 0.25s ease-in-out;
            }
            .bar-label {
              font-size: 10px;
              color: $grey;
            }
          }
        }
        .chart-legend {
          margin-top: 10px;
          font-size: 12px;
          color: $grey;
        }
      }
    }
    .table {
      width: 100%;
      border-collapse: collapse;
      color: $fg;
      font-family: Manrope-Medium;
      th,
      td {
        padding: 5px 10px;
        border-bottom: 1px solid $lead;
        vertical-align: top;
      }
      th {
        font-size: 12px;
        color: $grey;
        text-align: left;
      }
      td {
        font-size: 14px;
      }
    }
    .pager {
      margin-top: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      color: $fg;
      font-family: Manrope-Medium;
    }
    .muted {
      color: $grey;
      text-align: center;
    }
  }
}

.tab-fade-enter-active,
.tab-fade-leave-active {
  transition: opacity 0.25s ease-in-out;
}
.tab-fade-enter-from,
.tab-fade-leave-to {
  opacity: 0;
}

@media (max-width: 1280px) {
}
</style>
