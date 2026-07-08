<template>
  <div class="profile-tab-block block-sanctions">
    <div class="sanctions-head">
      <h3>История отстранений от игр, таймаутов и банов</h3>
    </div>
    <div v-if="sanctionsLoaded" class="sanctions-summary">
      <span>Всего: {{ sanctionsSummary.total }}</span>
      <span>Таймауты: {{ sanctionsSummary.timeout }}</span>
      <span>Отстранения: {{ sanctionsSummary.suspend }}</span>
      <span>Баны: {{ sanctionsSummary.ban }}</span>
    </div>
    <div v-if="sanctionsLoading" class="sanctions-empty">Загрузка…</div>
    <div v-else-if="sanctionsError" class="sanctions-empty danger">{{ sanctionsError }}</div>
    <div v-else-if="sanctions.length === 0" class="sanctions-empty">Ограничений пока не было</div>
    <div v-else class="sanctions-list">
      <article v-for="item in sanctions" :key="item.id" class="sanction-card" :class="`sanction-card--${item.kind}`">
        <div class="sanction-head">
          <div class="sanction-kind">
            <span class="sanction-tag">{{ formatSanctionKind(item.kind) }}</span>
          </div>
        </div>
        <div class="sanction-grid">
          <div class="sanction-cell">
            <span>Дата выдачи</span>
            <strong>{{ formatLocalDateTime(item.issued_at) }}</strong>
          </div>
          <div class="sanction-cell">
            <span>Пункт правил</span>
            <strong>{{ item.reason || 'Причина не указана' }}</strong>
          </div>
          <div class="sanction-cell">
            <span>Срок изначальный</span>
            <strong>{{ formatSanctionDuration(item.duration_seconds) }}</strong>
          </div>
          <div class="sanction-cell">
            <span>Дата снятия</span>
            <strong>{{ formatSanctionFinishedAt(item) }}</strong>
          </div>
          <div class="sanction-cell">
            <span>Причина снятия</span>
            <strong>{{ formatSanctionCompletionReason(item) }}</strong>
          </div>
          <div class="sanction-cell">
            <span>Срок по факту</span>
            <strong>{{ formatDurationSeconds(item.served_seconds, '0м') }}</strong>
          </div>
          <div v-if="item.kind === 'suspend'" class="sanction-cell">
            <span>Отработка ведущим</span>
            <strong>{{ formatDurationSeconds(item.hosted_workoff_seconds, '0м') }}</strong>
          </div>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
type SanctionKind = 'timeout' | 'ban' | 'suspend'
type SanctionCompletionReason = 'active' | 'expired' | 'revoked_staff' | 'hosted_game'

type SanctionItem = {
  id: number
  kind: SanctionKind
  completion_reason: SanctionCompletionReason
  reason?: string | null
  issued_at: string
  finished_at?: string | null
  duration_seconds?: number | null
  served_seconds: number
  hosted_workoff_seconds?: number | null
}

type SanctionsSummary = {
  total: number
  timeout: number
  suspend: number
  ban: number
}

defineProps<{
  sanctionsLoaded: boolean
  sanctionsSummary: SanctionsSummary
  sanctionsLoading: boolean
  sanctionsError: string
  sanctions: SanctionItem[]
  formatSanctionKind: (kind: SanctionKind) => string
  formatLocalDateTime: (value: string, options?: Intl.DateTimeFormatOptions) => string
  formatSanctionDuration: (seconds?: number | null) => string
  formatSanctionFinishedAt: (item: SanctionItem) => string
  formatSanctionCompletionReason: (item: SanctionItem) => string
  formatDurationSeconds: (seconds?: number | null, zeroLabel?: string) => string
}>()
</script>

<style scoped lang="scss">
.block-sanctions {
  .sanctions-head {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
  }
  .sanctions-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    font-size: 14px;
    color: $neutral-100;
  }
  .sanctions-empty {
    padding: 20px 0;
    color: $neutral-300;
    &.danger {
      color: $red-500;
    }
  }
  .sanctions-list {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
    margin-top: 10px;
    .sanction-card {
      border: 3px solid $neutral-700;
      border-radius: 5px;
      padding: 10px;
      &.sanction-card--timeout {
        border-color: rgba($yellow-500, 0.5);
        background-color: rgba($yellow-500, 0.25);
      }
      &.sanction-card--suspend {
        border-color: rgba($orange-500, 0.5);
        background-color: rgba($orange-500, 0.25);
      }
      &.sanction-card--ban {
        border-color: rgba($red-500, 0.5);
        background-color: rgba($red-500, 0.25);
      }
      .sanction-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        .sanction-kind {
          display: flex;
          align-items: center;
          gap: 5px;
          flex-wrap: wrap;
          .sanction-tag {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 5px 10px;
            min-width: 30px;
            border-radius: 999px;
            background-color: $neutral-900;
            font-size: 12px;
            color: $neutral-100;
          }
        }
      }
      .sanction-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin-top: 10px;
        .sanction-cell {
          display: flex;
          flex-direction: column;
          gap: 3px;
          font-size: 14px;
          span {
            color: $neutral-300;
            font-size: 12px;
          }
          strong {
            color: $neutral-100;
            overflow-wrap: anywhere;
          }
        }
      }
    }
  }
}
</style>
