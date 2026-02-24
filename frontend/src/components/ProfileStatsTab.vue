<template>
  <div class="stats-tab">
    <div class="stats-head">
      <h3>Неигровая статистика</h3>
      <button class="reload" type="button" :disabled="loading" @click="load(true)">
        {{ loading ? '...' : 'Обновить' }}
      </button>
    </div>

    <div v-if="loading && !loaded" class="state">Загрузка...</div>
    <div v-else-if="error" class="state state-danger">
      <span>{{ error }}</span>
      <button class="retry" type="button" :disabled="loading" @click="load(true)">Повторить</button>
    </div>
    <div v-else class="stats-content">
      <section class="summary">
        <article v-for="item in summaryItems" :key="item.key" class="metric">
          <span class="metric-label">{{ item.label }}</span>
          <strong class="metric-value">{{ item.value }}</strong>
        </article>
      </section>

      <section class="top-players">
        <h4>Топ-5 игроков по количеству игр вместе</h4>
        <div v-if="topPlayers.length === 0" class="state state-inline">Пока нет данных</div>
        <ol v-else class="top-list">
          <li v-for="(player, idx) in topPlayers" :key="player.id" class="top-item">
            <div class="top-row">
              <span class="top-rank">#{{ idx + 1 }}</span>
              <span class="top-name">{{ player.username || `user${player.id}` }}</span>
              <span class="top-count">{{ formatInt(player.games_together) }}</span>
            </div>
            <div class="top-bar">
              <span class="top-fill" :style="{ width: `${barPercent(player.games_together)}%` }"></span>
            </div>
          </li>
        </ol>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '@/services/axios'

type UserTopPlayer = {
  id: number
  username?: string | null
  games_together: number
}

type UserStats = {
  rooms_created: number
  room_minutes: number
  stream_minutes: number
  spectator_minutes: number
  top_players: UserTopPlayer[]
}

const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const numberFmt = new Intl.NumberFormat('ru-RU')

const stats = reactive<UserStats>({
  rooms_created: 0,
  room_minutes: 0,
  stream_minutes: 0,
  spectator_minutes: 0,
  top_players: [],
})

function safeInt(value: unknown): number {
  const num = Number(value)
  if (!Number.isFinite(num)) return 0
  return Math.max(0, Math.trunc(num))
}

function formatInt(value: number): string {
  return numberFmt.format(safeInt(value))
}

const topPlayers = computed(() => stats.top_players)
const maxTogether = computed(() => topPlayers.value.reduce((max, item) => Math.max(max, safeInt(item.games_together)), 1))

const summaryItems = computed(() => [
  { key: 'rooms-created', label: 'Создал комнат', value: formatInt(stats.rooms_created) },
  { key: 'room-minutes', label: 'Минут в комнатах', value: formatInt(stats.room_minutes) },
  { key: 'stream-minutes', label: 'Минут стримил', value: formatInt(stats.stream_minutes) },
  { key: 'spectator-minutes', label: 'Минут как зритель', value: formatInt(stats.spectator_minutes) },
])

function barPercent(value: number): number {
  const current = safeInt(value)
  if (current <= 0) return 0
  const max = maxTogether.value
  if (max <= 0) return 0
  const pct = Math.round((current / max) * 100)
  return Math.max(8, Math.min(100, pct))
}

