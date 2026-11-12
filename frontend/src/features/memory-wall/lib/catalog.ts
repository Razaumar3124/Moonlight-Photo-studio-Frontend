import { catalogService } from '@/services/catalogService'
import type { LayoutTemplate, PlannerCatalog } from '@/types/api'
import type { LengthUnit } from '@/lib/units'
import {
  FRAME_SIZES,
  installCatalog,
  LAYOUT_STYLES,
  type CatalogData,
  type FrameSize,
  type LayoutStyleId,
  type Orientation,
  type Swatch,
  type WoodFinish,
} from '../constants'
import { installTemplates, TEMPLATES, type PlannerTemplate } from './templates'

/**
 * Loads the planner catalog (GET /catalog) and templates (GET /templates), the source of truth
 * for every option the planner offers, and installs them over the bundled defaults.
 *
 * Everything from the network is validated first: a catalog that is malformed, or missing a whole
 * list, is rejected as a whole and the bundled defaults stay (they are contract-tested to match the
 * backend). Templates are installed one by one: a template that refers to a size the catalog doesn't
 * have is skipped, never half-applied.
 */

const ID_RE = /^[a-z0-9][a-z0-9-]{0,39}$/
const HEX_RE = /^#[0-9a-fA-F]{3,8}$/
const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null
const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const str = (v: unknown, max = 120): v is string => typeof v === 'string' && v.length > 0 && v.length <= max

function range(v: unknown, lo: number, hi: number): { min: number; max: number } | null {
  if (!isObject(v) || !num(v.min) || !num(v.max)) return null
  return v.min >= lo && v.max <= hi && v.min <= v.max ? { min: v.min, max: v.max } : null
}

function list<T extends { id: string }>(v: unknown, map: (item: unknown) => T | null, max = 64): T[] | null {
  if (!Array.isArray(v) || v.length === 0 || v.length > max) return null
  const out: T[] = []
  const seen = new Set<string>()
  for (const item of v) {
    const mapped = map(item)
    if (!mapped || seen.has(mapped.id)) return null
    seen.add(mapped.id)
    out.push(mapped)
  }
  return out
}

const swatch = (v: unknown): Swatch | null =>
  isObject(v) && str(v.id) && ID_RE.test(v.id) && str(v.label) && str(v.hex) && HEX_RE.test(v.hex)
    ? { id: v.id, label: v.label, hex: v.hex }
    : null

const finish = (v: unknown): WoodFinish | null => {
  const base = swatch(v)
  const o = v as Record<string, unknown>
  return base && num(o.profile_inches) && o.profile_inches >= 0 && o.profile_inches <= 3
    ? { ...base, profileIn: o.profile_inches }
    : null
}

const size = (v: unknown): FrameSize | null =>
  isObject(v) &&
  str(v.id) &&
  ID_RE.test(v.id) &&
  str(v.label, 200) &&
  num(v.width_inches) &&
  num(v.height_inches) &&
  v.width_inches > 0 &&
  v.height_inches > 0 &&
  v.width_inches <= 200 &&
  v.height_inches <= 200
    ? {
        id: v.id,
        w: v.width_inches,
        h: v.height_inches,
        label: v.label,
        recommended: v.recommended === true || undefined,
      }
    : null

const UNITS: readonly LengthUnit[] = ['ft', 'in', 'cm', 'm']

/** Validate a GET /catalog body. `null` means "don't trust it". */
export function parsePlannerCatalog(raw: unknown): CatalogData | null {
  if (!isObject(raw) || !isObject(raw.rules)) return null
  const frameSizes = list(raw.frame_sizes, size)
  const woodFinishes = list(raw.frame_finishes, finish)
  const mountColours = list(raw.mount_colors, swatch)
  const paintShades = list(raw.paint_shades, swatch)
  if (!frameSizes || !woodFinishes || !mountColours || !paintShades) return null

  const r = raw.rules
  const wallWidth = range(r.wall_width_inches, 1, 2000)
  const wallHeight = range(r.wall_height_inches, 1, 2000)
  const gap = range(r.gap_inches, 0, 100)
  const mat = range(r.mat_inches, 0, 50)
  const frames = range(r.frame_count, 1, 64)
  if (!wallWidth || !wallHeight || !gap || !mat || !frames) return null
  if (
    !num(r.eye_level_inches) ||
    !num(r.wall_margin_inches) ||
    !num(r.min_bottom_inches) ||
    !num(r.sofa_clearance_inches) ||
    !num(r.mat_step_inches) ||
    !num(r.variant_count) ||
    r.mat_step_inches <= 0 ||
    r.variant_count < 1 ||
    r.variant_count > 8 ||
    r.eye_level_inches <= 0 ||
    r.wall_margin_inches < 0 ||
    r.min_bottom_inches < 0 ||
    r.sofa_clearance_inches < 0
  ) {
    return null
  }

  const units = Array.isArray(raw.wall_units)
    ? UNITS.filter((u) => (raw.wall_units as unknown[]).includes(u))
    : []
  if (units.length === 0) return null

  return {
    frameSizes,
    woodFinishes,
    mountColours,
    paintShades,
    wallUnits: units,
    variantCount: Math.trunc(r.variant_count),
    rules: {
      eyeLevelIn: r.eye_level_inches,
      wallMarginIn: r.wall_margin_inches,
      minBottomIn: r.min_bottom_inches,
      sofaClearanceIn: r.sofa_clearance_inches,
      wallWidthIn: wallWidth,
      wallHeightIn: wallHeight,
      gapIn: gap,
      matIn: { ...mat, step: r.mat_step_inches },
      frameCount: frames,
    },
  }
}

