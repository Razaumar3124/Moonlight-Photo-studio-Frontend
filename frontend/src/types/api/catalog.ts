/** Contract §3 — Catalog: planner options (GET /catalog) and frame materials/mouldings. */
import type { DecimalString, EntityId, HexColor } from './common'
import type { TemplateCategory } from './templates'

/* --------------------------- §3.1 Planner catalog -------------------------- */
/*
 * The backend is the source of truth for every planner option and rule. IDs are permanent and
 * are what designs and quotes store. The planner loads this at start (`features/memory-wall/lib/catalog.ts`);
 * `constants.ts` keeps bundled defaults that backend/tests/test_catalog_contract.py checks against it.
 */

export interface CatalogFrameSize {
  /** e.g. `12x16` */
  id: string
  label: string
  /** Photo opening, portrait orientation (short side first). Landscape swaps the sides. */
  width_inches: number
  height_inches: number
  recommended: boolean
}

export interface CatalogFrameFinish {
  /** e.g. `natural-oak` */
  id: string
  label: string
  hex: HexColor
  /** Visible moulding face width added on each side of the frame. */
  profile_inches: number
}

export interface CatalogSwatch {
  id: string
  label: string
  hex: HexColor
}

export interface CatalogRange {
  min: number
  max: number
}

/** Physical planner rules in inches. Server-side validation uses exactly these values. */
export interface PlannerRules {
  eye_level_inches: number
  wall_margin_inches: number
  min_bottom_inches: number
  sofa_top_from_floor_inches: number
  sofa_clearance_inches: number
  wall_width_inches: CatalogRange
  wall_height_inches: CatalogRange
  gap_inches: CatalogRange
  mat_inches: CatalogRange
  mat_step_inches: number
  frame_count: CatalogRange
  variant_count: number
}

/** GET /catalog · public · Cache-Control: public, max-age=300 */
export interface PlannerCatalog {
  /** Revision date, YYYY-MM-DD. */
  version: string
  frame_sizes: CatalogFrameSize[]
  frame_finishes: CatalogFrameFinish[]
  mount_colors: CatalogSwatch[]
  paint_shades: CatalogSwatch[]
  layout_styles: Array<{ id: TemplateCategory; label: string }>
  /** Template slugs the planner ships with (GET /templates). */
  template_ids: string[]
  /** Units the planner offers. Every API value is in inches. */
  wall_units: Array<'ft' | 'in' | 'cm' | 'm'>
  gap_units: Array<'in' | 'cm'>
  rules: PlannerRules
}

/* ------------------------- §3.2 Materials & mouldings ----------------------- */

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

/** A colour option of a moulding. Wood colours use the catalog finish IDs (M8 resolved). */
export interface FrameColor {
  id: string
  name: string
  hex: HexColor
  profile_in: number
}

/** A moulding profile. */
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
  available_colors: FrameColor[]
  thumbnail_url: string
  is_active: boolean
}

/** GET /frames query */
export interface FramesQuery {
  material_id?: EntityId
  /** Colour name substring, case-insensitive. */
  color?: string
  min_width?: number
  max_width?: number
}
