/**
 * Shared primitives for the Moonlight API (docs/API_CONTRACT.md §1).
 * Field names stay snake_case to match the wire format 1:1 — no mapping layer to drift.
 */

/** Entity ID: a MongoDB ObjectId as a 24-character hex string (Q1, resolved 2026-11-12). */
export type EntityId = string

/** ISO-8601 UTC timestamp, e.g. `2026-11-01T22:45:00.000Z`. */
export type ISODateTime = string

/**
 * Money as a fixed-precision decimal string (`"1499.50"`). The API currently returns money only
 * in catalog prices (`price_per_linear_inch`); quotes are priced by the studio on WhatsApp.
 */
export type DecimalString = string

/** ISO-4217 currency code. */
export type CurrencyCode = 'INR' | (string & {})

/** Hex colour, e.g. `#F4F1EA`. */
export type HexColor = string

/** Catalog list envelope (`/frame-materials`, `/frames`, `/templates`). */
export interface ListResponse<T> {
  items: T[]
  total: number
}

/** Paginated envelope (`GET /designs`). `GET /photos` has the same fields minus `total_pages`. */
export interface PageResponse<T> extends ListResponse<T> {
  page: number
  page_size: number
  total_pages: number
}

/* --------------------------------- Errors ---------------------------------- */

/** Codes the backend returns (API_CONTRACT.md §1.4). Others are allowed but unknown to the UI. */
export type KnownApiErrorCode =
  | 'VALIDATION_ERROR' // 422 — see details[]
  | 'BAD_REQUEST' // 400
  | 'UNAUTHORIZED' // 401 — missing bearer token
  | 'INVALID_CREDENTIALS' // 401 — same for unknown account and wrong password
  | 'INVALID_TOKEN' // 401
  | 'TOKEN_EXPIRED' // 401
  | 'TOKEN_REVOKED' // 401 — logged out or password reset
  | 'INVALID_GOOGLE_TOKEN' // 401
  | 'FORBIDDEN' // 403 — not your resource
  | 'ACCOUNT_DISABLED' // 403
  | 'CSRF_VALIDATION_FAILED' // 403
  | 'RESOURCE_NOT_FOUND' // 404
  | 'ACCOUNT_ALREADY_EXISTS' // 409 — details[].field is `email` or `phone`
  | 'PAYLOAD_TOO_LARGE' // 413
  | 'RATE_LIMIT_EXCEEDED' // 429 + Retry-After
  | 'INTERNAL_SERVER_ERROR' // 500
  | 'DATABASE_UNAVAILABLE' // 503
  | 'STORAGE_UNAVAILABLE' // 503
  | 'GOOGLE_AUTH_NOT_CONFIGURED' // 503

export type ApiErrorCode = KnownApiErrorCode | (string & {})

export interface ApiErrorDetail {
  /** Request field the problem relates to, e.g. `email`, `items.f1.total_width_inches`. */
  field: string
  issue: string
}

/** Standard error envelope (contract §1.4). */
export interface ApiErrorEnvelope {
  error: {
    code: ApiErrorCode
    message: string
    details?: ApiErrorDetail[]
    timestamp: ISODateTime
  }
}

/* -------------------------------- Geometry --------------------------------- */
/* All geometry is in inches, top-left origin of the wall (contract §1.3). */

export interface BoundingBox {
  x: number
  y: number
  width: number
  height: number
}

/** Mount border per side, in inches (0–6). */
export interface MattingInches {
  top_inches: number
  bottom_inches: number
  left_inches: number
  right_inches: number
}

export type PhotoOrientation = 'portrait' | 'landscape'
