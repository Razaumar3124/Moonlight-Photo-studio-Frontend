import { useSyncExternalStore } from 'react'
import { savedDesignsStore } from '../lib/savedDesigns'

/** Live list of saved designs (mock store now, /designs API in Phase 5). */
export function useSavedDesigns() {
  return useSyncExternalStore(
    savedDesignsStore.subscribe,
    savedDesignsStore.getSnapshot,
    savedDesignsStore.getSnapshot,
  )
}
