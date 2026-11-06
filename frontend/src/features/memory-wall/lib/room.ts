import { memoryWallAssets } from '@/assets/memoryWall'
import type { Rect } from './geometry/rect'
import type { Scene } from './geometry/scene'

/**
 * Room layers drawn around the wall (presentation only: the geometry engine never reads this).
 * Everything is in inches in the wall's coordinate system (0,0 = top-left of the wall,
 * y = wallHeight is the floor line). Measurements come from the source images, see
 * memoryWallAssets.room and ASSETS.md W4.
 */

const strip = memoryWallAssets.room.floorStrip
/** 35px skirting board on the strip = 4″. */
const STRIP_PX_PER_IN = 8.75
const STRIP_SKIRT_TOP_PX = 450
const STRIP_FLOOR_TOP_PX = 485

/** Skirting board height, drawn over the bottom of the wall. */
export const SKIRTING_IN = (STRIP_FLOOR_TOP_PX - STRIP_SKIRT_TOP_PX) / STRIP_PX_PER_IN
/** Visible floor below the wall (extends the drawing, not the wall). */
export const FLOOR_BAND_IN = (strip.height - STRIP_FLOOR_TOP_PX) / STRIP_PX_PER_IN

/** One tile of the floor strip in inches, and the slice of the source it shows. */
export const FLOOR_TILE = {
  widthIn: strip.width / STRIP_PX_PER_IN,
  heightIn: (strip.height - STRIP_SKIRT_TOP_PX) / STRIP_PX_PER_IN,
  viewBox: `0 ${STRIP_SKIRT_TOP_PX} ${strip.width} ${strip.height - STRIP_SKIRT_TOP_PX}`,
} as const

/** Height of the whole drawing: wall + floor band. */
export const drawingHeight = (wallHeightIn: number) => wallHeightIn + FLOOR_BAND_IN

export type RoomItemKind = 'sofa' | 'lamp' | 'plant'

export interface RoomItem {
  kind: RoomItemKind
  /** Placement in wall inches. */
  rect: Rect
  /** The opaque box of the source image (source pixels), mapped onto `rect`. */
  crop: Rect
  src: string
  srcWidth: number
  srcHeight: number
}

const SOURCES = {
  sofa: { asset: memoryWallAssets.room.sofa, crop: { x: 24, y: 27, w: 2088, h: 693 } },
  lamp: { asset: memoryWallAssets.room.lamp, crop: { x: 203, y: 33, w: 480, h: 1710 } },
  plant: { asset: memoryWallAssets.room.plant, crop: { x: 10, y: 19, w: 867, h: 1732 } },
} as const

const SOFA_WIDTH_IN = 84
const LAMP_HEIGHT_IN = 60
const PLANT_HEIGHT_IN = 36
/** Clear space decor keeps from the arrangement and the wall edges. */
const DECOR_CLEARANCE_IN = 3

function item(kind: RoomItemKind, rect: Rect): RoomItem {
  const { asset, crop } = SOURCES[kind]
  return { kind, rect, crop, src: asset.src, srcWidth: asset.width, srcHeight: asset.height }
}

const sizeFor = (kind: RoomItemKind, by: { w?: number; h?: number }) => {
  const { crop } = SOURCES[kind]
  return by.w !== undefined
    ? { w: by.w, h: (by.w * crop.h) / crop.w }
    : { w: ((by.h ?? 0) * crop.w) / crop.h, h: by.h ?? 0 }
}

const overlaps = (a: Rect, b: Rect, pad: number) =>
  a.x < b.x + b.w + pad && b.x < a.x + a.w + pad && a.y < b.y + b.h + pad && b.y < a.y + a.h + pad

/**
 * The 84″ sofa (when the reference sofa is on) plus a floor lamp and a plant beside it.
 *
 * The sofa's TOP sits on `scene.sofaTopY`, the line the geometry keeps frames above; it stands a
 * little in front of the wall, so its feet land on the floor band below the wall. Decor is only
 * placed where it fits on the wall and clears the arrangement, so it never covers a frame.
 */
export function roomLayout(scene: Scene): { sofa: RoomItem | null; decor: RoomItem[] } {
  if (scene.sofaTopY === null) return { sofa: null, decor: [] }
  const { w: W, h: H } = scene.wall
  const sofaSize = sizeFor('sofa', { w: SOFA_WIDTH_IN })
  const sofa = item('sofa', { x: W / 2 - sofaSize.w / 2, y: scene.sofaTopY, ...sofaSize })
  // Never let the feet drop past the visible floor.
  const feetY = Math.min(sofa.rect.y + sofa.rect.h, H + FLOOR_BAND_IN - 1)
  sofa.rect.y = feetY - sofa.rect.h

  const lamp = sizeFor('lamp', { h: LAMP_HEIGHT_IN })
  const plant = sizeFor('plant', { h: PLANT_HEIGHT_IN })
  const candidates = [
    item('lamp', { x: sofa.rect.x + sofa.rect.w + 6, y: feetY - 1 - lamp.h, ...lamp }),
    item('plant', { x: sofa.rect.x - 4 - plant.w, y: feetY + 0.5 - plant.h, ...plant }),
  ]
  const art = scene.arrangement
  const decor = candidates.filter(({ rect }) => {
    const onWall = rect.x >= DECOR_CLEARANCE_IN && rect.x + rect.w <= W - DECOR_CLEARANCE_IN
    // Only the part above the floor line can meet a frame.
    const visible = { ...rect, h: Math.max(0, Math.min(rect.y + rect.h, H) - rect.y) }
    return onWall && rect.y > 0 && !overlaps(visible, art, DECOR_CLEARANCE_IN)
  })
  return { sofa, decor }
}
