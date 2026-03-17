<template>
  <span v-if="isAdmin" class="actions-trigger" @pointerdown.stop @click.stop.prevent="openModal">
    Подробности
  </span>

  <Teleport to="body">
    <Transition name="overlay">
      <div v-if="open" class="overlay" @pointerdown.self="armed = true"
           @pointerup.self="armed && closeModal()" @pointerleave.self="armed = false" @pointercancel.self="armed = false">
        <div class="modal" role="dialog" aria-modal="true" :aria-label="`Подробности игры #${gameNumber}`">
          <header>
            <span>Подробности игры #{{ gameNumber }}</span>
            <button class="icon" type="button" aria-label="Закрыть" @click="closeModal">
              <img :src="iconClose" alt="close" />
            </button>
          </header>

          <div class="modal-body">
            <div v-if="loading" class="state">Загрузка игровых действий...</div>
            <div v-else-if="error" class="state state-error">{{ error }}</div>
            <div v-else-if="items.length === 0" class="state">Игровые действия не найдены</div>

            <div v-else class="actions-list">
              <article v-for="action in items" :key="`${gameId}-${action.order}-${action.type}`" class="action-card">
                <div class="action-head">
                  <div class="action-head-main">
                    <span class="action-order">#{{ action.order }}</span>
                    <span class="action-title">{{ action.title }}</span>
                  </div>
                  <div class="action-head-meta">
                    <span class="action-type">{{ action.type }}</span>
                    <span v-if="action.occurred_at">{{ formatOccurredAt(action.occurred_at) }}</span>
                  </div>
                </div>

                <p class="action-summary">{{ action.summary }}</p>

                <div v-if="action.fields.length > 0" class="action-fields">
                  <div v-for="field in action.fields" :key="`${action.order}-${field.label}`" class="action-field">
                    <span class="field-label">{{ field.label }}</span>
                    <span class="field-value">{{ field.value }}</span>
                  </div>
                </div>
              </article>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '@/services/axios'
import { formatLocalDateTime } from '@/services/datetime'
import { useUserStore } from '@/store'

import iconClose from '@/assets/svg/close.svg'

interface AdminGameActionField {
  label: string
  value: string
}

interface AdminGameActionItem {
  order: number
  type: string
  occurred_at?: string | null
  title: string
  summary: string
  fields: AdminGameActionField[]
}

interface AdminGameActionsResponse {
  id: number
  number: number
  items: AdminGameActionItem[]
}

const props = defineProps<{
  gameId: number
  gameNumber: number
}>()

const userStore = useUserStore()
const isAdmin = computed(() => userStore.user?.role === 'admin')

const open = ref(false)
const armed = ref(false)
const loading = ref(false)
const error = ref('')
const items = ref<AdminGameActionItem[]>([])
const loaded = ref(false)

const DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
}

function closeModal(): void {
  armed.value = false
  open.value = false
}

function normalizeItems(raw: unknown): AdminGameActionItem[] {
  if (!Array.isArray(raw)) return []
  const out: AdminGameActionItem[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const fieldsRaw = Array.isArray((item as any).fields) ? (item as any).fields : []
    const fields: AdminGameActionField[] = []
    for (const field of fieldsRaw) {
      if (!field || typeof field !== 'object') continue
      const label = String((field as any).label || '').trim()
      const value = String((field as any).value || '').trim()
      if (!label || !value) continue
      fields.push({ label, value })
    }
    out.push({
      order: Math.max(1, Number((item as any).order) || 0),
      type: String((item as any).type || '').trim() || 'unknown',
      occurred_at: (item as any).occurred_at ? String((item as any).occurred_at) : null,
      title: String((item as any).title || '').trim() || 'Событие',
      summary: String((item as any).summary || '').trim(),
      fields,
    })
  }
  return out.sort((a, b) => a.order - b.order)
}