async function load(force = false) {
  if (loading.value) return
  if (loaded.value && !force) return
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<UserStats>('/users/stats')
    stats.rooms_created = safeInt(data?.rooms_created)
    stats.room_minutes = safeInt(data?.room_minutes)
    stats.stream_minutes = safeInt(data?.stream_minutes)
    stats.spectator_minutes = safeInt(data?.spectator_minutes)
    stats.top_players = Array.isArray(data?.top_players)
      ? data.top_players
          .map((item) => ({
            id: safeInt(item?.id),
            username: typeof item?.username === 'string' ? item.username : null,
            games_together: safeInt(item?.games_together),
          }))
          .filter((item) => item.id > 0)
          .slice(0, 5)
      : []
    loaded.value = true
  } catch {
    error.value = 'Не удалось загрузить статистику'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<style scoped lang="scss">
.stats-tab {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  .stats-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    h3 {
      margin: 0;
    }
    .reload {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 120px;
      height: 32px;
      padding: 0 12px;
      border: none;
      border-radius: 5px;
      background-color: $lead;
      font-family: Manrope-Medium;
      font-size: 14px;
      color: $fg;
      cursor: pointer;
      transition: background-color 0.25s ease-in-out, opacity 0.25s ease-in-out;
      &:hover {
        background-color: rgba($grey, 0.5);
      }
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
  }
  .state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    min-height: 140px;
    padding: 10px;
    border: 1px solid rgba($grey, 0.35);
    border-radius: 5px;
    color: $ashy;
    background-color: rgba($graphite, 0.4);
    &.state-danger {
      color: $red;
    }
    &.state-inline {
      min-height: auto;
    }
    .retry {
      min-width: 110px;
      height: 32px;
      border: none;
      border-radius: 5px;
      background-color: rgba($red, 0.75);
      color: $fg;
      cursor: pointer;
      transition: background-color 0.25s ease-in-out, opacity 0.25s ease-in-out;
      &:hover {
        background-color: $red;
      }
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
  }
  .stats-content {
    display: grid;
    grid-template-columns: minmax(250px, 340px) minmax(0, 1fr);
    gap: 10px;
    .summary {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
      .metric {
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        gap: 6px;
        min-height: 92px;
        border: 1px solid $lead;
        border-radius: 5px;
        padding: 10px;
        background: linear-gradient(145deg, rgba($graphite, 0.95), rgba($dark, 0.95));
        .metric-label {
          font-size: 14px;
          color: $ashy;
        }
        .metric-value {
          font-family: Manrope-SemiBold;
          font-size: 28px;
          line-height: 1;
          color: $fg;
        }
      }
    }
    .top-players {
      display: flex;
      flex-direction: column;
      gap: 10px;
      border: 1px solid $lead;
      border-radius: 5px;
      padding: 10px;
      background: linear-gradient(165deg, rgba($graphite, 0.9), rgba($dark, 0.95));
      h4 {
        margin: 0;
      }
      .top-list {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin: 0;
        padding: 0;
        list-style: none;
        .top-item {
          display: flex;
          flex-direction: column;
          gap: 6px;
          padding: 8px;
          border-radius: 5px;
          background-color: rgba($lead, 0.35);
          .top-row {
            display: grid;
            grid-template-columns: auto 1fr auto;
            align-items: center;
            gap: 8px;
            .top-rank {
              color: $ashy;
            }
            .top-name {
              overflow: hidden;
              text-overflow: ellipsis;
              white-space: nowrap;
            }
            .top-count {
              color: $fg;
              font-family: Manrope-SemiBold;
            }
          }
          .top-bar {
            width: 100%;
            height: 8px;
            border-radius: 999px;
            background-color: rgba($black, 0.35);
            overflow: hidden;
            .top-fill {
              display: block;
              height: 100%;
              border-radius: inherit;
              background: linear-gradient(90deg, rgba($orange, 0.85), rgba($yellow, 0.95));
            }
          }
        }
      }
    }
  }
}

@media (max-width: 980px) {
  .stats-tab {
    .stats-content {
      grid-template-columns: 1fr;
      .summary {
        grid-template-columns: 1fr 1fr;
      }
    }
  }
}

@media (max-width: 640px) {
  .stats-tab {
    .stats-head {
      .reload {
        min-width: 105px;
      }
    }
    .stats-content {
      .summary {
        grid-template-columns: 1fr;
        .metric {
          min-height: 78px;
          .metric-value {
            font-size: 22px;
          }
        }
      }
    }
  }
}
</style>
