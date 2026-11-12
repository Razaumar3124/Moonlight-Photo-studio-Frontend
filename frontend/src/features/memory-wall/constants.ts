import { memoryWallAssets } from '@/assets/memoryWall'
import type { LengthUnit } from '@/lib/units'
import type { TemplateCategory } from '@/types/api'

/**
 * Planner options and rules. The backend catalog (`GET /catalog`, backend/app/modules/catalog.py)
 * is the source of truth: `lib/catalog.ts` loads it when the planner opens and calls
 * `installCatalog`, which replaces the lists below. The values written here are the bundled
 * DEFAULTS, used until the catalog arrives and when it can't be fetched. backend/tests/
 * test_catalog_contract.py parses this file and fails if the defaults drift from the backend, so
 * change IDs and values on both sides together. IDs are permanent: saved designs and quotes store
 * them.
 *
 * The lists are `export let` live bindings: importers always read the current value. They are
 * replaced once, before the planner first renders, never while it is on screen.
 */

export interface Swatch {
  id: string
  label: string
  hex: string
}

/** "Paint Shade" → DesignWall.color_hex */
export let PAINT_SHADES: readonly Swatch[] = [
  { id: 'ivory-mist', label: 'Ivory Mist', hex: '#F0EBE4' },
  { id: 'warm-cream', label: 'Warm Cream', hex: '#EFDECA' },
  { id: 'sand', label: 'Sand', hex: '#E4CFB4' },
  { id: 'peach-blush', label: 'Peach Blush', hex: '#ECCAAF' },
  { id: 'charcoal', label: 'Charcoal', hex: '#6F6A64' },
  { id: 'stone-grey', label: 'Stone Grey', hex: '#8D8785' },
  { id: 'cloud-grey', label: 'Cloud Grey', hex: '#C5C5C7' },
]

export interface WoodFinish extends Swatch {
  /** Visible moulding face width in inches (adds to the frame's outer size). */
  profileIn: number
}

/** "Wood Moulding & Finish" → catalog `frame_finishes` (`profile_inches`). */
export let WOOD_FINISHES: readonly WoodFinish[] = [
  { id: 'walnut', label: 'Walnut', hex: '#784E2D', profileIn: 1 },
  { id: 'natural-oak', label: 'Natural Oak', hex: '#916843', profileIn: 1 },
  { id: 'ivory', label: 'Ivory', hex: '#FAF3E8', profileIn: 0.875 },
  { id: 'whitewash', label: 'Whitewash', hex: '#EEE6DE', profileIn: 0.875 },
  { id: 'dark-teak', label: 'Dark Teak', hex: '#774B31', profileIn: 1 },
  { id: 'honey', label: 'Honey', hex: '#B1875F', profileIn: 1 },
  { id: 'golden-teak', label: 'Golden Teak', hex: '#B07840', profileIn: 1.125 },
  { id: 'mahogany', label: 'Mahogany', hex: '#7A432D', profileIn: 1.125 },
]

/** "Mount Colour" → DesignMatting.color_hex */
export let MOUNT_COLOURS: readonly Swatch[] = [
  { id: 'museum-white', label: 'Museum White', hex: '#F4F3F3' },
  { id: 'antique-white', label: 'Antique White', hex: '#EDE8E3' },
  { id: 'black', label: 'Black', hex: '#1D191A' },
  { id: 'crimson', label: 'Crimson', hex: '#6B0A11' },
]

export type Orientation = 'portrait' | 'landscape'

export interface FrameSize {
  id: string
  /** Photo opening, portrait orientation (short side first), inches. */
  w: number
  h: number
  label: string
  recommended?: boolean
}

/** Standard photo openings (inches) → catalog `frame_sizes`. */
export let FRAME_SIZES: readonly FrameSize[] = [
  { id: '5x7', w: 5, h: 7, label: '5 x 7 inches' },
  { id: '8x10', w: 8, h: 10, label: '8 x 10 inches' },
  { id: '11x14', w: 11, h: 14, label: '11 x 14 inches' },
  { id: '12x16', w: 12, h: 16, label: '12 x 16 inches (Atelier Classic Recommended)', recommended: true },
  { id: '16x20', w: 16, h: 20, label: '16 x 20 inches' },
  { id: '18x24', w: 18, h: 24, label: '18 x 24 inches' },
  { id: '20x30', w: 20, h: 30, label: '20 x 30 inches' },
  { id: '24x36', w: 24, h: 36, label: '24 x 36 inches (Statement)' },
]

export let WALL_UNITS: readonly LengthUnit[] = ['ft', 'in', 'cm', 'm']
export const GAP_UNITS = ['in', 'cm'] as const satisfies readonly LengthUnit[]
export type GapUnit = (typeof GAP_UNITS)[number]

