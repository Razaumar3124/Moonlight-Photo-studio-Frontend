/** Contract §7 — Saved designs and immutable versions (bearer auth, owner only). */
import type { BoundingBox, EntityId, HexColor, ISODateTime, MattingInches, PageResponse } from './common'
import type { TemplateCategory } from './templates'

/** Units the customer sees. API values stay in inches; `mm` only appears on older designs. */
export type DisplayUnit = 'ft' | 'in' | 'cm' | 'm' | 'mm'

export type DesignStatus = 'draft' | 'saved' | 'ordered' | (string & {})

/** `custom` = hand-arranged; otherwise the planner layout style. */
export type LayoutType = 'custom' | TemplateCategory

/* ---------------------------------- Wall ----------------------------------- */

/** Input wall. Limits are the planner rules: 36–480 × 48–240 in. */
export interface DesignWallInput {
  width_inches: number
  height_inches: number
  /** Catalog paint shade; the server sets `color_hex` from it. */
  paint_id?: string | null
  color_hex?: HexColor
  texture?: string
  display_unit?: DisplayUnit
  has_sofa?: boolean
}

/** Stored wall (output). Older designs may predate the current limits. */
export interface DesignWall {
  width_inches: number
  height_inches: number
  paint_id: string | null
  color_hex: HexColor
  texture: string
  display_unit: DisplayUnit | (string & {})
  has_sofa: boolean
}

/* ------------------------------ Designs (CRUD) ----------------------------- */

/** POST /designs */
export interface CreateDesignRequest {
  /** 1–100 characters */
  title: string
  description?: string | null
  wall?: DesignWallInput
}

/** PATCH /designs/{id} — any subset; `wall` replaces the whole wall. */
export interface UpdateDesignRequest {
  title?: string
  description?: string | null
  status?: 'draft' | 'saved' | 'ordered'
  wall?: DesignWallInput
}

/** POST /designs (201) and PATCH /designs/{id} (200). */
export interface Design {
  id: EntityId
  user_id: EntityId
  title: string
  description: string | null
  wall: DesignWall
  current_version_id: EntityId | null
  current_version_number: number | null
  status: DesignStatus
  created_at: ISODateTime
  updated_at: ISODateTime
}

/** GET /designs?page&page_size&status&search&sort (sort: `updated_at:desc` default). */
export interface DesignListItem extends Design {
  items_count: number
}

export type DesignListResponse = PageResponse<DesignListItem>

/* ------------------------------ Versions ----------------------------------- */

export interface DesignMattingInput extends Partial<MattingInches> {
  enabled?: boolean
  /** Catalog mount colour; the server sets `color_hex` from it. */
  color_id?: string | null
  color_hex?: HexColor
}

export interface DesignMatting extends MattingInches {
  enabled: boolean
  color_id: string | null
  color_hex: HexColor
}

/**
 * A placed frame. With `size_id` the opening must equal the catalog size in `orientation`;
 * with `finish_id` the server computes the outer size (opening + mounts + 2 × moulding face).
 */
export interface DesignItemInput {
  /** Unique within the version; letters, digits, `_` and `-`, ≤ 64 characters. */
  item_id: string
  size_id?: string | null
  finish_id?: string | null
  /** Defaults to `size_id` (or `custom`). */
  frame_id?: string | null
  /** A photo uploaded by the same user — or `sample_id` for a bundled sample, never both. */
  photo_id?: EntityId | null
  sample_id?: string | null
  position_x_inches: number
  position_y_inches: number
  photo_width_inches: number
  photo_height_inches: number
  /** Only needed without `finish_id`; must match the server's value when sent. */
  total_width_inches?: number | null
  total_height_inches?: number | null
  orientation?: 'portrait' | 'landscape' | 'square'
  matting?: DesignMattingInput
  glass_type?: string
}

/** Planner layout settings saved with a version (M12). */
export interface LayoutMetadata {
  style?: TemplateCategory
  /** 0–12 */
  gap_inches?: number
  gap_unit?: 'in' | 'cm'
  seed?: number
  /** 0–2 */
  variant?: number
}

/** Planner preview toggles. `sofa` also selects the sofa clearance used for validation. */
export interface PreviewFlags {
  sofa?: boolean
  index_badges?: boolean
  guides?: boolean
}

/**
 * POST /designs/{id}/versions. 1–16 items. Rejected with 422 when the layout doesn't fit the
 * wall by the planner's own rules (6 in margin, 12 in above the floor or above the sofa, no
 * overlaps). Saving an identical layout returns the current version instead of a new one.
 */
export interface SaveDesignVersionRequest {
  layout_type?: LayoutType
  /** Template slug (e.g. `balanced-grid`) or template ID. */
  template_id?: string | null
  items: DesignItemInput[]
  layout_metadata?: LayoutMetadata | null
  preview?: PreviewFlags | null
}

export interface DesignVersionSummary {
  version_id: EntityId
  design_id: EntityId
  version_number: number
  layout_type: LayoutType
  items_count: number
  bounding_box: BoundingBox
  created_at: ISODateTime
}

export interface DesignItem {
  item_id: string
  frame_id: string
  photo_id: EntityId | null
  /** The referenced photo was deleted or is no longer accessible. */
  photo_missing: boolean
  sample_id: string | null
  position_x_inches: number
  position_y_inches: number
  photo_width_inches: number
  photo_height_inches: number
  total_width_inches: number
  total_height_inches: number
  orientation: 'portrait' | 'landscape' | 'square' | (string & {})
  finish_id: string | null
  size_id: string | null
  matting: DesignMatting
  glass_type: string
}

export interface DesignVersion {
  id: EntityId
  design_id: EntityId
  version_number: number
  layout_type: LayoutType | (string & {})
  template_id: string | null
  items_count: number
  bounding_box: BoundingBox
  items: DesignItem[]
  /** Older versions may hold other keys; sanitise before use. */
  layout_metadata: (LayoutMetadata & Record<string, unknown>) | null
  preview: (PreviewFlags & Record<string, unknown>) | null
  created_at: ISODateTime
}

/** GET /designs/{id} */
export interface DesignDetail {
  id: EntityId
  user_id: EntityId
  title: string
  description: string | null
  status: DesignStatus
  wall: DesignWall
  current_version_id: EntityId | null
  current_version: DesignVersion | null
  created_at: ISODateTime
  updated_at: ISODateTime
}
