import { samplePhotos } from '@/assets/memoryWall'
import {
  FRAME_SIZES,
  LAYOUT_STYLES,
  MOUNT_COLOURS,
  PAINT_SHADES,
  PLANNER_RULES,
  ROOM_PHOTO_IN,
  VARIANT_COUNT,
  WOOD_FINISHES,
  type LayoutStyleId,
  type Orientation,
} from '../../constants'
import type { FrameConfig, PhotoRef, PlannerState } from '../plannerState'
import { LAYOUTS } from './layouts'
import { createRng, mixSeed, shuffle } from './random'
import { area, bounds, conflicts, inset, translate, type Rect, type Size } from './rect'

/* ============================ Frame geometry ============================== */

export interface FrameGeometry {
  opening: Size
  profileIn: number
  matIn: number
  outer: Size
}

/** Photo opening + mat + moulding → the size the frame occupies on the wall. */
export function frameGeometry(
  frame: Pick<FrameConfig, 'sizeId' | 'orientation' | 'finishId' | 'mount'>,
): FrameGeometry {
  const size = FRAME_SIZES.find((s) => s.id === frame.sizeId) ?? FRAME_SIZES[3] ?? { w: 12, h: 16 }
  const [w, h] = frame.orientation === 'portrait' ? [size.w, size.h] : [size.h, size.w]
  const profileIn = WOOD_FINISHES.find((f) => f.id === frame.finishId)?.profileIn ?? 1
  const matIn = frame.mount.enabled ? frame.mount.marginIn : 0
  return {
    opening: { w, h },
    profileIn,
    matIn,
    outer: { w: w + 2 * (matIn + profileIn), h: h + 2 * (matIn + profileIn) },
  }
}

/* ================================ Scene ==================================== */

export interface ScenePhoto {
  href: string
  /** True when the frame is empty and shows a sample only because "Fill empty frames" is on. */
  isFill: boolean
  alt: string
}

export interface SceneFrame {
  id: string
  /** 1-based number shown on badges and chips. */
  number: number
  outer: Rect
  /** Inside the moulding (mat area, or photo when there's no mat). */
  inner: Rect
  photoRect: Rect
  orientation: Orientation
  finishHex: string
  mountHex: string | null
  photo: ScenePhoto | null
  label: string
}

export type SceneWarningCode = 'TOO_WIDE' | 'TOO_TALL' | 'OVERLAP' | 'LOW_COVERAGE'

export interface SceneWarning {
  code: SceneWarningCode
  message: string
}

export interface Scene {
  wall: Size & { paintHex: string }
  style: LayoutStyleId
  frames: SceneFrame[]
  /** Bounding box of the arrangement on the wall. */
  arrangement: Rect
  /** Y (from the top of the wall) of the eye-level line. */
  eyeLevelY: number
  /** Y of the sofa top when shown (for drawing the clearance). */
  sofaTopY: number | null
  fits: boolean
  coverage: number
  warnings: SceneWarning[]
}

function photoFor(
  ref: PhotoRef | null,
  index: number,
  orientation: Orientation,
  fill: boolean,
): ScenePhoto | null {
  if (ref?.kind === 'upload') return { href: ref.url, isFill: false, alt: ref.name }
  let sampleId: string | undefined
  if (ref?.kind === 'sample') sampleId = ref.sampleId
  else if (fill) {
    const pool = samplePhotos.filter((p) => p.orientation === orientation)
    const list = pool.length ? pool : samplePhotos
    sampleId = list[index % list.length]?.id
  }
  const sample = samplePhotos.find((p) => p.id === sampleId)
  return sample ? { href: sample.src, isFill: ref === null, alt: sample.alt } : null
}

/** Everything the geometry depends on (and nothing else, so callers can memoise precisely). */
export type SceneInput = Pick<PlannerState, 'wall' | 'layout' | 'frames' | 'fillWithSamples'> & {
  preview: Pick<PlannerState['preview'], 'sofa'>
}

/** Which frame sits in which layout slot: canonical for seed 0, reshuffled by "Regenerate". */
function slotOrder(count: number, seed: number): number[] {
  const identity = Array.from({ length: count }, (_, i) => i)
  return seed === 0 ? identity : shuffle(identity, createRng(mixSeed(seed, count)))
}

/**
 * The whole planner pipeline, recomputed from state on every change:
 * frame configs → outer sizes → layout algorithm (style, gap, wall space, seed, variant)
 * → placement on the wall (centred, eye level, above the sofa) → validation.
 */
