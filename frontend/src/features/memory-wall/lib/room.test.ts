import { describe, expect, it } from 'vitest'
import { ROOM_PHOTO_IN } from '../constants'
import { buildScene } from './geometry/scene'
import { createInitialState, plannerReducer } from './plannerState'
import { drawingHeight, FLOOR_BAND_IN, roomLayout, SKIRTING_IN } from './room'

const sceneFor = (
  patch: (s: ReturnType<typeof createInitialState>) => ReturnType<typeof createInitialState>,
) => buildScene(patch(createInitialState()))

describe('room layers', () => {
  it('derives the floor strip measurements (4″ skirting, ~16″ of floor)', () => {
    expect(SKIRTING_IN).toBeCloseTo(4, 5)
    expect(FLOOR_BAND_IN).toBeCloseTo(16.23, 1)
    expect(drawingHeight(108)).toBeCloseTo(108 + FLOOR_BAND_IN, 5)
  })

  it('draws an 84″ sofa centred on the wall, its top on the geometry sofa line', () => {
    const scene = sceneFor((s) => s)
    const { sofa } = roomLayout(scene)
    expect(sofa).not.toBeNull()
    expect(sofa?.rect.w).toBeCloseTo(84, 5)
    expect((sofa?.rect.x ?? 0) + (sofa?.rect.w ?? 0) / 2).toBeCloseTo(scene.wall.w / 2, 5)
    expect(sofa?.rect.y).toBeCloseTo(scene.wall.h - ROOM_PHOTO_IN.sofaTopFromFloor, 5)
    // Feet stand on the visible floor, never below it.
    expect((sofa?.rect.y ?? 0) + (sofa?.rect.h ?? 0)).toBeLessThanOrEqual(scene.wall.h + FLOOR_BAND_IN)
  })

  it('adds a lamp and a plant on the default 12 ft wall, clear of the frames', () => {
    const scene = sceneFor((s) => s)
    const kinds = roomLayout(scene).decor.map((d) => d.kind)
    expect(kinds).toEqual(['lamp', 'plant'])
  })

  it('drops decor that would not fit on a narrow wall', () => {
    const scene = sceneFor((s) =>
      plannerReducer(s, { type: 'wall/setSize', dimension: 'widthIn', value: 100 }),
    )
    expect(roomLayout(scene).decor).toEqual([])
  })

  it('drops decor that would cover the arrangement', () => {
    // 16 large frames in a row are far wider than the sofa: nothing may stand in front of them.
    let s = plannerReducer(createInitialState(), { type: 'frames/setCount', count: 16 })
    s = plannerReducer(s, { type: 'layout/setStyle', style: 'row' })
    s = plannerReducer(s, { type: 'wall/setSize', dimension: 'widthIn', value: 480 })
    const scene = buildScene(s)
    for (const d of roomLayout(scene).decor) {
      const a = scene.arrangement
      const clear = d.rect.x + d.rect.w <= a.x || d.rect.x >= a.x + a.w || d.rect.y >= a.y + a.h
      expect(clear).toBe(true)
    }
  })

  it('has no room layers without the reference sofa', () => {
    const scene = sceneFor((s) => plannerReducer(s, { type: 'preview/toggle', key: 'sofa', value: false }))
    expect(roomLayout(scene)).toEqual({ sofa: null, decor: [] })
  })
})
