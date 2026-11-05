import { memoryWallAssets } from '@/assets/memoryWall'
import type { LengthUnit } from '@/lib/units'
import type { TemplateCategory } from '@/types/api'

/**
 * Static planner options. Swatch hex values were sampled from
 * reference_designs/memory_wall/laptop_view.png. They're TEMPORARY where the API should be the
 * source (wood finishes → /frames available_colors, see API_ALIGNMENT.md M8).
 */

export interface Swatch {
  id: string
  label: string
  hex: string
}

/** "Paint Shade" → DesignWall.color_hex */
export const PAINT_SHADES: readonly Swatch[] = [
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

/** "Wood Moulding & Finish". Placeholder until /frames returns hex + profile per colour. */
export const WOOD_FINISHES: readonly WoodFinish[] = [
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
export const MOUNT_COLOURS: readonly Swatch[] = [
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

/** Standard photo openings (inches). Client-side list until the API offers one (M9). */
export const FRAME_SIZES: readonly FrameSize[] = [
  { id: '5x7', w: 5, h: 7, label: '5 x 7 inches' },
  { id: '8x10', w: 8, h: 10, label: '8 x 10 inches' },
  { id: '11x14', w: 11, h: 14, label: '11 x 14 inches' },
  { id: '12x16', w: 12, h: 16, label: '12 x 16 inches (Atelier Classic Recommended)', recommended: true },
  { id: '16x20', w: 16, h: 20, label: '16 x 20 inches' },
  { id: '18x24', w: 18, h: 24, label: '18 x 24 inches' },
  { id: '20x30', w: 20, h: 30, label: '20 x 30 inches' },
  { id: '24x36', w: 24, h: 36, label: '24 x 36 inches (Statement)' },
]

export const WALL_UNITS: readonly LengthUnit[] = ['ft', 'in', 'cm', 'm']
export const GAP_UNITS = ['in', 'cm'] as const satisfies readonly LengthUnit[]
export type GapUnit = (typeof GAP_UNITS)[number]

/** Physical rules of the planner (inches). */
export const PLANNER_RULES = {
  /** Centre of the arrangement sits at gallery eye level. */
  eyeLevelIn: 60,
  /** Keep this clear of the wall's sides and ceiling. */
  wallMarginIn: 6,
  /** Lowest the arrangement may go without furniture (skirting / switches). */
  minBottomIn: 12,
  /** Breathing room above the reference sofa. */
  sofaClearanceIn: 8,
  wallWidthIn: { min: 36, max: 480 },
  wallHeightIn: { min: 48, max: 240 },
  gapIn: { min: 0, max: 12 },
  matIn: { min: 0, max: 6, step: 0.5 },
  frameCount: { min: 1, max: 16 },
} as const

/**
 * The room photo (background-wall-plain.webp) is drawn to scale: its sofa is the "84″ reference
 * sofa". Pixel bounds measured on the 1466×667 source.
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
 * Layout options in the UI → API template category.
 * `row` has no matching category in the contract (API_ALIGNMENT.md M6); until it exists, the
 * client lays out a single row itself and saves the version as `layout_type: 'custom'`.
 */
export const LAYOUT_STYLES = [
  { id: 'grid', label: 'Grid', apiCategory: 'grid' },
  { id: 'salon', label: 'Salon', apiCategory: 'salon' },
  { id: 'centre', label: 'Centre', apiCategory: 'focal_center' },
  { id: 'row', label: 'Row', apiCategory: null },
] as const satisfies ReadonlyArray<{ id: string; label: string; apiCategory: TemplateCategory | null }>

export type LayoutStyleId = (typeof LAYOUT_STYLES)[number]['id']

/** Number of alternative arrangements shown in the canvas carousel. */
export const VARIANT_COUNT = 3

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
