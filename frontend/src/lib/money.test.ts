import { describe, expect, it } from 'vitest'
import { formatMoney } from './money'

describe('formatMoney', () => {
  it('formats decimal strings and numbers in INR with Indian grouping and 2 decimals', () => {
    expect(formatMoney('4526.02')).toBe('₹4,526.02')
    expect(formatMoney(150000)).toBe('₹1,50,000.00')
  })

  it('shows a dash for unparseable amounts instead of NaN', () => {
    expect(formatMoney('abc')).toBe('—')
  })
})
