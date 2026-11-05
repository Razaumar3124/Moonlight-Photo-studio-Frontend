/**
 * Shared primitives for the Moonlight API contract (docs/API_CONTRACT.md §1).
 * Field names stay snake_case to match the wire format 1:1 — no mapping layer to drift.
 */

/**
 * Entity ID. The contract shows integers (`"id": 1`), but the backend is MongoDB and the error
 * example uses an ObjectId string. Kept as a single alias so the switch is a one-line change.
 * Open question Q1 in docs/API_ALIGNMENT.md.
 */
export type EntityId = number

/** ISO-8601 UTC timestamp, e.g. `2026-11-01T22:45:00.000Z`. */
export type ISODateTime = string

/**
 * Money as a fixed-precision decimal string (`"1499.50"`). The contract also allows 2-dp floats;
 * we type the string form and parse defensively (see lib/money.ts). Open question Q7.
 */
export type DecimalString = string

/** ISO-4217 currency code. Only INR appears in the contract. */
export type CurrencyCode = 'INR' | (string & {})

/** Hex colour, e.g. `#F4F1EA`. */
export type HexColor = string

/** Every list endpoint returns this envelope. No pagination params are defined yet (Q12). */
export interface ListResponse<T> {
  items: T[]
  total: number
}

/* --------------------------------- Errors ---------------------------------- */

/** Codes that appear in the contract. Others are allowed but unknown to the UI. */
export type KnownApiErrorCode = 'RESOURCE_NOT_FOUND' | 'GEOMETRY_COLLISION_DETECTED'

export type ApiErrorCode = KnownApiErrorCode | (string & {})

export interface ApiErrorDetail {
  /** Request field the problem relates to, e.g. `design_id`, `frames`, `email`. */
  field: string
  issue: string
}

/** Standard error envelope (contract §1). */
export interface ApiErrorEnvelope {
  error: {
    code: ApiErrorCode
    message: string
    details?: ApiErrorDetail[]
    timestamp: ISODateTime
  }
}

/* -------------------------------- Geometry --------------------------------- */
/* All geometry is in inches, top-left origin (contract §1). */

export interface BoundingBox {
  min_x: number
  min_y: number
  max_x: number
  max_y: number
  width_inches: number
  height_inches: number
}

/** Mat border per side, in inches. Extended per endpoint (pricing, designs). */
export interface MattingInches {
  top_inches: number
  bottom_inches: number
  left_inches: number
  right_inches: number
}

export type PhotoOrientation = 'portrait' | 'landscape'