async function loadActions(): Promise<void> {
  if (loading.value || loaded.value) return
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<AdminGameActionsResponse>(`/admin/games/${props.gameId}/actions`)
    items.value = normalizeItems(data?.items)
    loaded.value = true
  } catch (e: any) {
    const status = Number(e?.response?.status || 0)
    error.value = status === 404 ? 'Игра не найдена' : 'Не удалось загрузить игровые действия'
  } finally {
    loading.value = false
  }
}

function openModal(): void {
  if (!isAdmin.value) return
  armed.value = false
  open.value = true
  void loadActions()
}

function formatOccurredAt(value: string): string {
  return formatLocalDateTime(value, DATE_OPTIONS)
}
</script>

<style scoped lang="scss">
.actions-trigger {
  display: inline-flex;
  align-items: center;
  color: $orange;
  font-size: 12px;
  line-height: 1;
  text-decoration: underline;
  cursor: pointer;
  transition: opacity 0.25s ease-in-out;
}
.overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba($black, 0.25);
  backdrop-filter: blur(5px);
  z-index: 1100;
  .modal {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: min(980px, calc(100% - 30px));
    max-height: calc(100vh - 40px);
    padding: 10px;
    border-radius: 5px;
    background-color: $graphite;
    box-sizing: border-box;
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      span {
        color: $fg;
        font-size: 18px;
        font-family: Manrope-Medium;
      }
      .icon {
        width: 25px;
        height: 25px;
        border: none;
        background: none;
        cursor: pointer;
        img {
          width: 20px;
          height: 20px;
        }
      }
    }
    .modal-body {
      overflow: auto;
      .state {
        padding: 30px 10px;
        color: $ashy;
        text-align: center;
        &.state-error {
          color: $orange;
        }
      }
      .actions-list {
        display: flex;
        flex-direction: column;
        gap: 10px;
        .action-card {
          display: flex;
          flex-direction: column;
          gap: 10px;
          padding: 10px;
          border: 1px solid rgba($grey, 0.25);
          border-radius: 5px;
          background-color: rgba($lead, 0.75);
          .action-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 10px;
            .action-head-main {
              display: flex;
              align-items: center;
              flex-wrap: wrap;
              gap: 10px;
              .action-order {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 30px;
                height: 25px;
                padding: 0 5px;
                border-radius: 5px;
                background-color: $fg;
                color: $bg;
                font-size: 12px;
                font-family: Manrope-SemiBold;
              }
              .action-title {
                color: $fg;
                font-size: 16px;
                font-family: Manrope-SemiBold;
              }
            }
            .action-head-meta {
              display: flex;
              flex-direction: column;
              align-items: flex-end;
              gap: 5px;
              color: $ashy;
              font-size: 12px;
              text-align: right;
              .action-type {
                color: $orange;
                text-transform: lowercase;
              }
            }
          }
          .action-summary {
            margin: 0;
            color: $fg;
            font-size: 14px;
            line-height: 1.2;
          }
          .action-fields {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 5px 10px;
            .action-field {
              display: flex;
              flex-direction: column;
              gap: 5px;
              padding: 10px;
              border-radius: 5px;
              background-color: rgba($dark, 0.5);
              .field-label {
                color: $grey;
                font-size: 12px;
                line-height: 1.2;
              }
              .field-value {
                color: $fg;
                font-size: 14px;
                line-height: 1.2;
                word-break: break-word;
                white-space: pre-wrap;
              }
            }
          }
        }
      }
    }
  }
}

.overlay-enter-active,
.overlay-leave-active {
  transition: opacity 0.25s ease-in-out;
}

.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}

@media (max-width: 1280px) {
  .overlay {
    .modal {
      .modal-body {
        .actions-list {
          .action-card {
            .action-head {
              flex-direction: column;
              .action-head-meta {
                align-items: flex-start;
                text-align: left;
              }
            }
            .action-fields {
              grid-template-columns: 1fr;
            }
          }
        }
      }
    }
  }
}
</style>
