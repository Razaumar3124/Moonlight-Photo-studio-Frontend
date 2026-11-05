import { describe, expect, it } from 'vitest'
import { convertLength, fromInches, roundTo, toInches } from './units'

describe('units', () => {
  it('converts the planner units to inches and back', () => {
    expect(toInches(12, 'ft')).toBe(144)
    expect(roundTo(toInches(100, 'cm'))).toBe(39.37)
    expect(roundTo(toInches(1, 'm'))).toBe(39.37)
    expect(fromInches(144, 'ft')).toBe(12)
    expect(roundTo(convertLength(3, 'in', 'cm'))).toBe(7.62)
    expect(convertLength(5, 'm', 'm')).toBe(5)
  })

  it('rounds away float noise', () => {
    expect(roundTo(0.1 + 0.2)).toBe(0.3)
    expect(roundTo(1.005, 2)).toBe(1.01)
  })
})