export interface PlannerRulesConfig {
  /** Centre of the arrangement sits at gallery eye level. */
  eyeLevelIn: number
  /** Keep this clear of the wall's sides and ceiling. */
  wallMarginIn: number
  /** Lowest the arrangement may go without furniture (skirting / switches). */
  minBottomIn: number
  /** Breathing room above the reference sofa. */
  sofaClearanceIn: number
  wallWidthIn: { min: number; max: number }
  wallHeightIn: { min: number; max: number }
  gapIn: { min: number; max: number }
  matIn: { min: number; max: number; step: number }
  frameCount: { min: number; max: number }
}

/** Physical rules of the planner (inches). */
export let PLANNER_RULES: PlannerRulesConfig = {
  eyeLevelIn: 60,
  wallMarginIn: 6,
  minBottomIn: 12,
  sofaClearanceIn: 8,
  wallWidthIn: { min: 36, max: 480 },
  wallHeightIn: { min: 48, max: 240 },
  gapIn: { min: 0, max: 12 },
  matIn: { min: 0, max: 6, step: 0.5 },
  frameCount: { min: 1, max: 16 },
}

/**
 * Reference-sofa line used by the GEOMETRY (sofa clearance): measured on the original room photo
 * (background-wall-plain.webp, 1466×667), whose sofa is the "84″ reference sofa". The room is now
 * drawn from separate cut-outs (lib/room.ts), which align the new sofa's top to this same line,
 * so layouts and fit checks are unchanged.
 */
export const ROOM_PHOTO = {
  widthPx: 1466,
  heightPx: 667,
  sofaLeftPx: 243,
  sofaRightPx: 1252,
  sofaTopPx: 492,
  sofaWidthIn: 84,
} as const

const roomPxPerIn = (ROOM_PHOTO.sofaRightPx - ROOM_PHOTO.sofaLeftPx) / ROOM_PHOTO.sofaWidthIn
/** Derived real-world size of the room photo and the sofa top height above the floor. */
export const ROOM_PHOTO_IN = {
  width: ROOM_PHOTO.widthPx / roomPxPerIn,
  height: ROOM_PHOTO.heightPx / roomPxPerIn,
  sofaCentreX: (ROOM_PHOTO.sofaLeftPx + ROOM_PHOTO.sofaRightPx) / 2 / roomPxPerIn,
  sofaTopFromFloor: (ROOM_PHOTO.heightPx - ROOM_PHOTO.sofaTopPx) / roomPxPerIn,
} as const

/**
 * Layout options in the UI → API template category / `layout_type` (M6 resolved: the API uses
 * the same four IDs; legacy `focal_center` is normalised to `centre` by the server).
 */
export const LAYOUT_STYLES = [
  { id: 'grid', label: 'Grid', apiCategory: 'grid' },
  { id: 'salon', label: 'Salon', apiCategory: 'salon' },
  { id: 'centre', label: 'Centre', apiCategory: 'centre' },
  { id: 'row', label: 'Row', apiCategory: 'row' },
] as const satisfies ReadonlyArray<{ id: string; label: string; apiCategory: TemplateCategory }>

export type LayoutStyleId = (typeof LAYOUT_STYLES)[number]['id']

/** Alternative arrangements per layout style (Generate searches them; the Variations menu picks one). */
export let VARIANT_COUNT = 3

/** AI Layout Assistant presets: featured templates with their bundled thumbnails. */
export const AI_LAYOUT_PRESETS = [
  {
    templateId: 'balanced-grid',
    label: 'Balanced Grid',
    thumbnail: memoryWallAssets.layoutThumbnails.balancedGrid,
  },
  {
    templateId: 'creative-salon',
    label: 'Creative Salon',
    thumbnail: memoryWallAssets.layoutThumbnails.creativeSalon,
  },
  {
    templateId: 'centre-focus',
    label: 'Centre Focus',
    thumbnail: memoryWallAssets.layoutThumbnails.centreFocus,
  },
  {
    templateId: 'minimal-row',
    label: 'Minimal Row',
    thumbnail: memoryWallAssets.layoutThumbnails.minimalRow,
  },
] as const

/* ============================= Catalog install ============================= */

/** A validated backend catalog (see `lib/catalog.ts`). */
export interface CatalogData {
  paintShades: readonly Swatch[]
  woodFinishes: readonly WoodFinish[]
  mountColours: readonly Swatch[]
  frameSizes: readonly FrameSize[]
  wallUnits: readonly LengthUnit[]
  rules: PlannerRulesConfig
  variantCount: number
}

/** Replace the bundled defaults with the backend catalog. Call before the planner renders. */
export function installCatalog(data: CatalogData) {
  PAINT_SHADES = data.paintShades
  WOOD_FINISHES = data.woodFinishes
  MOUNT_COLOURS = data.mountColours
  FRAME_SIZES = data.frameSizes
  WALL_UNITS = data.wallUnits
  PLANNER_RULES = data.rules
  VARIANT_COUNT = data.variantCount
}
