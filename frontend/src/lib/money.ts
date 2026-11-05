import type { CurrencyCode, DecimalString } from '@/types/api'

/**
 * Money arrives as decimal strings ("4526.02") — or possibly 2-dp floats (contract §1 allows both).
 * Do arithmetic on the server; on the client only format for display.
 */

const formatters = new Map<string, Intl.NumberFormat>()

function getFormatter(currency: string) {
  let fmt = formatters.get(currency)
  if (!fmt) {
    fmt = new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 })
    formatters.set(currency, fmt)
  }
  return fmt
}

/** formatMoney("4526.02", "INR") → "₹4,526.02" */
export function formatMoney(amount: DecimalString | number, currency: CurrencyCode = 'INR'): string {
  const value = typeof amount === 'number' ? amount : Number.parseFloat(amount)
  if (!Number.isFinite(value)) return '—'
  return getFormatter(currency).format(value)
}
