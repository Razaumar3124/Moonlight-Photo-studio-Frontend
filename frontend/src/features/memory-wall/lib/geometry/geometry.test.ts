import { describe, expect, it } from 'vitest'
import { PLANNER_RULES, ROOM_PHOTO_IN } from '../../constants'
import { createFrame, createInitialState, plannerReducer, type PlannerState } from '../plannerState'
import { LAYOUTS, type LayoutStyle } from './layouts'
import { createRng } from './random'
import { bounds, conflicts, EPS, type Size } from './rect'
import { buildScene, frameGeometry, suggestLayouts } from './scene'

const STYLES = Object.keys(LAYOUTS) as LayoutStyle[]

function randomSizes(n: number, seed: number): Size[] {
  const rng = createRng(seed)
  return Array.from({ length: n }, () => ({ w: 6 + Math.round(rng() * 30), h: 6 + Math.round(rng() * 30) }))
}

describe('layout algorithms: invariants for every style', () => {
  // 4 styles × 16 counts × 3 size mixes × 4 variants × 2 gaps = 1,536 layouts.
  for (const style of STYLES) {
    it(`${style}: one rect per frame, sizes preserved, never closer than the gap, normalised`, () => {
      for (let n = 1; n <= 16; n++) {
        for (const sizeSeed of [1, 2, 3]) {
          const sizes = randomSizes(n, sizeSeed * 97 + n)
          for (const variant of [0, 1, 2, 5]) {
            for (const gap of [0, 3]) {
              const rects = LAYOUTS[style]({ sizes, gap, maxWidth: 132, maxHeight: 70, variant, seed: 42 })
              expect(rects).toHaveLength(n)
              rects.forEach((r, i) => {
                expect(r.w).toBeCloseTo(sizes[i]?.w ?? NaN)
                expect(r.h).toBeCloseTo(sizes[i]?.h ?? NaN)
              })
              for (let i = 0; i < n; i++)
                for (let j = i + 1; j < n; j++) {
                  const a = rects[i]
                  const b = rects[j]
                  if (a && b && conflicts(a, b, gap))
                    throw new Error(`${style} n=${n} v=${variant} gap=${gap}: ${i}↔${j} too close`)
                }
              const b = bounds(rects)
              expect(Math.abs(b.x)).toBeLessThan(EPS)
              expect(Math.abs(b.y)).toBeLessThan(EPS)
            }
          }
        }
      }
    })

    it(`${style}: deterministic for the same seed and variant`, () => {
      const input = { sizes: randomSizes(9, 7), gap: 2, maxWidth: 120, maxHeight: 80, variant: 1, seed: 1234 }
      expect(LAYOUTS[style](input)).toEqual(LAYOUTS[style](input))
    })
  }

  it('grid: 9 equal frames on a 4:3 free area → 3 × 3 with exact gaps', () => {
    const rects = LAYOUTS.grid({
      sizes: Array.from({ length: 9 }, () => ({ w: 18, h: 22 })),
      gap: 3,
      maxWidth: 132,
      maxHeight: 88,
      variant: 0,
      seed: 0,
    })
    expect(new Set(rects.map((r) => r.x)).size).toBe(3)
    expect(new Set(rects.map((r) => r.y)).size).toBe(3)
    expect(bounds(rects)).toMatchObject({ w: 3 * 18 + 2 * 3, h: 3 * 22 + 2 * 3 })
  })

  it('grid: a short last row is centred under the full rows', () => {
    const rects = LAYOUTS.grid({
      sizes: Array.from({ length: 5 }, () => ({ w: 10, h: 10 })),
      gap: 2,
      maxWidth: 40,
      maxHeight: 40,
      variant: 0,
      seed: 0,
    })
    const b = bounds(rects)
    const lastRow = rects.filter((r) => r.y > 0)
    const lb = bounds(lastRow)
    expect(lb.x + lb.w / 2).toBeCloseTo(b.w / 2)
  })

  it('row: wraps into several centred lines when the wall is too narrow', () => {
    const rects = LAYOUTS.row({
      sizes: Array.from({ length: 6 }, () => ({ w: 20, h: 20 })),
      gap: 2,
      maxWidth: 70,
      maxHeight: 100,
      variant: 0,
      seed: 0,
    })
    expect(new Set(rects.map((r) => r.y)).size).toBeGreaterThan(1)
    expect(bounds(rects).w).toBeLessThanOrEqual(70)
  })

  it('row: variant 1 aligns tops, variant 2 aligns bottoms', () => {
    const sizes = [
      { w: 10, h: 10 },
      { w: 10, h: 20 },
    ]
    const tops = LAYOUTS.row({ sizes, gap: 1, maxWidth: 100, maxHeight: 100, variant: 1, seed: 0 })
    expect(tops[0]?.y).toBeCloseTo(tops[1]?.y ?? NaN)
    const bottoms = LAYOUTS.row({ sizes, gap: 1, maxWidth: 100, maxHeight: 100, variant: 2, seed: 0 })
    expect((bottoms[0]?.y ?? 0) + 10).toBeCloseTo((bottoms[1]?.y ?? 0) + 20)
  })

  it('centre: the largest frame is the horizontal centre of the composition', () => {
    const sizes = [
      { w: 10, h: 12 },
      { w: 30, h: 40 },
      { w: 10, h: 12 },
      { w: 10, h: 12 },
      { w: 10, h: 12 },
    ]
    const rects = LAYOUTS.centre({ sizes, gap: 2, maxWidth: 120, maxHeight: 80, variant: 0, seed: 0 })
    const hero = rects[1]
    const b = bounds(rects)
    expect((hero?.x ?? 0) + 15).toBeCloseTo(b.w / 2)
  })
})

