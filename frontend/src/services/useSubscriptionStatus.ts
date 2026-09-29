import { computed } from 'vue'
import { formatLocalDateTime } from '@/services/datetime'
import { useUserStore } from '@/store'

const SUBSCRIPTION_DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
}

export function useSubscriptionStatus() {
  const userStore = useUserStore()
  const subscriptionUntilText = computed(() => {
    const formatted = formatLocalDateTime(userStore.user?.subscription_until, SUBSCRIPTION_DATE_OPTIONS)
    return formatted === '-' ? '' : formatted
  })
  const subscriptionStatusText = computed(() => {
    if (!userStore.subscriptionActive) return 'Подписка не активна'
    return subscriptionUntilText.value
      ? `Подписка активна до ${subscriptionUntilText.value}`
      : 'Подписка активна'
  })

  function subscriptionHint(inactiveText: string): string {
    if (!userStore.subscriptionActive) return inactiveText
    return subscriptionUntilText.value
      ? `Доступно Вам до ${subscriptionUntilText.value}`
      : 'Доступно Вам'
  }

  return { subscriptionStatusText, subscriptionHint }
}
