/** Contract §7 — Pricing Engine. */
import type { CurrencyCode, DecimalString, EntityId, MattingInches } from './common'

/** Only `museum_uv` appears in the contract; full enum pending (Q9). */
export type GlassType = 'museum_uv' | (string & {})

/** Only `archival_white` appears in the contract; full enum pending (Q9). */
export type MatboardType = 'archival_white' | (string & {})

export interface PricingMatting extends MattingInches {
  enabled: boolean
  matboard_type: MatboardType
}

export interface PriceItemRequest {
  item_id: string
  frame_id: EntityId
  photo_width_inches: number
  photo_height_inches: number
  matting: PricingMatting
  glass_type: GlassType
  include_print: boolean
}

/** POST /pricing/calculate */
export interface PriceCalculationRequest {
  items: PriceItemRequest[]
  /** Indian PIN code (6 digits). Called `postal_code` in quotes (M4). */
  pincode: string
}

export interface PriceItemDimensions {
  opening_width_inches: number
  opening_height_inches: number
  glass_mat_width_inches: number
  glass_mat_height_inches: number
  frame_outer_width_inches: number
  frame_outer_height_inches: number
  perimeter_linear_inches: number
  area_square_inches: number
}

export interface PriceItemBreakdown {
  item_id: string
  dimensions: PriceItemDimensions
  molding_cost: DecimalString
  matting_cost: DecimalString
  glazing_cost: DecimalString
  printing_cost: DecimalString
  assembly_cost: DecimalString
  item_subtotal: DecimalString
}

export interface PriceSummary {
  total_molding: DecimalString
  subtotal: DecimalString
  discount_amount: DecimalString
  tax_gst_amount: DecimalString
  shipping_estimate: DecimalString
  final_total: DecimalString
}

export interface PriceCalculationResponse {
  currency: CurrencyCode
  items_breakdown: PriceItemBreakdown[]
  summary: PriceSummary
}
