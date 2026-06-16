<template>
  <section class="admin">
    <header>
      <nav class="tabs" aria-label="Админ" role="tablist">
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'stats' }" :aria-selected="activeTab === 'stats'" @click="activeTab = 'stats'">
          Статистика
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'settings' }" :aria-selected="activeTab === 'settings'" @click="activeTab = 'settings'">
          Параметры
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'updates' }" :aria-selected="activeTab === 'updates'" @click="activeTab = 'updates'">
          Уведомления
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'logs' }" :aria-selected="activeTab === 'logs'" @click="activeTab = 'logs'">
          Логи
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'rooms' }" :aria-selected="activeTab === 'rooms'" @click="activeTab = 'rooms'">
          Комнаты
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'users' }" :aria-selected="activeTab === 'users'" @click="activeTab = 'users'">
          Пользователи
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'sanctions' }" :aria-selected="activeTab === 'sanctions'" @click="activeTab = 'sanctions'">
          Санкции
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'contact_requests' }" :aria-selected="activeTab === 'contact_requests'" @click="activeTab = 'contact_requests'">
          Обращения
        </button>
        <button class="tab" type="button" role="tab" :class="{ active: activeTab === 'subscriptions' }" :aria-selected="activeTab === 'subscriptions'" @click="activeTab = 'subscriptions'">
          Подписки
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
              <UiSwitch class="switch-item" v-model="site.registration_enabled" label="Регистрация" :disabled="savingSettings" />
              <UiSwitch class="switch-item" v-model="site.rooms_can_create" label="Создание комнат" :disabled="savingSettings" />
              <UiSwitch class="switch-item" v-model="site.rooms_can_enter" label="Вход в комнату" :disabled="savingSettings" />
              <UiSwitch class="switch-item" v-model="site.games_can_start" label="Запуск игр" :disabled="savingSettings" />
              <UiSwitch class="switch-item" v-model="site.streams_can_start" label="Запуск трансляций" :disabled="savingSettings" />
              <UiSwitch class="switch-item" v-model="site.chat_open_enabled" label="Открытие чата" :disabled="savingSettings" />
              <UiSwitch class="switch-item" v-model="site.chat_messages_enabled" label="Сообщения в чат" :disabled="savingSettings" />
              <UiSwitch class="switch-item" v-model="site.verification_restrictions" label="Ограничения верификации" :disabled="savingSettings" />
              <div class="bulk-admin-actions">
                <button class="btn danger width-full" :disabled="kickRoomsBusy || clearChatBusy" @click="kickAllRooms">
                  Кик из комнат
                </button>
                <button class="btn danger width-full" :disabled="kickRoomsBusy || clearChatBusy" @click="clearGlobalChat">
                  Очистить чат
                </button>
              </div>
            </div>

            <div class="block">
              <div class="field-stack">
                <UiInput id="admin-banner-text" v-model="site.admin_banner_text"
                         autocomplete="off" :disabled="savingSettings" label="Текст баннера в хедере" />
                <UiInput id="admin-banner-link" v-model="site.admin_banner_link"
                         autocomplete="off" :disabled="savingSettings" label="Ссылка баннера в хедере" />
                <UiInput id="rooms-limit-global" v-model.number="site.rooms_limit_global" type="number" min="1" max="100" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Общий лимит комнат" />
                <UiInput id="rooms-limit-user" v-model.number="site.rooms_limit_per_user" type="number" min="1" max="10" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Лимит комнат на пользователя" />
                <UiInput id="rooms-empty-ttl-seconds" v-model.number="site.rooms_empty_ttl_seconds" type="number" min="10" max="300" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Время жизни пустой комнаты (сек)" />
                <UiInput id="rooms-single-ttl-minutes" v-model.number="site.rooms_single_ttl_minutes" type="number" min="1" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Кик при 1 участнике (мин)" />
                <UiInput id="season-start-game-number" v-model="site.season_start_game_number"
                         autocomplete="off" inputmode="text" :disabled="savingSettings" label="Стартовые игры сезонов (через запятую)" />
                <UiInput id="text-moderation-whitelist" v-model="site.text_moderation_whitelist"
                         autocomplete="off" inputmode="text" :disabled="savingSettings" label="Белый список слов (через запятую)" />
                <UiInput id="text-moderation-blacklist" v-model="site.text_moderation_blacklist"
                         autocomplete="off" inputmode="text" :disabled="savingSettings" label="Чёрный список слов (через запятую)" />
              </div>
            </div>

            <div class="block">
              <div class="field-stack">
                <UiInput id="game-min-ready" v-model.number="game.game_min_ready_players" type="number" min="1" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Количество игроков для старта" />
                <UiInput id="role-pick-seconds" v-model.number="game.role_pick_seconds" type="number" min="1" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Выбор ролей (сек)" />
                <UiInput id="mafia-talk-seconds" v-model.number="game.mafia_talk_seconds" type="number" min="1" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Договорка мафии (сек)" />
                <UiInput id="player-talk-seconds" v-model.number="game.player_talk_seconds" type="number" min="1" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Речь игрока (сек)" />
                <UiInput id="player-talk-short-seconds" v-model.number="game.player_talk_short_seconds" type="number" min="1" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Речь при 3х фолах (сек)" />
                <UiInput id="player-foul-seconds" v-model.number="game.player_foul_seconds" type="number" min="1" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Фол (сек)" />
                <UiInput id="night-action-seconds" v-model.number="game.night_action_seconds" type="number" min="1" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Отстрелы и проверки (сек)" />
                <UiInput id="vote-seconds" v-model.number="game.vote_seconds" type="number" min="1" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Голосование (сек)" />
                <UiInput id="winks-limit" v-model.number="game.winks_limit" type="number" min="0" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Подмигивания (шт)" />
                <UiInput id="knocks-limit" v-model.number="game.knocks_limit" type="number" min="0" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Постукивания (шт)" />
                <UiInput id="wink-spot-chance-percent" v-model.number="game.wink_spot_chance_percent" type="number" min="0" max="100" step="1"
                         autocomplete="off" inputmode="numeric" :disabled="savingSettings" label="Вероятность для подмигиваний (%)" />
              </div>
            </div>

            <div class="form-actions">
              <button class="btn confirm width-full" :disabled="savingSettings || !isSettingsDirty" @click="saveSettings">
                <img class="btn-img" :src="iconSave" alt="save" />
                Сохранить
              </button>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'updates'">
          <div class="grid updates-notice-grid">
            <div class="block updates-notice-block">
              <div class="field-stack">
                <UiInput id="update-notice-title" v-model.trim="updateNoticeForm.title" type="text" autocomplete="off" :disabled="updateNoticeSaving" label="Название" />
                <UiInput id="update-notice-text" v-model="updateNoticeForm.text" as="textarea" rows="7" :disabled="updateNoticeSaving" label="Текст" class="update-notice-textarea" />
              </div>
              <div v-if="updateNoticeForm.title.trim() || updateNoticeTextPreview" class="update-notice-preview">
                <article class="update-notice-preview-item">
                  <div class="update-notice-preview-header">
                    <span>{{ updateNoticePreviewTitle }}</span>
                    <time>{{ updateNoticePreviewDate }}</time>
                  </div>
                  <div v-if="updateNoticePreviewBlocks.length" class="update-notice-preview-text">
                    <template v-for="(block, blockIndex) in updateNoticePreviewBlocks" :key="`${block.type}-${blockIndex}`">
                      <p v-if="block.type === 'paragraph'" class="notification-text-paragraph">
                        <template v-for="(line, lineIndex) in block.lines" :key="`${blockIndex}-${lineIndex}`">
                          {{ line }}<br v-if="lineIndex < block.lines.length - 1" />
                        </template>
                      </p>
                      <ul v-else class="notification-text-list">
                        <li v-for="(item, itemIndex) in block.items" :key="`${blockIndex}-${itemIndex}`">
                          {{ item }}
                        </li>
                      </ul>
                    </template>
                  </div>
                </article>
              </div>
              <div class="form-actions">
                <button class="btn confirm width-full" :disabled="updateNoticeSaving || !canSendUpdateNotice" @click="sendUpdateNotice">
                  <img class="btn-img" :src="iconSave" alt="save" />
                  Отправить всем
                </button>
              </div>
            </div>
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
                <span class="label">В комнатах</span>
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
                        <img class="tooltip-avatar" v-minio-img="{ key: item.avatar_name ? `avatars/${item.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                        <span>{{ item.username || `user${item.id}` }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div class="stat-card">
                <span class="label">Аватары</span>
                <span class="value">{{ stats.avatars_count }} ({{ formatBytes(stats.avatars_bytes) }})</span>
              </div>
              <div class="stat-card">
                <span class="label">Изображения в чате</span>
                <span class="value">{{ stats.images_count }} ({{ formatBytes(stats.images_bytes) }})</span>
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
            </div>
            <div class="chart">
              <div class="filters">
                <div class="field">
                  <UiInput id="stats-month" v-model="statsMonth" type="month" label="Отобразить за" :disabled="statsLoading" />
                </div>
              </div>
              <div class="stats-grid">
                <div class="stat-card">
                  <span class="label">Комнаты</span>
                  <span class="value">{{ stats.last_month.rooms }}</span>
                </div>
                <div class="stat-card">
                  <span class="label">Игры</span>
                  <span class="value">{{ stats.last_month.games }}</span>
                </div>
                <div class="stat-card">
                  <span class="label">Стримы</span>
                  <span class="value">{{ formatMinutes(stats.last_month.stream_minutes) }}</span>
                </div>
              </div>
              <div class="stats-daily-grid">
                <div class="stats-daily-block">
                  <div class="stats-mini-title">Регистрации по дням</div>
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
                <div class="stats-daily-block">
                  <div class="stats-mini-title">Игры по дням</div>
                  <div v-if="stats.games_by_day.length === 0" class="muted">Нет данных</div>
                  <div v-else class="chart-body">
                    <div class="chart-axis">
                      <span v-for="tick in gamesByDayTicks" :key="tick">{{ tick }}</span>
                    </div>
                    <div class="chart-grid">
                      <div v-for="point in stats.games_by_day" :key="`game-day-${point.date}`" class="chart-bar">
                        <div class="bar" :style="{ height: chartBarHeight(point.count, gamesByDayMax) }">
                          <span class="bar-value">{{ point.count }}</span>
                        </div>
                        <span class="bar-label">{{ point.date.slice(-2) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="stats-daily-block">
                  <div class="stats-mini-title">Активные пользователи по дням</div>
                  <div v-if="stats.active_users_by_day.length === 0" class="muted">Нет данных</div>
                  <div v-else class="chart-body">
                    <div class="chart-axis">
                      <span v-for="tick in activeUsersByDayTicks" :key="tick">{{ tick }}</span>
                    </div>
                    <div class="chart-grid">
                      <div v-for="point in stats.active_users_by_day" :key="`active-day-${point.date}`" class="chart-bar">
                        <div class="bar" :style="{ height: chartBarHeight(point.count, activeUsersByDayMax) }">
                          <span class="bar-value">{{ point.count }}</span>
                        </div>
                        <span class="bar-label">{{ point.date.slice(-2) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="stats-monthly-grid">
              <div class="chart chart--monthly">
                <div class="stats-mini-title">Регистрации по месяцам</div>
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
              <div class="chart chart--monthly">
                <div class="stats-mini-title">Игры по месяцам</div>
                <div v-if="stats.games_monthly.length === 0" class="muted">Нет данных</div>
                <div v-else class="chart-body">
                  <div class="chart-axis">
                    <span v-for="tick in gamesMonthlyTicks" :key="tick">{{ tick }}</span>
                  </div>
                  <div class="chart-grid">
                    <div v-for="point in stats.games_monthly" :key="point.date" class="chart-bar">
                      <div class="bar" :style="{ height: chartBarHeight(point.count, gamesMonthlyMax) }">
                        <span class="bar-value">{{ point.count }}</span>
                      </div>
                      <span class="bar-label">{{ formatMonthLabel(point.date) }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div class="chart chart--monthly">
                <div class="stats-mini-title">Активные пользователи по месяцам</div>
                <div v-if="stats.active_users_monthly.length === 0" class="muted">Нет данных</div>
                <div v-else class="chart-body">
                  <div class="chart-axis">
                    <span v-for="tick in activeUsersMonthlyTicks" :key="tick">{{ tick }}</span>
                  </div>
                  <div class="chart-grid">
                    <div v-for="point in stats.active_users_monthly" :key="`active-month-${point.date}`" class="chart-bar">
                      <div class="bar" :style="{ height: chartBarHeight(point.count, activeUsersMonthlyMax) }">
                        <span class="bar-value">{{ point.count }}</span>
                      </div>
                      <span class="bar-label">{{ formatMonthLabel(point.date) }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'logs'">
          <div class="filters">
            <div class="field">
              <UiInput id="logs-user" v-model.trim="logsUser" label="Никнейм" :disabled="logsLoading" />
            </div>
            <div class="field">
              <UiInput id="logs-day" v-model="logsDay" type="date" label="Дата" :disabled="logsLoading" />
            </div>
            <div class="field">
              <label for="admin-logs-action">Событие</label>
              <select id="admin-logs-action" :value="logsAction" :disabled="logsLoading" @change="setLogsAction">
                <option v-for="option in logActionOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>
            <div class="field">
              <label for="admin-logs-limit">Отображать по</label>
              <select id="admin-logs-limit" :value="logsLimit" :disabled="logsLoading" @change="setLogsLimit">
                <option v-for="option in PAGE_LIMIT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>
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
                      <button class="user-link user-profile-trigger" type="button" :disabled="!canOpenLogUserMiniProfile(row)" @click="openLogUserMiniProfile(row)">
                        <img class="user-avatar" v-minio-img="{ key: row.avatar_name ? `avatars/${row.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                        <span>{{ row.username }}</span>
                      </button>
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
            <div class="field">
              <UiInput id="rooms-user" v-model.trim="roomsUser" label="Никнейм" :disabled="roomsLoading" />
            </div>
            <div class="field">
              <label for="admin-rooms-filter">Фильтры</label>
              <select id="admin-rooms-filter" :value="roomsFilter" :disabled="roomsLoading" @change="setRoomsFilter">
                <option v-for="option in ROOM_FILTER_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>
            <div class="field">
              <label for="admin-rooms-limit">Отображать по</label>
              <select id="admin-rooms-limit" :value="roomsLimit" :disabled="roomsLoading" @change="setRoomsLimit">
                <option v-for="option in PAGE_LIMIT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>
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
                  <th>Анонимность</th>
                  <th>Лимит</th>
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
                      <button class="user-link user-profile-trigger" type="button" :disabled="!canOpenRoomCreatorMiniProfile(row)" @click="openRoomCreatorMiniProfile(row)">
                        <img class="user-avatar" v-minio-img="{ key: row.creator_avatar_name ? `avatars/${row.creator_avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                        <span>{{ row.creator_name || `user${row.creator}` }}</span>
                      </button>
                    </div>
                  </td>
                  <td>{{ formatRoomPrivacy(row.privacy) }}</td>
                  <td>{{ formatRoomAnonymity(row.anonymity) }}</td>
                  <td>{{ row.user_limit }}</td>
                  <td>{{ formatLocalDateTime(row.created_at) }}</td>
                  <td>{{ row.deleted_at ? formatLocalDateTime(row.deleted_at) : '-' }}</td>
                  <td>
                    <div class="tooltip" tabindex="0">
                      <span class="tooltip-value">{{ row.visitors_count }}</span>
                      <div class="tooltip-body">
                        <div v-if="row.visitors.length === 0" class="tooltip-empty">Нет данных</div>
                        <div v-else class="tooltip-list">
                          <div v-for="item in row.visitors" :key="`visitor-${row.id}-${item.id}`" class="tooltip-row">
                            <div class="user-cell compact">
                              <img class="tooltip-avatar" v-minio-img="{ key: item.avatar_name ? `avatars/${item.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                              <span>{{ item.username || `user${item.id}` }}</span>
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
                            <div class="user-cell compact">
                              <img class="tooltip-avatar" v-minio-img="{ key: item.avatar_name ? `avatars/${item.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                              <span>{{ item.username || `user${item.id}` }}</span>
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
                          <div v-for="item in row.games" :key="`game-${row.id}-${item.result}-${item.number}`" class="tooltip-row">
                            <span class="tooltip-id">Игра {{ item.number }} - </span>
                            <span class="tooltip-minutes">
                              {{ formatRoomGameResult(item.result) }}<template v-if="item.result !== 'active'"> ({{ formatMinutes(item.minutes) }})</template>
                            </span>
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
                            <div class="user-cell compact">
                              <img class="tooltip-avatar" v-minio-img="{ key: item.avatar_name ? `avatars/${item.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                              <span>{{ item.username || `user${item.id}` }}</span>
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

        <div v-else-if="activeTab === 'users'">
          <div class="filters">
            <div class="field">
              <UiInput id="users-user" v-model.trim="usersUser" label="Никнейм" :disabled="usersLoading" />
            </div>
            <div class="field">
              <label for="admin-users-limit">Отображать по</label>
              <select id="admin-users-limit" :value="usersLimit" :disabled="usersLoading" @change="setUsersLimit">
                <option v-for="option in PAGE_LIMIT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>
          </div>

          <div v-if="usersLoading" class="loading">Загрузка...</div>
          <div v-else>
            <table class="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>TG_ID</th>
                  <th>Никнейм</th>
                  <th>Регистрация</th>
                  <th>Последнее общение</th>
                  <th>Последний зритель</th>
                  <th>Отстранения</th>
                  <th>Таймауты</th>
                  <th>Баны</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in users" :key="row.id">
                  <td>{{ row.id }}</td>
                  <td>{{ row.tg_id ?? '-' }}</td>
                  <td>
                    <div v-if="row.username" class="user-cell">
                      <button class="user-link user-profile-trigger" type="button" :disabled="!canOpenAdminUserMiniProfile(row)" @click="openAdminUserMiniProfile(row)">
                        <img class="user-avatar" v-minio-img="{ key: row.avatar_name ? `avatars/${row.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                        <span>{{ row.username }}</span>
                      </button>
                    </div>
                    <span v-else>-</span>
                  </td>
                  <td>{{ formatLocalDateTime(row.registered_at) }}</td>
                  <td>{{ formatRoomIdLabel(row.last_room_id) }}</td>
                  <td>{{ formatRoomIdLabel(row.last_spectator_room_id) }}</td>
                  <td>{{ row.suspends_count }}</td>
                  <td>{{ row.timeouts_count }}</td>
                  <td>{{ row.bans_count }}</td>
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

        <div v-else-if="activeTab === 'sanctions'">
          <div class="filters">
            <div class="field">
              <UiInput id="sanctions-user" v-model.trim="sanctionsUser" label="Никнейм" :disabled="sanctionsLoading" />
            </div>
            <div class="field">
              <label for="admin-sanctions-limit">Отображать по</label>
              <select id="admin-sanctions-limit" :value="sanctionsLimit" :disabled="sanctionsLoading" @change="setSanctionsLimit">
                <option v-for="option in PAGE_LIMIT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>
          </div>

          <div v-if="sanctionsLoading" class="loading">Загрузка...</div>
          <div v-else>
            <table class="table sanctions-table">
              <thead>
                <tr>
                  <th>Пользователь</th>
                  <th>Тип санкции</th>
                  <th>Статус</th>
                  <th>Дата выдачи</th>
                  <th>Дата окончания</th>
                  <th>Кем выдана</th>
                  <th>Кем снята</th>
                  <th>Срок изначальный</th>
                  <th>Срок по факту</th>
                  <th>Отработка ведущим</th>
                  <th>Пункт правил</th>
                  <th>Описание</th>
                  <th>Уменьшить</th>
                  <th>Увеличить</th>
                  <th>Удаление</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in sanctions" :key="row.id">
                  <td>
                    <div class="user-cell">
                      <button class="user-link user-profile-trigger" type="button" :disabled="!canOpenSanctionUserMiniProfile(row)" @click="openSanctionUserMiniProfile(row)">
                        <img class="user-avatar" v-minio-img="{ key: row.avatar_name ? `avatars/${row.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                        <span>{{ row.username || `user${row.user_id}` }}</span>
                      </button>
                    </div>
                  </td>
                  <td>{{ formatSanctionKindLabel(row.kind) }}</td>
                  <td>
                    <span class="status-badge" :class="sanctionStatusClass(row.status)">{{ formatSanctionStatusLabel(row.status) }}</span>
                  </td>
                  <td>{{ formatLocalDateTime(row.issued_at) }}</td>
                  <td>{{ row.finished_at ? formatLocalDateTime(row.finished_at) : '-' }}</td>
                  <td>{{ row.issued_by_display }}</td>
                  <td>{{ row.revoked_by_display || '-' }}</td>
                  <td>{{ formatSanctionDuration(row.duration_seconds) }}</td>
                  <td>{{ formatSanctionDuration(row.served_seconds) }}</td>
                  <td>{{ formatSanctionWorkoff(row) }}</td>
                  <td class="rule-cell">{{ row.reason || '-' }}</td>
                  <td class="description-cell">{{ row.description || '-' }}</td>
                  <td class="actions-cell">
                    <button v-if="canAdjustSanction(row)" class="btn dark" :disabled="isSanctionAdjustBusy(row, 'decrease')" @click="openSanctionAdjust(row, 'decrease')">
                      Уменьшить
                    </button>
                    <span v-else>-</span>
                  </td>
                  <td class="actions-cell">
                    <button v-if="canAdjustSanction(row)" class="btn" :disabled="isSanctionAdjustBusy(row, 'increase')" @click="openSanctionAdjust(row, 'increase')">
                      Увеличить
                    </button>
                    <span v-else>-</span>
                  </td>
                  <td class="actions-cell">
                    <button v-if="canDeleteSanction(row)" class="btn danger" :disabled="sanctionsDeleting[row.id]" @click="deleteSanction(row)">
                      <img class="btn-img" :src="iconDelete" alt="delete" />
                      Удалить
                    </button>
                    <span v-else>-</span>
                  </td>
                </tr>
                <tr v-if="sanctions.length === 0">
                  <td colspan="15" class="muted">Нет данных</td>
                </tr>
              </tbody>
            </table>
            <div class="pager">
              <button class="btn" :disabled="sanctionsPage <= 1" @click="prevSanctions">Назад</button>
              <span>{{ sanctionsPage }} / {{ sanctionsPages }}</span>
              <button class="btn" :disabled="sanctionsPage >= sanctionsPages" @click="nextSanctions">Вперед</button>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'contact_requests'">
          <div class="filters">
            <div class="field">
              <UiInput id="contact-requests-user" v-model.trim="contactRequestsUser" label="Никнейм" :disabled="contactRequestsLoading" />
            </div>
            <div class="field">
              <label for="admin-contact-requests-limit">Отображать по</label>
              <select id="admin-contact-requests-limit" :value="contactRequestsLimit" :disabled="contactRequestsLoading" @change="setContactRequestsLimit">
                <option v-for="option in PAGE_LIMIT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>
          </div>

          <div v-if="contactRequestsLoading" class="loading">Загрузка...</div>
          <div v-else>
            <table class="table contact-requests-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Дата</th>
                  <th>Никнейм</th>
                  <th>Контактные данные</th>
                  <th>Тема обращения</th>
                  <th>Текст обращения</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in contactRequests" :key="row.id">
                  <td>{{ row.id }}</td>
                  <td>{{ formatLocalDateTime(row.created_at) }}</td>
                  <td>
                    <div v-if="row.user_id" class="user-cell">
                      <button class="user-link user-profile-trigger" type="button" :disabled="!canOpenContactRequestUserMiniProfile(row)" @click="openContactRequestUserMiniProfile(row)">
                        <img class="user-avatar" v-minio-img="{ key: row.avatar_name ? `avatars/${row.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                        <span>{{ row.username || `user${row.user_id}` }}</span>
                      </button>
                    </div>
                    <span v-else>-</span>
                  </td>
                  <td class="contact-cell">{{ row.contact }}</td>
                  <td class="topic-cell">{{ row.topic }}</td>
                  <td class="text-cell">{{ row.text }}</td>
                  <td>
                    <button class="btn danger" :disabled="contactRequestsDeleting[row.id]" @click="deleteContactRequest(row)">
                      <img class="btn-img" :src="iconDelete" alt="delete" />
                      Удалить
                    </button>
                  </td>
                </tr>
                <tr v-if="contactRequests.length === 0">
                  <td colspan="7" class="muted">Нет данных</td>
                </tr>
              </tbody>
            </table>
            <div class="pager">
              <button class="btn" :disabled="contactRequestsPage <= 1" @click="prevContactRequests">Назад</button>
              <span>{{ contactRequestsPage }} / {{ contactRequestsPages }}</span>
              <button class="btn" :disabled="contactRequestsPage >= contactRequestsPages" @click="nextContactRequests">Вперед</button>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'subscriptions'" class="subscriptions-tab">
          <div class="block subscription-table-block">
            <h3>Активные подписки — {{ activeSubscriptionsCount }}</h3>
            <div v-if="subscriptionsLoading" class="loading">Загрузка...</div>
            <table v-else class="table">
              <thead>
                <tr>
                  <th>Пользователь</th>
                  <th>Дата начала подписки</th>
                  <th>Дата окончания подписки</th>
                  <th>Статус</th>
                  <th>Оформление</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in subscriptions" :key="row.user_id">
                  <td>
                    <div class="user-cell">
                      <button class="user-link user-profile-trigger" type="button" :disabled="!canOpenSubscriptionUserMiniProfile(row)" @click="openSubscriptionUserMiniProfile(row)">
                        <img class="user-avatar" v-minio-img="{ key: row.avatar_name ? `avatars/${row.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="avatar" />
                        <span>{{ row.username || `user${row.user_id}` }}</span>
                      </button>
                    </div>
                  </td>
                  <td>{{ formatLocalDateTime(row.starts_at) }}</td>
                  <td>{{ formatLocalDateTime(row.ends_at) }}</td>
                  <td>{{ row.is_active ? 'Активна' : 'Истекла' }}</td>
                  <td>
                    <div class="subscription-theme-preview">
                      <span class="subscription-theme-chip" :style="subscriptionThemeStyle(row.profile_theme_color)"></span>
                      <div v-if="subscriptionThemeIconSrcs(row.profile_theme_icon, row.role).length" class="subscription-theme-icons" aria-hidden="true">
                        <img v-for="badgeSrc in subscriptionThemeIconSrcs(row.profile_theme_icon, row.role)" :key="`${row.user_id}-${badgeSrc}`" class="subscription-theme-icon" :src="badgeSrc" alt="" />
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="subscription-actions">
                      <button class="btn confirm" :disabled="subscriptionSaving" @click="openExtendSubscription(row)">
                        Продлить
                      </button>
                      <button class="btn dark" :disabled="subscriptionSaving || !row.is_active" @click="openReduceSubscription(row)">
                        Уменьшить
                      </button>
                      <button class="btn danger" :disabled="subscriptionRemoving[row.user_id]" @click="removeSubscription(row)">
                        Удалить
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="subscriptions.length === 0">
                  <td colspan="6" class="muted">Нет подписок</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Transition>

    <Sanction
      :open="sanctionAdjustModalOpen"
      :title="sanctionAdjustTitle"
      :saving="sanctionAdjustSaving"
      :can-save="sanctionAdjustCanSave"
      :show-duration="true"
      :show-reason="false"
      :show-description="false"
      :save-label="sanctionAdjustSaveLabel"
      :form="sanctionAdjustForm"
      :reasons="sanctionReasons"
      @update:open="onSanctionAdjustModalOpenUpdate"
      @save="saveSanctionAdjust"
    />
    <Subscription
      :open="subscriptionModalOpen && Boolean(subscriptionTarget)"
      :title="subscriptionModalTitle"
      :status-text="selectedSubscriptionStatusText"
      :save-label="subscriptionModalSaveLabel"
      :saving="subscriptionSaving"
      :can-save="subscriptionCanSave"
      :target="subscriptionTarget"
      :form="subscriptionForm"
      @update:open="onSubscriptionModalOpenUpdate"
      @save="saveSubscription"
    />

    <MiniProfile
      :open="userMiniProfileOpen"
      :user-id="userMiniProfileTarget?.id ?? null"
      :initial-profile="userMiniProfileTarget"
      :stats-url="userMiniProfileStatsUrl"
      :history-url="userMiniProfileHistoryUrl"
      show-stats-button
      admin-mode
      @update:open="onUserMiniProfileOpenUpdate"
      @staff-action-complete="onUserMiniProfileStaffActionComplete"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/services/axios'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { formatLocalDateTime } from '@/services/datetime'
import { SANCTION_REASONS } from '@/constants/sanctionReasons'
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId } from '@/services/miniProfile'
import { useSettingsStore, useUserStore } from '@/store'

import Sanction from '@/components/Sanction.vue'
import Subscription from '@/components/Subscription.vue'
import MiniProfile from '@/components/MiniProfile.vue'
import UiSwitch from '@/components/UiSwitch.vue'
import UiInput from '@/components/UiInput.vue'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconDelete from '@/assets/svg/delete.svg'
import iconSave from '@/assets/svg/save.svg'
import { buildProfileThemeBgStyle } from '@/constants/profileThemes'
import { getProfileThemeBadgeSources } from '@/constants/profileIcons'
import { normalizeNotificationText, parseNotificationText } from '@/services/notificationText'

const UPDATE_NOTICE_PREVIEW_DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
}

type SiteSettings = {
  registration_enabled: boolean
  rooms_can_create: boolean
  rooms_can_enter: boolean
  games_can_start: boolean
  streams_can_start: boolean
  chat_open_enabled: boolean
  chat_messages_enabled: boolean
  verification_restrictions: boolean
  admin_banner_text: string
  admin_banner_link: string
  rooms_limit_global: number
  rooms_limit_per_user: number
  rooms_empty_ttl_seconds: number
  rooms_single_ttl_minutes: number
  season_start_game_number: string
  text_moderation_whitelist: string
  text_moderation_blacklist: string
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
  wink_spot_chance_percent: number
}

type RegistrationPoint = {
  date: string
  count: number
}

type OnlineUser = {
  id: number
  username?: string | null
  avatar_name?: string | null
}

type PeriodStats = {
  games: number
  rooms: number
  stream_minutes: number
}

type SiteStats = {
  total_users: number
  avatars_count: number
  avatars_bytes: number
  images_count: number
  images_bytes: number
  registrations: RegistrationPoint[]
  games_by_day: RegistrationPoint[]
  active_users_by_day: RegistrationPoint[]
  registrations_monthly: RegistrationPoint[]
  games_monthly: RegistrationPoint[]
  active_users_monthly: RegistrationPoint[]
  total_rooms: number
  total_games: number
  total_stream_minutes: number
  active_room_users: number
  online_users: number
  online_users_list: OnlineUser[]
  last_month: PeriodStats
}

type LogRow = {
  id: number
  user_id?: number | null
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  deleted_at?: string | null
  action: string
  details: string
  created_at: string
}

type ContactRequestRow = {
  id: number
  user_id?: number | null
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  deleted_at?: string | null
  contact: string
  topic: string
  text: string
  created_at: string
}

type RoomUserStat = {
  id: number
  username?: string | null
  avatar_name?: string | null
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
  creator_role?: string | null
  creator_deleted_at?: string | null
  title: string
  user_limit: number
  privacy: string
  anonymity: 'visible' | 'hidden'
  created_at: string
  deleted_at?: string | null
  visitors_count: number
  visitors: RoomUserStat[]
  spectators_count: number
  spectators: RoomUserStat[]
  games: RoomGameStat[]
  stream_minutes: number
  streamers: RoomUserStat[]
  has_stream: boolean
}

type UserRow = {
  id: number
  tg_id?: number | null
  username?: string | null
  avatar_name?: string | null
  role: string
  registered_at: string
  last_room_id?: number | null
  last_spectator_room_id?: number | null
  deleted_at?: string | null
  timeouts_count: number
  bans_count: number
  suspends_count: number
}

type UserMiniProfileTarget = {
  id: number
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  deleted_at?: string | null
}

type SubscriptionRow = {
  user_id: number
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  deleted_at?: string | null
  starts_at: string
  ends_at: string
  is_active: boolean
  profile_theme_color?: string | null
  profile_theme_icon?: string | null
}

type SubscriptionTarget = {
  user_id: number
  username?: string | null
  avatar_name?: string | null
}

type SanctionListStatus = 'active' | 'expired_auto' | 'revoked'
type SanctionAdjustMode = 'increase' | 'decrease'

type SanctionsRow = {
  id: number
  user_id: number
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  deleted_at?: string | null
  kind: 'timeout' | 'ban' | 'suspend'
  status: SanctionListStatus
  issued_at: string
  finished_at?: string | null
  issued_by_id?: number | null
  issued_by_name?: string | null
  issued_by_display: string
  revoked_by_id?: number | null
  revoked_by_name?: string | null
  revoked_by_display?: string | null
  duration_seconds?: number | null
  served_seconds: number
  hosted_workoff_seconds?: number | null
  reason?: string | null
  description?: string | null
}

type RoomFilter = 'all' | 'stream_only' | 'hidden_only' | 'has_games' | 'duo_only'
const route = useRoute()
const router = useRouter()

const TAB_KEYS = ['settings', 'updates', 'stats', 'logs', 'rooms', 'users', 'sanctions', 'contact_requests', 'subscriptions'] as const
type TabKey = typeof TAB_KEYS[number]
const PAGE_LIMIT_OPTIONS = [
  { value: 20, label: '20' },
  { value: 100, label: '100' },
] as const
const ROOM_FILTER_OPTIONS = [
  { value: 'all', label: 'Все комнаты' },
  { value: 'stream_only', label: 'Только со стримом' },
  { value: 'hidden_only', label: 'Скрытые комнаты' },
  { value: 'has_games', label: 'Комната с играми' },
  { value: 'duo_only', label: 'Duo-комната' },
] as const

function normalizeTab(v: unknown): TabKey {
  if (typeof v === 'string' && (TAB_KEYS as readonly string[]).includes(v)) return v as TabKey
  return 'stats'
}

const activeTab = ref<TabKey>('stats')
const loading = ref(false)
const savingSettings = ref(false)
const statsLoading = ref(false)
const logsLoading = ref(false)
const roomsLoading = ref(false)
const usersLoading = ref(false)
const sanctionsLoading = ref(false)
const contactRequestsLoading = ref(false)
const subscriptionsLoading = ref(false)

const site = reactive<SiteSettings>({
  registration_enabled: true,
  rooms_can_create: true,
  rooms_can_enter: true,
  games_can_start: true,
  streams_can_start: true,
  chat_open_enabled: true,
  chat_messages_enabled: true,
  verification_restrictions: true,
  admin_banner_text: '0',
  admin_banner_link: '0',
  rooms_limit_global: 100,
  rooms_limit_per_user: 3,
  rooms_empty_ttl_seconds: 10,
  rooms_single_ttl_minutes: 30,
  season_start_game_number: '1',
  text_moderation_whitelist: '0',
  text_moderation_blacklist: '0',
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
  wink_spot_chance_percent: 10,
})

const settingsStore = useSettingsStore()
const userStore = useUserStore()
const viewerUserId = computed(() => normalizeMiniProfileUserId(userStore.user?.id))
const siteSnapshot = ref('')
const gameSnapshot = ref('')

const statsMonth = ref('')
const stats = reactive<SiteStats>({
  total_users: 0,
  avatars_count: 0,
  avatars_bytes: 0,
  images_count: 0,
  images_bytes: 0,
  registrations: [],
  games_by_day: [],
  active_users_by_day: [],
  registrations_monthly: [],
  games_monthly: [],
  active_users_monthly: [],
  total_rooms: 0,
  total_games: 0,
  total_stream_minutes: 0,
  active_room_users: 0,
  online_users: 0,
  online_users_list: [],
  last_month: {
    games: 0,
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
const roomsFilter = ref<RoomFilter>('all')

const users = ref<UserRow[]>([])
const usersTotal = ref(0)
const usersPage = ref(1)
const usersLimit = ref(20)
const usersUser = ref('')
const sanctions = ref<SanctionsRow[]>([])
const sanctionsTotal = ref(0)
const sanctionsPage = ref(1)
const sanctionsLimit = ref(20)
const sanctionsUser = ref('')
const contactRequests = ref<ContactRequestRow[]>([])
const contactRequestsTotal = ref(0)
const contactRequestsPage = ref(1)
const contactRequestsLimit = ref(20)
const contactRequestsUser = ref('')
const contactRequestsDeleting = reactive<Record<number, boolean>>({})
const sanctionsDeleting = reactive<Record<number, boolean>>({})
const sanctionsAdjusting = reactive<Record<string, boolean>>({})
const subscriptions = ref<SubscriptionRow[]>([])
const subscriptionModalOpen = ref(false)
const subscriptionModalMode = ref<'extend' | 'reduce'>('extend')
const subscriptionTarget = ref<SubscriptionTarget | null>(null)
const subscriptionSaving = ref(false)
const subscriptionRemoving = reactive<Record<number, boolean>>({})
const subscriptionForm = reactive({
  months: 0,
  days: 0,
})
const userMiniProfileOpen = ref(false)
const userMiniProfileTarget = ref<UserMiniProfileTarget | null>(null)
const userMiniProfileStatsUrl = computed(() => {
  const target = userMiniProfileTarget.value
  return target ? `/admin/users/${target.id}/stats` : null
})
const userMiniProfileHistoryUrl = computed(() => {
  const target = userMiniProfileTarget.value
  return target ? `/admin/users/${target.id}/games/history` : null
})
const updateNoticeSaving = ref(false)
const updateNoticeForm = reactive({ title: '', text: '' })
const sanctionReasons = SANCTION_REASONS
const SANCTION_DURATION_LIMITS = {
  months: 240,
  days: 31,
  hours: 23,
} as const

function isSanctionDurationPartValid(value: number, max: number): boolean {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 0 && parsed <= max
}
const sanctionAdjustModalOpen = ref(false)
const sanctionAdjustSaving = ref(false)
const sanctionAdjustMode = ref<SanctionAdjustMode>('increase')
const sanctionAdjustTarget = ref<SanctionsRow | null>(null)
const sanctionAdjustForm = reactive({
  months: 0,
  days: 0,
  hours: 0,
  reason: '',
  description: '',
})
const sanctionAdjustDurationValid = computed(() => (
  isSanctionDurationPartValid(sanctionAdjustForm.months, SANCTION_DURATION_LIMITS.months)
  && isSanctionDurationPartValid(sanctionAdjustForm.days, SANCTION_DURATION_LIMITS.days)
  && isSanctionDurationPartValid(sanctionAdjustForm.hours, SANCTION_DURATION_LIMITS.hours)
))
const sanctionAdjustTotalSeconds = computed(() => {
  const months = Math.max(0, Number(sanctionAdjustForm.months) || 0)
  const days = Math.max(0, Number(sanctionAdjustForm.days) || 0)
  const hours = Math.max(0, Number(sanctionAdjustForm.hours) || 0)
  const totalMinutes = (months * 30 * 24 * 60) + (days * 24 * 60) + (hours * 60)
  return totalMinutes * 60
})
const sanctionAdjustCanSave = computed(() => {
  const target = sanctionAdjustTarget.value
  return Boolean(target && canAdjustSanction(target) && sanctionAdjustDurationValid.value && sanctionAdjustTotalSeconds.value > 0)
})
const sanctionAdjustSaveLabel = computed(() => sanctionAdjustMode.value === 'increase' ? 'Увеличить' : 'Уменьшить')
const sanctionAdjustTitle = computed(() => {
  const target = sanctionAdjustTarget.value
  const actionLabel = sanctionAdjustSaveLabel.value
  if (!target) return `${actionLabel} срок санкции`
  const userLabel = target.username || `user${target.user_id}`
  return `${actionLabel} ${formatSanctionKindLabel(target.kind).toLowerCase()}: ${userLabel}`
})
const kickRoomsBusy = ref(false)
const clearChatBusy = ref(false)
let logsUserTimer: number | undefined
let roomsUserTimer: number | undefined
let usersUserTimer: number | undefined
let sanctionsUserTimer: number | undefined
let contactRequestsUserTimer: number | undefined

function parseSeasonStartNumbers(raw: unknown): number[] {
  const source = String(raw ?? '').trim()
  if (!source) return []
  const values: number[] = []
  for (const part of source.split(',')) {
    const token = part.trim()
    if (!token) return []
    const parsed = Number(token)
    if (!Number.isFinite(parsed)) return []
    const value = Math.trunc(parsed)
    if (value < 1) return []
    values.push(value)
  }
  if (values.length === 0) return []
  return Array.from(new Set(values)).sort((a, b) => a - b)
}

function normalizeSeasonStartNumbers(raw: unknown): string {
  const parsed = parseSeasonStartNumbers(raw)
  if (parsed.length === 0) return '1'
  return parsed.join(',')
}

function normalizeTextModerationWordList(raw: unknown): string {
  const source = String(raw ?? '').trim()
  if (!source || source === '0') return '0'
  const values: string[] = []
  const seen = new Set<string>()
  for (const part of source.split(',')) {
    const normalized = part.trim().toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ')
    if (!normalized || normalized === '0' || seen.has(normalized)) continue
    seen.add(normalized)
    values.push(normalized)
  }
  return values.length > 0 ? values.join(',') : '0'
}

function normalizeTextModerationWhitelist(raw: unknown): string {
  return normalizeTextModerationWordList(raw)
}

function normalizeTextModerationBlacklist(raw: unknown): string {
  return normalizeTextModerationWordList(raw)
}

function normalizeAdminBannerText(raw: unknown): string {
  const text = String(raw ?? '').trim()
  if (!text || text === '0') return '0'
  return text
}

function normalizeAdminBannerLink(raw: unknown): string {
  const text = String(raw ?? '').trim()
  if (!text || text === '0') return '0'
  return text
}

function normalizeInt(value: number): number {
  return Number.isFinite(value) ? value : 0
}

function normalizePercent(value: number): number {
  const n = normalizeInt(value)
  if (n < 0) return 0
  if (n > 100) return 100
  return n
}

function normalizeRoomUsers(value: unknown): RoomUserStat[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item: any) => ({
      id: Number(item?.id) || 0,
      username: item?.username ?? null,
      avatar_name: item?.avatar_name ?? null,
      minutes: Number(item?.minutes) || 0,
    }))
    .filter(item => item.id > 0)
}

function normalizeRoomGames(value: unknown): RoomGameStat[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item: any) => {
      const number = Number(item?.number)
      return {
        number,
        result: String(item?.result || ''),
        minutes: Number(item?.minutes) || 0,
      }
    })
    .filter(item => Number.isFinite(item.number) && item.result)
}

function snapshotSite(): string {
  return JSON.stringify({
    registration_enabled: Boolean(site.registration_enabled),
    rooms_can_create: Boolean(site.rooms_can_create),
    rooms_can_enter: Boolean(site.rooms_can_enter),
    games_can_start: Boolean(site.games_can_start),
    streams_can_start: Boolean(site.streams_can_start),
    chat_open_enabled: Boolean(site.chat_open_enabled),
    chat_messages_enabled: Boolean(site.chat_messages_enabled),
    verification_restrictions: Boolean(site.verification_restrictions),
    admin_banner_text: normalizeAdminBannerText(site.admin_banner_text),
    admin_banner_link: normalizeAdminBannerLink(site.admin_banner_link),
    rooms_limit_global: normalizeInt(site.rooms_limit_global),
    rooms_limit_per_user: normalizeInt(site.rooms_limit_per_user),
    rooms_empty_ttl_seconds: normalizeInt(site.rooms_empty_ttl_seconds),
    rooms_single_ttl_minutes: normalizeInt(site.rooms_single_ttl_minutes),
    season_start_game_number: normalizeSeasonStartNumbers(site.season_start_game_number),
    text_moderation_whitelist: normalizeTextModerationWhitelist(site.text_moderation_whitelist),
    text_moderation_blacklist: normalizeTextModerationBlacklist(site.text_moderation_blacklist),
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
    wink_spot_chance_percent: normalizePercent(game.wink_spot_chance_percent),
  })
}

const isSiteDirty = computed(() => siteSnapshot.value !== snapshotSite())
const isGameDirty = computed(() => gameSnapshot.value !== snapshotGame())
const isSettingsDirty = computed(() => isSiteDirty.value || isGameDirty.value)
const logsPages = computed(() => Math.max(1, Math.ceil(logsTotal.value / logsLimit.value)))
const roomsPages = computed(() => Math.max(1, Math.ceil(roomsTotal.value / roomsLimit.value)))
const usersPages = computed(() => Math.max(1, Math.ceil(usersTotal.value / usersLimit.value)))
const sanctionsPages = computed(() => Math.max(1, Math.ceil(sanctionsTotal.value / sanctionsLimit.value)))
const contactRequestsPages = computed(() => Math.max(1, Math.ceil(contactRequestsTotal.value / contactRequestsLimit.value)))
const logActionOptions = computed(() => [
  { value: 'all', label: 'Все' },
  ...logActions.value.map((action) => ({ value: action, label: action })),
])
const subscriptionsByUserId = computed(() => {
  const mapped = new Map<number, SubscriptionRow>()
  for (const item of subscriptions.value) mapped.set(item.user_id, item)
  return mapped
})
const activeSubscriptionsCount = computed(() => {
  return subscriptions.value.filter(item => item.is_active).length
})
const selectedSubscriptionEntry = computed(() => {
  const selectedId = subscriptionTarget.value?.user_id
  if (!selectedId) return null
  return subscriptionsByUserId.value.get(selectedId) ?? null
})
const selectedSubscriptionStatusText = computed(() => {
  const entry = selectedSubscriptionEntry.value
  if (!entry) return ''
  return entry.is_active
    ? `Активна до ${formatLocalDateTime(entry.ends_at)}`
    : `Истекла ${formatLocalDateTime(entry.ends_at)}`
})
const subscriptionModalTitle = computed(() => {
  if (subscriptionModalMode.value === 'reduce') return 'Уменьшить подписку'
  return subscriptionModalMode.value === 'extend' ? 'Продлить подписку' : 'Выдать подписку'
})
const subscriptionModalSaveLabel = computed(() => {
  if (subscriptionModalMode.value === 'reduce') return 'Уменьшить'
  return subscriptionModalMode.value === 'extend' ? 'Продлить' : 'Выдать'
})
const subscriptionCanSave = computed(() => {
  const hasDuration = (Number(subscriptionForm.months) || 0) > 0 || (Number(subscriptionForm.days) || 0) > 0
  if (subscriptionModalMode.value === 'reduce') {
    return Boolean(subscriptionTarget.value && selectedSubscriptionEntry.value?.is_active && hasDuration)
  }
  return Boolean(subscriptionTarget.value && hasDuration)
})

function selectValue(event: Event): string {
  return (event.target as HTMLSelectElement).value
}

function normalizePageLimit(value: string): number {
  return Number(value) === 100 ? 100 : 20
}

function setLogsLimit(event: Event): void {
  logsLimit.value = normalizePageLimit(selectValue(event))
}

function setRoomsLimit(event: Event): void {
  roomsLimit.value = normalizePageLimit(selectValue(event))
}

function setUsersLimit(event: Event): void {
  usersLimit.value = normalizePageLimit(selectValue(event))
}

function setSanctionsLimit(event: Event): void {
  sanctionsLimit.value = normalizePageLimit(selectValue(event))
}

function setContactRequestsLimit(event: Event): void {
  contactRequestsLimit.value = normalizePageLimit(selectValue(event))
}

function setLogsAction(event: Event): void {
  logsAction.value = selectValue(event) || 'all'
}

function setRoomsFilter(event: Event): void {
  const next = selectValue(event) || 'all'
  roomsFilter.value = ROOM_FILTER_OPTIONS.some((option) => option.value === next)
    ? next as RoomFilter
    : 'all'
}

const registrationsMax = computed(() => {
  const vals = stats.registrations.map(p => p.count)
  return Math.max(1, ...vals)
})
const gamesByDayMax = computed(() => {
  const vals = stats.games_by_day.map(p => p.count)
  return Math.max(1, ...vals)
})
const activeUsersByDayMax = computed(() => {
  const vals = stats.active_users_by_day.map(p => p.count)
  return Math.max(1, ...vals)
})
const registrationsMonthlyMax = computed(() => {
  const vals = stats.registrations_monthly.map(p => p.count)
  return Math.max(1, ...vals)
})
const gamesMonthlyMax = computed(() => {
  const vals = stats.games_monthly.map(p => p.count)
  return Math.max(1, ...vals)
})
const activeUsersMonthlyMax = computed(() => {
  const vals = stats.active_users_monthly.map(p => p.count)
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
const gamesByDayTicks = computed(() => buildChartTicks(gamesByDayMax.value))
const activeUsersByDayTicks = computed(() => buildChartTicks(activeUsersByDayMax.value))
const registrationMonthlyTicks = computed(() => buildChartTicks(registrationsMonthlyMax.value))
const gamesMonthlyTicks = computed(() => buildChartTicks(gamesMonthlyMax.value))
const activeUsersMonthlyTicks = computed(() => buildChartTicks(activeUsersMonthlyMax.value))
const updateNoticePreviewTitle = computed(() => updateNoticeForm.title.trim() || 'Уведомление')
const updateNoticePreviewDate = computed(() => formatLocalDateTime(new Date(), UPDATE_NOTICE_PREVIEW_DATE_OPTIONS))
const updateNoticeTextPreview = computed(() => normalizeNotificationText(updateNoticeForm.text).trim())
const updateNoticePreviewBlocks = computed(() => parseNotificationText(updateNoticeTextPreview.value))
const canSendUpdateNotice = computed(() => {
  return Boolean(updateNoticeForm.title.trim() && updateNoticeTextPreview.value)
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

function formatRoomIdLabel(value?: number | null): string {
  const roomId = Number(value)
  return Number.isFinite(roomId) && roomId > 0 ? `Комната ${Math.trunc(roomId)}` : '-'
}

function formatBytes(value: number): string {
  const total = Math.max(0, Number(value) || 0)
  if (total < 1024) return `${Math.floor(total)} Б`
  if (total < 1024 * 1024) return `${(total / 1024).toFixed(total < 10 * 1024 ? 1 : 0)} КБ`
  if (total < 1024 * 1024 * 1024) return `${(total / (1024 * 1024)).toFixed(total < 10 * 1024 * 1024 ? 1 : 0)} МБ`
  return `${(total / (1024 * 1024 * 1024)).toFixed(total < 10 * 1024 * 1024 * 1024 ? 1 : 0)} ГБ`
}

function formatDurationSeconds(seconds?: number | null, zeroLabel = 'без срока'): string {
  if (!seconds) return zeroLabel
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

function formatSanctionDuration(seconds?: number | null): string {
  return formatDurationSeconds(seconds, 'без срока')
}

function formatSanctionWorkoff(row: SanctionsRow): string {
  if (row.kind !== 'suspend') return '-'
  return formatDurationSeconds(row.hosted_workoff_seconds, '0м')
}

function formatSanctionKindLabel(kind: 'timeout' | 'ban' | 'suspend'): string {
  if (kind === 'timeout') return 'Таймаут'
  if (kind === 'ban') return 'Бан'
  return 'Отстранение'
}

function formatSanctionStatusLabel(status: SanctionListStatus): string {
  if (status === 'active') return 'Активна'
  if (status === 'expired_auto') return 'Истекла'
  return 'Снята'
}

function sanctionStatusClass(status: SanctionListStatus): string {
  if (status === 'active') return 'status-active'
  if (status === 'expired_auto') return 'status-expired'
  return 'status-revoked'
}

function openUserMiniProfile(row: UserMiniProfileTarget): void {
  userMiniProfileTarget.value = row
  userMiniProfileOpen.value = true
}

function canOpenMiniProfileOnAdminPage(value: {
  id?: unknown
  role?: unknown
  deleted_at?: unknown
}): boolean {
  return canOpenMiniProfileTarget({
    targetId: value.id,
    viewerId: viewerUserId.value,
    viewerRole: userStore.user?.role,
    targetRole: value.role,
    targetDeletedAt: value.deleted_at,
  })
}

function canOpenAdminUserMiniProfile(row: UserRow): boolean {
  return canOpenMiniProfileOnAdminPage(row)
}

function openAdminUserMiniProfile(row: UserRow): void {
  if (!canOpenAdminUserMiniProfile(row)) return
  openUserMiniProfile({
    id: row.id,
    username: row.username ?? null,
    avatar_name: row.avatar_name ?? null,
    role: row.role ?? null,
    deleted_at: row.deleted_at ?? null,
  })
}

function getPositiveUserId(value: unknown): number {
  const id = Number(value ?? 0)
  return Number.isFinite(id) && id > 0 ? Math.trunc(id) : 0
}

function getLogUserId(row: LogRow): number {
  return getPositiveUserId(row.user_id)
}

function canOpenLogUserMiniProfile(row: LogRow): boolean {
  return canOpenMiniProfileOnAdminPage({
    id: getLogUserId(row),
    role: row.role,
    deleted_at: row.deleted_at,
  })
}

function openLogUserMiniProfile(row: LogRow): void {
  const id = getLogUserId(row)
  if (id <= 0) return
  openUserMiniProfile({
    id,
    username: row.username ?? null,
    avatar_name: row.avatar_name ?? null,
    role: row.role ?? null,
    deleted_at: row.deleted_at ?? null,
  })
}

function canOpenRoomCreatorMiniProfile(row: RoomRow): boolean {
  return canOpenMiniProfileOnAdminPage({
    id: row.creator,
    role: row.creator_role,
    deleted_at: row.creator_deleted_at,
  })
}

function openRoomCreatorMiniProfile(row: RoomRow): void {
  const id = getPositiveUserId(row.creator)
  if (id <= 0) return
  openUserMiniProfile({
    id,
    username: row.creator_name || null,
    avatar_name: row.creator_avatar_name ?? null,
    role: row.creator_role ?? null,
    deleted_at: row.creator_deleted_at ?? null,
  })
}

function canOpenSubscriptionUserMiniProfile(row: SubscriptionRow): boolean {
  return canOpenMiniProfileOnAdminPage({
    id: row.user_id,
    role: row.role,
    deleted_at: row.deleted_at,
  })
}

function canOpenSanctionUserMiniProfile(row: SanctionsRow): boolean {
  return canOpenMiniProfileOnAdminPage({
    id: row.user_id,
    role: row.role,
    deleted_at: row.deleted_at,
  })
}

function openSanctionUserMiniProfile(row: SanctionsRow): void {
  const id = getPositiveUserId(row.user_id)
  if (id <= 0) return
  openUserMiniProfile({
    id,
    username: row.username ?? null,
    avatar_name: row.avatar_name ?? null,
    role: row.role ?? null,
    deleted_at: row.deleted_at ?? null,
  })
}

function canOpenContactRequestUserMiniProfile(row: ContactRequestRow): boolean {
  return canOpenMiniProfileOnAdminPage({
    id: row.user_id,
    role: row.role,
    deleted_at: row.deleted_at,
  })
}

function openContactRequestUserMiniProfile(row: ContactRequestRow): void {
  const id = getPositiveUserId(row.user_id)
  if (id <= 0) return
  openUserMiniProfile({
    id,
    username: row.username ?? null,
    avatar_name: row.avatar_name ?? null,
    role: row.role ?? null,
    deleted_at: row.deleted_at ?? null,
  })
}

function canDeleteSanction(row: SanctionsRow): boolean {
  return row.status !== 'active'
}

function canAdjustSanction(row: SanctionsRow): boolean {
  return row.status === 'active' && (row.kind === 'timeout' || row.kind === 'suspend') && !row.deleted_at
}

function sanctionAdjustBusyKey(row: SanctionsRow, mode: SanctionAdjustMode): string {
  return `${row.id}:${mode}`
}

function isSanctionAdjustBusy(row: SanctionsRow, mode: SanctionAdjustMode): boolean {
  return Boolean(sanctionsAdjusting[sanctionAdjustBusyKey(row, mode)])
}

function openSubscriptionUserMiniProfile(row: SubscriptionRow): void {
  const id = getPositiveUserId(row.user_id)
  if (id <= 0) return
  openUserMiniProfile({
    id,
    username: row.username ?? null,
    avatar_name: row.avatar_name ?? null,
    role: row.role ?? null,
    deleted_at: row.deleted_at ?? null,
  })
}

function closeUserMiniProfile(): void {
  userMiniProfileOpen.value = false
  userMiniProfileTarget.value = null
}

function onUserMiniProfileOpenUpdate(open: boolean): void {
  userMiniProfileOpen.value = open
  if (!open) userMiniProfileTarget.value = null
}

function onUserMiniProfileStaffActionComplete(): void {
  if (activeTab.value === 'users'
    || activeTab.value === 'sanctions'
    || activeTab.value === 'contact_requests'
    || activeTab.value === 'subscriptions') {
    refreshActiveTab(activeTab.value)
  }
}

function formatRoomAnonymity(value: string | null | undefined): string {
  return value === 'hidden' ? 'Скрытая' : 'Видимая'
}

function formatRoomPrivacy(value: string | null | undefined): string {
  return value === 'private' ? 'Закрытая' : 'Открытая'
}

function formatRoomGameResult(result: string): string {
  if (result === 'active') return 'активна'
  if (result === 'red') return 'Победа мирных'
  if (result === 'black') return 'Победа мафии'
  if (result === 'draw') return 'Ничья'
  return result || '-'
}

function subscriptionThemeStyle(color: string | null | undefined): Record<string, string> {
  return buildProfileThemeBgStyle(color)
}

function subscriptionThemeIconSrcs(icon: string | null | undefined, role?: string | null): string[] {
  return getProfileThemeBadgeSources(icon, role)
}

function resetSubscriptionForm(): void {
  subscriptionForm.months = 0
  subscriptionForm.days = 0
}

function clearSubscriptionModalState(): void {
  subscriptionModalOpen.value = false
  subscriptionTarget.value = null
  resetSubscriptionForm()
}

function closeSubscriptionModal(): void {
  if (subscriptionSaving.value) return
  clearSubscriptionModalState()
}

function onSubscriptionModalOpenUpdate(open: boolean): void {
  if (open) return
  closeSubscriptionModal()
}

function openExtendSubscription(row: SubscriptionRow): void {
  subscriptionModalMode.value = 'extend'
  subscriptionTarget.value = {
    user_id: row.user_id,
    username: row.username ?? null,
    avatar_name: row.avatar_name ?? null,
  }
  resetSubscriptionForm()
  subscriptionModalOpen.value = true
}

function openReduceSubscription(row: SubscriptionRow): void {
  if (!row.is_active) return
  subscriptionModalMode.value = 'reduce'
  subscriptionTarget.value = {
    user_id: row.user_id,
    username: row.username ?? null,
    avatar_name: row.avatar_name ?? null,
  }
  resetSubscriptionForm()
  subscriptionModalOpen.value = true
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
    site.admin_banner_text = normalizeAdminBannerText(site.admin_banner_text)
    site.admin_banner_link = normalizeAdminBannerLink(site.admin_banner_link)
    site.season_start_game_number = normalizeSeasonStartNumbers(site.season_start_game_number)
    site.text_moderation_whitelist = normalizeTextModerationWhitelist(site.text_moderation_whitelist)
    site.text_moderation_blacklist = normalizeTextModerationBlacklist(site.text_moderation_blacklist)
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
    const seasonStarts = parseSeasonStartNumbers(site.season_start_game_number)
    if (seasonStarts.length === 0) {
      void alertDialog('Укажите сезоны числами через запятую, например: 1, 250, 500')
      return
    }
    const normalizedSeasonStarts = seasonStarts.join(',')
    const payload = {
      site: {
        registration_enabled: Boolean(site.registration_enabled),
        rooms_can_create: Boolean(site.rooms_can_create),
        rooms_can_enter: Boolean(site.rooms_can_enter),
        games_can_start: Boolean(site.games_can_start),
        streams_can_start: Boolean(site.streams_can_start),
        chat_open_enabled: Boolean(site.chat_open_enabled),
        chat_messages_enabled: Boolean(site.chat_messages_enabled),
        verification_restrictions: Boolean(site.verification_restrictions),
        admin_banner_text: normalizeAdminBannerText(site.admin_banner_text),
        admin_banner_link: normalizeAdminBannerLink(site.admin_banner_link),
        rooms_limit_global: normalizeInt(site.rooms_limit_global),
        rooms_limit_per_user: normalizeInt(site.rooms_limit_per_user),
        rooms_empty_ttl_seconds: normalizeInt(site.rooms_empty_ttl_seconds),
        rooms_single_ttl_minutes: normalizeInt(site.rooms_single_ttl_minutes),
        season_start_game_number: normalizedSeasonStarts,
        text_moderation_whitelist: normalizeTextModerationWhitelist(site.text_moderation_whitelist),
        text_moderation_blacklist: normalizeTextModerationBlacklist(site.text_moderation_blacklist),
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
        wink_spot_chance_percent: normalizePercent(game.wink_spot_chance_percent),
      },
    }
    const { data } = await api.patch('/admin/settings', payload)
    Object.assign(site, data?.site || {})
    Object.assign(game, data?.game || {})
    site.admin_banner_text = normalizeAdminBannerText(site.admin_banner_text)
    site.admin_banner_link = normalizeAdminBannerLink(site.admin_banner_link)
    site.season_start_game_number = normalizeSeasonStartNumbers(site.season_start_game_number)
    site.text_moderation_whitelist = normalizeTextModerationWhitelist(site.text_moderation_whitelist)
    site.text_moderation_blacklist = normalizeTextModerationBlacklist(site.text_moderation_blacklist)
    siteSnapshot.value = snapshotSite()
    gameSnapshot.value = snapshotGame()
    settingsStore.applyPublic({
      registration_enabled: site.registration_enabled,
      rooms_can_create: site.rooms_can_create,
      rooms_can_enter: site.rooms_can_enter,
      games_can_start: site.games_can_start,
      streams_can_start: site.streams_can_start,
      chat_open_enabled: site.chat_open_enabled,
      chat_messages_enabled: site.chat_messages_enabled,
      verification_restrictions: site.verification_restrictions,
      admin_banner_text: site.admin_banner_text,
      admin_banner_link: site.admin_banner_link,
      game_min_ready_players: game.game_min_ready_players,
      winks_limit: game.winks_limit,
      knocks_limit: game.knocks_limit,
      wink_spot_chance_percent: normalizePercent(game.wink_spot_chance_percent),
      season_start_game_number: site.season_start_game_number,
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
      avatars_count: data?.avatars_count ?? 0,
      avatars_bytes: data?.avatars_bytes ?? 0,
      images_count: data?.images_count ?? 0,
      images_bytes: data?.images_bytes ?? 0,
      registrations: Array.isArray(data?.registrations) ? data.registrations : [],
      games_by_day: Array.isArray(data?.games_by_day) ? data.games_by_day : [],
      active_users_by_day: Array.isArray(data?.active_users_by_day) ? data.active_users_by_day : [],
      registrations_monthly: Array.isArray(data?.registrations_monthly) ? data.registrations_monthly : [],
      games_monthly: Array.isArray(data?.games_monthly) ? data.games_monthly : [],
      active_users_monthly: Array.isArray(data?.active_users_monthly) ? data.active_users_monthly : [],
      total_rooms: data?.total_rooms ?? 0,
      total_games: data?.total_games ?? 0,
      total_stream_minutes: data?.total_stream_minutes ?? 0,
      active_room_users: data?.active_room_users ?? 0,
      online_users: data?.online_users ?? 0,
      online_users_list: Array.isArray(data?.online_users_list)
        ? data.online_users_list.map((item: any) => ({
          id: Number(item?.id) || 0,
          username: item?.username ?? null,
          avatar_name: item?.avatar_name ?? null,
        }))
        : [],
      last_month: {
        games: data?.last_month?.games ?? 0,
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
      room_filter: roomsFilter.value === 'all' ? undefined : roomsFilter.value,
    }
    if (roomsUser.value) params.username = roomsUser.value
    const { data } = await api.get('/admin/rooms', { params })
    const items = Array.isArray(data?.items) ? data.items : []
    rooms.value = items.map((item: any) => ({
      ...item,
      creator_avatar_name: item?.creator_avatar_name ?? null,
      anonymity: item?.anonymity === 'hidden' ? 'hidden' : 'visible',
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
    const items = Array.isArray(data?.items) ? data.items : []
    users.value = items.map((item: any) => ({
      ...item,
      tg_id: item?.tg_id ?? null,
      last_room_id: Number.isFinite(item?.last_room_id) ? item.last_room_id : null,
      last_spectator_room_id: Number.isFinite(item?.last_spectator_room_id) ? item.last_spectator_room_id : null,
    }))
    usersTotal.value = Number.isFinite(data?.total) ? data.total : 0
  } catch {
    void alertDialog('Не удалось загрузить пользователей')
  } finally {
    usersLoading.value = false
  }
}

async function loadSanctions(): Promise<void> {
  if (sanctionsLoading.value) return
  sanctionsLoading.value = true
  try {
    const params: Record<string, any> = {
      page: sanctionsPage.value,
      limit: sanctionsLimit.value,
    }
    if (sanctionsUser.value) params.username = sanctionsUser.value
    const { data } = await api.get('/admin/sanctions', { params })
    const items = Array.isArray(data?.items) ? data.items : []
    sanctions.value = items.map((item: any) => ({
      ...item,
      username: item?.username ?? null,
      avatar_name: item?.avatar_name ?? null,
      finished_at: item?.finished_at ?? null,
      issued_by_display: String(item?.issued_by_display || '-'),
      revoked_by_display: item?.revoked_by_display ? String(item.revoked_by_display) : null,
      duration_seconds: Number.isFinite(item?.duration_seconds) ? item.duration_seconds : null,
      served_seconds: Math.max(0, Number(item?.served_seconds) || 0),
      hosted_workoff_seconds: Number.isFinite(item?.hosted_workoff_seconds)
        ? Math.max(0, Number(item.hosted_workoff_seconds))
        : null,
      reason: item?.reason ?? null,
      description: item?.description ?? null,
    }))
    sanctionsTotal.value = Number.isFinite(data?.total) ? data.total : 0
  } catch {
    sanctions.value = []
    void alertDialog('Не удалось загрузить санкции')
  } finally {
    sanctionsLoading.value = false
  }
}

async function loadContactRequests(): Promise<void> {
  if (contactRequestsLoading.value) return
  contactRequestsLoading.value = true
  try {
    const { data } = await api.get('/admin/contact_requests', {
      params: {
        page: contactRequestsPage.value,
        limit: contactRequestsLimit.value,
        username: contactRequestsUser.value || undefined,
      },
    })
    contactRequests.value = Array.isArray(data?.items) ? data.items : []
    contactRequestsTotal.value = Number.isFinite(data?.total) ? data.total : 0
  } catch {
    contactRequests.value = []
    void alertDialog('Не удалось загрузить обращения')
  } finally {
    contactRequestsLoading.value = false
  }
}

async function deleteContactRequest(row: ContactRequestRow): Promise<void> {
  if (contactRequestsDeleting[row.id]) return
  const ok = await confirmDialog({
    title: 'Удалить обращение',
    text: `Удалить обращение #${row.id} из базы данных?`,
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  contactRequestsDeleting[row.id] = true
  try {
    await api.delete(`/admin/contact_requests/${row.id}`)
    const nextTotal = Math.max(0, contactRequestsTotal.value - 1)
    const nextPages = Math.max(1, Math.ceil(nextTotal / contactRequestsLimit.value))
    if (contactRequestsPage.value > nextPages) contactRequestsPage.value = nextPages
    await loadContactRequests()
    void alertDialog('Обращение удалено')
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 404 && d === 'contact_request_not_found') void alertDialog('Обращение не найдено')
    else void alertDialog('Не удалось удалить обращение')
  } finally {
    contactRequestsDeleting[row.id] = false
  }
}

async function deleteSanction(row: SanctionsRow): Promise<void> {
  if (!canDeleteSanction(row) || sanctionsDeleting[row.id]) return
  const userLabel = row.username || `user${row.user_id}`
  const ok = await confirmDialog({
    title: 'Удалить санкцию',
    text: `Удалить неактивную санкцию из истории у ${userLabel}?`,
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  sanctionsDeleting[row.id] = true
  try {
    await api.delete(`/admin/sanctions/${row.id}`)
    const nextTotal = Math.max(0, sanctionsTotal.value - 1)
    const nextPages = Math.max(1, Math.ceil(nextTotal / sanctionsLimit.value))
    if (sanctionsPage.value > nextPages) sanctionsPage.value = nextPages
    await loadSanctions()
    void alertDialog('Санкция удалена')
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 404 && d === 'sanction_not_found') void alertDialog('Санкция не найдена')
    else if (st === 409 && d === 'sanction_active') void alertDialog('Активную санкцию нельзя удалить')
    else void alertDialog('Не удалось удалить санкцию')
  } finally {
    sanctionsDeleting[row.id] = false
  }
}

function resetSanctionAdjustForm(): void {
  sanctionAdjustForm.months = 0
  sanctionAdjustForm.days = 0
  sanctionAdjustForm.hours = 0
  sanctionAdjustForm.reason = ''
  sanctionAdjustForm.description = ''
}

function clearSanctionAdjustModalState(): void {
  sanctionAdjustModalOpen.value = false
  sanctionAdjustTarget.value = null
  resetSanctionAdjustForm()
}

function onSanctionAdjustModalOpenUpdate(open: boolean): void {
  sanctionAdjustModalOpen.value = open
  if (!open) clearSanctionAdjustModalState()
}

function openSanctionAdjust(row: SanctionsRow, mode: SanctionAdjustMode): void {
  if (!canAdjustSanction(row) || isSanctionAdjustBusy(row, mode)) return
  sanctionAdjustTarget.value = row
  sanctionAdjustMode.value = mode
  resetSanctionAdjustForm()
  sanctionAdjustModalOpen.value = true
}

async function saveSanctionAdjust(): Promise<void> {
  const target = sanctionAdjustTarget.value
  if (!target || sanctionAdjustSaving.value || !sanctionAdjustCanSave.value) return
  const mode = sanctionAdjustMode.value
  const busyKey = sanctionAdjustBusyKey(target, mode)
  sanctionAdjustSaving.value = true
  sanctionsAdjusting[busyKey] = true
  const duration = {
    months: Math.max(0, Math.trunc(Number(sanctionAdjustForm.months) || 0)),
    days: Math.max(0, Math.trunc(Number(sanctionAdjustForm.days) || 0)),
    hours: Math.max(0, Math.trunc(Number(sanctionAdjustForm.hours) || 0)),
  }
  try {
    await api.patch(`/admin/sanctions/${target.id}/${mode}`, duration)
    await loadSanctions()
    clearSanctionAdjustModalState()
    void alertDialog(mode === 'increase' ? 'Срок санкции увеличен' : 'Срок санкции уменьшен')
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 404 && d === 'sanction_not_found') void alertDialog('Санкция не найдена')
    else if (st === 404 && d === 'user_not_found') void alertDialog('Пользователь не найден')
    else if (st === 409 && d === 'sanction_not_active') void alertDialog('Санкция уже не активна')
    else if (st === 422 && d === 'duration_required') void alertDialog('Укажите срок изменения')
    else if (st === 422 && d === 'sanction_not_timed') void alertDialog('Для этой санкции нельзя изменить срок')
    else if (st === 422 && d === 'sanction_decrease_too_large') void alertDialog('Нельзя уменьшить срок на все оставшееся время санкции или больше')
    else void alertDialog('Не удалось изменить срок санкции')
  } finally {
    sanctionsAdjusting[busyKey] = false
    sanctionAdjustSaving.value = false
  }
}

async function loadSubscriptions(): Promise<void> {
  if (subscriptionsLoading.value) return
  subscriptionsLoading.value = true
  try {
    const { data } = await api.get('/admin/subscriptions')
    subscriptions.value = Array.isArray(data?.items) ? data.items : []
  } catch {
    subscriptions.value = []
    void alertDialog('Не удалось загрузить подписки')
  } finally {
    subscriptionsLoading.value = false
  }
}

async function saveSubscription(): Promise<void> {
  if (subscriptionSaving.value || !subscriptionCanSave.value || !subscriptionTarget.value) return
  subscriptionSaving.value = true
  const selectedEntry = selectedSubscriptionEntry.value
  const hadActiveSubscription = Boolean(selectedEntry?.is_active)
  const mode = subscriptionModalMode.value
  const userId = subscriptionTarget.value.user_id
  const duration = {
    months: Math.max(0, Math.trunc(Number(subscriptionForm.months) || 0)),
    days: Math.max(0, Math.trunc(Number(subscriptionForm.days) || 0)),
  }
  try {
    if (mode === 'reduce') {
      await api.patch(`/admin/subscriptions/${userId}/reduce`, duration)
    } else {
      await api.post('/admin/subscriptions', {
        user_id: userId,
        ...duration,
      })
    }
    await loadSubscriptions()
    clearSubscriptionModalState()
    let message = 'Подписка продлена'
    if (mode === 'reduce') message = 'Срок подписки уменьшен'
    else if (!hadActiveSubscription && selectedEntry) message = 'Подписка активирована'
    void alertDialog(message)
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 404 && d === 'user_not_found') void alertDialog('Пользователь не найден')
    else if (st === 404 && d === 'subscription_not_found') void alertDialog('Подписка уже отсутствует')
    else if (st === 422 && d === 'duration_required') void alertDialog('Укажите срок подписки')
    else if (st === 422 && d === 'subscription_not_active') void alertDialog('Подписка уже не активна')
    else if (st === 422 && d === 'subscription_reduce_too_large') {
      void alertDialog('Нельзя уменьшить срок до нуля или больше оставшегося времени')
    }
    else void alertDialog('Не удалось сохранить подписку')
  } finally {
    subscriptionSaving.value = false
  }
}

async function removeSubscription(row: SubscriptionRow): Promise<void> {
  if (subscriptionRemoving[row.user_id]) return
  const ok = await confirmDialog({
    title: 'Удалить подписку',
    text: `Удалить подписку у ${row.username || `user${row.user_id}`}?`,
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!ok) return
  subscriptionRemoving[row.user_id] = true
  try {
    await api.delete(`/admin/subscriptions/${row.user_id}`)
    await loadSubscriptions()
    void alertDialog('Подписка снята')
  } catch (e: any) {
    const st = e?.response?.status
    const d = e?.response?.data?.detail
    if (st === 404 && d === 'subscription_not_found') void alertDialog('Подписка уже отсутствует')
    else void alertDialog('Не удалось удалить подписку')
  } finally {
    subscriptionRemoving[row.user_id] = false
  }
}

async function sendUpdateNotice(): Promise<void> {
  if (updateNoticeSaving.value || !canSendUpdateNotice.value) return
  updateNoticeSaving.value = true
  const title = updateNoticeForm.title.trim()
  const text = updateNoticeTextPreview.value
  try {
    await api.post('/admin/update-notification', {
      title,
      text,
    })
    updateNoticeForm.title = ''
    updateNoticeForm.text = ''
    void alertDialog('Уведомление отправлено')
  } catch {
    void alertDialog('Не удалось отправить уведомление')
  } finally {
    updateNoticeSaving.value = false
  }
}

async function kickAllRooms(): Promise<void> {
  if (kickRoomsBusy.value) return
  const ok = await confirmDialog({
    title: 'Кик из комнат',
    text: 'Кикнуть всех пользователей из всех активных комнат?',
    confirmText: 'Кикнуть',
    cancelText: 'Отмена',
    checkboxLabel: 'Подтверждаю',
    checkboxRequired: true,
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

async function clearGlobalChat(): Promise<void> {
  if (clearChatBusy.value) return
  const ok = await confirmDialog({
    title: 'Очистить чат',
    text: 'Полностью очистить общий чат?',
    confirmText: 'Очистить',
    cancelText: 'Отмена',
    checkboxLabel: 'Подтверждаю',
    checkboxRequired: true,
  })
  if (!ok) return
  clearChatBusy.value = true
  try {
    await api.post('/admin/chat/clear')
    void alertDialog('Общий чат очищен')
  } catch {
    void alertDialog('Не удалось очистить общий чат')
  } finally {
    clearChatBusy.value = false
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

function nextSanctions(): void {
  if (sanctionsPage.value >= sanctionsPages.value) return
  sanctionsPage.value += 1
  void loadSanctions()
}

function prevSanctions(): void {
  if (sanctionsPage.value <= 1) return
  sanctionsPage.value -= 1
  void loadSanctions()
}

function nextContactRequests(): void {
  if (contactRequestsPage.value >= contactRequestsPages.value) return
  contactRequestsPage.value += 1
  void loadContactRequests()
}

function prevContactRequests(): void {
  if (contactRequestsPage.value <= 1) return
  contactRequestsPage.value -= 1
  void loadContactRequests()
}

function refreshActiveTab(tab: typeof activeTab.value): void {
  if (tab === 'settings') {
    void loadSettings()
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
  if (tab === 'users') {
    void loadUsers()
    return
  }
  if (tab === 'sanctions') {
    void loadSanctions()
    return
  }
  if (tab === 'contact_requests') {
    void loadContactRequests()
    return
  }
  if (tab === 'subscriptions') {
    void loadSubscriptions()
  }
}

watch(() => route.query.tab, (tab) => {
  const next = normalizeTab(tab)
  if (next !== activeTab.value) activeTab.value = next
})

watch(activeTab, (tab) => {
  if (normalizeTab(route.query.tab) !== tab) {
    router.replace({ query: { ...route.query, tab } }).catch(() => {})
  }
  if (tab !== 'users' && userMiniProfileOpen.value) {
    closeUserMiniProfile()
  }
  if (tab !== 'subscriptions' && subscriptionModalOpen.value) {
    closeSubscriptionModal()
  }
  refreshActiveTab(tab)
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

watch([roomsFilter, roomsLimit], () => {
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

watch(sanctionsLimit, () => {
  sanctionsPage.value = 1
  if (activeTab.value !== 'sanctions') return
  void loadSanctions()
})

watch(sanctionsUser, () => {
  sanctionsPage.value = 1
  if (activeTab.value !== 'sanctions') return
  if (sanctionsUserTimer) window.clearTimeout(sanctionsUserTimer)
  sanctionsUserTimer = window.setTimeout(() => { void loadSanctions() }, 500)
})

watch(contactRequestsLimit, () => {
  contactRequestsPage.value = 1
  if (activeTab.value !== 'contact_requests') return
  void loadContactRequests()
})

watch(contactRequestsUser, () => {
  contactRequestsPage.value = 1
  if (activeTab.value !== 'contact_requests') return
  if (contactRequestsUserTimer) window.clearTimeout(contactRequestsUserTimer)
  contactRequestsUserTimer = window.setTimeout(() => { void loadContactRequests() }, 500)
})

onMounted(() => {
  const now = new Date()
  statsMonth.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  refreshActiveTab(activeTab.value)
  const requestedTab = normalizeTab(route.query.tab)
  if (typeof route.query.tab === 'string' && requestedTab !== activeTab.value) {
    Promise.resolve().then(() => {
      activeTab.value = requestedTab
    })
  }
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
  overflow: auto;
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
  .user-stats-overlay {
    display: flex;
    position: fixed;
    align-items: center;
    justify-content: center;
    inset: 0;
    padding: 20px;
    background-color: rgba($black, 0.5);
    backdrop-filter: blur(5px);
    z-index: 1200;
    .user-stats-modal {
      display: flex;
      flex-direction: column;
      width: min(96vw, 1500px);
      max-height: 92vh;
      border: 1px solid $lead;
      border-radius: 5px;
      background-color: $dark;
      overflow: hidden;
    }
    .user-stats-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px;
      border-bottom: 1px solid $lead;
      background-color: $graphite;
      span {
        font-size: 16px;
        font-family: Manrope-SemiBold;
      }
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        padding: 0;
        border: none;
        border-radius: 5px;
        background: transparent;
        cursor: pointer;
        img {
          width: 20px;
          height: 20px;
        }
      }
    }
    .user-stats-body {
      padding: 10px;
      overflow: auto;
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
    &.width-min {
      min-width: 150px;
    }
    &.width-full {
      width: 100%;
    }
  }
  .tab-panel {
    margin-top: 10px;
    .loading {
      padding: 20px;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 10px;
      .block {
        border: 3px solid $lead;
        border-radius: 5px;
        padding: 15px;
        .field-stack {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .bulk-admin-actions {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        :deep(.switch-item) {
          margin-bottom: 15px;
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
        min-width: 300px;
        max-width: 400px;
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
        font-size: 18px;
        color: $fg;
      }
      .tooltip-avatar {
        width: 16px;
        height: 16px;
        border-radius: 50%;
        object-fit: cover;
        flex: 0 0 auto;
      }
      .tooltip-id,
      .tooltip-minutes {
        color: $grey;
      }
      .tooltip-empty {
        font-size: 18px;
        color: $grey;
      }
      &:hover .tooltip-body,
      &:focus-within .tooltip-body {
        opacity: 1;
        transform: translateY(0);
        pointer-events: auto;
      }
    }
    .stats {
      display: flex;
      flex-direction: column;
      gap: 15px;
      .stats-mini-title {
        margin-bottom: 5px;
        font-size: 12px;
        color: $grey;
      }
      .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
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
            color: $fg;
          }
          .value {
            font-size: 20px;
            color: $green;
          }
        }
      }
      .stats-daily-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
        margin-top: 10px;
      }
      .stats-daily-block {
        min-width: 0;
      }
      .stats-monthly-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
      }
      .chart {
        padding: 10px;
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
          gap: 8px;
          height: 200px;
          overflow-x: auto;
          padding: 5px 3px;
          flex: 1;
          .chart-bar {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-end;
            gap: 5px;
            width: 10px;
            flex: 0 0 10px;
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
            width: 30px;
            flex: 0 0 30px;
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
      .user-cell {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        &.compact {
          gap: 5px;
        }
        .user-link {
          padding: 0;
          border: none;
          background: transparent;
          color: $fg;
          font: inherit;
          text-align: left;
          cursor: pointer;
          transition: color 0.25s ease-in-out;
          &:hover {
            color: $white;
            text-decoration: underline;
          }
        }
        .user-profile-trigger {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          min-width: 0;
          &:disabled {
            cursor: default;
            &:hover {
              color: $fg;
              text-decoration: none;
            }
          }
        }
      }
      .user-avatar {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        object-fit: cover;
      }
    }
    .updates-notice-grid {
      grid-template-columns: minmax(0, 800px);
    }
    .updates-notice-block {
      max-width: 800px;
    }
    :deep(.update-notice-textarea textarea) {
      min-height: 200px;
    }
    .update-notice-preview {
      display: flex;
      flex-direction: column;
      margin-top: 15px;
      width: 400px;
      max-width: 100%;
      padding: 10px;
      box-sizing: border-box;
      border-radius: 5px;
      background-color: $graphite;
      box-shadow: 3px 3px 5px rgba($black, 0.25);
      color: $fg;
    }
    .update-notice-preview-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 10px;
      gap: 15px;
      border-radius: 5px;
      background-color: $lead;
      box-shadow: 0 3px 5px rgba($black, 0.25);
    }
    .update-notice-preview-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      width: 100%;
      span {
        margin: 0;
        max-width: 240px;
        font-size: 18px;
        font-weight: bold;
      }
      time {
        margin-top: 3px;
        color: $grey;
        font-size: 12px;
      }
    }
    .update-notice-preview-text {
      margin: 0;
      width: 100%;
      color: $fg;
      line-height: 1.35;
      overflow-wrap: anywhere;
      word-break: break-word;
      .notification-text-paragraph,
      .notification-text-list {
        margin: 0;
      }
      .notification-text-paragraph + .notification-text-paragraph,
      .notification-text-paragraph + .notification-text-list,
      .notification-text-list + .notification-text-paragraph,
      .notification-text-list + .notification-text-list {
        margin-top: 8px;
      }
      .notification-text-list {
        padding-left: 20px;
        li + li {
          margin-top: 4px;
        }
      }
    }
    .sanctions-table .rule-cell,
    .sanctions-table .description-cell {
      max-width: 520px;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .sanctions-table .actions-cell {
      white-space: nowrap;
    }
    .contact-requests-table .contact-cell,
    .contact-requests-table .topic-cell,
    .contact-requests-table .text-cell {
      max-width: 520px;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .status-badge {
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-family: Manrope-SemiBold;
      line-height: 1;
      white-space: nowrap;
      &.status-active {
        background-color: rgba($green, 0.25);
      }
      &.status-expired {
        background-color: rgba($yellow, 0.25);
      }
      &.status-revoked {
        background-color: rgba($red, 0.25);
      }
    }
    .subscriptions-tab {
      .block {
        padding: 10px 0;
        h3 {
          margin: 0 0 20px;
          font-size: 20px;
          color: $fg;
        }
      }
      .subscription-table-block {
        min-width: 0;
      }
      .subscription-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }
      .subscription-theme-preview {
        display: inline-flex;
        align-items: center;
        gap: 5px;
      }
      .subscription-theme-chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        border-radius: 999px;
        background-color: var(--user-theme-bg, $graphite);
        font-family: Manrope-Medium;
      }
      .subscription-theme-icon {
        width: 30px;
        height: 30px;
        object-fit: contain;
      }
      .subscription-theme-icons {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        flex: 0 0 auto;
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

</style>

