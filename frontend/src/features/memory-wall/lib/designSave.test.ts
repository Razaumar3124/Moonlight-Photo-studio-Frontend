import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/services/apiClient'
import { designsService } from '@/services/designsService'
import type { Design, DesignVersionSummary } from '@/types/api'
import { describeSaveError, NEW_DESIGN, saveDesign, sessionFor } from './designSave'
import { buildScene } from './geometry/scene'
import { createInitialState, plannerReducer } from './plannerState'

vi.mock('@/services/designsService', () => ({
  designsService: {
    create: vi.fn<() => Promise<unknown>>(),
    update: vi.fn<() => Promise<unknown>>(),
    saveVersion: vi.fn<() => Promise<unknown>>(),
    remove: vi.fn<() => Promise<unknown>>(),
  },
}))

const svc = vi.mocked(designsService)
const design = (id = '665f1c2e9b1d4a00aaaaaaaa'): Design => ({
  id,
  user_id: 'u',
  title: 't',
  description: null,
  wall: {
    width_inches: 144,
    height_inches: 108,
    paint_id: 'warm-cream',
    color_hex: '#EFDECA',
    texture: 'smooth',
    display_unit: 'ft',
    has_sofa: true,
  },
  current_version_id: null,
  current_version_number: null,
  status: 'saved',
  created_at: '',
  updated_at: '',
})
const version = (n: number): DesignVersionSummary => ({
  version_id: `v${n}`,
  design_id: 'd',
  version_number: n,
  layout_type: 'grid',
  items_count: 9,
  bounding_box: { x: 0, y: 0, width: 1, height: 1 },
  created_at: '',
})

const state = () => ({ ...createInitialState(), title: 'My wall' })

beforeEach(() => {
  vi.resetAllMocks()
  svc.remove.mockResolvedValue(undefined)
})

