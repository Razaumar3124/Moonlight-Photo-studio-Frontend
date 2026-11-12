/** Contract §4 — Layout Templates. */
import type { EntityId, PhotoOrientation } from './common'

/**
 * Template category = planner layout style (M6 resolved 2026-11-12). Legacy names sent as a
 * filter (`focal_center`, `triptych`, `linear`) are accepted and normalised by the server.
 */
export type TemplateCategory = 'grid' | 'salon' | 'centre' | 'row'

export interface TemplateSlot {
  slot_id: string
  /** 0–1, relative to the wall width/height. */
  relative_x_ratio: number
  relative_y_ratio: number
  default_photo_width_inches: number
  default_photo_height_inches: number
  aspect_ratio: number
  /** Catalog frame size of the opening; null if it isn't a standard size. */
  size_id: string | null
  orientation: PhotoOrientation
}

export interface LayoutTemplate {
  id: EntityId
  /** Stable planner ID, e.g. `balanced-grid` (GET /catalog `template_ids`). */
  slug: string
  name: string
  description: string
  category: TemplateCategory
  /** Spacing between frames; null for templates seeded before Phase 3. */
  gap_inches: number | null
  min_wall_width_inches: number
  min_wall_height_inches: number
  recommended_wall_width_inches: number
  recommended_wall_height_inches: number
  slots_count: number
  slots: TemplateSlot[]
  thumbnail_url: string
}

/** GET /templates query */
export interface TemplatesQuery {
  category?: TemplateCategory
  min_frames?: number
  max_frames?: number
}
