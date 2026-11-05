import { samplePhotos } from '@/assets/memoryWall'
import type { LengthUnit } from '@/lib/units'
import {
  FRAME_SIZES,
  GAP_UNITS,
  LAYOUT_STYLES,
  MOUNT_COLOURS,
  PAINT_SHADES,
  PLANNER_RULES,
  VARIANT_COUNT,
  WALL_UNITS,
  WOOD_FINISHES,
  type GapUnit,
  type LayoutStyleId,
  type Orientation,
} from '../constants'
import { newSeed } from './geometry/random'

/* ================================== Types ================================== */

export type PhotoRef =
  | { kind: 'sample'; sampleId: string }
  /** Session-only upload (object URL). Not persisted; Phase 5 uploads to /photos. */
  | { kind: 'upload'; url: string; name: string; widthPx: number; heightPx: number }

export interface FrameConfig {
  id: string
  sizeId: string
  orientation: Orientation
  finishId: string
  mount: { enabled: boolean; colourId: string; marginIn: number }
  photo: PhotoRef | null
}

export type FrameStyle = Omit<FrameConfig, 'id' | 'photo'>

export interface PlannerState {
  title: string
  /** Template the current frames came from (highlights the AI preset); null once customised. */
  templateId: string | null
  wall: { widthIn: number; heightIn: number; paintId: string }
  /** Unit for the wall inputs and the canvas dimension labels. */
  displayUnit: LengthUnit
  layout: {
    style: LayoutStyleId
    gapIn: number
    gapUnit: GapUnit
    /** 0 = canonical order; any other value reshuffles which frame goes where. */
    seed: number
    /** Index into the canvas carousel (0..VARIANT_COUNT-1). */
    variant: number
  }
  frames: FrameConfig[]
  selectedIndex: number
  fillWithSamples: boolean
  preview: { sofa: boolean; indexBadges: boolean; guides: boolean }
}

/** What a template prescribes: style + one entry per frame. */
export interface TemplateSpec {
  style: LayoutStyleId
  frames: ReadonlyArray<Pick<FrameConfig, 'sizeId' | 'orientation'> & Partial<Pick<FrameConfig, 'finishId'>>>
  gapIn?: number
}

/* ================================ Defaults ================================= */

const DEFAULT_STYLE: FrameStyle = {
  sizeId: '12x16',
  orientation: 'portrait',
  finishId: 'natural-oak',
  mount: { enabled: true, colourId: 'museum-white', marginIn: 2 },
}

let frameCounter = 0
export const newFrameId = () => `f${Date.now().toString(36)}${(frameCounter++).toString(36)}`

/** Sample photo for the i-th frame, matching its orientation where possible. */
export function sampleFor(index: number, orientation: Orientation): PhotoRef {
  const pool = samplePhotos.filter((p) => p.orientation === orientation)
  const list = pool.length ? pool : samplePhotos
  const photo = list[index % list.length]
  return { kind: 'sample', sampleId: photo?.id ?? 'frame-01' }
}

export function createFrame(
  index: number,
  style: FrameStyle = DEFAULT_STYLE,
  withSample = true,
): FrameConfig {
  // Copy ONLY the style fields: callers may pass a whole FrameConfig (e.g. "add a frame like the
  // last one"), and spreading its id/photo would create duplicate React keys.
  const { sizeId, orientation, finishId, mount } = style
  return {
    id: newFrameId(),
    sizeId,
    orientation,
    finishId,
    mount: { ...mount },
    photo: withSample ? sampleFor(index, orientation) : null,
  }
}

export function createInitialState(): PlannerState {
  return {
    title: 'Living Room Gallery Wall',
    templateId: 'balanced-grid',
    wall: { widthIn: 144, heightIn: 108, paintId: 'warm-cream' },
    displayUnit: 'ft',
    layout: { style: 'grid', gapIn: 3, gapUnit: 'in', seed: 0, variant: 0 },
    frames: Array.from({ length: 9 }, (_, i) => createFrame(i)),
    selectedIndex: 0,
    fillWithSamples: false,
    preview: { sofa: true, indexBadges: true, guides: true },
  }
}

/* ================================= Actions ================================= */

