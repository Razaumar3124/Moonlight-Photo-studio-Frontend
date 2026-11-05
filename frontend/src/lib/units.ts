/**
 * The API speaks inches only (contract §1). The planner lets users pick ft / in / cm / m.
 * Convert at the boundary: UI state keeps the user's unit, payloads are always inches.
 */

export type LengthUnit = 'ft' | 'in' | 'cm' | 'm'

const INCHES_PER_UNIT: Record<LengthUnit, number> = {
  in: 1,
  ft: 12,
  cm: 1 / 2.54,
  m: 100 / 2.54,
}

export function toInches(value: number, unit: LengthUnit): number {
  return value * INCHES_PER_UNIT[unit]
}

export function fromInches(inches: number, unit: LengthUnit): number {
  return inches / INCHES_PER_UNIT[unit]
}

export function convertLength(value: number, from: LengthUnit, to: LengthUnit): number {
  return from === to ? value : fromInches(toInches(value, from), to)
}

const UNIT_SUFFIX: Record<LengthUnit, string> = { ft: ' ft', in: ' in', cm: ' cm', m: ' m' }
const UNIT_PRECISION: Record<LengthUnit, number> = { ft: 1, in: 0, cm: 0, m: 2 }

/** Display a length given in inches in the chosen unit: 144 → "12 ft", "366 cm", "3.66 m". */
export function formatLength(inches: number, unit: LengthUnit, precision = UNIT_PRECISION[unit]): string {
  return `${roundTo(fromInches(inches, unit), precision)}${UNIT_SUFFIX[unit]}`
}

/** Round for display/inputs without float noise: 3.0000000004 → 3. */
export function roundTo(value: number, decimals = 2): number {
  const f = 10 ** decimals
  return Math.round((value + Number.EPSILON) * f) / f
}
