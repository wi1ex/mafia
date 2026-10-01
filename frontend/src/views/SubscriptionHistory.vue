<template>
  <Teleport to="#desktop-teleport-root">
    <Transition name="overlay">
      <div v-if="open" class="overlay" @pointerdown.stop.self="armed = true"
           @pointerup.stop.self="armed && close()" @pointerleave.stop.self="armed = false" @pointercancel.stop.self="armed = false" @click.stop>
        <div class="modal" role="dialog" aria-modal="true" aria-label="История подписок" @pointerdown.stop @pointerup.stop @click.stop>
          <header>
            <div class="heading">
              <h2>История подписок — Донат</h2>
              <p>Изменения относятся только к истории выдач и не меняют действующий срок подписки.</p>
            </div>
            <UiButton variant="white" size="low" :icon="iconClose" width="40px" aria-label="Закрыть" :disabled="busy" @click="close" />
          </header>
          <div v-if="loading" class="state">Загрузка...</div>
          <div v-else-if="error" class="state danger">
            {{ error }}
            <UiButton size="low" text="Повторить" @click="load" />
          </div>
          <div v-else class="table-wrap">
            <table>
              <colgroup>
                <col class="user-column" />
                <col class="date-column" />
                <col class="reason-column" />
                <col class="duration-column" />
                <col class="actions-column" />
              </colgroup>
              <thead><tr><th>Пользователь</th><th>Дата выдачи</th><th>Причина</th><th>Длительность</th><th>Действия</th></tr></thead>
              <tbody>
                <tr v-for="row in items" :key="row.id" :class="{ 'is-editing': editingId === row.id }">
                  <td><span class="username" :title="row.username || `user${row.user_id}`">{{ row.username || `user${row.user_id}` }}</span><small>ID: {{ row.user_id }}</small></td>
                  <td>{{ formatLocalDateTime(row.issued_at) }}</td>
                  <td>{{ row.reason }}</td>
                  <td>
                    <div v-if="editingId === row.id" class="duration-fields">
                      <UiInput :id="`grant-${row.id}-months`" v-model.number="form.months" label="Месяцы" type="number" min="0" max="240" step="1" size="low" :disabled="busy" />
                      <UiInput :id="`grant-${row.id}-days`" v-model.number="form.days" label="Дни" type="number" min="0" max="36500" step="1" size="low" :disabled="busy" />
                    </div>
                    <span v-else>{{ duration(row) }}</span>
                  </td>
                  <td>
                    <div class="actions">
                      <template v-if="editingId === row.id">
                        <UiButton size="low" :text="busy ? 'Сохранение…' : 'Сохранить'" :disabled="busy || !canSave" @click="save(row)" />
                        <UiButton variant="white" size="low" text="Отмена" :disabled="busy" @click="editingId = null" />
                      </template>
                      <UiButton v-else size="low" text="Изменить" :disabled="busy" @click="edit(row)" />
                      <UiButton variant="red" size="low" text="Удалить" :disabled="busy" @click="remove(row)" />
                    </div>
                  </td>
                </tr>
                <tr v-if="items.length === 0"><td colspan="5" class="empty-state">Выдач с причиной «Донат» пока нет</td></tr>
              </tbody>
            </table>
          </div>
          <footer v-if="total > 50">
            <UiButton variant="white" size="low" text="Назад" :disabled="busy || loading || page <= 1" @click="changePage(-1)" />
            <span>Страница {{ page }} из {{ Math.ceil(total / 50) }} · Выдач: {{ total }}</span>
            <UiButton variant="white" size="low" text="Вперёд" :disabled="busy || loading || page * 50 >= total" @click="changePage(1)" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { formatLocalDateTime } from '@/services/datetime'
import UiButton from '@/components/UiButton.vue'
import UiInput from '@/components/UiInput.vue'
import iconClose from '@/assets/svg/iconClose.svg'

type GrantRow = { id: number; user_id: number; username?: string | null; issued_at: string; reason: string; months: number; days: number }
const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [boolean] }>()
const armed = ref(false)
const items = ref<GrantRow[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const busy = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ months: 0, days: 0 })
let requestSeq = 0
const canSave = computed(() => Number.isInteger(form.months) && Number.isInteger(form.days)
  && form.months >= 0 && form.months <= 240 && form.days >= 0 && form.days <= 36500
  && (form.months > 0 || form.days > 0))

function close(): void {
  if (!busy.value) emit('update:open', false)
}

function duration(row: GrantRow): string {
  return [row.months ? `${row.months} мес.` : '', row.days ? `${row.days} сут.` : ''].filter(Boolean).join(' ') || '-'
}