export type PlannerAction =
  | { type: 'wall/setSize'; dimension: 'widthIn' | 'heightIn'; value: number }
  | { type: 'wall/setPaint'; paintId: string }
  | { type: 'unit/set'; unit: LengthUnit }
  | { type: 'layout/setStyle'; style: LayoutStyleId }
  | { type: 'layout/setGap'; gapIn: number }
  | { type: 'layout/setGapUnit'; unit: GapUnit }
  | { type: 'layout/setVariant'; variant: number }
  | { type: 'layout/regenerate'; seed?: number }
  | { type: 'layout/redesign'; seed?: number }
  | { type: 'layout/apply'; style: LayoutStyleId; variant: number }
  | { type: 'frames/setCount'; count: number }
  | { type: 'frames/select'; index: number }
  | { type: 'frames/update'; index: number; patch: Partial<FrameStyle> }
  | { type: 'frames/updateMount'; index: number; patch: Partial<FrameConfig['mount']> }
  | { type: 'frames/applyToAll'; index: number }
  /** By frame id, not index: an upload can finish after frames were added, removed or replaced. */
  | { type: 'frames/setPhoto'; frameId: string; photo: PhotoRef | null }
  | { type: 'samples/toggle'; value: boolean }
  | { type: 'preview/toggle'; key: keyof PlannerState['preview']; value: boolean }
  | { type: 'template/apply'; template: TemplateSpec; templateId?: string }
  | { type: 'design/load'; state: PlannerState }
  | { type: 'design/rename'; title: string }
  | { type: 'reset' }

/* ================================= Reducer ================================= */

const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v))
const isFiniteNumber = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

function patchFrame(state: PlannerState, index: number, fn: (f: FrameConfig) => FrameConfig): PlannerState {
  if (!state.frames[index]) return state
  return { ...state, frames: state.frames.map((f, i) => (i === index ? fn(f) : f)) }
}

const exists = <T extends { id: string }>(list: readonly T[], id: string) => list.some((x) => x.id === id)

/**
 * Pure reducer: every user input maps to one action, and the layout is recomputed from the
 * resulting state (see buildScene). Invalid values are clamped or ignored here, so the UI can
 * never put the planner into an impossible state.
 */
