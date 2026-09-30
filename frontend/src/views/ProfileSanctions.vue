<template>
  <section class="block-sanctions">
    <div class="sanctions-panel">
      <header class="section-header">
        <div>
          <span class="section-title">История санкций</span>
        </div>
      </header>
      <div v-if="sanctionsLoaded" class="sanctions-summary">
        <span>Таймауты {{ sanctionsSummary.timeout }}</span>
        <span>Отстранения {{ sanctionsSummary.suspend }}</span>
        <span>Баны {{ sanctionsSummary.ban }}</span>
      </div>
    </div>
    <div v-if="sanctionsLoading" class="sanctions-empty">Загрузка…</div>
    <div v-else-if="sanctionsError" class="sanctions-empty danger">{{ sanctionsError }}</div>
    <div v-else-if="sanctions.length === 0" class="sanctions-empty">Список санкций пуст</div>
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
            <span>Срок изначальный/по факту</span>
            <strong>{{ formatSanctionDuration(item.duration_seconds) }} / {{ formatDurationSeconds(item.served_seconds, '0м') }}</strong>
          </div>
          <div class="sanction-cell">
            <span>Пункт правил</span>
            <strong>{{ item.reason || 'Причина не указана' }}</strong>
          </div>
          <div v-if="item.kind === 'suspend'" class="sanction-cell">
            <span>Отработка ведущим</span>
            <strong>{{ formatDurationSeconds(item.hosted_workoff_seconds, '0м') }}</strong>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '@/services/axios'
import { formatLocalDateTime } from '@/services/datetime'

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

const sanctions = ref<SanctionItem[]>([])
const sanctionsLoading = ref(false)
const sanctionsLoaded = ref(false)
const sanctionsError = ref('')
let onSanctionsUpdate: ((e: Event) => void) | null = null

const sanctionsSummary = computed(() => {
  const out = { total: sanctions.value.length, timeout: 0, ban: 0, suspend: 0 }
  for (const item of sanctions.value) {
    if (item.kind === 'timeout') out.timeout += 1
    else if (item.kind === 'ban') out.ban += 1
    else if (item.kind === 'suspend') out.suspend += 1
  }
  return out
})

async function loadSanctions(force = false) {
  if (sanctionsLoading.value) return
  if (sanctionsLoaded.value && !force) return
  sanctionsLoading.value = true
  sanctionsError.value = ''
  try {
    const { data } = await api.get<{ items: SanctionItem[] }>('/users/sanctions')
    sanctions.value = Array.isArray(data?.items) ? data.items : []
    sanctionsLoaded.value = true
  } catch {
    sanctionsError.value = 'Не удалось загрузить историю ограничений'
  } finally {
    sanctionsLoading.value = false
  }
}

function formatSanctionKind(kind: SanctionKind): string {
  if (kind === 'timeout') return 'Таймаут'
  if (kind === 'suspend') return 'Отстранение'
  if (kind === 'ban') return 'Бан'
  return kind
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

function isSanctionCompleted(item: SanctionItem): boolean {
  return item.completion_reason !== 'active'
}

function formatSanctionFinishedAt(item: SanctionItem): string {
  if (!isSanctionCompleted(item) || !item.finished_at) return '-'
  return formatLocalDateTime(item.finished_at)
}

function formatSanctionCompletionReason(item: SanctionItem): string {
  if (item.completion_reason === 'expired') return 'Истекла'
  if (item.completion_reason === 'revoked_staff') return 'Досрочное снятие'
  if (item.completion_reason === 'hosted_game') return 'Проведение игры'
  return '-'
}

onMounted(() => {
  void loadSanctions(true)
  onSanctionsUpdate = () => {
    void loadSanctions(true)
  }
  window.addEventListener('auth-sanctions_update', onSanctionsUpdate)
})

onBeforeUnmount(() => {
  if (onSanctionsUpdate) window.removeEventListener('auth-sanctions_update', onSanctionsUpdate)
})
</script>

<style scoped lang="scss">
.block-sanctions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  .sanctions-panel,
  .sanction-card {
    padding: 12px 24px;
    border-radius: 24px;
    background-color: $soft-purple-900;
  }
  .section-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    .section-title {
      display: block;
      color: $neutral-white;
      font-family: Involve-Medium;
      font-size: 24px;
      line-height: 26px;
    }
  }
  .sanctions-summary {
    display: flex;
    flex-wrap: wrap;
    margin-top: 20px;
    gap: 8px;
    color: $neutral-300;
    span {
      padding: 8px 12px;
      border-radius: 12px;
      background-color: $soft-purple-800;
      font-size: 13px;
    }
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
    margin-top: 0;
    .sanction-card {
      border: none;
      min-width: 0;
      &.sanction-card--timeout {
        box-shadow: inset 3px 0 $yellow-500;
      }
      &.sanction-card--suspend {
        box-shadow: inset 3px 0 $orange-500;
      }
      &.sanction-card--ban {
        box-shadow: inset 3px 0 $red-500;
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
            background-color: $soft-purple-800;
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
