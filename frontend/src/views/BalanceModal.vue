<template>
  <Teleport to="#desktop-teleport-root">
    <Transition name="balance-overlay">
      <div v-if="open && snapshot && isAdmin" class="balance-overlay" :style="{ zIndex }" @pointerdown.stop.self="armed = true" @pointerup.stop.self="armed && close()" @pointerleave.stop.self="armed = false" @click.stop>
        <section ref="panel" class="balance-modal" role="dialog" aria-modal="true" aria-labelledby="balance-modal-title" @keydown.esc.stop="close">
          <header><h2 id="balance-modal-title">{{ snapshot.action === 'credit' ? 'Выдать монеты' : 'Снять монеты' }}</h2><UiButton variant="white" size="low" :icon="iconClose" width="40px" aria-label="Закрыть" :disabled="saving" @click="close" /></header>
          <div class="balance-target"><img v-minio-img="{ key: snapshot.avatar_name ? `avatars/${snapshot.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" /><span>{{ snapshot.username || `user${snapshot.user_id}` }}</span></div>
          <p v-if="loading" role="status">Загрузка баланса…</p>
          <form v-else @submit.prevent="save">
            <strong>Баланс: {{ formatBalance(balance) }} DC</strong>
            <UiInput id="balance-modal-quantity" v-model="quantity" type="number" min="1" :max="snapshot.action === 'debit' ? balance : undefined" step="1" inputmode="numeric" label="Количество, DC" size="low" :disabled="saving || !!pending" />
            <p v-if="preview !== null">{{ snapshot.action === 'credit' ? 'После выдачи' : 'После снятия' }}: {{ formatBalance(preview) }} DC</p>
            <p v-if="snapshot.action === 'debit' && balance === 0" class="balance-error">На балансе нет монет для снятия.</p>
            <p v-if="error" class="balance-error" role="alert">{{ error }}</p>
            <p v-if="pending && !saving" class="balance-error">Результат операции пока не получен. Проверьте тот же запрос.</p>
            <div class="balance-actions"><UiButton variant="white" size="middle" text="Отмена" :disabled="saving" @click="close" /><UiButton type="submit" size="middle" :text="saving ? 'Сохранение…' : pending ? 'Проверить результат' : snapshot.action === 'credit' ? 'Выдать' : 'Снять'" :disabled="saving || (!pending && !valid)" /></div>
          </form>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { api } from '@/services/axios'
import { useUserStore } from '@/store'
import { newDcRequestId, positiveDc } from '@/services/dc'
import { dcErrorMessage, dcRequestUncertain } from '@/store/modules/wallet'
import UiInput from '@/components/UiInput.vue'
import UiButton from '@/components/UiButton.vue'
import defaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconClose from '@/assets/svg/iconClose.svg'