export function plannerReducer(state: PlannerState, action: PlannerAction): PlannerState {
  switch (action.type) {
    case 'wall/setSize': {
      if (!isFiniteNumber(action.value)) return state
      const rule = action.dimension === 'widthIn' ? PLANNER_RULES.wallWidthIn : PLANNER_RULES.wallHeightIn
      return {
        ...state,
        wall: { ...state.wall, [action.dimension]: clamp(action.value, rule.min, rule.max) },
      }
    }
    case 'wall/setPaint':
      return exists(PAINT_SHADES, action.paintId)
        ? { ...state, wall: { ...state.wall, paintId: action.paintId } }
        : state
    case 'unit/set':
      return { ...state, displayUnit: action.unit }
    case 'layout/setStyle':
      return exists(LAYOUT_STYLES, action.style)
        ? { ...state, templateId: null, layout: { ...state.layout, style: action.style, variant: 0 } }
        : state
    case 'layout/setGap':
      if (!isFiniteNumber(action.gapIn)) return state
      return {
        ...state,
        layout: {
          ...state.layout,
          gapIn: clamp(action.gapIn, PLANNER_RULES.gapIn.min, PLANNER_RULES.gapIn.max),
        },
      }
    case 'layout/setGapUnit':
      return { ...state, layout: { ...state.layout, gapUnit: action.unit } }
    case 'layout/setVariant':
      if (!isFiniteNumber(action.variant)) return state
      return {
        ...state,
        layout: {
          ...state.layout,
          variant: ((action.variant % VARIANT_COUNT) + VARIANT_COUNT) % VARIANT_COUNT,
        },
      }
    case 'layout/regenerate':
      return { ...state, layout: { ...state.layout, seed: action.seed ?? newSeed() } }
    case 'layout/redesign': {
      const i = LAYOUT_STYLES.findIndex((s) => s.id === state.layout.style)
      const next = LAYOUT_STYLES[(i + 1) % LAYOUT_STYLES.length]?.id ?? 'grid'
      return {
        ...state,
        templateId: null,
        layout: { ...state.layout, style: next, variant: 0, seed: action.seed ?? newSeed() },
      }
    }
    case 'layout/apply':
      if (!exists(LAYOUT_STYLES, action.style) || !isFiniteNumber(action.variant)) return state
      return {
        ...state,
        layout: {
          ...state.layout,
          style: action.style,
          variant: ((Math.trunc(action.variant) % VARIANT_COUNT) + VARIANT_COUNT) % VARIANT_COUNT,
        },
      }
    case 'frames/setCount': {
      if (!isFiniteNumber(action.count)) return state
      const count = clamp(
        Math.round(action.count),
        PLANNER_RULES.frameCount.min,
        PLANNER_RULES.frameCount.max,
      )
      if (count === state.frames.length) return state
      const template = state.frames[state.frames.length - 1] ?? createFrame(0)
      const frames =
        count < state.frames.length
          ? state.frames.slice(0, count)
          : [
              ...state.frames,
              ...Array.from({ length: count - state.frames.length }, (_, k) =>
                createFrame(state.frames.length + k, template, true),
              ),
            ]
      return { ...state, templateId: null, frames, selectedIndex: Math.min(state.selectedIndex, count - 1) }
    }
    case 'frames/select':
      return state.frames[action.index] ? { ...state, selectedIndex: action.index } : state
    case 'frames/update': {
      const patch = action.patch
      if (patch.sizeId && !exists(FRAME_SIZES, patch.sizeId)) return state
      if (patch.finishId && !exists(WOOD_FINISHES, patch.finishId)) return state
      const next = patchFrame(state, action.index, (f) => ({ ...f, ...patch, mount: patch.mount ?? f.mount }))
      // Changing what a template prescribes (size/orientation) means it's now a custom design.
      return patch.sizeId || patch.orientation ? { ...next, templateId: null } : next
    }
    case 'frames/updateMount': {
      const { colourId, marginIn } = action.patch
      if (colourId && !exists(MOUNT_COLOURS, colourId)) return state
      const safeMargin =
        marginIn === undefined || !isFiniteNumber(marginIn)
          ? undefined
          : clamp(marginIn, PLANNER_RULES.matIn.min, PLANNER_RULES.matIn.max)
      return patchFrame(state, action.index, (f) => ({
        ...f,
        mount: { ...f.mount, ...action.patch, ...(safeMargin === undefined ? {} : { marginIn: safeMargin }) },
      }))
    }
    case 'frames/applyToAll': {
      const source = state.frames[action.index]
      if (!source) return state
      const { sizeId, orientation, finishId, mount } = source
      return {
        ...state,
        templateId: null,
        frames: state.frames.map((f) => ({ ...f, sizeId, orientation, finishId, mount: { ...mount } })),
      }
    }
    case 'frames/setPhoto':
      return patchFrame(
        state,
        state.frames.findIndex((f) => f.id === action.frameId),
        (f) => ({ ...f, photo: action.photo }),
      )
    case 'samples/toggle':
      return { ...state, fillWithSamples: action.value }
    case 'preview/toggle':
      return { ...state, preview: { ...state.preview, [action.key]: action.value } }
    case 'template/apply': {
      const { template } = action
      const frames = template.frames.slice(0, PLANNER_RULES.frameCount.max).map((spec, i) => {
        const previous = state.frames[i]
        const base = createFrame(i, {
          ...DEFAULT_STYLE,
          ...spec,
          mount: previous?.mount ?? DEFAULT_STYLE.mount,
        })
        // Keep the user's photos where the slot already had one.
        return previous?.photo ? { ...base, photo: previous.photo } : base
      })
      if (!frames.length) return state
      return {
        ...state,
        frames,
        selectedIndex: 0,
        templateId: action.templateId ?? null,
        layout: {
          ...state.layout,
          style: template.style,
          gapIn: template.gapIn ?? state.layout.gapIn,
          variant: 0,
          seed: 0,
        },
      }
    }
    case 'design/load':
      return structuredClone(action.state)
    case 'design/rename': {
      const title = action.title.trim().replace(/\s+/g, ' ').slice(0, 80)
      return title ? { ...state, title } : state
    }
    case 'reset':
      return createInitialState()
  }
}

/* ============================== Sanitising ================================= */

type Loose<T> = { [K in keyof T]?: unknown }
const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null
const oneOf = <T extends string>(list: readonly T[], v: unknown, fallback: T): T =>
  list.includes(v as T) ? (v as T) : fallback
const idOf = <T extends { id: string }>(list: readonly T[], v: unknown, fallback: string) =>
  typeof v === 'string' && exists(list, v) ? v : fallback
const numberIn = (v: unknown, rule: { min: number; max: number }, fallback: number) =>
  isFiniteNumber(v) ? clamp(v, rule.min, rule.max) : fallback
const bool = (v: unknown, fallback: boolean) => (typeof v === 'boolean' ? v : fallback)

