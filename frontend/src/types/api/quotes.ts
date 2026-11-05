/** Contract §9 — Quotation Requests. */
import type { CurrencyCode, DecimalString, EntityId, ISODateTime } from './common'

export interface QuoteContact {
  full_name: string
  email: string
  /** E.164 */
  phone: string
  shipping_address: string
  city: string
  state: string
  postal_code: string
}

/** POST /quotes */
export interface CreateQuoteRequest {
  design_id: EntityId
  layout_version_id: EntityId
  contact: QuoteContact
  special_instructions?: string
}

export type QuoteStatus = 'pending_review' | (string & {})

export interface QuotePricingSummary {
  subtotal: DecimalString
  tax_gst: DecimalString
  estimated_shipping: DecimalString
  total_estimated: DecimalString
  currency: CurrencyCode
}

export interface Quote {
  id: EntityId
  quote_number: string
  status: QuoteStatus
  design_id: EntityId
  pricing_summary: QuotePricingSummary
  expires_at: ISODateTime
  created_at: ISODateTime
}

/** GET /quotes list item */
export interface QuoteSummary {
  id: EntityId
  quote_number: string
  design_id: EntityId
  design_title: string
  total_amount: DecimalString
  currency: CurrencyCode
  status: QuoteStatus
  created_at: ISODateTime
}