async function load(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  error.value = ''
  editingId.value = null
  try {
    const { data } = await api.get<{ total: number; items: GrantRow[] }>('/admin/subscriptions/grants', { params: { page: page.value } })
    if (seq !== requestSeq) return
    items.value = data.items
    total.value = data.total
  } catch {
    if (seq === requestSeq) error.value = 'Не удалось загрузить историю подписок'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function changePage(delta: number): void {
  page.value += delta
  void load()
}

function edit(row: GrantRow): void {
  editingId.value = row.id
  form.months = row.months
  form.days = row.days
}

async function save(row: GrantRow): Promise<void> {
  if (busy.value || !canSave.value) return
  busy.value = true
  try {
    await api.patch(`/admin/subscriptions/grants/${row.id}`, { months: form.months, days: form.days })
    await load()
  } catch {
    void alertDialog('Не удалось изменить запись истории')
  } finally {
    busy.value = false
  }
}

async function remove(row: GrantRow): Promise<void> {
  if (busy.value) return
  const confirmed = await confirmDialog({ title: 'Удалить запись истории', text: `Удалить выдачу подписки пользователю ${row.username || `user${row.user_id}`} от ${formatLocalDateTime(row.issued_at)}? Действующая подписка сохранится.`, confirmText: 'Удалить', cancelText: 'Отмена' })
  if (!confirmed || busy.value || !props.open) return
  busy.value = true
  try {
    await api.delete(`/admin/subscriptions/grants/${row.id}`)
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    await load()
  } catch {
    void alertDialog('Не удалось удалить запись истории')
  } finally {
    busy.value = false
  }
}

watch(() => props.open, open => {
  if (open) {
    page.value = 1
    void load()
  } else {
    requestSeq += 1
    loading.value = false
    editingId.value = null
  }
}, { immediate: true })
onBeforeUnmount(() => { requestSeq += 1 })
</script>

<style scoped lang="scss">
.overlay {
  display: flex;
  position: fixed;
  inset: 0;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 40px;
  background-color: rgba($neutral-black, 0.6);
  backdrop-filter: blur(12px);
  z-index: 1000;
  .modal {
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    width: 1360px;
    max-width: 100%;
    max-height: 100%;
    min-height: 0;
    padding: 24px;
    gap: 24px;
    border-radius: 24px;
    background-color: $soft-purple-900;
    color: $neutral-100;
    font-family: Hauora-Regular;
    line-height: 1.4;
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      flex-shrink: 0;
      gap: 24px;
      .heading {
        display: flex;
        flex-direction: column;
        min-width: 0;
        gap: 10px;
        h2 {
          margin: 0;
          color: $neutral-white;
          font-family: Involve-Medium;
          font-weight: 500;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
        p {
          margin: 0;
          color: $neutral-300;
          font-size: 14px;
          line-height: 20px;
        }
      }
    }
    .state {
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      padding: 24px;
      gap: 16px;
      border-radius: 20px;
      background-color: $soft-purple-800;
      color: $neutral-300;
      text-align: center;
      &.danger {
        color: $red-300;
      }
    }
    .table-wrap {
      min-height: 0;
      border-radius: 20px;
      background-color: $soft-purple-800;
      overflow: auto;
      overscroll-behavior: contain;
      scrollbar-width: thin;
      scrollbar-color: $soft-purple-700 transparent;
      table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        table-layout: fixed;
        colgroup {
          .user-column {
            width: 21%;
          }
          .date-column {
            width: 17%;
          }
          .reason-column {
            width: 8%;
          }
          .duration-column {
            width: 23%;
          }
          .actions-column {
            width: 31%;
          }
        }
        thead {
          position: sticky;
          top: 0;
          z-index: 1;
          tr {
            th {
              padding: 16px;
              border-bottom: 1px solid $soft-purple-700;
              background-color: $soft-purple-800;
              color: $neutral-300;
              font-family: Hauora-Medium;
              font-weight: 500;
              font-size: 14px;
              line-height: 20px;
              text-align: left;
            }
          }
        }
        tbody {
          tr {
            transition: background-color 0.25s ease-in-out;
            &.is-editing {
              background-color: rgba($green-500, 0.06);
            }
            &:last-child td {
              border-bottom: none;
            }
            td {
              padding: 16px;
              border-bottom: 1px solid $soft-purple-700;
              vertical-align: middle;
              font-size: 16px;
              line-height: 22px;
              overflow-wrap: anywhere;
              .username {
                display: block;
                overflow: hidden;
                color: $neutral-white;
                font-family: Hauora-Medium;
                text-overflow: ellipsis;
                white-space: nowrap;
              }
              small {
                display: block;
                margin-top: 4px;
                color: $neutral-300;
                font-size: 12px;
                line-height: 16px;
              }
              .duration-fields {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                min-width: 0;
                gap: 12px;
                --ui-input-label-bg: #{$soft-purple-800};
                :deep(input) {
                  box-sizing: content-box;
                }
              }
              .actions {
                display: flex;
                align-items: center;
                gap: 8px;
              }
              &.empty-state {
                padding: 32px 24px;
                color: $neutral-300;
                text-align: center;
              }
            }
          }
        }
      }
    }
    footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      gap: 16px;
      span {
        color: $neutral-300;
        font-size: 14px;
        line-height: 20px;
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
</style>
