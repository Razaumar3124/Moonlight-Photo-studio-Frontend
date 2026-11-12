import type {
  DesignDetail,
  DesignItemInput,
  DesignVersion,
  DesignWallInput,
  SaveDesignVersionRequest,
} from '@/types/api'
import type { LengthUnit } from '@/lib/units'
import {
  FRAME_SIZES,
  LAYOUT_STYLES,
  MOUNT_COLOURS,
  PAINT_SHADES,
  WOOD_FINISHES,
  type LayoutStyleId,
  type Orientation,
} from '../constants'
import { frameGeometry, type Scene } from './geometry/scene'
import {
  sampleFor,
  sanitizePlannerState,
  type FrameConfig,
  type PhotoRef,
  type PlannerState,
} from './plannerState'
import { findTemplate } from './templates'
import type { LibraryPhoto } from './photos'
import { toPhotoRef } from './photos'

/* ================================ Planner → API ================================ */

const ITEM_ID_RE = /^[A-Za-z0-9_-]{1,64}$/

/** The server wants unique, URL-safe item ids; the planner's own ids already are, but never trust that. */
export function itemIds(frames: readonly FrameConfig[]): string[] {
  const used = new Set<string>()
  return frames.map((f, i) => {
    let id = ITEM_ID_RE.test(f.id) ? f.id : `f${i + 1}`
    while (used.has(id)) id = `${id.slice(0, 58)}_${i + 1}`
    used.add(id)
    return id
  })
}

export function toDesignWall(state: PlannerState): DesignWallInput {
  return {
    width_inches: state.wall.widthIn,
    height_inches: state.wall.heightIn,
    paint_id: state.wall.paintId,
    display_unit: state.displayUnit,
    has_sofa: state.preview.sofa,
  }
}

/** What the frame shows: its own photo, or the "fill" sample when that preview option is on. */
export function shownPhoto(frame: FrameConfig, index: number, fillWithSamples: boolean): PhotoRef | null {
  return frame.photo ?? (fillWithSamples ? sampleFor(index, frame.orientation) : null)
}

function photoFields(frame: FrameConfig, index: number, fillWithSamples: boolean) {
  // What the user sees is what is saved: an empty frame showing a "fill" sample keeps that sample.
  const ref = shownPhoto(frame, index, fillWithSamples)
  if (ref?.kind === 'upload') return { photo_id: ref.photoId }
  if (ref?.kind === 'sample') return { sample_id: ref.sampleId }
  return {}
}

/**
 * The planner state → POST /designs/{id}/versions. Positions come from the scene (the same
 * geometry the user sees); the server recomputes outer sizes from catalog ids and re-checks the fit.
 */
export function toVersionRequest(state: PlannerState, scene: Scene): SaveDesignVersionRequest {
  const ids = itemIds(state.frames)
  const items: DesignItemInput[] = state.frames.map((frame, i) => {
    const placed = scene.frames[i]
    const g = frameGeometry(frame)
    const margin = frame.mount.marginIn
    return {
      item_id: ids[i] as string,
      size_id: frame.sizeId,
      finish_id: frame.finishId,
      orientation: frame.orientation,
      ...photoFields(frame, i, state.fillWithSamples),
      position_x_inches: round4(placed?.outer.x ?? 0),
      position_y_inches: round4(placed?.outer.y ?? 0),
      photo_width_inches: g.opening.w,
      photo_height_inches: g.opening.h,
      matting: {
        enabled: frame.mount.enabled,
        top_inches: margin,
        bottom_inches: margin,
        left_inches: margin,
        right_inches: margin,
        color_id: frame.mount.colourId,
      },
    }
  })
  return {
    layout_type: state.layout.style,
    template_id: state.templateId,
    items,
    layout_metadata: {
      style: state.layout.style,
      gap_inches: state.layout.gapIn,
      gap_unit: state.layout.gapUnit,
      seed: state.layout.seed,
      variant: state.layout.variant,
    },
    preview: {
      sofa: state.preview.sofa,
      index_badges: state.preview.indexBadges,
      guides: state.preview.guides,
    },
  }
}

const round4 = (n: number) => Math.round(n * 10000) / 10000

/**
 * What identifies "the saved content" of a design: everything a version stores, nothing about the
 * editing session (selected frame). Equal fingerprints mean there is nothing new to save.
 */
export function designFingerprint(state: PlannerState): string {
  return JSON.stringify([
    state.title,
    state.templateId,
    state.wall,
    state.displayUnit,
    state.layout,
    state.fillWithSamples,
    state.preview,
    state.frames.map((f) => [f.id, f.sizeId, f.orientation, f.finishId, f.mount, f.photo]),
  ])
}

/* ================================ API → planner ================================ */

/** Legacy layout names the server may still return for older versions. */
const LAYOUT_ALIASES: Record<string, LayoutStyleId> = {
  focal_center: 'centre',
  center: 'centre',
  linear: 'row',
  triptych: 'row',
}