describe('saveDesign', () => {
  it('creates the design, then its first version, and tracks the session', async () => {
    svc.create.mockResolvedValue(design())
    svc.saveVersion.mockResolvedValue(version(1))
    const s = state()
    const result = await saveDesign({ state: s, scene: buildScene(s), session: NEW_DESIGN })
    expect(result.outcome).toBe('created')
    expect(svc.create).toHaveBeenCalledWith(
      { title: 'My wall', wall: expect.objectContaining({ width_inches: 144, paint_id: 'warm-cream' }) },
      undefined,
    )
    expect(svc.saveVersion).toHaveBeenCalledWith(
      '665f1c2e9b1d4a00aaaaaaaa',
      expect.objectContaining({ layout_type: 'grid', items: expect.any(Array) }),
      undefined,
    )
    expect(result.session).toMatchObject({ designId: '665f1c2e9b1d4a00aaaaaaaa', versionNumber: 1 })
  })

  it('removes the empty design again when its first version is rejected', async () => {
    svc.create.mockResolvedValue(design())
    svc.saveVersion.mockRejectedValue(new ApiError({ status: 422, code: 'VALIDATION_ERROR', message: 'no' }))
    const s = state()
    await expect(saveDesign({ state: s, scene: buildScene(s), session: NEW_DESIGN })).rejects.toMatchObject({
      status: 422,
    })
    expect(svc.remove).toHaveBeenCalledWith('665f1c2e9b1d4a00aaaaaaaa')
  })

  it('appends a version to an existing design and updates nothing else when title and wall are unchanged', async () => {
    const s = state()
    const session = sessionFor('665f1c2e9b1d4a00aaaaaaaa', 1, s)
    svc.saveVersion.mockResolvedValue(version(2))
    const changed = plannerReducer(s, { type: 'frames/updateMount', index: 0, patch: { marginIn: 4 } })
    const result = await saveDesign({ state: changed, scene: buildScene(changed), session })
    expect(result.outcome).toBe('new-version')
    expect(result.session.versionNumber).toBe(2)
    expect(svc.update).not.toHaveBeenCalled()
    expect(svc.create).not.toHaveBeenCalled()
  })

  it('reports an identical save as unchanged (the server returns the current version)', async () => {
    const s = state()
    svc.saveVersion.mockResolvedValue(version(3))
    const result = await saveDesign({
      state: s,
      scene: buildScene(s),
      session: sessionFor('665f1c2e9b1d4a00aaaaaaaa', 3, s),
    })
    expect(result.outcome).toBe('unchanged')
  })

  it('reports a record-only change (title, wall size, paint) as updated, not as unchanged', async () => {
    const s = state()
    const session = sessionFor('665f1c2e9b1d4a00aaaaaaaa', 2, s)
    svc.update.mockResolvedValue(design())
    svc.saveVersion.mockResolvedValue(version(2)) // identical layout: the server returns version 2 again
    const repainted = plannerReducer(s, { type: 'wall/setPaint', paintId: 'sand' })
    const result = await saveDesign({ state: repainted, scene: buildScene(repainted), session })
    expect(result.outcome).toBe('updated')
    expect(svc.update).toHaveBeenCalledTimes(1)
  })

  it('updates the design record first when the title or wall changed', async () => {
    const s = state()
    const session = sessionFor('665f1c2e9b1d4a00aaaaaaaa', 1, s)
    svc.update.mockResolvedValue(design())
    svc.saveVersion.mockResolvedValue(version(2))
    const next = {
      ...plannerReducer(s, { type: 'wall/setSize', dimension: 'widthIn', value: 200 }),
      title: 'Renamed',
    }
    await saveDesign({ state: next, scene: buildScene(next), session })
    expect(svc.update).toHaveBeenCalledWith(
      '665f1c2e9b1d4a00aaaaaaaa',
      { title: 'Renamed', wall: expect.objectContaining({ width_inches: 200 }) },
      undefined,
    )
    expect(svc.update.mock.invocationCallOrder[0]).toBeLessThan(
      svc.saveVersion.mock.invocationCallOrder[0] as number,
    )
  })

  it('puts the design record back if the new version is rejected', async () => {
    const s = state()
    const session = sessionFor('665f1c2e9b1d4a00aaaaaaaa', 1, s)
    svc.update.mockResolvedValue(design())
    svc.saveVersion.mockRejectedValue(new ApiError({ status: 422, code: 'VALIDATION_ERROR', message: 'no' }))
    const next = {
      ...plannerReducer(s, { type: 'wall/setSize', dimension: 'widthIn', value: 200 }),
      title: 'Renamed',
    }
    await expect(saveDesign({ state: next, scene: buildScene(next), session })).rejects.toBeInstanceOf(
      ApiError,
    )
    expect(svc.update).toHaveBeenCalledTimes(2)
    expect(svc.update.mock.calls[1]).toEqual([
      '665f1c2e9b1d4a00aaaaaaaa',
      { title: 'My wall', wall: expect.objectContaining({ width_inches: 144 }) },
    ])
  })

  it('"save as new" never touches the open design', async () => {
    const s = state()
    svc.create.mockResolvedValue(design('665f1c2e9b1d4a00bbbbbbbb'))
    svc.saveVersion.mockResolvedValue(version(1))
    const result = await saveDesign({
      state: s,
      scene: buildScene(s),
      session: sessionFor('665f1c2e9b1d4a00aaaaaaaa', 4, s),
      asNew: true,
    })
    expect(result.outcome).toBe('created')
    expect(result.session.designId).toBe('665f1c2e9b1d4a00bbbbbbbb')
    expect(svc.update).not.toHaveBeenCalled()
    expect(svc.saveVersion).toHaveBeenCalledWith('665f1c2e9b1d4a00bbbbbbbb', expect.anything(), undefined)
  })
})

describe('describeSaveError', () => {
  const e = (status: number, details: { field: string; issue: string }[] = [], code = 'X') =>
    new ApiError({ status, code, message: 'internal server text', details })

  it.each([
    [e(0, [], 'NETWORK_ERROR'), /offline/, false],
    [e(401), /session ended/, false],
    [e(403), /permission/, false],
    [e(404), /no longer exists/, false],
    [e(429), /Too many saves/, false],
    [e(500), /right now/, false],
  ])('maps %o safely', (error, message, fixable) => {
    const problem = describeSaveError(error)
    expect(problem.message).toMatch(message)
    expect(problem.fixable).toBe(fixable)
    expect(problem.message).not.toMatch(/internal server text/)
  })

  it('shows the server’s field message for a fixable layout problem', () => {
    const problem = describeSaveError(
      e(422, [{ field: 'items.f1', issue: 'Frames overlap or leave the wall margin' }]),
    )
    expect(problem).toEqual({
      message: 'The layout can’t be saved yet (one of the frames): Frames overlap or leave the wall margin',
      fixable: true,
    })
  })

  it('has a neutral message for unknown failures', () => {
    expect(describeSaveError(new Error('boom')).message).toBe(
      'We couldn’t save your design. Please try again.',
    )
  })
})
