import { designFingerprint } from './designMapper'
import type { DesignSession } from './designSave'
import { sanitizePlannerState, type PlannerState } from './plannerState'

/**
 * Keeps the planner's unsaved work across a page reload and across an expired session, in
 * sessionStorage (this tab only, gone when it closes). It holds design content only: no tokens, no
 * credentials, no photo bytes (photos are references to the user's library). A draft belongs to one
 * user id and is ignored for anyone else; deliberate sign-out deletes it (`lib/sessionData.ts`).
 * Everything read back is rebuilt by `sanitizePlannerState`, since storage is user-editable.
 */

export const DRAFT_KEY = 'moonlight.planner.draft.v1'

interface StoredDraft {
  v: 1
  userId: string
  session: DesignSession
  state: PlannerState
}

export interface Draft {
  session: DesignSession
  state: PlannerState
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null
const strOrNull = (v: unknown, max = 200) => (typeof v === 'string' && v.length <= max ? v : null)

export function saveDraft(userId: string, session: DesignSession, state: PlannerState) {
  try {
    const draft: StoredDraft = { v: 1, userId, session, state }
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
  } catch {
    // Storage full or blocked: the planner still works, it just can't survive a reload.
  }
}

export function clearDraft() {
  try {
    sessionStorage.removeItem(DRAFT_KEY)
  } catch {
    // Nothing to clear.
  }
}

export function loadDraft(userId: string): Draft | null {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!isObject(parsed) || parsed.v !== 1 || parsed.userId !== userId) return null
    const state = sanitizePlannerState(parsed.state)
    if (!state) return null
    const s = isObject(parsed.session) ? parsed.session : {}
    const designId = typeof s.designId === 'string' && /^[0-9a-f]{24}$/i.test(s.designId) ? s.designId : null
    return {
      state,
      session: {
        designId,
        versionNumber:
          designId && typeof s.versionNumber === 'number' && Number.isInteger(s.versionNumber)
            ? s.versionNumber
            : null,
        savedFingerprint: designId ? strOrNull(s.savedFingerprint, 100_000) : null,
        savedTitle: designId ? strOrNull(s.savedTitle) : null,
        savedWall: designId ? strOrNull(s.savedWall) : null,
      },
    }
  } catch {
    return null
  }
}

/** True when the planner holds something worth warning about before the tab closes. */
export function hasUnsavedChanges(state: PlannerState, session: DesignSession, initial: string): boolean {
  return designFingerprint(state) !== (session.savedFingerprint ?? initial)
}