function layoutStyleOf(version: DesignVersion): LayoutStyleId {
  const raw = String(version.layout_metadata?.style ?? version.layout_type ?? '')
  const id = LAYOUT_ALIASES[raw] ?? raw
  return LAYOUT_STYLES.some((s) => s.id === id) ? (id as LayoutStyleId) : 'grid'
}

/** The catalog size whose opening matches (in either orientation), if any. */
function sizeForOpening(w: number, h: number): { sizeId: string; orientation: Orientation } | null {
  const close = (a: number, b: number) => Math.abs(a - b) < 0.05
  for (const s of FRAME_SIZES) {
    if (close(s.w, w) && close(s.h, h)) return { sizeId: s.id, orientation: 'portrait' }
    if (close(s.h, w) && close(s.w, h)) return { sizeId: s.id, orientation: 'landscape' }
  }
  return null
}

const nearestHex = (list: readonly { id: string; hex: string }[], hex: string | null | undefined) =>
  hex ? list.find((x) => x.hex.toLowerCase() === hex.toLowerCase())?.id : undefined

export interface LoadedDesign {
  state: PlannerState
  /** Plain-language notes about anything that had to be approximated or is no longer available. */
  notes: string[]
  /** Photos the design references that are gone from the library. */
  missingPhotos: number
}

/**
 * GET /designs/{id} → a planner state. Tolerant by design: designs saved under older rules,
 * legacy layout names, `mm` units, missing catalog ids and deleted photos all load, with notes
 * about what changed. The result passes through the same sanitiser as any untrusted data.
 */
export function fromDesignDetail(
  detail: DesignDetail,
  photos: ReadonlyMap<string, LibraryPhoto>,
): LoadedDesign | null {
  const version = detail.current_version
  if (!version || version.items.length === 0) return null

  const notes: string[] = []
  let approximated = 0
  let missingPhotos = 0

  const frames = version.items.map((item) => {
    let sizeId = item.size_id && FRAME_SIZES.some((s) => s.id === item.size_id) ? item.size_id : undefined
    let orientation: Orientation = item.orientation === 'landscape' ? 'landscape' : 'portrait'
    if (!sizeId) {
      const match = sizeForOpening(item.photo_width_inches, item.photo_height_inches)
      if (match) {
        sizeId = match.sizeId
        orientation = match.orientation
      } else approximated += 1
    }
    const finishId =
      item.finish_id && WOOD_FINISHES.some((f) => f.id === item.finish_id) ? item.finish_id : undefined
    if (!finishId) approximated += 1
    const colourId =
      (item.matting.color_id && MOUNT_COLOURS.some((m) => m.id === item.matting.color_id)
        ? item.matting.color_id
        : undefined) ?? nearestHex(MOUNT_COLOURS, item.matting.color_hex)

    let photo: PhotoRef | null = null
    if (item.photo_id) {
      const found = photos.get(item.photo_id)
      if (found && !item.photo_missing) photo = toPhotoRef(found)
      else missingPhotos += 1
    } else if (item.sample_id) {
      photo = { kind: 'sample', sampleId: item.sample_id }
    }

    return {
      id: item.item_id,
      sizeId,
      orientation,
      finishId,
      mount: {
        enabled: item.matting.enabled,
        colourId,
        marginIn: item.matting.top_inches,
      },
      photo,
    }
  })

  const meta = version.layout_metadata ?? {}
  const preview = version.preview ?? {}
  const wall = detail.wall
  const unit = wall.display_unit === 'mm' ? 'cm' : wall.display_unit
  const paintId =
    (wall.paint_id && PAINT_SHADES.some((p) => p.id === wall.paint_id) ? wall.paint_id : undefined) ??
    nearestHex(PAINT_SHADES, wall.color_hex)

  const raw = {
    title: detail.title,
    templateId: version.template_id && findTemplate(version.template_id) ? version.template_id : null,
    wall: { widthIn: wall.width_inches, heightIn: wall.height_inches, paintId },
    displayUnit: unit as LengthUnit,
    layout: {
      style: layoutStyleOf(version),
      gapIn: meta.gap_inches,
      gapUnit: meta.gap_unit,
      seed: meta.seed,
      variant: meta.variant,
    },
    frames,
    selectedIndex: 0,
    fillWithSamples: false,
    preview: {
      sofa: preview.sofa ?? wall.has_sofa,
      indexBadges: preview.index_badges,
      guides: preview.guides,
    },
  }
  const state = sanitizePlannerState(raw)
  if (!state) return null

  if (approximated) {
    notes.push(
      'Some frame options in this design are no longer offered, so the closest standard ones are shown.',
    )
  }
  if (missingPhotos) {
    notes.push(
      `${missingPhotos} ${missingPhotos === 1 ? 'photo is' : 'photos are'} no longer in your library, so those frames are empty.`,
    )
  }
  return { state, notes, missingPhotos }
}
