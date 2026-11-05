/** Contract §3 — Frame Catalog & Materials. */
import type { DecimalString, EntityId } from './common'

export type FrameMaterialCategory = 'wood' | 'metal' | 'synthetic'

export interface FrameMaterial {
  id: EntityId
  code: string
  name: string
  category: FrameMaterialCategory
  finish: string
  base_price_per_linear_inch: DecimalString
  waste_factor_percentage: number
  /** Relative to the API host, e.g. `/static/materials/teak-natural.webp`. Resolve with `resolveApiUrl`. */
  thumbnail_url: string
  is_available: boolean
}

/** GET /frame-materials query */
export interface FrameMaterialsQuery {
  category?: FrameMaterialCategory
  /** Server default: true */
  available_only?: boolean
}

/** A moulding profile. Shown in "Wood Moulding & Finish". */
export interface FrameMolding {
  id: EntityId
  sku: string
  name: string
  material_id: EntityId
  material_name: string
  profile_width_inches: number
  profile_depth_inches: number
  rabbet_depth_inches: number
  price_per_linear_inch: DecimalString
  /** Colour NAMES only (e.g. "Dark Walnut"). The swatch UI needs hex values (mismatch M8). */
  available_colors: string[]
  thumbnail_url: string
  is_active: boolean
}

/** GET /frames query */
export interface FramesQuery {
  material_id?: EntityId
  color?: string
  min_width?: number
  max_width?: number
}
