import { describe, expect, it } from 'vitest'
import type { DesignDetail, DesignItem, DesignVersion } from '@/types/api'
import { buildScene } from './geometry/scene'
import { designFingerprint, fromDesignDetail, toDesignWall, toVersionRequest } from './designMapper'
import type { LibraryPhoto } from './photos'
import { createInitialState, plannerReducer, type PlannerState } from './plannerState'
import { findTemplate } from './templates'

const PHOTO_ID = '665f1c2e9b1d4a0012345678'
const libPhoto = (id = PHOTO_ID): LibraryPhoto => ({
  id,
  name: 'family.jpg',
  widthPx: 3000,
  heightPx: 4000,
  thumbnailUrl: `/api/v1/photos/${id}/thumbnail?sig=a&exp=9999999999`,
  previewUrl: `/api/v1/photos/${id}/preview?sig=b&exp=9999999999`,
  createdAt: '2026-11-12T00:00:00Z',
  expiresAt: 9999999999000,
})
const library = (...photos: LibraryPhoto[]) => new Map(photos.map((p) => [p.id, p]))
const must = <T>(v: T | undefined | null): T => {
  if (v === undefined || v === null) throw new Error('missing')
  return v
}

/** What the server would send back for the request (it computes outer sizes from the catalog). */
function serverEcho(state: PlannerState, overrides: Partial<DesignVersion> = {}): DesignDetail {
  const req = toVersionRequest(state, buildScene(state))
  const items: DesignItem[] = req.items.map((i) => ({
    item_id: i.item_id,
    frame_id: i.size_id ?? 'custom',
    photo_id: i.photo_id ?? null,
    photo_missing: false,
    sample_id: i.sample_id ?? null,
    position_x_inches: i.position_x_inches,
    position_y_inches: i.position_y_inches,
    photo_width_inches: i.photo_width_inches,
    photo_height_inches: i.photo_height_inches,
    total_width_inches: 0,
    total_height_inches: 0,
    orientation: i.orientation ?? 'portrait',
    finish_id: i.finish_id ?? null,
    size_id: i.size_id ?? null,
    matting: {
      enabled: i.matting?.enabled ?? true,
      top_inches: i.matting?.top_inches ?? 0,
      bottom_inches: i.matting?.bottom_inches ?? 0,
      left_inches: i.matting?.left_inches ?? 0,
      right_inches: i.matting?.right_inches ?? 0,
      color_id: i.matting?.color_id ?? null,
      color_hex: '#F4F3F3',
    },
    glass_type: 'standard',
  }))
  return {
    id: '665f1c2e9b1d4a00aaaaaaaa',
    user_id: '665f1c2e9b1d4a00bbbbbbbb',
    title: state.title,
    description: null,
    status: 'saved',
    wall: {
      width_inches: state.wall.widthIn,
      height_inches: state.wall.heightIn,
      paint_id: state.wall.paintId,
      color_hex: '#EFDECA',
      texture: 'smooth',
      display_unit: state.displayUnit,
      has_sofa: state.preview.sofa,
    },
    current_version_id: '665f1c2e9b1d4a00cccccccc',
    current_version: {
      id: '665f1c2e9b1d4a00cccccccc',
      design_id: '665f1c2e9b1d4a00aaaaaaaa',
      version_number: 1,
      layout_type: req.layout_type ?? 'custom',
      template_id: req.template_id ?? null,
      items_count: items.length,
      bounding_box: { x: 0, y: 0, width: 1, height: 1 },
      items,
      layout_metadata: (req.layout_metadata ?? null) as DesignVersion['layout_metadata'],
      preview: (req.preview ?? null) as DesignVersion['preview'],
      created_at: '2026-11-12T00:00:00Z',
      ...overrides,
    },
    created_at: '2026-11-12T00:00:00Z',
    updated_at: '2026-11-12T00:00:00Z',
  }
}

