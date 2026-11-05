/** Contract §8 — Designs & Versions Management. */
import type {
  BoundingBox,
  CurrencyCode,
  DecimalString,
  EntityId,
  HexColor,
  ISODateTime,
  MattingInches,
} from './common'
import type { GlassType } from './pricing'
import type { TemplateCategory } from './templates'

export type WallTexture = 'plaster_smooth' | (string & {})

export interface DesignWall {
  width_inches: number
  height_inches: number
  /** Paint Shade swatch. */
  color_hex: HexColor
  texture: WallTexture
}

export type DesignStatus = 'draft' | 'saved' | (string & {})

/** `custom` = hand-arranged; otherwise the template category it came from. */
export type LayoutType = 'custom' | TemplateCategory

/* ------------------------------ §8.1 Create -------------------------------- */

/** POST /designs */
export interface CreateDesignRequest {
  title: string
  description?: string
  wall: DesignWall
}

export interface Design {
  id: EntityId
  user_id: EntityId
  title: string
  description: string | null
  wall: DesignWall
  current_version_id: EntityId | null
  status: DesignStatus
  created_at: ISODateTime
  updated_at: ISODateTime
}

/* --------------------------- §8.2 Save version ----------------------------- */

export interface DesignMatting extends MattingInches {
  /** Mount Colour swatch. */
  color_hex: HexColor
}

export interface DesignItemInput {
  item_id: string
  frame_id: EntityId
  photo_id: EntityId | null
  position_x_inches: number
  position_y_inches: number
  photo_width_inches: number
  photo_height_inches: number
  matting: DesignMatting
  glass_type: GlassType
}

/** POST /designs/{id}/versions */
export interface SaveDesignVersionRequest {
  layout_type: LayoutType
  template_id: EntityId | null
  items: DesignItemInput[]
}

export interface EstimatedPrice {
  subtotal: DecimalString
  tax: DecimalString
  total: DecimalString
  currency: CurrencyCode
}

export interface DesignVersionSummary {
  version_id: EntityId
  design_id: EntityId
  version_number: number
  items_count: number
  bounding_box: BoundingBox
  estimated_price: EstimatedPrice
  created_at: ISODateTime
}

/* ----------------------------- §8.3 Get detail ----------------------------- */

export interface DesignItem extends DesignItemInput {
  total_width_inches: number
  total_height_inches: number
  calculated_price: DecimalString
}

export interface DesignVersion {
  id: EntityId
  version_number: number
  layout_type: LayoutType
  items: DesignItem[]
  bounding_box: BoundingBox
}

/** GET /designs/{id} — note: no `user_id`, `description`, or `current_version_id` here (M5). */
export interface DesignDetail {
  id: EntityId
  title: string
  status: DesignStatus
  wall: DesignWall
  current_version: DesignVersion | null
  created_at: ISODateTime
  updated_at: ISODateTime
}
