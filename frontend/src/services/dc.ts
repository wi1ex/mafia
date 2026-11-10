export type DcCurrency = 'RUB' | 'USD' | 'EUR'
export type WalletTab = 'coins' | 'subscription' | 'gifts'
export type CoinPackageQuantity = 25 | 50 | 100 | 250
export type CoinPackageCatalog = Record<CoinPackageQuantity, Record<DcCurrency, string>>
export type SubscriptionPlan = 'week' | 'month' | 'quarter' | 'year'

export const DC_CURRENCIES: readonly DcCurrency[] = ['RUB', 'USD', 'EUR']
export const COIN_PACKAGES: readonly { quantity: CoinPackageQuantity; discount: number }[] = [
  { quantity: 25, discount: 0 },
  { quantity: 50, discount: 15 },
  { quantity: 100, discount: 20 },
  { quantity: 250, discount: 25 },
]
export const DEFAULT_COIN_PACKAGES: CoinPackageCatalog = {
  25: { RUB: '475.00', USD: '6.20', EUR: '5.50' },
  50: { RUB: '800.00', USD: '10.60', EUR: '9.40' },
  100: { RUB: '1500.00', USD: '20.00', EUR: '17.60' },
  250: { RUB: '3500.00', USD: '46.60', EUR: '41.20' },
}
export const SUBSCRIPTION_PLANS: readonly { id: SubscriptionPlan; label: string; cost: number; discount: number; months: number; days: number }[] = [
  { id: 'week', label: '1 неделя', cost: 7, discount: 0, months: 0, days: 7 },
  { id: 'month', label: '1 месяц', cost: 25, discount: 15, months: 1, days: 0 },
  { id: 'quarter', label: '3 месяца', cost: 70, discount: 20, months: 3, days: 0 },
  { id: 'year', label: '1 год', cost: 270, discount: 25, months: 12, days: 0 },
]
const MAX_PRICE_MINOR = 999_999_999_999_999_999n

/** Decimal strings stay in minor units until formatting. */
function moneyToMinor(value: unknown): bigint | null {
  const text = String(value ?? '').trim().replace(',', '.')
  if (!/^\d+(?:\.\d{1,2})?$/.test(text)) return null
  const [whole = '0', fraction = ''] = text.split('.')
  const minor = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))
  return minor > 0n ? minor : null
}

export function priceToMinor(value: unknown): bigint | null {
  const minor = moneyToMinor(value)
  return minor !== null && minor <= MAX_PRICE_MINOR ? minor : null
}

export function normalizeDcPrice(value: unknown, fallback: string): string {
  const minor = priceToMinor(value) ?? priceToMinor(fallback)!
  return `${minor / 100n}.${String(minor % 100n).padStart(2, '0')}`
}

export function normalizeCoinPackages(value: unknown): CoinPackageCatalog {
  return (typeof value === 'string' ? parseCoinPackagePrices(value) : null)
    ?? parseCoinPackagePrices(serializeCoinPackagePrices(DEFAULT_COIN_PACKAGES))!
}

export function parseCoinPackagePrices(value: string): CoinPackageCatalog | null {
  const prices = value.split('-')
  if (prices.length !== COIN_PACKAGES.length * DC_CURRENCIES.length) return null
  const catalog = {} as CoinPackageCatalog
  let index = 0
  for (const { quantity } of COIN_PACKAGES) {
    catalog[quantity] = {} as Record<DcCurrency, string>
    for (const currency of DC_CURRENCIES) {
      const minor = priceToMinor(prices[index++])
      if (minor === null) return null
      catalog[quantity][currency] = `${minor / 100n}.${String(minor % 100n).padStart(2, '0')}`
    }
  }
  return catalog
}

export function serializeCoinPackagePrices(catalog: CoinPackageCatalog): string {
  return COIN_PACKAGES.flatMap(({ quantity }) => DC_CURRENCIES.map(currency => catalog[quantity][currency].replace(/\.00$/, ''))).join('-')
}

export function isCoinPackage(value: unknown): value is CoinPackageQuantity {
  return COIN_PACKAGES.some(item => item.quantity === value)
}

export function dcMoney(unitPrice: string, quantity: number, currency: DcCurrency): string {
  const minor = moneyToMinor(unitPrice)
  if (minor === null || !Number.isSafeInteger(quantity) || quantity < 0) return '—'
  const total = minor * BigInt(quantity)
  const whole = new Intl.NumberFormat('ru-RU').format(total / 100n)
  const symbol = { RUB: '₽', USD: '$', EUR: '€' }[currency]
  return `${whole},${String(total % 100n).padStart(2, '0')} ${symbol}`
}

export function positiveDc(value: unknown): number | null {
  const text = String(value ?? '').trim()
  if (!/^\d+$/.test(text)) return null
  const number = Number(text)
  return Number.isSafeInteger(number) && number > 0 ? number : null
}

export function dcPurchaseRestriction(isAuthed: boolean, profile: {
  ban_active?: boolean
  telegram_verified?: boolean
  rules_acceptance_required?: boolean
} | null | undefined, verificationRestrictions: boolean): string {
  if (!isAuthed) return 'Для покупок войдите в аккаунт.'
  if (!profile) return 'Загрузка профиля…'
  if (profile.ban_active) return 'Покупки недоступны: аккаунт забанен.'
  if (verificationRestrictions && !profile.telegram_verified) return 'Для покупок подтвердите аккаунт через Telegram.'
  if (profile.rules_acceptance_required) return 'Для покупок примите актуальные правила сайта.'
  return ''
}

const moscowParts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Moscow', year: 'numeric', month: '2-digit', day: '2-digit' })

export function subscriptionPreview(now: number, until: string | null | undefined, planId: SubscriptionPlan): string | null {
  const plan = SUBSCRIPTION_PLANS.find(item => item.id === planId)
  if (!plan || !Number.isFinite(now)) return null
  const currentEnd = Date.parse(until || '')
  let base: number
  if (Number.isFinite(currentEnd) && currentEnd > now) base = currentEnd
  else {
    const parts = moscowParts.formatToParts(new Date(now))
    const get = (type: string) => Number(parts.find(part => part.type === type)?.value)
    base = Date.UTC(get('year'), get('month') - 1, get('day'), -1)
    if (base < now) base += 86_400_000
  }
  const local = new Date(base + 3 * 3_600_000)
  const targetMonth = local.getUTCMonth() + plan.months
  const lastDay = new Date(Date.UTC(local.getUTCFullYear(), targetMonth + 1, 0)).getUTCDate()
  const result = new Date(Date.UTC(
    local.getUTCFullYear(), targetMonth, Math.min(local.getUTCDate(), lastDay) + plan.days,
    local.getUTCHours() - 3, local.getUTCMinutes(), local.getUTCSeconds(), local.getUTCMilliseconds(),
  ))
  return Number.isFinite(result.getTime()) ? result.toISOString() : null
}

export function formatMoscowDate(value: string | null | undefined): string {
  const date = new Date(value || '')
  if (!Number.isFinite(date.getTime())) return '—'
  const formatted = new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Europe/Moscow', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).format(date).replace(', ', ' в ')
  return `${formatted} МСК`
}

export function newDcRequestId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6]! & 15) | 64
  bytes[8] = (bytes[8]! & 63) | 128
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
