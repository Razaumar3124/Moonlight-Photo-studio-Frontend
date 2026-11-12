import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as constants from '../constants'
import type { LayoutTemplate, PlannerCatalog } from '@/types/api'

const first = <T>(list: readonly T[]): T => {
  const item = list[0]
  if (item === undefined) throw new Error('empty')
  return item
}

const ORIGINAL = {
  sizes: constants.FRAME_SIZES,
  finishes: constants.WOOD_FINISHES,
  mounts: constants.MOUNT_COLOURS,
  paints: constants.PAINT_SHADES,
  units: constants.WALL_UNITS,
  rules: constants.PLANNER_RULES,
  variants: constants.VARIANT_COUNT,
}

function backendCatalog(overrides: Partial<PlannerCatalog> = {}): PlannerCatalog {
  return {
    version: '2099-01-01',
    frame_sizes: [
      { id: '12x16', label: '12 x 16 inches', width_inches: 12, height_inches: 16, recommended: true },
      { id: '30x40', label: '30 x 40 inches', width_inches: 30, height_inches: 40, recommended: false },
    ],
    frame_finishes: [
      { id: 'natural-oak', label: 'Natural Oak', hex: '#916843', profile_inches: 1 },
      { id: 'ebony', label: 'Ebony', hex: '#1b1b1b', profile_inches: 1.25 },
    ],
    mount_colors: [{ id: 'museum-white', label: 'Museum White', hex: '#F4F3F3' }],
    paint_shades: [{ id: 'warm-cream', label: 'Warm Cream', hex: '#EFDECA' }],
    layout_styles: [
      { id: 'grid', label: 'Grid' },
      { id: 'salon', label: 'Salon' },
      { id: 'centre', label: 'Centre' },
      { id: 'row', label: 'Row' },
    ],
    template_ids: ['balanced-grid'],
    wall_units: ['ft', 'in', 'cm', 'm'],
    gap_units: ['in', 'cm'],
    rules: {
      eye_level_inches: 58,
      wall_margin_inches: 5,
      min_bottom_inches: 10,
      sofa_top_from_floor_inches: 14.5689,
      sofa_clearance_inches: 8,
      wall_width_inches: { min: 30, max: 500 },
      wall_height_inches: { min: 40, max: 250 },
      gap_inches: { min: 0, max: 10 },
      mat_inches: { min: 0, max: 5 },
      mat_step_inches: 0.5,
      frame_count: { min: 1, max: 12 },
      variant_count: 3,
    },
    ...overrides,
  }
}

const tpl = (over: Partial<LayoutTemplate> = {}): LayoutTemplate => ({
  id: '672522012e5c6a1b2c3d5001',
  slug: 'server-trio',
  name: 'Server Trio',
  description: 'From the API',
  category: 'row',
  gap_inches: 2,
  min_wall_width_inches: 80,
  min_wall_height_inches: 60,
  recommended_wall_width_inches: 120,
  recommended_wall_height_inches: 96,
  slots_count: 3,
  slots: [1, 2, 3].map((n) => ({
    slot_id: `slot-${n}`,
    relative_x_ratio: 0.3,
    relative_y_ratio: 0.4,
    default_photo_width_inches: 16,
    default_photo_height_inches: 12,
    aspect_ratio: 1.33,
    size_id: '12x16',
    orientation: 'landscape' as const,
  })),
  thumbnail_url: '/static/x.webp',
  ...over,
})

describe('parsePlannerCatalog', () => {
  it('converts a valid backend catalog', async () => {
    const { parsePlannerCatalog } = await import('./catalog')
    const data = parsePlannerCatalog(backendCatalog())
    expect(data?.frameSizes.map((s) => [s.id, s.w, s.h, s.recommended])).toEqual([
      ['12x16', 12, 16, true],
      ['30x40', 30, 40, undefined],
    ])
    expect(data?.woodFinishes[1]).toEqual({ id: 'ebony', label: 'Ebony', hex: '#1b1b1b', profileIn: 1.25 })
    expect(data?.rules).toMatchObject({
      eyeLevelIn: 58,
      wallMarginIn: 5,
      minBottomIn: 10,
      wallWidthIn: { min: 30, max: 500 },
      matIn: { min: 0, max: 5, step: 0.5 },
      frameCount: { min: 1, max: 12 },
    })
  })

  it.each([
    ['not an object', null],
    ['a missing list', { ...backendCatalog(), frame_sizes: undefined }],
    ['an empty list', backendCatalog({ frame_finishes: [] })],
    [
      'a duplicate id',
      backendCatalog({
        mount_colors: [first(backendCatalog().mount_colors), first(backendCatalog().mount_colors)],
      }),
    ],
    ['a hostile id', backendCatalog({ paint_shades: [{ id: '../x', label: 'x', hex: '#fff' }] })],
    [
      'a non-colour hex',
      backendCatalog({ paint_shades: [{ id: 'x', label: 'x', hex: 'url(javascript:1)' }] }),
    ],
    [
      'a negative size',
      backendCatalog({
        frame_sizes: [{ id: 'a', label: 'a', width_inches: -1, height_inches: 5, recommended: false }],
      }),
    ],
    [
      'an absurd profile',
      backendCatalog({ frame_finishes: [{ id: 'a', label: 'a', hex: '#fff', profile_inches: 99 }] }),
    ],
    [
      'inverted rule range',
      backendCatalog({ rules: { ...backendCatalog().rules, frame_count: { min: 9, max: 2 } } }),
    ],
    ['NaN rule', backendCatalog({ rules: { ...backendCatalog().rules, eye_level_inches: Number.NaN } })],
    ['no usable units', backendCatalog({ wall_units: [] })],
  ])('rejects %s as a whole', async (_name, raw) => {
    const { parsePlannerCatalog } = await import('./catalog')
    expect(parsePlannerCatalog(raw)).toBeNull()
  })
})

