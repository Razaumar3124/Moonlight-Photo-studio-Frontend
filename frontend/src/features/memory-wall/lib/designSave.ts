import { isApiError } from '@/services/apiClient'
import { designsService } from '@/services/designsService'
import type { DesignWallInput } from '@/types/api'
import type { Scene } from './geometry/scene'
import { designFingerprint, toDesignWall, toVersionRequest } from './designMapper'
import type { PlannerState } from './plannerState'

/** What the planner knows about the design it is editing (null id = not saved yet). */
export interface DesignSession {
  designId: string | null
  versionNumber: number | null
  /** Fingerprint of the last saved content: equal to the current one means nothing is unsaved. */
  savedFingerprint: string | null
  /** Title and wall as stored, to know whether the design record itself needs an update. */
  savedTitle: string | null
  savedWall: string | null
}

export const NEW_DESIGN: DesignSession = {
  designId: null,
  versionNumber: null,
  savedFingerprint: null,
  savedTitle: null,
  savedWall: null,
}

/**
 * - `created`: a new design with its first version.
 * - `new-version`: the layout changed, so a new immutable version was stored.
 * - `updated`: only the design record changed (title, wall size or paint live on the design, not in
 *   versions), so the current version stays the current one.
 * - `unchanged`: nothing differed from what is stored.
 */
export type SaveOutcome = 'created' | 'new-version' | 'updated' | 'unchanged'

export interface SaveResult {
  outcome: SaveOutcome
  session: DesignSession
}

const wallKey = (wall: DesignWallInput) => JSON.stringify(wall)

export function sessionFor(
  designId: string,
  versionNumber: number | null,
  state: PlannerState,
): DesignSession {
  return {
    designId,
    versionNumber,
    savedFingerprint: designFingerprint(state),
    savedTitle: state.title,
    savedWall: wallKey(toDesignWall(state)),
  }
}

/**
 * Save the planner as a design.
 *
 * - New design (or `asNew`): create the design, then its first version. If the version is
 *   rejected, the empty design is removed again so no blank "My Designs" card is left behind.
 * - Existing design: update its title/wall if they changed, then append a version. Versions are
 *   immutable, so nothing is ever overwritten; saving identical content is reported as
 *   `unchanged` (the server returns the current version). If the version is rejected after the
 *   design record was updated, the record is put back.
 *
 * `title` is the name the user confirmed; the saved state carries it.
 */
export async function saveDesign(args: {
  state: PlannerState
  scene: Scene
  session: DesignSession
  asNew?: boolean
  signal?: AbortSignal
}): Promise<SaveResult> {
  const { state, scene, session, asNew = false, signal } = args
  const wall = toDesignWall(state)
  const request = toVersionRequest(state, scene)

  if (asNew || !session.designId) {
    const design = await designsService.create({ title: state.title, wall }, signal)
    try {
      const version = await designsService.saveVersion(design.id, request, signal)
      return { outcome: 'created', session: sessionFor(design.id, version.version_number, state) }
    } catch (error) {
      await designsService.remove(design.id).catch(() => undefined)
      throw error
    }
  }

  const designId = session.designId
  const recordChanged = session.savedTitle !== state.title || session.savedWall !== wallKey(wall)
  if (recordChanged) await designsService.update(designId, { title: state.title, wall }, signal)

  try {
    const version = await designsService.saveVersion(designId, request, signal)
    const isNew = session.versionNumber === null || version.version_number > session.versionNumber
    return {
      outcome: isNew ? 'new-version' : recordChanged ? 'updated' : 'unchanged',
      session: sessionFor(designId, version.version_number, state),
    }
  } catch (error) {
    if (recordChanged && session.savedTitle !== null && session.savedWall !== null) {
      // Best effort: don't leave the record describing a wall the stored version doesn't fit.
      await designsService
        .update(designId, {
          title: session.savedTitle,
          wall: JSON.parse(session.savedWall) as DesignWallInput,
        })
        .catch(() => undefined)
    }
    throw error
  }
}

/** A message for the user, and the offending frame (1-based) when the server pointed at one. */
export interface SaveProblem {
  message: string
  /** True for "your layout doesn't fit / is invalid": the user can fix it. */
  fixable: boolean
}

export function describeSaveError(error: unknown): SaveProblem {
  if (!isApiError(error))
    return { message: 'We couldn’t save your design. Please try again.', fixable: false }
  if (error.isNetworkError) {
    return {
      message: 'You appear to be offline. Your changes are kept here, so try again when you’re back.',
      fixable: false,
    }
  }
  if (error.status === 401) {
    return {
      message: 'Your session ended. Sign in again and your changes will still be here.',
      fixable: false,
    }
  }
  if (error.status === 403) {
    return { message: 'You don’t have permission to change this design.', fixable: false }
  }
  if (error.status === 404) {
    return {
      message: 'That design no longer exists. Save it as a new design to keep your work.',
      fixable: false,
    }
  }
  if (error.status === 422 || error.status === 400) {
    const first = error.details[0]
    const frame = first?.field.match(/^items\.([^.]+)/)?.[1]
    const where = frame ? ' (one of the frames)' : ''
    return {
      message: `The layout can’t be saved yet${where}: ${first?.issue ?? error.message}`,
      fixable: true,
    }
  }
  if (error.status === 429) {
    return { message: 'Too many saves in a short time. Please wait a moment and try again.', fixable: false }
  }
  return { message: 'We couldn’t save your design right now. Please try again shortly.', fixable: false }
}