describe('planner → API', () => {
  it('maps the wall, layout metadata and preview flags', () => {
    const state = createInitialState()
    expect(toDesignWall(state)).toEqual({
      width_inches: 144,
      height_inches: 108,
      paint_id: 'warm-cream',
      display_unit: 'ft',
      has_sofa: true,
    })
    const req = toVersionRequest(state, buildScene(state))
    expect(req).toMatchObject({
      layout_type: 'grid',
      template_id: 'balanced-grid',
      layout_metadata: { style: 'grid', gap_inches: 3, gap_unit: 'in', seed: 0, variant: 0 },
      preview: { sofa: true, index_badges: true, guides: true },
    })
    expect(req.items).toHaveLength(9)
  })

  it('sends catalog ids, the opening size, the outer top-left position and the mount', () => {
    const state = createInitialState()
    const scene = buildScene(state)
    const item = must(toVersionRequest(state, scene).items[0])
    const frame = must(state.frames[0])
    expect(item).toMatchObject({
      item_id: frame.id,
      size_id: '12x16',
      finish_id: 'natural-oak',
      orientation: 'portrait',
      photo_width_inches: 12,
      photo_height_inches: 16,
      matting: {
        enabled: true,
        top_inches: 2,
        bottom_inches: 2,
        left_inches: 2,
        right_inches: 2,
        color_id: 'museum-white',
      },
    })
    expect(item.position_x_inches).toBeCloseTo(must(scene.frames[0]).outer.x, 3)
    expect(item.position_y_inches).toBeCloseTo(must(scene.frames[0]).outer.y, 3)
    // The server computes outer sizes from the finish; the client must not send conflicting ones.
    expect(item).not.toHaveProperty('total_width_inches')
  })

  it('swaps the opening for landscape frames', () => {
    let state = createInitialState()
    state = plannerReducer(state, { type: 'frames/update', index: 0, patch: { orientation: 'landscape' } })
    const item = must(toVersionRequest(state, buildScene(state)).items[0])
    expect([item.photo_width_inches, item.photo_height_inches]).toEqual([16, 12])
  })

  it('references uploads by photo_id and samples by sample_id, never both', () => {
    let state = createInitialState()
    const id0 = must(state.frames[0]).id
    state = plannerReducer(state, {
      type: 'frames/setPhoto',
      frameId: id0,
      photo: { kind: 'upload', photoId: PHOTO_ID, name: 'family.jpg', widthPx: 3000, heightPx: 4000 },
    })
    const [first, second] = toVersionRequest(state, buildScene(state)).items
    expect(first).toMatchObject({ photo_id: PHOTO_ID })
    expect(first).not.toHaveProperty('sample_id')
    expect(second).toHaveProperty('sample_id')
    expect(second).not.toHaveProperty('photo_id')
  })

  it('saves what is shown: empty frames keep the fill sample, or stay empty', () => {
    let state = createInitialState()
    state = { ...state, frames: state.frames.map((f) => ({ ...f, photo: null })) }
    const empty = toVersionRequest(state, buildScene(state)).items[0]
    expect(empty).not.toHaveProperty('sample_id')
    const filled = toVersionRequest({ ...state, fillWithSamples: true }, buildScene(state)).items[0]
    expect(filled).toHaveProperty('sample_id')
  })

  it('keeps the margin of a disabled mount and gives every item a unique, safe id', () => {
    let state = createInitialState()
    state = plannerReducer(state, { type: 'frames/updateMount', index: 0, patch: { enabled: false } })
    state = {
      ...state,
      frames: state.frames.map((f, i) =>
        i < 2 ? { ...f, id: 'dup' } : i === 2 ? { ...f, id: 'bad id!' } : f,
      ),
    }
    const items = toVersionRequest(state, buildScene(state)).items
    expect(items[0]?.matting).toMatchObject({ enabled: false, top_inches: 2 })
    const ids = items.map((i) => i.item_id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids.every((id) => /^[A-Za-z0-9_-]{1,64}$/.test(id))).toBe(true)
  })
})

