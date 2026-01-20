<template>
  <section class="admin">
    <header>
      <nav class="tabs" aria-label="Админ" role="tablist">
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'settings' }"
                :aria-selected="activeTab === 'settings'" @click="activeTab = 'settings'">
          Параметры
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'updates' }"
                :aria-selected="activeTab === 'updates'" @click="activeTab = 'updates'">
          Обновления
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
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'games' }"
                :aria-selected="activeTab === 'games'" @click="activeTab = 'games'">
          Игры
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

        <div v-else-if="activeTab === 'settings'">
          <div class="grid">
            <div class="block">
              <h3>Доступ</h3>
              <div class="switch">
                <span class="switch-label">Регистрация</span>
                <label>
                  <input type="checkbox" v-model="site.registration_enabled" :disabled="savingSettings" aria-label="Регистрация" />
                  <div class="slider">
                    <span>Откл</span>
                    <span>Вкл</span>
                  </div>
                </label>
              </div>
              <div class="switch">
                <span class="switch-label">Создание комнат</span>
                <label>
                  <input type="checkbox" v-model="site.rooms_can_create" :disabled="savingSettings" aria-label="Создание комнат" />
                  <div class="slider">
                    <span>Откл</span>
                    <span>Вкл</span>
                  </div>
                </label>
              </div>
              <div class="switch">
                <span class="switch-label">Вход в комнату</span>
                <label>
                  <input type="checkbox" v-model="site.rooms_can_enter" :disabled="savingSettings" aria-label="Вход в комнату" />
                  <div class="slider">
                    <span>Откл</span>
                    <span>Вкл</span>
                  </div>
                </label>
              </div>
              <div class="switch">
                <span class="switch-label">Запуск игр</span>
                <label>
                  <input type="checkbox" v-model="site.games_can_start" :disabled="savingSettings" aria-label="Запуск игр" />
                  <div class="slider">
                    <span>Откл</span>
                    <span>Вкл</span>
                  </div>
                </label>
              </div>
              <div class="switch">
                <span class="switch-label">Запуск трансляций</span>
                <label>
                  <input type="checkbox" v-model="site.streams_can_start" :disabled="savingSettings" aria-label="Запуск трансляций" />
                  <div class="slider">
                    <span>Откл</span>
                    <span>Вкл</span>
                  </div>
                </label>
              </div>
              <div class="form-actions">
                <button class="btn danger" :disabled="kickRoomsBusy" @click="kickAllRooms">
                  Кик из комнат
                </button>
              </div>
            </div>

            <div class="block">
              <h3>Лимиты комнат</h3>
              <div class="ui-input" :class="{ filled: Number.isFinite(site.rooms_limit_global) }">
                <input id="rooms-limit-global" v-model.number="site.rooms_limit_global" type="number" min="1" max="100" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="rooms-limit-global">Общий лимит комнат</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(site.rooms_limit_per_user) }">
                <input id="rooms-limit-user" v-model.number="site.rooms_limit_per_user" type="number" min="1" max="10" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="rooms-limit-user">Лимит комнат на пользователя</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(site.rooms_empty_ttl_seconds) }">
                <input id="rooms-empty-ttl-seconds" v-model.number="site.rooms_empty_ttl_seconds" type="number" min="10" max="300" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="rooms-empty-ttl-seconds">Время жизни пустой комнаты (сек)</label>
              </div>
            </div>

            <div class="block">
              <div class="ui-input" :class="{ filled: Number.isFinite(game.game_min_ready_players) }">
                <input id="game-min-ready" v-model.number="game.game_min_ready_players" type="number" min="1" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="game-min-ready">Количество игроков для старта</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(game.role_pick_seconds) }">
                <input id="role-pick-seconds" v-model.number="game.role_pick_seconds" type="number" min="1" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="role-pick-seconds">Выбор ролей (сек)</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(game.mafia_talk_seconds) }">
                <input id="mafia-talk-seconds" v-model.number="game.mafia_talk_seconds" type="number" min="1" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="mafia-talk-seconds">Договорка мафии (сек)</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(game.night_action_seconds) }">
                <input id="night-action-seconds" v-model.number="game.night_action_seconds" type="number" min="1" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="night-action-seconds">Отстрелы и проверки (сек)</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(game.vote_seconds) }">
                <input id="vote-seconds" v-model.number="game.vote_seconds" type="number" min="1" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="vote-seconds">Голосование (сек)</label>
              </div>
            </div>

            <div class="block">
              <div class="ui-input" :class="{ filled: Number.isFinite(game.player_talk_seconds) }">
                <input id="player-talk-seconds" v-model.number="game.player_talk_seconds" type="number" min="1" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="player-talk-seconds">Речь игрока (сек)</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(game.player_talk_short_seconds) }">
                <input id="player-talk-short-seconds" v-model.number="game.player_talk_short_seconds" type="number"
                       min="1" step="1" placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="player-talk-short-seconds">Речь при 3х фолах (сек)</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(game.player_foul_seconds) }">
                <input id="player-foul-seconds" v-model.number="game.player_foul_seconds" type="number" min="1" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="player-foul-seconds">Фол (сек)</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(game.winks_limit) }">
                <input id="winks-limit" v-model.number="game.winks_limit" type="number" min="0" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="winks-limit">Подмигивания (шт)</label>
              </div>
              <div class="ui-input" :class="{ filled: Number.isFinite(game.knocks_limit) }">
                <input id="knocks-limit" v-model.number="game.knocks_limit" type="number" min="0" step="1"
                       placeholder=" " autocomplete="off" inputmode="numeric" :disabled="savingSettings" />
                <label for="knocks-limit">Постукивания (шт)</label>
              </div>
            </div>

            <div class="form-actions">
              <button class="btn confirm" :disabled="savingSettings || !isSettingsDirty" @click="saveSettings">
                <img class="btn-img" :src="iconSave" alt="save" />
                Сохранить
              </button>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'updates'">
          <div class="updates-toolbar">
            <button class="btn confirm" @click="openCreateUpdate">Добавить</button>
          </div>

          <div v-if="updatesLoading" class="loading">Загрузка...</div>
          <div v-else>
            <table class="table updates-table">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Версия</th>
                  <th>Описание</th>
                  <th>Действие</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in updates" :key="row.id">
                  <td>{{ formatLocalDateTime(row.date, DATE_ONLY) }}</td>
                  <td>{{ row.version }}</td>
                  <td class="desc">{{ row.description }}</td>
                  <td>
                    <button class="btn dark" @click="openEditUpdate(row)">
                      <img class="btn-img" :src="iconEdit" alt="edit" />
                      Изменить
                    </button>
                    <button class="btn danger" :disabled="updatesDeleting[row.id]" @click="deleteUpdate(row)">
                      <img class="btn-img" :src="iconDelete" alt="delete" />
                      Удалить
                    </button>
                  </td>
                </tr>
                <tr v-if="updates.length === 0">
                  <td colspan="4" class="muted">Нет обновлений</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-else-if="activeTab === 'stats'">
          <div v-if="statsLoading" class="loading">Загрузка...</div>
          <div v-else class="stats">
            <div class="stats-grid">
              <div class="stat-card">
                <span class="label">Всего пользователей</span>
                <span class="value">{{ stats.total_users }}</span>
              </div>
              <div class="stat-card">
                <span class="label">Всего комнат</span>
                <span class="value">{{ stats.total_rooms }}</span>
              </div>
              <div class="stat-card">
                <span class="label">Всего игр</span>
                <span class="value">{{ stats.total_games }}</span>
              </div>
              <div class="stat-card">
                <span class="label">Всего стримы</span>
                <span class="value">{{ formatMinutes(stats.total_stream_minutes) }}</span>
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
                <span class="label">Онлайн текущий</span>
                <div class="tooltip" tabindex="0">
                  <span class="value tooltip-value">{{ stats.online_users }}</span>
                  <div class="tooltip-body">
                    <div v-if="stats.online_users_list.length === 0" class="tooltip-empty">Нет данных</div>
                    <div v-else class="tooltip-list">
                      <div v-for="item in stats.online_users_list" :key="`online-${item.id}`" class="tooltip-row">
                        <span class="tooltip-id">ID {{ item.id }}</span>
                        <span>{{ item.username || `user${item.id}` }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="stats-subtitle">За последние 24 часа</div>
            <div class="stats-grid stats-grid--compact">
              <div class="stat-card">
                <span class="label">Онлайн</span>
                <span class="value">{{ stats.last_day.online_users }}</span>
              </div>
              <div class="stat-card">
                <span class="label">Комнаты </span>
                <span class="value">{{ stats.last_day.rooms }}</span>
              </div>
              <div class="stat-card">
                <span class="label">Стримы</span>
                <span class="value">{{ formatMinutes(stats.last_day.stream_minutes) }}</span>
              </div>
              <div class="stat-card">
                <span class="label">Игры</span>
                <span class="value">{{ stats.last_day.games }}</span>
              </div>
            </div>
            <div class="stats-subtitle">За календарный месяц</div>

            <div class="chart">
              <div class="filters">
                <label class="field">
                  <span>Отобразить за</span>
                  <input type="month" v-model="statsMonth" :disabled="statsLoading" />
                </label>
              </div>
              <div class="stats-grid stats-grid--compact">
                <div class="stat-card">
                  <span class="label">Онлайн</span>
                  <span class="value">{{ stats.last_month.online_users }}</span>
                </div>
                <div class="stat-card">
                  <span class="label">Комнаты</span>
                  <span class="value">{{ stats.last_month.rooms }}</span>
                </div>
                <div class="stat-card">
                  <span class="label">Стримы</span>
                  <span class="value">{{ formatMinutes(stats.last_month.stream_minutes) }}</span>
                </div>
                <div class="stat-card">
                  <span class="label">Игры</span>
                  <span class="value">{{ stats.last_month.games }}</span>
                </div>
              </div>
              <div v-if="stats.registrations.length === 0" class="muted">Нет данных</div>
              <div v-else class="chart-body">
                <div class="chart-axis">
                  <span v-for="tick in registrationTicks" :key="tick">{{ tick }}</span>
                </div>
                <div class="chart-grid">
                  <div v-for="point in stats.registrations" :key="point.date" class="chart-bar">
                    <div class="bar" :style="{ height: chartBarHeight(point.count, registrationsMax) }">
                      <span class="bar-value">{{ point.count }}</span>
                    </div>
                    <span class="bar-label">{{ point.date.slice(-2) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="chart chart--monthly">
              <div v-if="stats.registrations_monthly.length === 0" class="muted">Нет данных</div>
              <div v-else class="chart-body">
                <div class="chart-axis">
                  <span v-for="tick in registrationMonthlyTicks" :key="tick">{{ tick }}</span>
                </div>
                <div class="chart-grid">
                  <div v-for="point in stats.registrations_monthly" :key="point.date" class="chart-bar">
                    <div class="bar" :style="{ height: chartBarHeight(point.count, registrationsMonthlyMax) }">
                      <span class="bar-value">{{ point.count }}</span>
                    </div>
                    <span class="bar-label">{{ formatMonthLabel(point.date) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'logs'">
          <div class="filters">
            <label class="field">
              <span>Событие</span>
              <select v-model="logsAction" :disabled="logsLoading">
                <option value="all">Все</option>
                <option v-for="act in logActions" :key="act" :value="act">{{ act }}</option>
              </select>
            </label>
            <label class="field">
              <span>Никнейм</span>
              <input type="text" v-model.trim="logsUser" :disabled="logsLoading" placeholder="Никнейм" />
            </label>
            <label class="field">
              <span>Дата</span>
              <input type="date" v-model="logsDay" :disabled="logsLoading" />
            </label>
            <label class="field">
              <span>Отображать по</span>
              <select v-model.number="logsLimit" :disabled="logsLoading">
                <option :value="20">20</option>
                <option :value="100">100</option>
              </select>
            </label>
          </div>

          <div v-if="logsLoading" class="loading">Загрузка...</div>
          <div v-else>
            <table class="table">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Никнейм</th>
                  <th>Событие</th>
                  <th>Описание</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in logs" :key="row.id">
                  <td>{{ formatLocalDateTime(row.created_at) }}</td>
                  <td>
                    <div v-if="row.username" class="user-cell">
                      <img class="user-avatar" v-minio-img="{ key: row.avatar_name ? `avatars/${row.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                      <span>{{ row.username }}</span>
                    </div>
                    <span v-else>-</span>
                  </td>
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
              <span>Никнейм</span>
              <input type="text" v-model.trim="roomsUser" :disabled="roomsLoading" placeholder="Никнейм" />
            </label>
            <label class="field">
              <span>Наличие стримов</span>
              <select v-model="roomsStreamOnly" :disabled="roomsLoading">
                <option :value="false">Все комнаты</option>
                <option :value="true">Только со стримом</option>
              </select>
            </label>
            <label class="field">
              <span>Отображать по</span>
              <select v-model.number="roomsLimit" :disabled="roomsLoading">
                <option :value="20">20</option>
                <option :value="100">100</option>
              </select>
            </label>
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
                  <th>Лимит</th>
                  <th>Параметры игры</th>
                  <th>Создана</th>
                  <th>Удалена</th>
                  <th>Посетители</th>
                  <th>Стримы</th>
                  <th>Игры</th>
                  <th>Зрители</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rooms" :key="row.id">
                  <td>{{ row.id }}</td>
                  <td>{{ row.title }}</td>
                  <td>
                    <div class="user-cell">
                      <img class="user-avatar" v-minio-img="{ key: row.creator_avatar_name ? `avatars/${row.creator_avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                      <span>{{ row.creator_name }}</span>
                    </div>
                  </td>
                  <td>{{ row.privacy }}</td>
                  <td>{{ row.user_limit }}</td>
                  <td>{{ formatRoomGame(row) }}</td>
                  <td>{{ formatLocalDateTime(row.created_at) }}</td>
                  <td>{{ row.deleted_at ? formatLocalDateTime(row.deleted_at) : '-' }}</td>
                  <td>
                    <div class="tooltip" tabindex="0">
                      <span class="tooltip-value">{{ row.visitors_count }}</span>
                      <div class="tooltip-body">
                        <div v-if="row.visitors.length === 0" class="tooltip-empty">Нет данных</div>
                        <div v-else class="tooltip-list">
                          <div v-for="item in row.visitors" :key="`visitor-${row.id}-${item.id}`" class="tooltip-row">
                            <span class="tooltip-id">ID {{ item.id }}</span>
                            <div class="user-cell compact">
                              <span>{{ item.username || '-' }}</span>
                            </div>
                            <span class="tooltip-minutes">{{ formatMinutes(item.minutes) }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="tooltip" tabindex="0">
                      <span class="tooltip-value">{{ formatMinutes(row.stream_minutes) }}</span>
                      <div class="tooltip-body">
                        <div v-if="row.streamers.length === 0" class="tooltip-empty">Нет данных</div>
                        <div v-else class="tooltip-list">
                          <div v-for="item in row.streamers" :key="`stream-${row.id}-${item.id}`" class="tooltip-row">
                            <span class="tooltip-id">ID {{ item.id }}</span>
                            <div class="user-cell compact">
                              <span>{{ item.username || '-' }}</span>
                            </div>
                            <span class="tooltip-minutes">{{ formatMinutes(item.minutes) }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="tooltip" tabindex="0">
                      <span class="tooltip-value">{{ row.games.length }}</span>
                      <div class="tooltip-body">
                        <div v-if="row.games.length === 0" class="tooltip-empty">Нет данных</div>
                        <div v-else class="tooltip-list">
                          <div v-for="item in row.games" :key="`game-${row.id}-${item.number}`" class="tooltip-row">
                            <span class="tooltip-id">Игра {{ item.number }} - </span>
                            <span class="tooltip-minutes">{{ formatRoomGameResult(item.result) }} ({{ formatMinutes(item.minutes) }})</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="tooltip" tabindex="0">
                      <span class="tooltip-value">{{ row.spectators_count }}</span>
                      <div class="tooltip-body">
                        <div v-if="row.spectators.length === 0" class="tooltip-empty">Нет данных</div>
                        <div v-else class="tooltip-list">
                          <div v-for="item in row.spectators" :key="`spectator-${row.id}-${item.id}`" class="tooltip-row">
                            <span class="tooltip-id">ID {{ item.id }}</span>
                            <div class="user-cell compact">
                              <span>{{ item.username || '-' }}</span>
                            </div>
                            <span class="tooltip-minutes">{{ formatMinutes(item.minutes) }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </td>
                </tr>
                <tr v-if="rooms.length === 0">
                  <td colspan="12" class="muted">Нет данных</td>
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

        <div v-else-if="activeTab === 'games'">
          <div class="filters">
            <label class="field">
              <span>Никнейм</span>
              <input type="text" v-model.trim="gamesUser" :disabled="gamesLoading" placeholder="Никнейм" />
            </label>
            <label class="field">
              <span>Дата игры</span>
              <input type="date" v-model="gamesDay" :disabled="gamesLoading" />
            </label>
            <label class="field">
              <span>Отображать по</span>
              <select v-model.number="gamesLimit" :disabled="gamesLoading">
                <option :value="20">20</option>
                <option :value="100">100</option>
              </select>
            </label>
          </div>

          <div v-if="gamesLoading" class="loading">Загрузка...</div>
          <div v-else>
            <table class="table games-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Комната</th>
                  <th>Владелец</th>
                  <th>Ведущий</th>
                  <th>Результат</th>
                  <th>Длительность</th>
                  <th>Старт</th>
                  <th>Игроки</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in games" :key="row.id">
                  <td>{{ row.id }}</td>
                  <td>{{ row.room_id }}</td>
                  <td>
                    <div class="user-cell">
                      <img class="user-avatar" v-minio-img="{ key: row.owner?.avatar_name ? `avatars/${row.owner.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                      <span>{{ row.owner?.username || ('user' + row.owner.id) }}</span>
                    </div>
                  </td>
                  <td>
                    <div v-if="row.head" class="user-cell">
                      <img class="user-avatar" v-minio-img="{ key: row.head.avatar_name ? `avatars/${row.head.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                      <span>{{ row.head.username || ('user' + row.head.id) }}</span>
                    </div>
                    <span v-else>-</span>
                  </td>
                  <td>{{ formatRoomGameResult(row.result) }} {{ row.black_alive_at_finish }}/{{ row.black_alive_at_finish }}</td>
                  <td>{{ formatGameDuration(row.duration_seconds) }}</td>
                  <td>{{ formatLocalDateTime(row.started_at) }}</td>
                  <td class="players-cell">
                    <ul v-if="row.players.length" class="players-list">
                      <li v-for="p in row.players" :key="p.id">{{ formatGamePlayer(p) }}</li>
                    </ul>
                    <div v-else class="muted">Нет данных</div>
                  </td>
                  <td class="actions-cell">
                    <ul v-if="row.actions.length" class="actions-list">
                      <li v-for="(a, idx) in row.actions" :key="idx">{{ formatGameAction(a) }}</li>
                    </ul>
                    <div v-else class="muted">Нет данных</div>
                  </td>
                </tr>
                <tr v-if="games.length === 0">
                  <td colspan="9" class="muted">Нет данных</td>
                </tr>
              </tbody>
            </table>
            <div class="pager">
              <button class="btn" :disabled="gamesPage <= 1" @click="prevGames">Назад</button>
              <span>{{ gamesPage }} / {{ gamesPages }}</span>
              <button class="btn" :disabled="gamesPage >= gamesPages" @click="nextGames">Вперед</button>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'users'">
          <div class="filters">
            <label class="field">
              <span>Никнейм</span>
              <input type="text" v-model.trim="usersUser" :disabled="usersLoading" placeholder="Никнейм" />
            </label>
            <label class="field">
              <span>Отображать по</span>
              <select v-model.number="usersLimit" :disabled="usersLoading">
                <option :value="20">20</option>
                <option :value="100">100</option>
              </select>
            </label>
          </div>

          <div v-if="usersLoading" class="loading">Загрузка...</div>
          <div v-else>
            <table class="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Никнейм</th>
                  <th>Роль</th>
                  <th>Регистрация</th>
                  <th>Авторизация</th>
                  <th>Онлайн</th>
                  <th>Комнаты</th>
                  <th>В комнатах</th>
                  <th>Стримы</th>
                  <th>Игры</th>
                  <th>Ведущий</th>
                  <th>Зритель</th>
                  <th>Таймауты</th>
                  <th>Баны</th>
                  <th>Огранич.</th>
                  <th>Админка</th>
                  <th>Аккаунт</th>
                  <th>Огранич.</th>
                  <th>Таймаут</th>
                  <th>Бан</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in users" :key="row.id">
                  <td>{{ row.id }}</td>
                  <td>
                    <div v-if="row.username" class="user-cell">
                      <img class="user-avatar" v-minio-img="{ key: row.avatar_name ? `avatars/${row.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                      <span>{{ row.username }}</span>
                    </div>
                    <span v-else>-</span>
                  </td>
                  <td>{{ row.role }}</td>
                  <td>{{ formatLocalDateTime(row.registered_at) }}</td>
                  <td>{{ formatLocalDateTime(row.last_login_at) }}</td>
                  <td>{{ formatLocalDateTime(row.last_visit_at) }}</td>
                  <td>{{ row.rooms_created }}</td>
                  <td>{{ formatMinutes(row.room_minutes) }}</td>
                  <td>{{ formatMinutes(row.stream_minutes) }}</td>
                  <td>{{ row.games_played }}</td>
                  <td>{{ row.games_hosted }}</td>
                  <td>{{ formatMinutes(row.spectator_minutes) }}</td>
                  <td>
                    <div class="tooltip" tabindex="0">
                      <span class="tooltip-value">{{ row.timeouts_count }}</span>
                      <div class="tooltip-body">
                        <div v-if="row.timeouts.length === 0" class="tooltip-empty">Нет данных</div>
                        <div v-else class="tooltip-list">
                          <div v-for="item in row.timeouts" :key="`timeout-${item.id}`" class="tooltip-row">
                            {{ formatSanctionLine(item) }}
                          </div>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="tooltip" tabindex="0">
                      <span class="tooltip-value">{{ row.bans_count }}</span>
                      <div class="tooltip-body">
                        <div v-if="row.bans.length === 0" class="tooltip-empty">Нет данных</div>
                        <div v-else class="tooltip-list">
                          <div v-for="item in row.bans" :key="`ban-${item.id}`" class="tooltip-row">
                            {{ formatSanctionLine(item) }}
                          </div>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="tooltip" tabindex="0">
                      <span class="tooltip-value">{{ row.suspends_count }}</span>
                      <div class="tooltip-body">
                        <div v-if="row.suspends.length === 0" class="tooltip-empty">Нет данных</div>
                        <div v-else class="tooltip-list">
                          <div v-for="item in row.suspends" :key="`suspend-${item.id}`" class="tooltip-row">
                            {{ formatSanctionLine(item) }}
                          </div>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <button class="btn" :class="row.role === 'admin' ? 'dark' : 'danger'" :disabled="usersRoleBusy[row.id]" @click="toggleUserRole(row)">
                      <img class="btn-img" :src="row.role === 'admin' ? iconClose : iconJudge" alt="" />
                    </button>
                  </td>
                  <td>
                    <button class="btn" :class="row.deleted_at ? 'dark' : 'danger'" :disabled="usersDeleteBusy[row.id]" @click="toggleDeleteAccount(row)">
                      <img class="btn-img" :src="row.deleted_at ? iconClose : iconJudge" alt="" />
                    </button>
                  </td>
                  <td>
                    <button class="btn" :class="row.suspend_active ? 'dark' : 'danger'" :disabled="isSanctionBusy(row.id, 'suspend')" @click="toggleSuspend(row)">
                      <img class="btn-img" :src="row.suspend_active ? iconClose : iconJudge" alt="" />
                    </button>
                  </td>
                  <td>
                    <button class="btn" :class="row.timeout_active ? 'dark' : 'danger'" :disabled="isSanctionBusy(row.id, 'timeout')" @click="toggleTimeout(row)">
                      <img class="btn-img" :src="row.timeout_active ? iconClose : iconJudge" alt="" />
                    </button>
                  </td>
                  <td>
                    <button class="btn" :class="row.ban_active ? 'dark' : 'danger'" :disabled="isSanctionBusy(row.id, 'ban')" @click="toggleBan(row)">
                      <img class="btn-img" :src="row.ban_active ? iconClose : iconJudge" alt="" />
                    </button>
                  </td>
                </tr>
                <tr v-if="users.length === 0">
                  <td colspan="20" class="muted">Нет данных</td>
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

    <UpdateModal
      v-model:open="updateModalOpen"
      :title="updateEditing ? 'Редактировать обновление' : 'Новое обновление'"
      :saving="updateSaving"
      :can-save="canSaveUpdate"
      :save-icon="iconSave"
      :form="updateForm"
      @save="saveUpdate"
    />
    <SanctionModal
      v-model:open="sanctionModalOpen"
      :title="sanctionTitle"
      :saving="sanctionSaving"
      :can-save="sanctionCanSave"
      :form="sanctionForm"
      :reasons="sanctionReasons"
      @save="saveTimedSanction"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { formatLocalDateTime } from '@/services/datetime'
import { useSettingsStore } from '@/store'
import UpdateModal from '@/components/UpdateModal.vue'
import SanctionModal from '@/components/SanctionModal.vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconClose from '@/assets/svg/close.svg'
import iconJudge from '@/assets/svg/judge.svg'
import iconEdit from '@/assets/svg/edit.svg'
import iconDelete from '@/assets/svg/delete.svg'
import iconSave from '@/assets/svg/save.svg'

const DATE_ONLY: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}

type SiteSettings = {
  registration_enabled: boolean
  rooms_can_create: boolean
  rooms_can_enter: boolean
  games_can_start: boolean
  streams_can_start: boolean
  rooms_limit_global: number
  rooms_limit_per_user: number
  rooms_empty_ttl_seconds: number
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
  winks_limit: number
  knocks_limit: number
}

type RegistrationPoint = {
  date: string
  count: number
}

type OnlineUser = {
  id: number
  username?: string | null
}

type PeriodStats = {
  games: number
  online_users: number
  rooms: number
  stream_minutes: number
}

type SiteStats = {
  total_users: number
  registrations: RegistrationPoint[]
  registrations_monthly: RegistrationPoint[]
  total_rooms: number
  total_games: number
  total_stream_minutes: number
  active_rooms: number
  active_room_users: number
  online_users: number
  online_users_list: OnlineUser[]
  last_day: PeriodStats
  last_month: PeriodStats
}

type LogRow = {
  id: number
  user_id?: number | null
  username?: string | null
  avatar_name?: string | null
  action: string
  details: string
  created_at: string
}

type RoomUserStat = {
  id: number
  username?: string | null
  minutes: number
}

type RoomGameStat = {
  number: number
  result: string
  minutes: number
}

type RoomRow = {
  id: number
  creator: number
  creator_name: string
  creator_avatar_name?: string | null
  title: string
  user_limit: number
  privacy: string
  created_at: string
  deleted_at?: string | null
  game_mode: string
  game_format: string
  spectators_limit: number
  break_at_zero: boolean
  lift_at_zero: boolean
  lift_3x: boolean
  visitors_count: number
  visitors: RoomUserStat[]
  spectators_count: number
  spectators: RoomUserStat[]
  games: RoomGameStat[]
  stream_minutes: number
  streamers: RoomUserStat[]
  has_stream: boolean
}

type SanctionRow = {
  id: number
  kind: 'timeout' | 'ban' | 'suspend'
  reason?: string | null
  issued_at: string
  issued_by_id?: number | null
  issued_by_name?: string | null
  duration_seconds?: number | null
  expires_at?: string | null
  revoked_at?: string | null
  revoked_by_id?: number | null
  revoked_by_name?: string | null
}

type UserRow = {
  id: number
  username?: string | null
  avatar_name?: string | null
  role: string
  registered_at: string
  last_login_at: string
  last_visit_at: string
  deleted_at?: string | null
  rooms_created: number
  room_minutes: number
  stream_minutes: number
  games_played: number
  games_hosted: number
  spectator_minutes: number
  timeout_active: boolean
  timeout_until?: string | null
  ban_active: boolean
  suspend_active: boolean
  suspend_until?: string | null
  timeouts_count: number
  bans_count: number
  suspends_count: number
  timeouts: SanctionRow[]
  bans: SanctionRow[]
  suspends: SanctionRow[]
}

type GameUser = {
  id: number
  username?: string | null
  avatar_name?: string | null
}

type GamePlayer = {
  seat: number
  id: number
  username?: string | null
  avatar_name?: string | null
  role: string
  points: number
  mmr: number
}

type GameRow = {
  id: number
  room_id: number
  owner: GameUser
  head?: GameUser | null
  result: string
  black_alive_at_finish: number
  started_at: string
  finished_at: string
  duration_seconds: number
  players: GamePlayer[]
  actions: any[]
}

type UpdateRow = {
  id: number
  version: string
  date: string
  description: string
}

const activeTab = ref<'settings' | 'updates' | 'stats' | 'logs' | 'rooms' | 'games' | 'users'>('settings')
const loading = ref(true)
const savingSettings = ref(false)
const statsLoading = ref(false)
const logsLoading = ref(false)
const roomsLoading = ref(false)
const gamesLoading = ref(false)
const usersLoading = ref(false)
const updatesLoading = ref(false)

const site = reactive<SiteSettings>({
  registration_enabled: true,
  rooms_can_create: true,
  rooms_can_enter: true,
  games_can_start: true,
  streams_can_start: true,
  rooms_limit_global: 100,
  rooms_limit_per_user: 3,
  rooms_empty_ttl_seconds: 10,
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
  winks_limit: 3,
  knocks_limit: 3,
})

const settingsStore = useSettingsStore()
const siteSnapshot = ref('')
const gameSnapshot = ref('')

const statsMonth = ref('')
const stats = reactive<SiteStats>({
  total_users: 0,
  registrations: [],
  registrations_monthly: [],
  total_rooms: 0,
  total_games: 0,
  total_stream_minutes: 0,
  active_rooms: 0,
  active_room_users: 0,
  online_users: 0,
  online_users_list: [],
  last_day: {
    games: 0,
    online_users: 0,
    rooms: 0,
    stream_minutes: 0,
  },
  last_month: {
    games: 0,
    online_users: 0,
    rooms: 0,
    stream_minutes: 0,
  },
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

const games = ref<GameRow[]>([])
const gamesTotal = ref(0)
const gamesPage = ref(1)
const gamesLimit = ref(20)
const gamesUser = ref('')
const gamesDay = ref('')

const users = ref<UserRow[]>([])
const usersTotal = ref(0)
const usersPage = ref(1)
const usersLimit = ref(20)
const usersUser = ref('')
const usersRoleBusy = reactive<Record<number, boolean>>({})
const usersDeleteBusy = reactive<Record<number, boolean>>({})
const usersSanctionBusy = reactive<Record<string, boolean>>({})
const updates = ref<UpdateRow[]>([])
const updateModalOpen = ref(false)
const updateSaving = ref(false)
const updateEditing = ref<UpdateRow | null>(null)
const updateForm = reactive({ version: '', date: '', description: '' })
const updatesDeleting = reactive<Record<number, boolean>>({})
const sanctionModalOpen = ref(false)
const sanctionSaving = ref(false)
const sanctionKind = ref<'timeout' | 'suspend'>('timeout')
const sanctionTarget = ref<UserRow | null>(null)
const sanctionReasons = [
  { value: 'Нарушение правил платформы', label: 'Нарушение правил платформы' },
  { value: '1.1. Использование платформы deceit.games означает согласие с настоящими Правилами и связанными документами (Политика приватности, Правила контента, Регламент санкций, правила отдельных режимов/комнат).', label: '1.1. Использование платформы deceit.games означает согласие с настоящими Правилами и связанными документами (Политика приватности, Правила контента, Регламент санкций, правила отдельных режимов/комнат).' },
  { value: '1.2. Администрация вправе изменять Правила. Новая редакция публикуется на сайте и применяется с даты публикации (или иной указанной даты). Продолжение использования платформы означает согласие с изменениями.', label: '1.2. Администрация вправе изменять Правила. Новая редакция публикуется на сайте и применяется с даты публикации (или иной указанной даты). Продолжение использования платформы означает согласие с изменениями.' },
  { value: '1.3. Авторизация через Telegram. Для входа/регистрации пользователь использует Telegram. Авторизация возможна только при передаче платформе данных Telegram, необходимых для идентификации и работы аккаунта.', label: '1.3. Авторизация через Telegram. Для входа/регистрации пользователь использует Telegram. Авторизация возможна только при передаче платформе данных Telegram, необходимых для идентификации и работы аккаунта.' },
  { value: '1.4. Согласие на обработку данных. При авторизации через Telegram пользователь соглашается на обработку данных, получаемых от Telegram и/или предоставляемых пользователем, включая: Telegram ID, никнейм/username (если имеется), аватар (фото профиля).', label: '1.4. Согласие на обработку данных. При авторизации через Telegram пользователь соглашается на обработку данных, получаемых от Telegram и/или предоставляемых пользователем, включая: Telegram ID, никнейм/username (если имеется), аватар (фото профиля).' },
  { value: '1.5. Отзыв согласия. Пользователь может отозвать согласие на обработку данных, удалив свой аккаунт в Личном кабинете.', label: '1.5. Отзыв согласия. Пользователь может отозвать согласие на обработку данных, удалив свой аккаунт в Личном кабинете.' },
  { value: '1.6. О привязке санкций к Telegram-аккаунту. Аккаунт на платформе привязан к Telegram-аккаунту пользователя (в первую очередь — к Telegram ID). При применении санкций доступ к платформе может быть ограничен/заблокирован именно для аккаунта, авторизованного через соответствующий Telegram-аккаунт.', label: '1.6. О привязке санкций к Telegram-аккаунту. Аккаунт на платформе привязан к Telegram-аккаунту пользователя (в первую очередь — к Telegram ID). При применении санкций доступ к платформе может быть ограничен/заблокирован именно для аккаунта, авторизованного через соответствующий Telegram-аккаунт.' },
  { value: '2.1. Платформа предназначена для пользователей не младше 14 лет. При выявлении нарушения возрастного ограничения доступ может быть запрещён.', label: '2.1. Платформа предназначена для пользователей не младше 14 лет. При выявлении нарушения возрастного ограничения доступ может быть запрещён.' },
  { value: '2.2. Если на платформе возможны видео/аудио-трансляции, пользователь подтверждает, что осознаёт риски публичного общения и обязуется соблюдать ограничения по контенту (включая 18+). Нарушение ограничений по контенту наказывается по соответствующим пунктам Раздела 4.', label: '2.2. Если на платформе возможны видео/аудио-трансляции, пользователь подтверждает, что осознаёт риски публичного общения и обязуется соблюдать ограничения по контенту (включая 18+). Нарушение ограничений по контенту наказывается по соответствующим пунктам Раздела 4.' },
  { value: '2.3. Несовершеннолетним запрещено публиковать/передавать персональные данные и контент, если это нарушает применимое законодательство или настоящие Правила.', label: '2.3. Несовершеннолетним запрещено публиковать/передавать персональные данные и контент, если это нарушает применимое законодательство или настоящие Правила.' },
  { value: '3.1. Запрещено передавать доступ к своему аккаунту третьим лицам.', label: '3.1. Запрещено передавать доступ к своему аккаунту третьим лицам.' },
  { value: '3.2. Запрещён мультиаккаунтинг и обход санкций (вход под другим аккаунтом/устройством/идентификатором для избегания наказания).', label: '3.2. Запрещён мультиаккаунтинг и обход санкций (вход под другим аккаунтом/устройством/идентификатором для избегания наказания).' },
  { value: '3.3. Запрещена выдача себя за другое лицо, за администрацию платформы или за ведущего/судью в игровых комнатах, а также фальсификация статуса или полномочий.', label: '3.3. Запрещена выдача себя за другое лицо, за администрацию платформы или за ведущего/судью в игровых комнатах, а также фальсификация статуса или полномочий.' },
  { value: '3.4. При подозрении на компрометацию аккаунта пользователь обязан уведомить администрацию.', label: '3.4. При подозрении на компрометацию аккаунта пользователь обязан уведомить администрацию.' },
  { value: '4.1.1. Запрещены оскорбления, унижение, травля, клевета, жесткий троллинг, провокации, шантаж, угрозы, «минус глаза/минус уши».', label: '4.1.1. Запрещены оскорбления, унижение, травля, клевета, жесткий троллинг, провокации, шантаж, угрозы, «минус глаза/минус уши».' },
  { value: '4.1.2. Запрещены пожелания смерти/болезни, призывы к самоубийству/самоповреждению, подстрекательство.', label: '4.1.2. Запрещены пожелания смерти/болезни, призывы к самоубийству/самоповреждению, подстрекательство.' },
  { value: '4.1.3. Запрещена дискриминация/разжигание ненависти по полу, гендеру, расе, национальности, языку, возрасту, инвалидности, религии, политическим взглядам и др.', label: '4.1.3. Запрещена дискриминация/разжигание ненависти по полу, гендеру, расе, национальности, языку, возрасту, инвалидности, религии, политическим взглядам и др.' },
  { value: '4.2.1. Запрещён доксинг: публикация/угрозы публикации персональных данных без согласия (адреса, телефоны, документы, банковские сведения, переписки и т.п.).', label: '4.2.1. Запрещён доксинг: публикация/угрозы публикации персональных данных без согласия (адреса, телефоны, документы, банковские сведения, переписки и т.п.).' },
  { value: '4.2.2. Запрещены попытки выманивания персональных данных и доступов (социнженерия), фишинг, скам.', label: '4.2.2. Запрещены попытки выманивания персональных данных и доступов (социнженерия), фишинг, скам.' },
  { value: '4.2.3. Запрещено преследование (harassment), навязчивые контакты, сексуальные домогательства.', label: '4.2.3. Запрещено преследование (harassment), навязчивые контакты, сексуальные домогательства.' },
  { value: '4.3.1. Запрещены порнография, сексуальный контент с участием/образом несовершеннолетних (в т.ч. имитации), контент сексуальной эксплуатации.', label: '4.3.1. Запрещены порнография, сексуальный контент с участием/образом несовершеннолетних (в т.ч. имитации), контент сексуальной эксплуатации.' },
  { value: '4.3.2. Запрещён шок-контент (жестокость, расчленёнка и т.п.), демонстрация насилия ради эффекта.', label: '4.3.2. Запрещён шок-контент (жестокость, расчленёнка и т.п.), демонстрация насилия ради эффекта.' },
  { value: '4.3.3. Запрещена пропаганда/сбыт/инструкции по наркотикам и запрещённым веществам.', label: '4.3.3. Запрещена пропаганда/сбыт/инструкции по наркотикам и запрещённым веществам.' },
  { value: '4.3.4. Запрещены призывы к насилию/экстремизму, символика и пропаганда запрещённых организаций.', label: '4.3.4. Запрещены призывы к насилию/экстремизму, символика и пропаганда запрещённых организаций.' },
  { value: '4.4.1. Запрещён спам, флуд, массовые однотипные сообщения, навязчивая реклама.', label: '4.4.1. Запрещён спам, флуд, массовые однотипные сообщения, навязчивая реклама.' },
  { value: '4.4.2. Запрещены бессмысленные жалобы и злоупотребление обращениями к модерации.', label: '4.4.2. Запрещены бессмысленные жалобы и злоупотребление обращениями к модерации.' },
  { value: '4.5.1. Запрещены никнеймы/аватары/названия комнат/описания, содержащие: мат и грубую вульгарность; оскорбления; дискриминацию/хейт; экстремизм; порнографию; призывы к насилию; рекламу/донат-ссылки без согласования; вводящие в заблуждение обозначения (в т.ч. «модератор», «админ», имитация служебных статусов), а также выдача себя за другого человека.', label: '4.5.1. Запрещены никнеймы/аватары/названия комнат/описания, содержащие: мат и грубую вульгарность; оскорбления; дискриминацию/хейт; экстремизм; порнографию; призывы к насилию; рекламу/донат-ссылки без согласования; вводящие в заблуждение обозначения (в т.ч. «модератор», «админ», имитация служебных статусов), а также выдача себя за другого человека.' },
  { value: '4.5.2. Администрация вправе потребовать изменить никнейм/аватар/название комнаты/описание или удалить контент. Отказ выполнить требование рассматривается как нарушение.', label: '4.5.2. Администрация вправе потребовать изменить никнейм/аватар/название комнаты/описание или удалить контент. Отказ выполнить требование рассматривается как нарушение.' },
  { value: '5.1. Запрещено умышленно создавать помехи участию в комнате (постоянные выключения, демонстративное «затыкание ушей», намеренное скрытие лица при обязательной камере и т.п.), если режим комнаты требует видимость/слышимость.', label: '5.1. Запрещено умышленно создавать помехи участию в комнате (постоянные выключения, демонстративное «затыкание ушей», намеренное скрытие лица при обязательной камере и т.п.), если режим комнаты требует видимость/слышимость.' },
  { value: '5.2. Пользователь понимает, что другие участники могут вести запись экрана/звука для доказательства нарушений, если это не запрещено законом. Администрация может запрашивать такие доказательства при рассмотрении жалоб.', label: '5.2. Пользователь понимает, что другие участники могут вести запись экрана/звука для доказательства нарушений, если это не запрещено законом. Администрация может запрашивать такие доказательства при рассмотрении жалоб.' },
  { value: '6.1. Запрещены попытки взлома, эксплуатация уязвимостей, DDoS/«дудос паузой», вмешательство в сетевое взаимодействие, обход ограничений.', label: '6.1. Запрещены попытки взлома, эксплуатация уязвимостей, DDoS/«дудос паузой», вмешательство в сетевое взаимодействие, обход ограничений.' },
  { value: '6.2. Запрещено использование ботов/скриптов/автоматизации без разрешения.', label: '6.2. Запрещено использование ботов/скриптов/автоматизации без разрешения.' },
  { value: '6.3. Запрещено целенаправленно препятствовать развитию платформы, дискредитировать администрацию через ложные обвинения, подделывать доказательства.', label: '6.3. Запрещено целенаправленно препятствовать развитию платформы, дискредитировать администрацию через ложные обвинения, подделывать доказательства.' },
  { value: '6.4. Запрещена подделка скриншотов/логов/видео и иных материалов с целью наказания других пользователей.', label: '6.4. Запрещена подделка скриншотов/логов/видео и иных материалов с целью наказания других пользователей.' },
  { value: '6.5. Запрещена реклама, публикация ссылок на донат/платёжные страницы, сбор средств без согласования с администрацией.', label: '6.5. Запрещена реклама, публикация ссылок на донат/платёжные страницы, сбор средств без согласования с администрацией.' },
  { value: '7.1. В игровых комнатах нарушения в рамках игры фиксирует ведущий/судья; также пользователь может подать жалобу в администрацию.', label: '7.1. В игровых комнатах нарушения в рамках игры фиксирует ведущий/судья; также пользователь может подать жалобу в администрацию.' },
  { value: '7.2. Жалобы по оскорблениям/личным конфликтам могут приниматься от пострадавшей стороны; нарушения приватности/мошенничества/безопасности/запрещённого контента рассматриваются по обращению любого пользователя или по инициативе администрации.', label: '7.2. Жалобы по оскорблениям/личным конфликтам могут приниматься от пострадавшей стороны; нарушения приватности/мошенничества/безопасности/запрещённого контента рассматриваются по обращению любого пользователя или по инициативе администрации.' },
  { value: '7.3. Допустимые доказательства: записи экрана, скриншоты, логи комнаты, системные события.', label: '7.3. Допустимые доказательства: записи экрана, скриншоты, логи комнаты, системные события.' },
  { value: '7.4. Администрация вправе удалять контент, ограничивать доступ к функциям, блокировать комнаты/аккаунты и применять санкции по настоящим Правилам.', label: '7.4. Администрация вправе удалять контент, ограничивать доступ к функциям, блокировать комнаты/аккаунты и применять санкции по настоящим Правилам.' },
  { value: '7.5. Апелляции: пользователь вправе подать апелляцию в течение 3 дней, приложив аргументы и доказательства. Решение принимает администрация; повторные апелляции по тем же фактам могут быть отклонены.', label: '7.5. Апелляции: пользователь вправе подать апелляцию в течение 3 дней, приложив аргументы и доказательства. Решение принимает администрация; повторные апелляции по тем же фактам могут быть отклонены.' },
  { value: '8.1. Запрещены подсказки извне, переписка с третьими лицами по игре, просмотр стрима игры, находясь в игре, «слив роли».', label: '8.1. Запрещены подсказки извне, переписка с третьими лицами по игре, просмотр стрима игры, находясь в игре, «слив роли».' },
  { value: '8.2. Запрещено преднамеренное «вскрытие роли» другим игрокам любыми способами.', label: '8.2. Запрещено преднамеренное «вскрытие роли» другим игрокам любыми способами.' },
  { value: '8.3. Запрещено влияние на игру через сообщения/статусы «со стороны», скрины, откаты и т.п.', label: '8.3. Запрещено влияние на игру через сообщения/статусы «со стороны», скрины, откаты и т.п.' },
  { value: '8.4. Запрещены клятвы/пари/шантаж/подкуп для влияния на голосование или «доказательства роли».', label: '8.4. Запрещены клятвы/пари/шантаж/подкуп для влияния на голосование или «доказательства роли».' },
  { value: '8.5. Запрещено озвучивать речевую информацию на языке, который очевидно скрывает смысл от ведущего/судьи или большинства игроков. (внутриигровые меры комнаты)', label: '8.5. Запрещено озвучивать речевую информацию на языке, который очевидно скрывает смысл от ведущего/судьи или большинства игроков. (внутриигровые меры комнаты)' },
  { value: '8.6. После решающего убийства/голосования, определившего результат игры, меры, связанные с игровым преимуществом, как правило, не применяются, если нарушение уже не могло повлиять на исход (кроме грубых нарушений поведения/безопасности, которые могут наказываться всегда).', label: '8.6. После решающего убийства/голосования, определившего результат игры, меры, связанные с игровым преимуществом, как правило, не применяются, если нарушение уже не могло повлиять на исход (кроме грубых нарушений поведения/безопасности, которые могут наказываться всегда).' },
  { value: '8.7. Ведущему запрещено злоупотреблять правами, требовать оплату за проведение игр (если владелец комнаты это запрещает), применять меры из личной выгоды.', label: '8.7. Ведущему запрещено злоупотреблять правами, требовать оплату за проведение игр (если владелец комнаты это запрещает), применять меры из личной выгоды.' },
  { value: '8.8. Ведущему запрещено раскрывать роли до окончания игры или подсказывать/комментировать так, что это даёт игровую информацию.', label: '8.8. Ведущему запрещено раскрывать роли до окончания игры или подсказывать/комментировать так, что это даёт игровую информацию.' },
]

const sanctionForm = reactive({
  months: 0,
  days: 0,
  hours: 0,
  minutes: 0,
  reason: sanctionReasons[0]?.value || '',
})
const sanctionTotalSeconds = computed(() => {
  const months = Math.max(0, Number(sanctionForm.months) || 0)
  const days = Math.max(0, Number(sanctionForm.days) || 0)
  const hours = Math.max(0, Number(sanctionForm.hours) || 0)
  const minutes = Math.max(0, Number(sanctionForm.minutes) || 0)
  const totalMinutes = (months * 30 * 24 * 60) + (days * 24 * 60) + (hours * 60) + minutes
  return totalMinutes * 60
})
const sanctionCanSave = computed(() => sanctionTotalSeconds.value > 0 && Boolean(sanctionForm.reason))
const sanctionTitle = computed(() => (sanctionKind.value === 'timeout' ? 'Выдать таймаут' : 'Выдать ограничение'))
const kickRoomsBusy = ref(false)
let logsUserTimer: number | undefined
let roomsUserTimer: number | undefined
let gamesUserTimer: number | undefined
let usersUserTimer: number | undefined

function normalizeInt(value: number): number {
  return Number.isFinite(value) ? value : 0
}

function normalizeRoomUsers(value: unknown): RoomUserStat[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item: any) => ({
      id: Number(item?.id) || 0,
      username: item?.username ?? null,
      minutes: Number(item?.minutes) || 0,
    }))
    .filter(item => item.id > 0)
}

function normalizeRoomGames(value: unknown): RoomGameStat[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item: any) => ({
      number: Number(item?.number) || 0,
      result: String(item?.result || ''),
      minutes: Number(item?.minutes) || 0,
    }))
    .filter(item => item.number > 0 && item.result)
}

function snapshotSite(): string {
  return JSON.stringify({
    registration_enabled: Boolean(site.registration_enabled),
    rooms_can_create: Boolean(site.rooms_can_create),
    rooms_can_enter: Boolean(site.rooms_can_enter),
    games_can_start: Boolean(site.games_can_start),
    streams_can_start: Boolean(site.streams_can_start),
    rooms_limit_global: normalizeInt(site.rooms_limit_global),
    rooms_limit_per_user: normalizeInt(site.rooms_limit_per_user),
    rooms_empty_ttl_seconds: normalizeInt(site.rooms_empty_ttl_seconds),
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
    winks_limit: normalizeInt(game.winks_limit),
    knocks_limit: normalizeInt(game.knocks_limit),
  })
}

const isSiteDirty = computed(() => siteSnapshot.value !== snapshotSite())
const isGameDirty = computed(() => gameSnapshot.value !== snapshotGame())
const isSettingsDirty = computed(() => isSiteDirty.value || isGameDirty.value)
const logsPages = computed(() => Math.max(1, Math.ceil(logsTotal.value / logsLimit.value)))
const roomsPages = computed(() => Math.max(1, Math.ceil(roomsTotal.value / roomsLimit.value)))
const gamesPages = computed(() => Math.max(1, Math.ceil(gamesTotal.value / gamesLimit.value)))
const usersPages = computed(() => Math.max(1, Math.ceil(usersTotal.value / usersLimit.value)))
const registrationsMax = computed(() => {
  const vals = stats.registrations.map(p => p.count)
  return Math.max(1, ...vals)
})
const registrationsMonthlyMax = computed(() => {
  const vals = stats.registrations_monthly.map(p => p.count)
  return Math.max(1, ...vals)
})
function buildChartTicks(maxValue: number): number[] {
  const max = Math.max(1, maxValue)
  if (max <= 4) {
    return Array.from({ length: max + 1 }, (_, i) => max - i)
  }
  const step = max / 4
  const raw = [max, max - step, max - step * 2, max - step * 3, 0]
  const out: number[] = []
  const seen = new Set<number>()
  for (const val of raw) {
    const rounded = Math.round(val)
    if (!seen.has(rounded)) {
      seen.add(rounded)
      out.push(rounded)
    }
  }
  if (!seen.has(0)) out.push(0)
  return out
}
const registrationTicks = computed(() => buildChartTicks(registrationsMax.value))
const registrationMonthlyTicks = computed(() => buildChartTicks(registrationsMonthlyMax.value))
const canSaveUpdate = computed(() => {
  return Boolean(updateForm.version.trim() && updateForm.date && updateForm.description.trim())
})

function formatMinutes(value: number): string {
  const total = Math.max(0, Math.floor(Number(value) || 0))
  const days = Math.floor(total / 1440)
  const hours = Math.floor((total % 1440) / 60)
  const minutes = total % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days}д`)
  if (hours > 0) parts.push(`${hours}ч`)
  if (minutes > 0 || parts.length === 0) parts.push(`${minutes}м`)
  return parts.join(' ')
}

function formatSanctionDuration(seconds?: number | null): string {
  if (!seconds) return 'без срока'
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  const mins = Math.floor(total / 60)
  const days = Math.floor(mins / 1440)
  const hours = Math.floor((mins % 1440) / 60)
  const minutes = mins % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days}д`)
  if (hours > 0) parts.push(`${hours}ч`)
  if (minutes > 0 || parts.length === 0) parts.push(`${minutes}м`)
  return parts.join(' ')
}

function formatSanctionActor(name?: string | null, id?: number | null): string {
  if (name) return name
  if (Number.isFinite(id)) return `#${id}`
  return '-'
}

function formatSanctionLine(item: SanctionRow): string {
  const issuedBy = formatSanctionActor(item.issued_by_name, item.issued_by_id)
  const issuedAt = formatLocalDateTime(item.issued_at)
  const duration = formatSanctionDuration(item.duration_seconds)
  let end = 'активен'
  if (item.revoked_at) {
    const revokedBy = formatSanctionActor(item.revoked_by_name, item.revoked_by_id)
    end = `снял: ${revokedBy} ${formatLocalDateTime(item.revoked_at)}`
  } else if (item.expires_at) {
    end = `авто: ${formatLocalDateTime(item.expires_at)}`
  }
  return `${issuedAt} • ${duration} • выдал: ${issuedBy} • ${end}`
}

function isSanctionBusy(userId: number, kind: 'timeout' | 'ban' | 'suspend'): boolean {
  return Boolean(usersSanctionBusy[`${userId}:${kind}`])
}

function formatRoomGame(row: RoomRow): string {
  const mode = row.game_mode === 'rating' ? 'Рейтинг' : 'Обычный'
  const judge = row.game_format === 'nohost' ? 'Авто' : 'Ведущий'
  const spectators = Number.isFinite(row.spectators_limit) ? row.spectators_limit : 0
  const breakAtZero = row.break_at_zero ? 'Вкл' : 'Выкл'
  const liftAtZero = row.lift_at_zero ? 'Вкл' : 'Выкл'
  const lift3x = row.lift_3x ? 'Вкл' : 'Выкл'
  return `Режим: ${mode}, Судья: ${judge}, Зрители: ${spectators}, Слом в нуле: ${breakAtZero}, Подъем в нуле: ${liftAtZero}, Подъем 3х: ${lift3x}`
}

function formatRoomGameResult(result: string): string {
  if (result === 'red') return 'Победа мирных'
  if (result === 'black') return 'Победа мафии'
  if (result === 'draw') return 'Ничья'
  return result || '-'
}

function formatRoleName(role: string): string {
  if (role === 'citizen') return 'Мирный'
  if (role === 'mafia') return 'Мафия'
  if (role === 'don') return 'Дон'
  if (role === 'sheriff') return 'Шериф'
  return role || '-'
}

function formatGameDuration(seconds: number): string {
  const total = Math.max(0, Number(seconds) || 0)
  const mins = Math.floor(total / 60)
  const secs = Math.floor(total % 60)
  return `${mins}:${String(secs).padStart(2, '0')}`
}

function formatGamePlayer(player: GamePlayer): string {
  const name = player.username || `user${player.id}`
  const role = formatRoleName(player.role)
  return `${player.seat}. ${name} ${role} ${player.points} ${player.mmr}`
}

function formatGameAction(action: any): string {
  if (typeof action === 'string') return action
  try { return JSON.stringify(action) } catch { return String(action) }
}

const hiddenGameActionTypes = new Set(['nominate', 'foul'])

function getGameActionType(action: any): string | null {
  if (!action) return null
  if (typeof action === 'string') {
    if (hiddenGameActionTypes.has(action)) return action
    try {
      const parsed = JSON.parse(action)
      if (parsed && typeof parsed === 'object') {
        return (parsed as { type?: string }).type
      }
    } catch {}
    return null
  }
  if (typeof action === 'object') {
    return (action as { type?: string }).type
  }
  return null
}

function filterGameActions(actions: any[]): any[] {
  return actions.filter(action => {
    const actionType = getGameActionType(action)
    return !actionType || !hiddenGameActionTypes.has(actionType)
  })
}

function chartBarHeight(count: number, maxValue: number): string {
  const max = maxValue || 1
  const pct = Math.round((count / max) * 85)
  return `${Math.max(2, pct)}%`
}

function formatMonthLabel(value: string): string {
  const [year, month] = value.split('-', 2)
  if (!year || !month) return value
  return `${month}.${year.slice(-2)}`
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

async function saveSettings(): Promise<void> {
  if (savingSettings.value) return
  savingSettings.value = true
  try {
    const payload = {
      site: {
        registration_enabled: Boolean(site.registration_enabled),
        rooms_can_create: Boolean(site.rooms_can_create),
        rooms_can_enter: Boolean(site.rooms_can_enter),
        games_can_start: Boolean(site.games_can_start),
        streams_can_start: Boolean(site.streams_can_start),
        rooms_limit_global: normalizeInt(site.rooms_limit_global),
        rooms_limit_per_user: normalizeInt(site.rooms_limit_per_user),
        rooms_empty_ttl_seconds: normalizeInt(site.rooms_empty_ttl_seconds),
      },
      game: {
        game_min_ready_players: normalizeInt(game.game_min_ready_players),
        role_pick_seconds: normalizeInt(game.role_pick_seconds),
        mafia_talk_seconds: normalizeInt(game.mafia_talk_seconds),
        player_talk_seconds: normalizeInt(game.player_talk_seconds),
        player_talk_short_seconds: normalizeInt(game.player_talk_short_seconds),
        player_foul_seconds: normalizeInt(game.player_foul_seconds),
        night_action_seconds: normalizeInt(game.night_action_seconds),
        vote_seconds: normalizeInt(game.vote_seconds),
        winks_limit: normalizeInt(game.winks_limit),
        knocks_limit: normalizeInt(game.knocks_limit),
      },
    }
    const { data } = await api.patch('/admin/settings', payload)
    Object.assign(site, data?.site || {})
    Object.assign(game, data?.game || {})
    siteSnapshot.value = snapshotSite()
    gameSnapshot.value = snapshotGame()
    settingsStore.applyPublic({
      registration_enabled: site.registration_enabled,
      rooms_can_create: site.rooms_can_create,
      rooms_can_enter: site.rooms_can_enter,
      games_can_start: site.games_can_start,
      streams_can_start: site.streams_can_start,
      game_min_ready_players: game.game_min_ready_players,
      winks_limit: game.winks_limit,
      knocks_limit: game.knocks_limit,
    })
    void alertDialog('Настройки сохранены')
  } catch {
    void alertDialog('Не удалось сохранить настройки')
  } finally {
    savingSettings.value = false
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
      registrations_monthly: Array.isArray(data?.registrations_monthly) ? data.registrations_monthly : [],
      total_rooms: data?.total_rooms ?? 0,
      total_games: data?.total_games ?? 0,
      total_stream_minutes: data?.total_stream_minutes ?? 0,
      active_rooms: data?.active_rooms ?? 0,
      active_room_users: data?.active_room_users ?? 0,
      online_users: data?.online_users ?? 0,
      online_users_list: Array.isArray(data?.online_users_list) ? data.online_users_list : [],
      last_day: {
        games: data?.last_day?.games ?? 0,
        online_users: data?.last_day?.online_users ?? 0,
        rooms: data?.last_day?.rooms ?? 0,
        stream_minutes: data?.last_day?.stream_minutes ?? 0,
      },
      last_month: {
        games: data?.last_month?.games ?? 0,
        online_users: data?.last_month?.online_users ?? 0,
        rooms: data?.last_month?.rooms ?? 0,
        stream_minutes: data?.last_month?.stream_minutes ?? 0,
      },
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
    const items = Array.isArray(data?.items) ? data.items : []
    rooms.value = items.map((item: any) => ({
      ...item,
      creator_avatar_name: item?.creator_avatar_name ?? null,
      break_at_zero: Boolean(item?.break_at_zero),
      lift_at_zero: Boolean(item?.lift_at_zero),
      lift_3x: Boolean(item?.lift_3x),
      visitors: normalizeRoomUsers(item?.visitors),
      spectators: normalizeRoomUsers(item?.spectators),
      games: normalizeRoomGames(item?.games),
      streamers: normalizeRoomUsers(item?.streamers),
    }))
    roomsTotal.value = Number.isFinite(data?.total) ? data.total : 0
  } catch {
    void alertDialog('Не удалось загрузить комнаты')
  } finally {
    roomsLoading.value = false
  }
}

async function loadGames(): Promise<void> {
  if (gamesLoading.value) return
  gamesLoading.value = true
  try {
    const params: Record<string, any> = {
      page: gamesPage.value,
      limit: gamesLimit.value,
    }
    if (gamesUser.value) params.username = gamesUser.value
    if (gamesDay.value) params.day = gamesDay.value
    const { data } = await api.get('/admin/games', { params })
    const items = Array.isArray(data?.items) ? data.items : []
    games.value = items.map((item: any) => ({
      ...item,
      owner: item?.owner || { id: 0, username: null, avatar_name: null },
      head: item?.head || null,
      players: Array.isArray(item?.players) ? item.players : [],
      actions: filterGameActions(Array.isArray(item?.actions) ? item.actions : []),
    }))
    gamesTotal.value = Number.isFinite(data?.total) ? data.total : 0
  } catch {
    void alertDialog('Не удалось загрузить игры')
  } finally {
    gamesLoading.value = false
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

async function loadUpdates(): Promise<void> {
  if (updatesLoading.value) return
  updatesLoading.value = true
  try {
    const { data } = await api.get('/admin/updates')
    updates.value = Array.isArray(data?.items) ? data.items : []
  } catch {
    updates.value = []
    void alertDialog('Не удалось загрузить обновления')
  } finally {
    updatesLoading.value = false
  }
}

function resetUpdateForm(row?: UpdateRow | null) {
  updateForm.version = row?.version || ''
  updateForm.date = row?.date ? String(row.date).slice(0, 10) : ''
  updateForm.description = row?.description || ''
}

function openCreateUpdate() {
  updateEditing.value = null
  resetUpdateForm()
  updateModalOpen.value = true
}

function openEditUpdate(row: UpdateRow) {
  updateEditing.value = row
  resetUpdateForm(row)
  updateModalOpen.value = true
}

async function deleteUpdate(row: UpdateRow): Promise<void> {
  if (updatesDeleting[row.id]) return
  const ok = await confirmDialog({
    title: 'Удалить обновление',
    text: `Удалить обновление версии ${row.version}?`,
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  updatesDeleting[row.id] = true
  try {
    await api.delete(`/admin/updates/${row.id}`)
    updates.value = updates.value.filter(item => item.id !== row.id)
    void alertDialog('Обновление удалено')
  } catch {
    void alertDialog('Не удалось удалить обновление')
  } finally {
    updatesDeleting[row.id] = false
  }
}

async function saveUpdate(): Promise<void> {
  if (updateSaving.value || !canSaveUpdate.value) return
  updateSaving.value = true
  const payload = {
    version: updateForm.version.trim(),
    date: updateForm.date,
    description: updateForm.description.trim(),
  }
  try {
    if (updateEditing.value) {
      await api.patch(`/admin/updates/${updateEditing.value.id}`, payload)
      void alertDialog('Обновление сохранено')
    } else {
      await api.post('/admin/updates', payload)
      void alertDialog('Обновление добавлено')
    }
    updateModalOpen.value = false
    await loadUpdates()
  } catch {
    void alertDialog('Не удалось сохранить обновление')
  } finally {
    updateSaving.value = false
  }
}

async function kickAllRooms(): Promise<void> {
  if (kickRoomsBusy.value) return
  const ok = await confirmDialog({
    title: 'Кик из комнат',
    text: 'Кикнуть всех пользователей из всех активных комнат?',
    confirmText: 'Кикнуть',
    cancelText: 'Отмена',
  })
  if (!ok) return
  kickRoomsBusy.value = true
  try {
    await api.post('/admin/rooms/kick')
    void alertDialog('Пользователи кикнуты из комнат')
  } catch {
    void alertDialog('Не удалось кикнуть пользователей')
  } finally {
    kickRoomsBusy.value = false
  }
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

function nextGames(): void {
  if (gamesPage.value >= gamesPages.value) return
  gamesPage.value += 1
  void loadGames()
}

function prevGames(): void {
  if (gamesPage.value <= 1) return
  gamesPage.value -= 1
  void loadGames()
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
  const isAdmin = row.role === 'admin'
  const targetRole = isAdmin ? 'user' : 'admin'
  const userLabel = row.username ? `пользователю ${row.username}` : `пользователю #${row.id}`
  const ok = await confirmDialog({
    title: isAdmin ? 'Снять ADMIN' : 'Выдать ADMIN',
    text: `${isAdmin ? 'Снять' : 'Выдать'} права администратора ${userLabel}?`,
    confirmText: isAdmin ? 'Снять' : 'Выдать',
    cancelText: 'Отмена',
  })
  if (!ok) return
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

async function toggleDeleteAccount(row: UserRow): Promise<void> {
  if (usersDeleteBusy[row.id]) return
  const isDeleted = Boolean(row.deleted_at)
  const userLabel = row.username ? `${row.username}` : `#${row.id}`
  const ok = await confirmDialog({
    title: isDeleted ? 'Восстановить аккаунт' : 'Удалить аккаунт',
    text: isDeleted
      ? `Восстановить доступ для ${userLabel}?`
      : `Удаление аккаунта ${userLabel} произойдет навсегда без возможности восстановления.`,
    confirmText: isDeleted ? 'Восстановить' : 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  usersDeleteBusy[row.id] = true
  try {
    const url = isDeleted ? `/admin/users/${row.id}/restore` : `/admin/users/${row.id}/delete`
    await api.post(url)
    await loadUsers()
  } catch {
    void alertDialog(isDeleted ? 'Не удалось восстановить аккаунт' : 'Не удалось удалить аккаунт')
  } finally {
    usersDeleteBusy[row.id] = false
  }
}

function resetSanctionForm(): void {
  sanctionForm.months = 0
  sanctionForm.days = 0
  sanctionForm.hours = 0
  sanctionForm.minutes = 0
  sanctionForm.reason = sanctionReasons[0]?.value || ''
}

function openTimedSanction(row: UserRow, kind: 'timeout' | 'suspend'): void {
  sanctionTarget.value = row
  sanctionKind.value = kind
  resetSanctionForm()
  sanctionModalOpen.value = true
}

function setSanctionBusy(userId: number, kind: 'timeout' | 'ban' | 'suspend', value: boolean): void {
  usersSanctionBusy[`${userId}:${kind}`] = value
}

async function saveTimedSanction(): Promise<void> {
  const target = sanctionTarget.value
  if (!target || sanctionSaving.value || !sanctionCanSave.value) return
  sanctionSaving.value = true
  const kind = sanctionKind.value
  const url = kind === 'timeout' ? `/admin/users/${target.id}/timeout` : `/admin/users/${target.id}/suspend`
  const payload = {
    months: sanctionForm.months,
    days: sanctionForm.days,
    hours: sanctionForm.hours,
    minutes: sanctionForm.minutes,
    reason: sanctionForm.reason,
  }
  try {
    await api.post(url, payload)
    sanctionModalOpen.value = false
    void alertDialog(kind === 'timeout' ? 'Таймаут выдан' : 'Ограничение выдано')
    await loadUsers()
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 409 && d === 'sanction_active') {
      void alertDialog('Санкция уже активна')
    } else if (st === 422 && d === 'duration_required') {
      void alertDialog('Укажите срок санкции')
    } else {
      void alertDialog('Не удалось применить санкцию')
    }
  } finally {
    sanctionSaving.value = false
  }
}

async function revokeSanction(row: UserRow, kind: 'timeout' | 'ban' | 'suspend'): Promise<void> {
  if (isSanctionBusy(row.id, kind)) return
  const userLabel = row.username ? `${row.username}` : `#${row.id}`
  const title = kind === 'ban' ? 'Разбанить' : kind === 'timeout' ? 'Снять таймаут' : 'Снять ограничение'
  const text = kind === 'ban'
    ? `Разбанить ${userLabel}?`
    : kind === 'timeout'
      ? `Снять таймаут у ${userLabel}?`
      : `Снять ограничение у ${userLabel}?`
  const ok = await confirmDialog({
    title,
    text,
    confirmText: title,
    cancelText: 'Отмена',
  })
  if (!ok) return
  setSanctionBusy(row.id, kind, true)
  try {
    await api.delete(`/admin/users/${row.id}/${kind}`)
    void alertDialog(kind === 'ban' ? 'Бан снят' : kind === 'timeout' ? 'Таймаут снят' : 'Ограничение снято')
    await loadUsers()
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 404 && d === 'sanction_not_found') {
      void alertDialog('Санкция не найдена')
    } else {
      void alertDialog('Не удалось снять санкцию')
    }
  } finally {
    setSanctionBusy(row.id, kind, false)
  }
}

async function toggleTimeout(row: UserRow): Promise<void> {
  if (row.timeout_active) {
    await revokeSanction(row, 'timeout')
  } else {
    openTimedSanction(row, 'timeout')
  }
}

async function toggleSuspend(row: UserRow): Promise<void> {
  if (row.suspend_active) {
    await revokeSanction(row, 'suspend')
  } else {
    openTimedSanction(row, 'suspend')
  }
}

async function toggleBan(row: UserRow): Promise<void> {
  if (row.ban_active) {
    await revokeSanction(row, 'ban')
    return
  }
  const userLabel = row.username ? `${row.username}` : `#${row.id}`
  const ok = await confirmDialog({
    title: 'Бан',
    text: `Забанить ${userLabel}?`,
    confirmText: 'Забанить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  if (isSanctionBusy(row.id, 'ban')) return
  setSanctionBusy(row.id, 'ban', true)
  try {
    await api.post(`/admin/users/${row.id}/ban`, { reason: sanctionReasons[0]?.value || 'Нарушение правил платформы' })
    void alertDialog('Бан выдан')
    await loadUsers()
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 409 && d === 'sanction_active') {
      void alertDialog('Санкция уже активна')
    } else {
      void alertDialog('Не удалось выдать бан')
    }
  } finally {
    setSanctionBusy(row.id, 'ban', false)
  }
}

watch(activeTab, (tab) => {
  if (tab === 'updates') {
    void loadUpdates()
    return
  }
  if (tab === 'stats') {
    void loadStats()
    return
  }
  if (tab === 'logs') {
    void loadLogActions()
    void loadLogs()
    return
  }
  if (tab === 'rooms') {
    void loadRooms()
    return
  }
  if (tab === 'games') {
    void loadGames()
    return
  }
  if (tab === 'users') {
    void loadUsers()
  }
})

watch(statsMonth, () => {
  if (activeTab.value !== 'stats') return
  void loadStats()
})

watch([logsAction, logsLimit, logsDay], () => {
  logsPage.value = 1
  if (activeTab.value !== 'logs') return
  void loadLogs()
})

watch(logsUser, () => {
  logsPage.value = 1
  if (activeTab.value !== 'logs') return
  if (logsUserTimer) window.clearTimeout(logsUserTimer)
  logsUserTimer = window.setTimeout(() => { void loadLogs() }, 500)
})

watch([roomsStreamOnly, roomsLimit], () => {
  roomsPage.value = 1
  if (activeTab.value !== 'rooms') return
  void loadRooms()
})

watch(roomsUser, () => {
  roomsPage.value = 1
  if (activeTab.value !== 'rooms') return
  if (roomsUserTimer) window.clearTimeout(roomsUserTimer)
  roomsUserTimer = window.setTimeout(() => { void loadRooms() }, 500)
})

watch([gamesLimit, gamesDay], () => {
  gamesPage.value = 1
  if (activeTab.value !== 'games') return
  void loadGames()
})

watch(gamesUser, () => {
  gamesPage.value = 1
  if (activeTab.value !== 'games') return
  if (gamesUserTimer) window.clearTimeout(gamesUserTimer)
  gamesUserTimer = window.setTimeout(() => { void loadGames() }, 500)
})

watch(usersLimit, () => {
  usersPage.value = 1
  if (activeTab.value !== 'users') return
  void loadUsers()
})

watch(usersUser, () => {
  usersPage.value = 1
  if (activeTab.value !== 'users') return
  if (usersUserTimer) window.clearTimeout(usersUserTimer)
  usersUserTimer = window.setTimeout(() => { void loadUsers() }, 500)
})

onMounted(() => {
  const now = new Date()
  statsMonth.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  void loadSettings()
})
</script>

<style scoped lang="scss">
.admin {
  display: flex;
  flex-direction: column;
  margin: 0 10px 10px;
  padding: 10px;
  border-radius: 5px;
  background-color: $dark;
  overflow-x: hidden;
  scrollbar-width: none;
  user-select: text;
  header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    border-bottom: 3px solid $lead;
    .tabs {
      display: flex;
      align-items: flex-end;
      width: 80%;
      height: 30px;
      .tab {
        width: 200px;
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
    &.confirm {
      background-color: rgba($green, 0.75);
      &:hover {
        background-color: $green;
      }
    }
    &.danger {
      background-color: rgba($red, 0.75);
      color: $fg;
      &:hover {
        background-color: $red;
      }
    }
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .btn-img {
      width: 20px;
      height: 20px;
    }
  }
  .tab-panel {
    margin-top: 10px;
    .loading {
      padding: 20px;
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
            border-radius: 5px;
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
          margin-top: 10px;
        }
        .switch {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 10px;
          .switch-label {
            height: 18px;
          }
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
                transition: color 0.25s ease-in-out;
              }
            }
            .slider:before {
              content: "";
              position: absolute;
              top: 0;
              left: 0;
              width: 83px;
              height: 23px;
              background-color: $fg;
              border-radius: 5px;
              transition: transform 0.25s ease-in-out;
            }
            input:checked + .slider:before {
              transform: translateX(85px);
            }
            input:not(:checked) + .slider span:first-child,
            input:checked + .slider span:last-child {
              color: $bg;
            }
            input:disabled + .slider {
              opacity: 0.5;
              cursor: not-allowed;
            }
          }
        }
      }
      .form-actions {
        display: flex;
        justify-content: flex-end;
        grid-column: 1 / -1;
      }
    }
    .filters {
      display: flex;
      flex-wrap: wrap;
      align-items: flex-start;
      gap: 10px;
      margin: 10px 0;
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
      .stats-subtitle {
        font-size: 14px;
        color: $grey;
      }
      .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 10px;
        &.stats-grid--compact {
          grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        }
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
            color: $fg;
          }
          .value {
            font-size: 20px;
            color: $green;
          }
        }
      }
      .tooltip {
        position: relative;
        display: inline-flex;
        align-items: center;
        cursor: default;
        width: fit-content;
        .tooltip-value {
          border-bottom: 1px dashed $grey;
        }
        .tooltip-body {
          position: absolute;
          top: calc(100% - 35px);
          right: 15px;
          min-width: 220px;
          max-width: 320px;
          max-height: 200px;
          overflow: auto;
          padding: 10px;
          border: 1px solid $lead;
          border-radius: 5px;
          background-color: $graphite;
          box-shadow: 0 5px 15px rgba($black, 0.25);
          opacity: 0;
          transform: translateY(-5px);
          pointer-events: none;
          transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
          z-index: 10;
        }
        .tooltip-list {
          display: flex;
          flex-direction: column;
          gap: 5px;
        }
        .tooltip-row {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 5px;
          font-size: 12px;
          color: $fg;
        }
        .tooltip-id {
          color: $grey;
        }
        .tooltip-empty {
          font-size: 12px;
          color: $grey;
        }
        &:hover .tooltip-body,
        &:focus-within .tooltip-body {
          opacity: 1;
          transform: translateY(0);
          pointer-events: auto;
        }
      }
      .chart {
        padding: 10px;
        border: 1px solid $lead;
        border-radius: 5px;
        background-color: $graphite;
        .chart-body {
          display: flex;
          margin-top: 10px;
          gap: 10px;
        }
        .chart-axis {
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          height: 185px;
          padding: 2px 0;
          font-size: 14px;
          color: $grey;
          min-width: 10px;
          text-align: right;
        }
        .chart-grid {
          display: flex;
          align-items: flex-end;
          gap: 5px;
          height: 180px;
          overflow-x: auto;
          padding: 5px 3px;
          flex: 1;
          .chart-bar {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-end;
            gap: 5px;
            width: 15px;
            flex: 0 0 15px;
            height: 100%;
            .bar {
              position: relative;
              width: 100%;
              background-color: $fg;
              border-radius: 3px 3px 0 0;
              transition: height 0.25s ease-in-out;
              .bar-value {
                position: absolute;
                top: -14px;
                left: 50%;
                transform: translateX(-50%);
                font-size: 10px;
                color: $fg;
                white-space: nowrap;
              }
            }
            .bar-label {
              font-size: 10px;
              color: $grey;
            }
          }
        }
      }
      .chart--monthly {
        .chart-grid {
          .chart-bar {
            width: 28px;
            flex: 0 0 28px;
          }
        }
      }
    }
    .table {
      width: 100%;
      border-collapse: collapse;
      color: $fg;
      font-family: Manrope-Medium;
      th {
        padding: 10px;
        border-bottom: 1px solid $lead;
        font-size: 16px;
        color: $grey;
        text-align: left;
      }
      td {
        padding: 10px;
        border-bottom: 1px solid $lead;
        font-size: 14px;
      }
      .players-cell,
      .actions-cell {
        min-width: 240px;
        white-space: normal;
      }
      .players-list,
      .actions-list {
        margin: 0;
        padding-left: 18px;
      }
      .actions-list {
        max-height: 180px;
        overflow: auto;
      }
      .user-cell {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        &.compact {
          gap: 5px;
        }
      }
      .user-avatar {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        object-fit: cover;
      }
      .tooltip {
        position: relative;
        display: inline-flex;
        align-items: center;
        cursor: default;
        width: fit-content;
        .tooltip-value {
          border-bottom: 1px dashed $grey;
        }
        .tooltip-body {
          position: absolute;
          top: calc(100% - 35px);
          right: 15px;
          min-width: 220px;
          max-width: 320px;
          max-height: 200px;
          overflow: auto;
          padding: 10px;
          border: 1px solid $lead;
          border-radius: 5px;
          background-color: $graphite;
          box-shadow: 0 5px 15px rgba($black, 0.25);
          opacity: 0;
          transform: translateY(-5px);
          pointer-events: none;
          transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
          z-index: 10;
        }
        .tooltip-list {
          display: flex;
          flex-direction: column;
          gap: 5px;
        }
        .tooltip-row {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 5px;
          font-size: 12px;
          color: $fg;
        }
        .tooltip-id,
        .tooltip-minutes {
          color: $grey;
        }
        .tooltip-empty {
          font-size: 12px;
          color: $grey;
        }
        &:hover .tooltip-body,
        &:focus-within .tooltip-body {
          opacity: 1;
          transform: translateY(0);
          pointer-events: auto;
        }
      }
    }
    .updates-toolbar {
      display: flex;
      justify-content: flex-end;
      margin-bottom: 10px;
    }
    .updates-table .desc {
      white-space: pre-wrap;
      max-width: 520px;
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
  .admin {
    header {
      .tabs {
        .tab {
          height: 25px;
          font-size: 12px;
          &.active {
            height: 30px;
          }
        }
      }
    }
    .btn {
      padding: 0 5px;
      gap: 3px;
      height: 25px;
      font-size: 14px;
      &.nav {
        padding: 0 10px;
        font-size: 12px;
      }
      .btn-img {
        width: 16px;
        height: 16px;
      }
    }
    .tab-panel {
      .stats {
        .chart {
          padding: 5px;
          .chart-grid {
            gap: 3px;
          }
        }
      }
      .table {
        th {
          padding: 3px;
          font-size: 12px;
        }
        td {
          padding: 3px;
          font-size: 10px;
        }
        .user-avatar {
          width: 16px;
          height: 16px;
        }
        .tooltip {
          .tooltip-body {
            padding: 5px;
          }
        }
      }
    }
  }
}
</style>