type BalanceAction = 'credit' | 'debit'
type Target = { user_id: number; username?: string | null; avatar_name?: string | null }
type Request = { action: BalanceAction; quantity: number; request_id: string }
const props = withDefaults(defineProps<{ open: boolean; action: BalanceAction; target: Target | null; currentBalance?: number | null; zIndex?: number }>(), { zIndex: 1700, currentBalance: null })
const emit = defineEmits<{ 'update:open': [boolean]; busy: [boolean]; complete: [result: { userId: number; action: BalanceAction; dc_balance: number }] }>()
const user = useUserStore()
const isAdmin = computed(() => user.user?.role === 'admin')
const snapshot = ref<(Target & { action: BalanceAction; actorId: number }) | null>(null)
const panel = ref<HTMLElement | null>(null)
const balance = ref(0)
const quantity = ref<string | number>('')
const pending = ref<Request | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const armed = ref(false)
let sequence = 0
const numericQuantity = computed(() => positiveDc(quantity.value))
const preview = computed(() => {
  if (!numericQuantity.value || !snapshot.value) return null
  const next = balance.value + (snapshot.value.action === 'credit' ? numericQuantity.value : -numericQuantity.value)
  return Number.isSafeInteger(next) && next >= 0 ? next : null
})
const valid = computed(() => numericQuantity.value !== null && preview.value !== null && !loading.value && !error.value.startsWith('Не удалось загрузить'))
const formatBalance = (value: number) => new Intl.NumberFormat('ru-RU').format(value)
function key(target = snapshot.value): string { return `dc:admin:${target?.actorId}:${target?.user_id}:${target?.action}` }
function persist(): void {
  try { if (pending.value) sessionStorage.setItem(key(), JSON.stringify(pending.value)); else sessionStorage.removeItem(key()) } catch {}
}
function close(): void { if (!saving.value) emit('update:open', false) }
async function refreshBalance(target: Target, seq: number): Promise<void> {
  const { data } = await api.get<{ dc_balance?: number | null }>(`/users/${target.user_id}/mini_profile`, { params: { allow_deleted: 1 } })
  if (seq !== sequence) return
  if (data.dc_balance === null || !Number.isSafeInteger(data.dc_balance) || Number(data.dc_balance) < 0) throw new Error('balance_unavailable')
  balance.value = data.dc_balance!
}
async function save(): Promise<void> {
  const target = snapshot.value
  if (!target || !isAdmin.value || user.user?.id !== target.actorId || saving.value || (!pending.value && !valid.value)) return
  pending.value ||= { action: target.action, quantity: numericQuantity.value!, request_id: newDcRequestId() }
  persist()
  saving.value = true; error.value = ''
  emit('busy', true)
  const request = { ...pending.value }
  const seq = sequence
  const previousBalance = balance.value
  try {
    const { data } = await api.post<{ dc_balance: number }>(`/admin/users/${target.user_id}/coins`, request)
    pending.value = null; persist()
    if (seq !== sequence || user.user?.id !== target.actorId) return
    if (balance.value === previousBalance) balance.value = data.dc_balance
    await refreshBalance(target, seq).catch(() => {})
    if (seq !== sequence || user.user?.id !== target.actorId) return
    if (target.user_id === user.user?.id) user.setWalletState({ dc_balance: balance.value })
    window.dispatchEvent(new CustomEvent('dc-wallet-changed', { detail: { user_id: target.user_id } }))
    emit('complete', { userId: target.user_id, action: target.action, dc_balance: balance.value })
    emit('update:open', false)
  } catch (err) {
    if (seq !== sequence) return
    const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
    error.value = detail === 'insufficient_dc_balance' ? 'На балансе недостаточно монет для снятия.' : dcErrorMessage(err)
    if (!dcRequestUncertain(err)) {
      pending.value = null; persist()
      await refreshBalance(target, sequence).catch(() => {})
    }
  } finally { saving.value = false; emit('busy', false) }
}
watch(() => props.open, async open => {
  const seq = ++sequence
  if (!open || !props.target || !isAdmin.value) return
  snapshot.value = { ...props.target, action: props.action, actorId: user.user!.id }
  quantity.value = ''; pending.value = null; error.value = ''; armed.value = false; loading.value = true
  try {
    const saved = JSON.parse(sessionStorage.getItem(key()) || 'null') as Request | null
    if (saved && saved.action === props.action && positiveDc(saved.quantity) && /^[a-f0-9-]{36}$/i.test(saved.request_id)) { pending.value = saved; quantity.value = saved.quantity }
  } catch {}
  try { await refreshBalance(snapshot.value, seq) }
  catch { if (seq === sequence) error.value = 'Не удалось загрузить баланс. Закройте окно и повторите попытку.' }
  finally { if (seq === sequence) { loading.value = false; await nextTick(); panel.value?.querySelector<HTMLInputElement>('input')?.focus() } }
})
watch(() => props.currentBalance, value => { if (props.open && Number.isSafeInteger(value) && Number(value) >= 0) balance.value = value! })
watch(isAdmin, allowed => { if (!allowed) emit('update:open', false) })
watch(() => user.user?.id, (next, previous) => { if (next !== previous) emit('update:open', false) })
onBeforeUnmount(() => { sequence++ })
</script>

<style scoped lang="scss">
.balance-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 24px;
  background: rgba($neutral-black, .6);
  backdrop-filter: blur(12px);
  .balance-modal {
    display: flex;
    flex-direction: column;
    gap: 24px;
    box-sizing: border-box;
    width: 560px;
    max-width: 100%;
    max-height: 100%;
    overflow-y: auto;
    padding: 24px;
    border-radius: 24px;
    background: $soft-purple-900;
    color: $neutral-100;
    font-family: Hauora-Regular;
    line-height: 1.4;
    --ui-input-label-bg: #{$soft-purple-900};
    header {
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-start;
      h2 {
        margin: 0;
        font-family: Involve-Medium;
        font-size: 24px;
        line-height: 26px;
      }
    }
    .balance-target {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 20px;
      border-radius: 20px;
      background: $soft-purple-800;
      img {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        object-fit: cover;
      }
      span {
        overflow-wrap: anywhere;
        min-width: 0;
      }
    }
    p {
      margin: 0;
    }
    form {
      display: flex;
      flex-direction: column;
      gap: 20px;
      .balance-error {
        color: $orange-500;
        font-size: 14px;
      }
      .balance-actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 12px;
      }
    }
  }
}
.balance-overlay-enter-active,
.balance-overlay-leave-active {
  transition: opacity .2s ease;
}
.balance-overlay-enter-from,
.balance-overlay-leave-to {
  opacity: 0;
}
</style>
