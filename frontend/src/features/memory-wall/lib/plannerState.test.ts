import { describe, expect, it } from 'vitest'
import { PLANNER_RULES } from '../constants'
import { buildScene } from './geometry/scene'
import { createInitialState, plannerReducer, sanitizePlannerState } from './plannerState'

/** Test helper: fail loudly instead of using a non-null assertion. */
function must<T>(value: T | null | undefined): T {
  if (value === null || value === undefined) throw new Error('expected a value')
  return value
}

describe('plannerReducer guards', () => {
  it('ignores NaN frame counts and variants instead of corrupting state', () => {
    const s = createInitialState()
    expect(plannerReducer(s, { type: 'frames/setCount', count: Number.NaN })).toBe(s)
    expect(plannerReducer(s, { type: 'layout/setVariant', variant: Number.NaN })).toBe(s)
    expect(plannerReducer(s, { type: 'layout/apply', style: 'grid', variant: Number.NaN })).toBe(s)
  })

  it('sets photos by frame id, so a late upload never lands on the wrong frame', () => {
    const s = createInitialState()
    const target = must(s.frames[4])
    const photo = { kind: 'upload', url: 'blob:x', name: 'a.jpg', widthPx: 900, heightPx: 1200 } as const
    // Frames 0-3 are removed while the upload is in flight…
    const shrunk = { ...s, frames: s.frames.slice(4) }
    const next = plannerReducer(shrunk, { type: 'frames/setPhoto', frameId: target.id, photo })
    expect(next.frames[0]?.id).toBe(target.id)
    expect(next.frames[0]?.photo).toEqual(photo)
    // …or the frame no longer exists at all.
    expect(plannerReducer(s, { type: 'frames/setPhoto', frameId: 'nope', photo })).toBe(s)
  })
})

describe('sanitizePlannerState (untrusted saved designs)', () => {
  it('round-trips a valid state unchanged', () => {
    const s = createInitialState()
    expect(sanitizePlannerState(JSON.parse(JSON.stringify(s)))).toEqual(s)
  })

  it('rejects things that are not designs', () => {
    const bad = [null, 42, 'x', [], {}, { wall: {}, frames: [] }, { wall: { widthIn: 'a' }, frames: [{}] }]
    for (const value of bad) expect(sanitizePlannerState(value)).toBeNull()
  })

  it('repairs tampered fields into a state the geometry engine can always draw', () => {
    const s = must(
      sanitizePlannerState({
        title: '   ',
        wall: { widthIn: 1e9, heightIn: -5, paintId: '<script>' },
        displayUnit: 'parsec',
        layout: { style: 'chaos', gapIn: Number.NaN, gapUnit: 'mile', seed: 'x', variant: -7 },
        frames: Array.from({ length: 40 }, () => ({
          id: 'dup',
          sizeId: '999x999',
          orientation: 'diagonal',
          finishId: 'gold-leaf',
          mount: { enabled: 'yes', colourId: 1, marginIn: 99 },
          photo: { kind: 'upload', url: 'https://tracker.example/pixel.gif', name: 'x' },
        })),
        selectedIndex: 999,
        preview: null,
      }),
    )
    expect(s).not.toBeNull()
    expect(s.title).toBe('Untitled wall')
    expect(s.wall).toEqual({
      widthIn: PLANNER_RULES.wallWidthIn.max,
      heightIn: PLANNER_RULES.wallHeightIn.min,
      paintId: 'warm-cream',
    })
    expect(s.displayUnit).toBe('ft')
    expect(s.layout).toEqual({ style: 'grid', gapIn: 3, gapUnit: 'in', seed: 0, variant: 2 })
    expect(s.frames).toHaveLength(PLANNER_RULES.frameCount.max)
    expect(new Set(s.frames.map((f) => f.id)).size).toBe(s.frames.length)
    for (const f of s.frames) {
      expect(f).toMatchObject({
        sizeId: '12x16',
        orientation: 'portrait',
        finishId: 'natural-oak',
        photo: null,
      })
      expect(f.mount).toEqual({ enabled: true, colourId: 'museum-white', marginIn: PLANNER_RULES.matIn.max })
    }
    expect(s.selectedIndex).toBe(s.frames.length - 1)
    expect(s.preview).toEqual({ sofa: true, indexBadges: true, guides: true })
    expect(() => buildScene(s)).not.toThrow()
  })

  it('keeps known sample photos but never restores upload URLs', () => {
    const base = createInitialState()
    const frames = base.frames.map((f, i) =>
      i === 0 ? { ...f, photo: { kind: 'upload', url: 'blob:old', name: 'a', widthPx: 1, heightPx: 1 } } : f,
    )
    const s = must(sanitizePlannerState({ ...base, frames }))
    expect(s.frames[0]?.photo).toBeNull()
    expect(s.frames[1]?.photo).toEqual(base.frames[1]?.photo)
    const unknownSample = must(
      sanitizePlannerState({
        ...base,
        frames: [{ ...base.frames[0], photo: { kind: 'sample', sampleId: '../../etc' } }],
      }),
    )
    expect(unknownSample.frames[0]?.photo).toBeNull()
  })
})
