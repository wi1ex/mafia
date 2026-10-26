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
    const formatted = formatLocalDateTime(userStore.user?.subscription_until, SUBSCRIPTION_DATE_OPTIONS, 'ru-RU')
    return formatted === '—' ? '' : formatted
  })
  const subscriptionExpiryLabel = computed(() => (
    userStore.subscriptionActive && subscriptionUntilText.value
      ? `до ${subscriptionUntilText.value}`
      : '—'
  ))

  function subscriptionHint(explanation: string, inactiveText = 'Доступно только при активной подписке.'): string {
    const availabilityText = userStore.subscriptionActive
      ? subscriptionUntilText.value
        ? `Доступно Вам до ${subscriptionUntilText.value}.`
        : 'Доступно Вам при активной подписке.'
      : inactiveText
    return `${explanation} ${availabilityText}`
  }

  return { subscriptionExpiryLabel, subscriptionHint }
}
