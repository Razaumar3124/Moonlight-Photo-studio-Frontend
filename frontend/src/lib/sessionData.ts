/**
 * Browser data that belongs to the signed-in person and must not outlive a deliberate sign-out.
 * Kept here (not in a feature) so the auth layer can clear it without importing the planner.
 */
const SESSION_KEYS = ['moonlight.planner.draft.v1']

export function clearSessionData() {
  for (const key of SESSION_KEYS) {
    try {
      sessionStorage.removeItem(key)
    } catch {
      // Storage unavailable: nothing was stored.
    }
  }
}
