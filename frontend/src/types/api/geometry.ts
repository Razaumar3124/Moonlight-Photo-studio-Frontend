/** Contract §6 — Geometry Engine & Layout Validation. All values in inches, top-left origin. */
import type { BoundingBox, EntityId, MattingInches } from './common'
import type { TemplateCategory } from './templates'

/* ----------------------------- §6.1 Validate ------------------------------- */

export interface GeometryFrameInput {
  /** Client-generated stable id, e.g. `frame-item-1`. */
  item_id: string
  x_inches: number
  y_inches: number
  photo_width_inches: number
  photo_height_inches: number
  matting: MattingInches
  frame_profile_width_inches: number
}

export interface ValidateLayoutRequest {
  wall: {
    width_inches: number
    height_inches: number
    safe_margin_inches: number
  }
  frames: GeometryFrameInput[]
}

export type LayoutIssueCode = 'LOW_WALL_COVERAGE' | (string & {})

export interface LayoutIssue {
  code: LayoutIssueCode
  message: string
}

export interface CalculatedLayoutItem {
  item_id: string
  outer_x_inches: number
  outer_y_inches: number
  outer_width_inches: number
  outer_height_inches: number
}

/**
 * 200 response. Collisions come back as a 422 error envelope with
 * code `GEOMETRY_COLLISION_DETECTED` instead of in `errors` (see Q10).
 */
export interface ValidateLayoutResponse {
  is_valid: boolean
  bounding_box: BoundingBox
  wall_coverage_percentage: number
  errors: LayoutIssue[]
  warnings: LayoutIssue[]
  calculated_items: CalculatedLayoutItem[]
}

/* ----------------------------- §6.2 Generate ------------------------------- */

/** Values beyond the contract's example ("triptych") are unconfirmed (Q6). */
export type LayoutStyle = TemplateCategory

export type TargetAlignment = 'center_eye_level' | (string & {})

export interface GenerateLayoutRequest {
  wall: {
    width_inches: number
    height_inches: number
    margin_inches: number
  }
  photo_ids: EntityId[]
  layout_style: LayoutStyle
  spacing_inches: number
  target_alignment: TargetAlignment
  eye_level_height_inches: number
}

export interface GeneratedLayoutItem {
  slot_index: number
  photo_id: EntityId
  x_inches: number
  y_inches: number
  photo_width_inches: number
  photo_height_inches: number
  matting: MattingInches
  frame_profile_width_inches: number
  total_width_inches: number
  total_height_inches: number
}

export interface GenerateLayoutResponse {
  layout_type: LayoutStyle
  bounding_box: BoundingBox
  items: GeneratedLayoutItem[]
}
