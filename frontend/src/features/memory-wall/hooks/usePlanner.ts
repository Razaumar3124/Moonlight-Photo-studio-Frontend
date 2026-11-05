import { useMemo, useReducer } from 'react'
import { buildScene } from '../lib/geometry/scene'
import { createInitialState, plannerReducer } from '../lib/plannerState'

/**
 * Single source of planner state. Every control dispatches an action; the scene (all frame
 * positions, fit checks, warnings) is derived from state, so any input change recalculates the
 * whole layout. buildScene is a few hundred microseconds even at 16 frames.
 */
export function usePlanner() {
  const [state, dispatch] = useReducer(plannerReducer, undefined, createInitialState)
  // Only what the geometry reads: selecting a frame, switching units or toggling guides/badges
  // keeps the same scene object, so the memoised SVG doesn't re-render for them.
  const { wall, layout, frames, fillWithSamples } = state
  const sofa = state.preview.sofa
  const scene = useMemo(
    () => buildScene({ wall, layout, frames, fillWithSamples, preview: { sofa } }),
    [wall, layout, frames, fillWithSamples, sofa],
  )
  return { state, dispatch, scene }
}
