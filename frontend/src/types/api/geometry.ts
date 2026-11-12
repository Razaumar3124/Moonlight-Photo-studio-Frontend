/** Contract §6 — Geometry & layout engine. All values in inches, top-left origin. Optional auth. */
import type { BoundingBox, EntityId, MattingInches } from './common'
import type { TemplateCategory } from './templates'

export type LayoutStyle = TemplateCategory

export interface GeometryWall {
  /** 36–480 */
  width_inches: number
  /** 48–240 */
  height_inches: number
  /** Default 6 (planner margin). */
  margin_inches?: number
  /** Reference sofa shown: the arrangement stays above sofa top + 8 in. */
  has_sofa?: boolean
  /** Default 60. */
  eye_level_height_inches?: number
}

export interface GeometryFrameInput {
  item_id: string
  photo_id?: EntityId | null
  /** Catalog size: sets the photo opening from size + orientation (preferred). */
  size_id?: string | null
  /** Catalog finish: sets the moulding face width (preferred). */
  finish_id?: string | null
  orientation?: 'portrait' | 'landscape' | 'square'
  /** Only needed without `size_id`. Default 12 × 16. */
  photo_width_inches?: number
  photo_height_inches?: number
  /** Only needed without `finish_id`. Default 1. */
  frame_profile_width_inches?: number
  /** Mount per side 0–6 in; the engine uses `top_inches` on every side. */
  matting?: Partial<MattingInches> & { enabled?: boolean }
}

export interface PlacedItem {
  item_id: string
  photo_id: EntityId | null
  outer_x_inches: number
  outer_y_inches: number
  outer_width_inches: number
  outer_height_inches: number
  photo_x_inches: number
  photo_y_inches: number
  photo_width_inches: number
  photo_height_inches: number
}

export interface LayoutIssue {
  /** e.g. TOO_WIDE, TOO_TALL, OVERLAP, LOW_COVERAGE */
  code: string
  message: string
}

/* ----------------------------- §6.1 Validate ------------------------------- */

/** POST /geometry/validate-layout */
export interface ValidateLayoutRequest {
  wall: GeometryWall
  /** 1–16 frames as outer boxes. */
  frames: Array<{
    item_id: string
    outer_x_inches: number
    outer_y_inches: number
    outer_width_inches: number
    outer_height_inches: number
  }>
}

/**
 * Always 200 for a well-formed request (Q10 resolved): collisions and boundary problems come
 * back in `errors[]` with `item_ids`; 422 is only for malformed payloads.
 */
export interface ValidateLayoutResponse {
  is_valid: boolean
  bounding_box: BoundingBox
  wall_coverage_percentage: number
  /** GEOMETRY_COLLISION_DETECTED, GEOMETRY_OUT_OF_BOUNDS, GEOMETRY_INVALID_DIMENSIONS */
  errors: Array<LayoutIssue & { item_ids: string[] }>
  warnings: LayoutIssue[]
  calculated_items: Array<{
    item_id: string
    outer_x_inches: number
    outer_y_inches: number
    outer_width_inches: number
    outer_height_inches: number
  }>
}

/* ---------------------- §6.2 Generate / regenerate / redesign --------------- */

/** POST /geometry/generate-layout. Frames can be empty placeholders (no `photo_id`): M10. */
export interface GenerateLayoutRequest {
  wall: GeometryWall
  /** 1–16 */
  frames: GeometryFrameInput[]
  /** Omit to let the engine pick the best-fitting style. */
  layout_style?: LayoutStyle | null
  /** 0–12, default 3. */
  spacing_inches?: number
  engine_mode?: 'geometric' | 'smart_llm'
  seed?: number | null
  /** 0–2 */
  variant?: number
}

export interface GeneratedLayout {
  layout_type: LayoutStyle
  variant: number
  seed: number
  bounding_box: BoundingBox
  wall_coverage_percentage: number
  fits: boolean
  items: PlacedItem[]
}

export interface GenerateLayoutResponse extends GeneratedLayout {
  engine_used: 'smart_llm' | 'geometric' | 'fallback_geometric'
  ai_rationale: string | null
  warnings: LayoutIssue[]
}

/** POST /geometry/regenerate — same style, next arrangement. */
export interface RegenerateLayoutRequest {
  wall: GeometryWall
  frames: GeometryFrameInput[]
  layout_style: LayoutStyle
  current_seed: number
  current_variant?: number
  spacing_inches?: number
}

export interface RegenerateLayoutResponse extends GeneratedLayout {
  engine_used: 'geometric'
}

/** POST /geometry/redesign — a different style. */
export interface RedesignLayoutRequest {
  wall: GeometryWall
  frames: GeometryFrameInput[]
  current_layout_style: LayoutStyle
  spacing_inches?: number
  engine_mode?: 'geometric' | 'smart_llm'
}

export interface RedesignLayoutResponse extends GeneratedLayout {
  engine_used: 'smart_llm' | 'geometric' | 'fallback_geometric'
  ai_rationale: string | null
}