describe('API → planner', () => {
  it('round-trips: what was saved is what opens (including photos, mounts, seed and variant)', () => {
    let state = plannerReducer(createInitialState(), {
      type: 'template/apply',
      template: must(findTemplate('creative-salon')),
      templateId: 'creative-salon',
    })
    state = plannerReducer(state, { type: 'layout/regenerate', seed: 12345 })
    state = plannerReducer(state, { type: 'layout/setVariant', variant: 2 })
    state = plannerReducer(state, { type: 'wall/setPaint', paintId: 'cloud-grey' })
    state = plannerReducer(state, { type: 'unit/set', unit: 'cm' })
    state = plannerReducer(state, { type: 'layout/setGapUnit', unit: 'cm' })
    state = plannerReducer(state, {
      type: 'frames/updateMount',
      index: 1,
      patch: { enabled: false, marginIn: 3.5 },
    })
    state = plannerReducer(state, { type: 'frames/update', index: 2, patch: { finishId: 'mahogany' } })
    state = plannerReducer(state, { type: 'preview/toggle', key: 'guides', value: false })
    state = plannerReducer(state, {
      type: 'frames/setPhoto',
      frameId: must(state.frames[0]).id,
      photo: { kind: 'upload', photoId: PHOTO_ID, name: 'family.jpg', widthPx: 3000, heightPx: 4000 },
    })
    state = { ...state, title: 'Salon' }

    const loaded = must(fromDesignDetail(serverEcho(state), library(libPhoto())))
    expect(loaded.notes).toEqual([])
    expect(designFingerprint(loaded.state)).toBe(designFingerprint(state))
    // Same geometry too, which is what the server validated.
    expect(buildScene(loaded.state).frames.map((f) => f.outer)).toEqual(
      buildScene(state).frames.map((f) => f.outer),
    )
  })

  it('loads legacy designs: `mm` unit, legacy layout name, no catalog ids, odd sizes', () => {
    const base = serverEcho(createInitialState())
    const items = base.current_version?.items.map((i, n) => ({
      ...i,
      size_id: null,
      finish_id: null,
      frame_id: 'frame-oak-12x16',
      // n=0: a custom opening that is not a catalog size; others: a catalog opening given in landscape.
      photo_width_inches: n === 0 ? 13.3 : 16,
      photo_height_inches: n === 0 ? 17.7 : 12,
      matting: { ...i.matting, color_id: null, color_hex: '#1D191A' },
    }))
    const legacy: DesignDetail = {
      ...base,
      wall: { ...base.wall, display_unit: 'mm', paint_id: null, color_hex: '#8D8785' },
      current_version: {
        ...must(base.current_version),
        layout_type: 'focal_center',
        layout_metadata: { style: undefined, some_old_key: 1 } as never,
        items: items ?? [],
      },
    }
    const loaded = must(fromDesignDetail(legacy, library()))
    expect(loaded.state.displayUnit).toBe('cm')
    expect(loaded.state.layout.style).toBe('centre')
    expect(loaded.state.wall.paintId).toBe('stone-grey') // matched by colour
    expect(loaded.state.frames[1]).toMatchObject({
      sizeId: '12x16',
      orientation: 'landscape',
      mount: { colourId: 'black' },
    })
    expect(loaded.state.frames[0]?.sizeId).toBe('12x16') // fell back to the default size
    expect(loaded.notes.join(' ')).toMatch(/closest standard/)
    expect(() => buildScene(loaded.state)).not.toThrow()
  })

  it('clamps walls saved under older limits instead of refusing them', () => {
    const base = serverEcho(createInitialState())
    const old: DesignDetail = { ...base, wall: { ...base.wall, width_inches: 24, height_inches: 400 } }
    const loaded = must(fromDesignDetail(old, library()))
    expect(loaded.state.wall).toMatchObject({ widthIn: 36, heightIn: 240 })
  })

  it('empties frames whose photo is gone and says so, without losing the frames', () => {
    let state = createInitialState()
    state = plannerReducer(state, {
      type: 'frames/setPhoto',
      frameId: must(state.frames[0]).id,
      photo: { kind: 'upload', photoId: PHOTO_ID, name: 'family.jpg', widthPx: 3000, heightPx: 4000 },
    })
    const echo = serverEcho(state)
    const flagged = {
      ...echo,
      current_version: {
        ...must(echo.current_version),
        items: must(echo.current_version).items.map((i) => (i.photo_id ? { ...i, photo_missing: true } : i)),
      },
    }
    for (const lib of [library(libPhoto()), library()]) {
      const loaded = must(fromDesignDetail(flagged, lib))
      expect(loaded.state.frames).toHaveLength(9)
      expect(loaded.state.frames[0]?.photo).toBeNull()
      expect(loaded.missingPhotos).toBe(1)
      expect(loaded.notes.join(' ')).toMatch(/1 photo is no longer in your library/)
    }
    // Not flagged and present in the library: kept.
    expect(must(fromDesignDetail(echo, library(libPhoto()))).state.frames[0]?.photo).toMatchObject({
      photoId: PHOTO_ID,
    })
  })

  it('returns null for a design with no saved layout', () => {
    const base = serverEcho(createInitialState())
    expect(fromDesignDetail({ ...base, current_version: null }, library())).toBeNull()
    expect(
      fromDesignDetail({ ...base, current_version: { ...must(base.current_version), items: [] } }, library()),
    ).toBeNull()
  })

  it('never lets API data smuggle in unsafe values', () => {
    const base = serverEcho(createInitialState())
    const hostile: DesignDetail = {
      ...base,
      title: '<img src=x onerror=alert(1)>'.repeat(10),
      current_version: {
        ...must(base.current_version),
        template_id: '../../etc/passwd',
        items: must(base.current_version).items.map((i) => ({
          ...i,
          sample_id: '../../secret',
          photo_id: null,
        })),
      },
    }
    const loaded = must(fromDesignDetail(hostile, library()))
    expect(loaded.state.title.length).toBeLessThanOrEqual(80)
    expect(loaded.state.templateId).toBeNull()
    expect(loaded.state.frames.every((f) => f.photo === null)).toBe(true)
  })
})

describe('designFingerprint', () => {
  it('ignores the selected frame but not anything that is saved', () => {
    const state = createInitialState()
    const f = designFingerprint(state)
    expect(designFingerprint({ ...state, selectedIndex: 3 })).toBe(f)
    expect(designFingerprint({ ...state, title: 'Other' })).not.toBe(f)
    expect(designFingerprint(plannerReducer(state, { type: 'wall/setPaint', paintId: 'sand' }))).not.toBe(f)
    expect(
      designFingerprint(
        plannerReducer(state, { type: 'frames/updateMount', index: 0, patch: { marginIn: 4 } }),
      ),
    ).not.toBe(f)
    expect(
      designFingerprint(plannerReducer(state, { type: 'preview/toggle', key: 'sofa', value: false })),
    ).not.toBe(f)
  })
})