const LEGACY_STYLE: Record<string, LayoutStyleId> = {
  focal_center: 'centre',
  center: 'centre',
  linear: 'row',
  triptych: 'row',
}

/** Convert GET /templates to planner templates; invalid ones are skipped. */
export function parseTemplates(
  raw: readonly LayoutTemplate[] | unknown,
  fallbackGaps: ReadonlyMap<string, number> = new Map(),
): PlannerTemplate[] {
  if (!Array.isArray(raw)) return []
  const out: PlannerTemplate[] = []
  const seen = new Set<string>()
  for (const t of raw as unknown[]) {
    if (!isObject(t) || !str(t.slug) || !ID_RE.test(t.slug) || seen.has(t.slug)) continue
    if (!str(t.name, 80) || !Array.isArray(t.slots) || t.slots.length === 0 || t.slots.length > 16) continue
    const categoryRaw = String(t.category)
    const style = LEGACY_STYLE[categoryRaw] ?? (categoryRaw as LayoutStyleId)
    if (!LAYOUT_STYLES.some((s) => s.id === style)) continue

    const frames: PlannerTemplate['frames'][number][] = []
    for (const slot of t.slots as unknown[]) {
      if (!isObject(slot) || !str(slot.size_id) || !FRAME_SIZES.some((s) => s.id === slot.size_id)) break
      const orientation: Orientation = slot.orientation === 'landscape' ? 'landscape' : 'portrait'
      frames.push({ sizeId: slot.size_id, orientation })
    }
    if (frames.length !== t.slots.length) continue

    seen.add(t.slug)
    // Templates seeded before gap_inches existed have null: keep the bundled gap for that slug.
    const gap = num(t.gap_inches) ? t.gap_inches : fallbackGaps.get(t.slug)
    out.push({
      id: t.slug,
      name: t.name,
      description: typeof t.description === 'string' ? t.description.slice(0, 200) : '',
      style,
      frames,
      ...(gap === undefined ? {} : { gapIn: gap }),
    })
  }
  return out
}

export type CatalogLoad =
  | { source: 'server'; version: string; templates: 'server' | 'bundled' }
  | { source: 'bundled'; reason: 'unreachable' | 'invalid' }

let pending: Promise<CatalogLoad> | null = null
let settled: CatalogLoad | null = null

async function load(): Promise<CatalogLoad> {
  let raw: PlannerCatalog
  try {
    raw = await catalogService.planner()
  } catch {
    return { source: 'bundled', reason: 'unreachable' }
  }
  const data = parsePlannerCatalog(raw)
  if (!data) return { source: 'bundled', reason: 'invalid' }
  installCatalog(data)

  let templates: 'server' | 'bundled' = 'bundled'
  try {
    const res = await catalogService.templates()
    const gaps = new Map(TEMPLATES.flatMap((t) => (t.gapIn === undefined ? [] : [[t.id, t.gapIn] as const])))
    const parsed = parseTemplates(res.items, gaps)
    if (parsed.length > 0) {
      installTemplates(parsed)
      templates = 'server'
    }
  } catch {
    // Templates are a convenience: the bundled ones keep working.
  }
  return { source: 'server', version: String(raw.version), templates }
}

/**
 * Load once per page visit. A failed attempt is not cached, so "Try again" (or reopening the
 * planner) retries; a successful one is reused.
 */
export function loadCatalog(force = false): Promise<CatalogLoad> {
  if (settled?.source === 'server' && !force) return Promise.resolve(settled)
  pending ??= load()
    .then((result) => {
      settled = result
      return result
    })
    .finally(() => {
      pending = null
    })
  return pending
}
