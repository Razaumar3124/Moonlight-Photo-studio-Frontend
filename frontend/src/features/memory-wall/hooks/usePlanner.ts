import { useMemo, useReducer } from 'react'
import { buildScene, type PhotoUrlResolver } from '../lib/geometry/scene'
import { createInitialState, plannerReducer, type PlannerState } from '../lib/plannerState'

/**
 * Single source of planner state. Every control dispatches an action; the scene (all frame
 * positions, fit checks, warnings) is derived from state, so any input change recalculates the
 * whole layout. buildScene is a few hundred microseconds even at 16 frames.
 *
 * `initial` restores unsaved work (see lib/plannerDraft.ts); `photoUrl` resolves uploaded photos
 * to their current signed URLs (the photo library changes it when URLs are refreshed).
 */
export function usePlanner(initial: PlannerState | null, photoUrl: PhotoUrlResolver) {
  const [state, dispatch] = useReducer(plannerReducer, initial, (draft) => draft ?? createInitialState())
  // Only what the geometry reads: selecting a frame, switching units or toggling guides/badges
  // keeps the same scene object, so the memoised SVG doesn't re-render for them.
  const { wall, layout, frames, fillWithSamples } = state
  const sofa = state.preview.sofa
  const scene = useMemo(
    () => buildScene({ wall, layout, frames, fillWithSamples, preview: { sofa }, photoUrl }),
    [wall, layout, frames, fillWithSamples, sofa, photoUrl],
  )
  return { state, dispatch, scene }
}