function sanitizeFrame(value: unknown, seen: Set<string>): FrameConfig | null {
  if (!isObject(value)) return null
  const f = value as Loose<FrameConfig>
  const mount: Loose<FrameConfig['mount']> = isObject(f.mount) ? f.mount : {}
  const photo: unknown = f.photo
  const sample =
    isObject(photo) &&
    photo.kind === 'sample' &&
    typeof photo.sampleId === 'string' &&
    samplePhotos.some((p) => p.id === photo.sampleId)
      ? ({ kind: 'sample', sampleId: photo.sampleId } as const)
      : null
  // Ids become React keys: replace missing or duplicate ones.
  const id = typeof f.id === 'string' && f.id && !seen.has(f.id) ? f.id.slice(0, 64) : newFrameId()
  seen.add(id)
  return {
    id,
    sizeId: idOf(FRAME_SIZES, f.sizeId, DEFAULT_STYLE.sizeId),
    orientation: oneOf(['portrait', 'landscape'], f.orientation, 'portrait'),
    finishId: idOf(WOOD_FINISHES, f.finishId, DEFAULT_STYLE.finishId),
    mount: {
      enabled: bool(mount.enabled, true),
      colourId: idOf(MOUNT_COLOURS, mount.colourId, DEFAULT_STYLE.mount.colourId),
      marginIn: numberIn(mount.marginIn, PLANNER_RULES.matIn, DEFAULT_STYLE.mount.marginIn),
    },
    // Uploads are session object URLs (or, from tampered storage, arbitrary URLs): never restored.
    photo: sample,
  }
}

/**
 * Rebuilds a PlannerState from untrusted data (localStorage now, the /designs API later):
 * unknown ids fall back to defaults, numbers are clamped to the planner rules, and anything that
 * isn't a known sample photo is dropped. Returns null when it isn't recognisably a design.
 */
export function sanitizePlannerState(value: unknown): PlannerState | null {
  if (!isObject(value)) return null
  const s = value as Loose<PlannerState>
  if (!isObject(s.wall) || !Array.isArray(s.frames)) return null
  const wall = s.wall as Loose<PlannerState['wall']>
  if (!isFiniteNumber(wall.widthIn) || !isFiniteNumber(wall.heightIn)) return null

  const seen = new Set<string>()
  const frames = s.frames
    .slice(0, PLANNER_RULES.frameCount.max)
    .map((f) => sanitizeFrame(f, seen))
    .filter((f): f is FrameConfig => f !== null)
  if (!frames.length) return null

  const layout: Loose<PlannerState['layout']> = isObject(s.layout) ? s.layout : {}
  const preview: Loose<PlannerState['preview']> = isObject(s.preview) ? s.preview : {}
  const title = typeof s.title === 'string' ? s.title.trim().replace(/\s+/g, ' ').slice(0, 80) : ''
  const variant = isFiniteNumber(layout.variant) ? Math.trunc(layout.variant) : 0
  const selected = isFiniteNumber(s.selectedIndex) ? Math.trunc(s.selectedIndex) : 0

  return {
    title: title || 'Untitled wall',
    templateId: typeof s.templateId === 'string' ? s.templateId.slice(0, 64) : null,
    wall: {
      widthIn: clamp(wall.widthIn, PLANNER_RULES.wallWidthIn.min, PLANNER_RULES.wallWidthIn.max),
      heightIn: clamp(wall.heightIn, PLANNER_RULES.wallHeightIn.min, PLANNER_RULES.wallHeightIn.max),
      paintId: idOf(PAINT_SHADES, wall.paintId, 'warm-cream'),
    },
    displayUnit: oneOf(WALL_UNITS, s.displayUnit, 'ft'),
    layout: {
      style: oneOf(
        LAYOUT_STYLES.map((l) => l.id),
        layout.style,
        'grid',
      ),
      gapIn: numberIn(layout.gapIn, PLANNER_RULES.gapIn, 3),
      gapUnit: oneOf(GAP_UNITS, layout.gapUnit, 'in'),
      seed: isFiniteNumber(layout.seed) ? Math.trunc(layout.seed) >>> 0 : 0,
      variant: ((variant % VARIANT_COUNT) + VARIANT_COUNT) % VARIANT_COUNT,
    },
    frames,
    selectedIndex: clamp(selected, 0, frames.length - 1),
    fillWithSamples: bool(s.fillWithSamples, false),
    preview: {
      sofa: bool(preview.sofa, true),
      indexBadges: bool(preview.indexBadges, true),
      guides: bool(preview.guides, true),
    },
  }
}