describe('parseTemplates', () => {
  it('maps slots to catalog sizes and keeps the API gap', async () => {
    const { parseTemplates } = await import('./catalog')
    const [t] = parseTemplates([tpl()])
    expect(t).toMatchObject({ id: 'server-trio', style: 'row', gapIn: 2 })
    expect(t?.frames).toEqual([
      { sizeId: '12x16', orientation: 'landscape' },
      { sizeId: '12x16', orientation: 'landscape' },
      { sizeId: '12x16', orientation: 'landscape' },
    ])
  })

  it('normalises legacy categories and falls back to the bundled gap when the API has none', async () => {
    const { parseTemplates } = await import('./catalog')
    const [t] = parseTemplates(
      [tpl({ category: 'triptych' as never, gap_inches: null })],
      new Map([['server-trio', 3.5]]),
    )
    expect(t).toMatchObject({ style: 'row', gapIn: 3.5 })
  })

  it('skips templates it cannot represent instead of half-applying them', async () => {
    const { parseTemplates } = await import('./catalog')
    const slots = tpl().slots
    const result = parseTemplates([
      tpl({ slug: 'unknown-size', slots: [{ ...first(slots), size_id: '99x99' }] }),
      tpl({ slug: 'non-standard', slots: [{ ...first(slots), size_id: null }] }),
      tpl({ slug: 'bad-category', category: 'spiral' as never }),
      tpl({ slug: 'no-slots', slots: [] }),
      tpl({ slug: '../evil' }),
      tpl({ slug: 'good' }),
      tpl({ slug: 'good' }), // duplicate
    ])
    expect(result.map((t) => t.id)).toEqual(['good'])
  })

  it('returns nothing for a malformed body', async () => {
    const { parseTemplates } = await import('./catalog')
    expect(parseTemplates('nope')).toEqual([])
    expect(parseTemplates(null)).toEqual([])
  })
})

describe('loadCatalog', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  afterEach(async () => {
    // Put the bundled defaults back: they are module state shared by the other test files.
    const c = await import('../constants')
    c.installCatalog({
      frameSizes: ORIGINAL.sizes,
      woodFinishes: ORIGINAL.finishes,
      mountColours: ORIGINAL.mounts,
      paintShades: ORIGINAL.paints,
      wallUnits: ORIGINAL.units,
      rules: ORIGINAL.rules,
      variantCount: ORIGINAL.variants,
    })
    vi.doUnmock('@/services/catalogService')
  })

  async function withService(planner: () => Promise<unknown>, templates: () => Promise<unknown>) {
    vi.doMock('@/services/catalogService', () => ({ catalogService: { planner, templates } }))
    const c = await import('../constants')
    const t = await import('./templates')
    const { loadCatalog } = await import('./catalog')
    return { c, t, loadCatalog }
  }

  it('installs the backend catalog and templates before the planner uses them', async () => {
    const { c, t, loadCatalog } = await withService(
      async () => backendCatalog(),
      async () => ({ items: [tpl()], total: 1 }),
    )
    expect(c.FRAME_SIZES.map((s) => s.id)).toEqual([
      '5x7',
      '8x10',
      '11x14',
      '12x16',
      '16x20',
      '18x24',
      '20x30',
      '24x36',
    ])
    const result = await loadCatalog()
    expect(result).toEqual({ source: 'server', version: '2099-01-01', templates: 'server' })
    expect(c.FRAME_SIZES.map((s) => s.id)).toEqual(['12x16', '30x40'])
    expect(c.PLANNER_RULES.eyeLevelIn).toBe(58)
    expect(c.PLANNER_RULES.frameCount.max).toBe(12)
    expect(t.TEMPLATES.map((x) => x.id)).toEqual(['server-trio'])
  })

  it('keeps the bundled defaults when the catalog cannot be fetched, and retries next time', async () => {
    let attempts = 0
    const { c, loadCatalog } = await withService(
      async () => {
        attempts += 1
        if (attempts === 1) throw new Error('offline')
        return backendCatalog()
      },
      async () => ({ items: [], total: 0 }),
    )
    expect(await loadCatalog()).toEqual({ source: 'bundled', reason: 'unreachable' })
    expect(c.FRAME_SIZES).toHaveLength(8)
    expect((await loadCatalog()).source).toBe('server') // a failure is not cached
    expect(c.FRAME_SIZES).toHaveLength(2)
  })

  it('keeps the bundled defaults when the catalog is malformed', async () => {
    const { c, loadCatalog } = await withService(
      async () => ({ version: 'x', frame_sizes: 'nope' }),
      async () => ({ items: [], total: 0 }),
    )
    expect(await loadCatalog()).toEqual({ source: 'bundled', reason: 'invalid' })
    expect(c.FRAME_SIZES).toHaveLength(8)
  })

  it('keeps bundled templates when only the templates request fails', async () => {
    const { t, loadCatalog } = await withService(
      async () => backendCatalog(),
      async () => {
        throw new Error('boom')
      },
    )
    const before = t.TEMPLATES.length
    expect(await loadCatalog()).toMatchObject({ source: 'server', templates: 'bundled' })
    expect(t.TEMPLATES).toHaveLength(before)
  })

  it('shares one request between concurrent callers', async () => {
    const planner = vi.fn<() => Promise<PlannerCatalog>>(async () => backendCatalog())
    const { loadCatalog } = await withService(planner, async () => ({ items: [], total: 0 }))
    await Promise.all([loadCatalog(), loadCatalog(), loadCatalog()])
    expect(planner).toHaveBeenCalledTimes(1)
  })
})