describe('frameGeometry', () => {
  it('adds mat and moulding on every side; landscape swaps the opening', () => {
    const g = frameGeometry({
      sizeId: '12x16',
      orientation: 'landscape',
      finishId: 'natural-oak',
      mount: { enabled: true, colourId: 'museum-white', marginIn: 2 },
    })
    expect(g.opening).toEqual({ w: 16, h: 12 })
    expect(g.outer).toEqual({ w: 16 + 2 * (2 + 1), h: 12 + 2 * (2 + 1) })
  })
  it('ignores the mat margin when the mount is off', () => {
    const g = frameGeometry({
      sizeId: '8x10',
      orientation: 'portrait',
      finishId: 'walnut',
      mount: { enabled: false, colourId: 'museum-white', marginIn: 4 },
    })
    expect(g.outer).toEqual({ w: 10, h: 12 })
  })
})

describe('buildScene: placement on the wall', () => {
  const base = createInitialState()

  it('default 3×3 grid sits centred, at eye level, above the sofa, and fits', () => {
    const s = buildScene(base)
    expect(s.fits).toBe(true)
    expect(s.arrangement.x + s.arrangement.w / 2).toBeCloseTo(s.wall.w / 2)
    expect(s.arrangement.y + s.arrangement.h / 2).toBeCloseTo(s.wall.h - PLANNER_RULES.eyeLevelIn)
    expect(s.wall.h - (s.arrangement.y + s.arrangement.h)).toBeGreaterThanOrEqual(
      ROOM_PHOTO_IN.sofaTopFromFloor + PLANNER_RULES.sofaClearanceIn - EPS,
    )
  })

  it('recalculates when any input changes', () => {
    const before = buildScene(base)
    const changes: PlannerState[] = [
      plannerReducer(base, { type: 'layout/setGap', gapIn: 6 }),
      plannerReducer(base, { type: 'frames/update', index: 0, patch: { sizeId: '24x36' } }),
      plannerReducer(base, { type: 'frames/update', index: 2, patch: { orientation: 'landscape' } }),
      plannerReducer(base, { type: 'frames/updateMount', index: 0, patch: { marginIn: 5 } }),
      plannerReducer(base, { type: 'frames/setCount', count: 6 }),
      plannerReducer(base, { type: 'wall/setSize', dimension: 'widthIn', value: 200 }),
      plannerReducer(base, { type: 'layout/setStyle', style: 'salon' }),
      plannerReducer(base, { type: 'layout/regenerate', seed: 99 }),
    ]
    for (const next of changes) {
      expect(JSON.stringify(buildScene(next).frames.map((f) => f.outer))).not.toBe(
        JSON.stringify(before.frames.map((f) => f.outer)),
      )
    }
  })

  it('adapts the grid shape to a low wall instead of overflowing', () => {
    // 84" wall: 3×3 (72" tall) can't clear the sofa, so the grid goes wider (e.g. 5×2) and fits.
    const low = plannerReducer(base, { type: 'wall/setSize', dimension: 'heightIn', value: 84 })
    const s = buildScene(low)
    expect(s.fits).toBe(true)
    expect(s.wall.h - (s.arrangement.y + s.arrangement.h)).toBeGreaterThanOrEqual(
      ROOM_PHOTO_IN.sofaTopFromFloor + PLANNER_RULES.sofaClearanceIn - EPS,
    )
  })

  it('flags walls that are genuinely too small', () => {
    // 60" wall with 24×36 statement frames: no arrangement can fit above the sofa.
    let tiny = plannerReducer(base, { type: 'wall/setSize', dimension: 'heightIn', value: 60 })
    tiny = plannerReducer(tiny, { type: 'frames/update', index: 0, patch: { sizeId: '24x36' } })
    const s = buildScene(tiny)
    expect(s.fits).toBe(false)
    expect(s.warnings.map((w) => w.code)).toContain('TOO_TALL')

    const narrow = plannerReducer(base, { type: 'wall/setSize', dimension: 'widthIn', value: 36 })
    expect(buildScene(narrow).warnings.map((w) => w.code)).toContain('TOO_WIDE')
  })

  it('without the sofa, the arrangement can sit lower and still respects the minimum height', () => {
    const noSofa = plannerReducer(base, { type: 'preview/toggle', key: 'sofa', value: false })
    const s = buildScene(noSofa)
    expect(s.sofaTopY).toBeNull()
    expect(s.wall.h - (s.arrangement.y + s.arrangement.h)).toBeGreaterThanOrEqual(
      PLANNER_RULES.minBottomIn - EPS,
    )
  })

  it('"Regenerate" keeps every frame and its size, only moves them', () => {
    const a = buildScene(base)
    const b = buildScene(plannerReducer(base, { type: 'layout/regenerate', seed: 7 }))
    expect(b.frames.map((f) => f.id)).toEqual(a.frames.map((f) => f.id))
    b.frames.forEach((f, i) => {
      expect(f.outer.w).toBeCloseTo(a.frames[i]?.outer.w ?? NaN)
    })
  })

  it('photo rect = outer minus moulding and mat', () => {
    const s = buildScene(base)
    const f = s.frames[0]
    expect(f?.photoRect.w).toBeCloseTo(12)
    expect(f?.photoRect.h).toBeCloseTo(16)
  })
})

