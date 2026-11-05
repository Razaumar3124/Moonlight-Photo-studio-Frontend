/** Contract §5 — Layout Templates. */
import type { EntityId } from './common'

/**
 * Template categories from the contract. The planner's Layout control shows
 * Grid / Salon / Centre / Row — "Row" has no category yet (mismatch M6).
 */
export type TemplateCategory = 'grid' | 'salon' | 'triptych' | 'staircase' | 'focal_center'

export interface TemplateSlot {
  slot_id: string
  /** 0–1, relative to the wall width/height. */
  relative_x_ratio: number
  relative_y_ratio: number
  default_photo_width_inches: number
  default_photo_height_inches: number
  aspect_ratio: number
}

export interface LayoutTemplate {
  id: EntityId
  slug: string
  name: string
  description: string
  category: TemplateCategory
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