export function buildScene(
  state: SceneInput,
  overrides: Partial<{ style: LayoutStyleId; variant: number }> = {},
): Scene {
  const { wall, layout, frames, preview, fillWithSamples } = state
  const style = overrides.style ?? layout.style
  const variant = overrides.variant ?? layout.variant
  const W = wall.widthIn
  const H = wall.heightIn
  const margin = PLANNER_RULES.wallMarginIn
  const sofaTopFromFloor = ROOM_PHOTO_IN.sofaTopFromFloor
  const minBottom = preview.sofa
    ? Math.max(PLANNER_RULES.minBottomIn, sofaTopFromFloor + PLANNER_RULES.sofaClearanceIn)
    : PLANNER_RULES.minBottomIn
  const maxWidth = Math.max(1, W - 2 * margin)
  const maxHeight = Math.max(1, H - margin - minBottom)

  const geometries = frames.map(frameGeometry)
  const order = slotOrder(frames.length, layout.seed)
  const slotSizes = order.map((i) => (geometries[i] as FrameGeometry).outer)
  const slotRects = LAYOUTS[style]({
    sizes: slotSizes,
    gap: layout.gapIn,
    maxWidth,
    maxHeight,
    variant,
    seed: layout.seed,
  })

  // Back from slot order to frame order.
  const relative: Rect[] = new Array<Rect>(frames.length)
  order.forEach((frameIndex, slot) => {
    relative[frameIndex] = slotRects[slot] as Rect
  })

  // Placement: centred horizontally, centre on eye level, but never below the minimum bottom
  // (sofa clearance) and never above the top margin.
  const box = bounds(relative)
  const x0 = (W - box.w) / 2
  const eyeLevelY = H - PLANNER_RULES.eyeLevelIn
  let top = eyeLevelY - box.h / 2
  top = Math.min(top, H - minBottom - box.h)
  top = Math.max(top, margin)
  const placed = translate(relative, x0, top)
  const arrangement = bounds(placed)

  const sceneFrames: SceneFrame[] = frames.map((frame, i) => {
    const g = geometries[i] as FrameGeometry
    const outer = placed[i] as Rect
    const inner = inset(outer, g.profileIn)
    const photoRect = inset(inner, g.matIn)
    const size = FRAME_SIZES.find((s) => s.id === frame.sizeId)
    return {
      id: frame.id,
      number: i + 1,
      outer,
      inner,
      photoRect,
      orientation: frame.orientation,
      finishHex: WOOD_FINISHES.find((f) => f.id === frame.finishId)?.hex ?? '#916843',
      mountHex: frame.mount.enabled
        ? (MOUNT_COLOURS.find((m) => m.id === frame.mount.colourId)?.hex ?? '#F4F3F3')
        : null,
      photo: photoFor(frame.photo, i, frame.orientation, fillWithSamples),
      label: `Frame ${i + 1}, ${size ? `${size.w} × ${size.h} in` : ''} ${frame.orientation}`,
    }
  })

  // Validation (mirrors POST /geometry/validate-layout so results match once it's wired).
  const warnings: SceneWarning[] = []
  const tooWide = arrangement.w > maxWidth + 1e-6
  const tooTall = arrangement.y < margin - 1e-6 || arrangement.y + arrangement.h > H - minBottom + 1e-6
  if (tooWide)
    warnings.push({
      code: 'TOO_WIDE',
      message:
        'The arrangement is wider than the wall allows. Try smaller frames, fewer frames or a narrower gap.',
    })
  if (tooTall)
    warnings.push({
      code: 'TOO_TALL',
      message: preview.sofa
        ? 'The arrangement doesn’t fit between the ceiling and the sofa. Try smaller frames or another layout.'
        : 'The arrangement is taller than the wall allows. Try smaller frames or another layout.',
    })
  const overlap = placed.some((a, i) => placed.some((b, j) => j > i && conflicts(a, b, 0)))
  if (overlap) warnings.push({ code: 'OVERLAP', message: 'Some frames overlap.' })
  const coverage = placed.reduce((s, r) => s + area(r), 0) / (W * H)
  if (coverage < 0.05 && frames.length > 0)
    warnings.push({
      code: 'LOW_COVERAGE',
      message:
        'The arrangement covers very little of the wall. Larger frames or more frames will look more intentional.',
    })

  return {
    wall: { w: W, h: H, paintHex: PAINT_SHADES.find((p) => p.id === wall.paintId)?.hex ?? '#EFDECA' },
    style,
    frames: sceneFrames,
    arrangement,
    eyeLevelY,
    sofaTopY: preview.sofa ? H - sofaTopFromFloor : null,
    fits: !tooWide && !tooTall && !overlap,
    coverage,
    warnings,
  }
}

/* ======================= "Generate Layout" assistant ======================= */

export interface Suggestion {
  style: LayoutStyleId
  variant: number
  scene: Scene
  score: number
}

/**
 * Tries every style × variant for the current frames and wall and ranks them: fitting the wall
 * matters most, then filling ~25% of it, then matching the free space's proportions.
 */
export function suggestLayouts(state: SceneInput): Suggestion[] {
  const results: Suggestion[] = []
  for (const { id: style } of LAYOUT_STYLES) {
    for (let variant = 0; variant < VARIANT_COUNT; variant++) {
      const scene = buildScene(state, { style, variant })
      const a = scene.arrangement
      const free = {
        w: scene.wall.w - 2 * PLANNER_RULES.wallMarginIn,
        h: scene.wall.h - PLANNER_RULES.wallMarginIn - PLANNER_RULES.minBottomIn,
      }
      const aspect = Math.abs(Math.log(a.w / a.h / (free.w / free.h)))
      const coverageMiss = Math.abs(scene.coverage - 0.25)
      const score = (scene.fits ? 0 : 10) + coverageMiss * 2 + aspect * 0.6 + variant * 0.01
      results.push({ style, variant, scene, score })
    }
  }
  return results.sort((a, b) => a.score - b.score)
}