describe('suggestLayouts', () => {
  it('ranks fitting arrangements first and covers every style × variant', () => {
    const results = suggestLayouts(createInitialState())
    expect(results).toHaveLength(12)
    expect(results[0]?.scene.fits).toBe(true)
  })

  it('prefers a fitting layout over a non-fitting one on a narrow wall', () => {
    let s = createInitialState()
    s = plannerReducer(s, { type: 'wall/setSize', dimension: 'widthIn', value: 60 })
    s = { ...s, frames: Array.from({ length: 4 }, (_, i) => createFrame(i)) }
    const best = suggestLayouts(s)[0]
    expect(best?.scene.fits).toBe(true)
  })
})

describe('plannerReducer: frame identity', () => {
  it('every frame keeps a unique id when frames are added (regression: duplicate React keys)', () => {
    let s = createInitialState()
    s = plannerReducer(s, { type: 'frames/setCount', count: 14 })
    expect(new Set(s.frames.map((f) => f.id)).size).toBe(14)
  })

  it('a new frame copies the last frame’s style but not its photo or id', () => {
    let s = createInitialState()
    s = plannerReducer(s, { type: 'frames/update', index: 8, patch: { sizeId: '20x30', finishId: 'walnut' } })
    s = plannerReducer(s, { type: 'frames/setCount', count: 10 })
    const [prev, added] = [s.frames[8], s.frames[9]]
    expect(added?.id).not.toBe(prev?.id)
    expect(added?.sizeId).toBe('20x30')
    expect(added?.finishId).toBe('walnut')
  })
})
