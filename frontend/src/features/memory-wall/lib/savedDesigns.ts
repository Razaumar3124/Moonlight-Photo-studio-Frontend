import { createInitialState, plannerReducer, sanitizePlannerState, type PlannerState } from './plannerState'
import { findTemplate } from './templates'

/**
 * MOCK store for "My Designs" (UI-only phases). Phase 5 swaps this module for
 * GET/POST/DELETE /designs (API_ALIGNMENT M7). The function signatures stay the same.
 * Persisted in localStorage so the mock behaves realistically across reloads. Everything read
 * back is shape-checked, since storage is user-editable.
 */

export interface SavedDesign {
  id: string
  title: string
  /** ISO-8601 */
  savedAt: string
  state: PlannerState
  /** True when session-only uploaded photos were dropped while saving. */
  droppedUploads: boolean
}

const STORAGE_KEY = 'moonlight.mock.savedDesigns.v1'
/** Keeps the mock store well inside the ~5 MB localStorage quota. */
const MAX_DESIGNS = 50
const listeners = new Set<() => void>()
let cache: SavedDesign[] | null = null

function seed(): SavedDesign[] {
  const fromTemplate = (
    id: string,
    templateId: string,
    title: string,
    savedAt: string,
    patch: (s: PlannerState) => PlannerState = (s) => s,
  ): SavedDesign => {
    const template = findTemplate(templateId)
    let state = createInitialState()
    if (template) state = plannerReducer(state, { type: 'template/apply', template })
    return { id, title, savedAt, state: patch({ ...state, title }), droppedUploads: false }
  }
  return [
    fromTemplate('demo-living', 'balanced-grid', 'Living Room Gallery Wall', '2026-11-02T18:30:00.000Z'),
    fromTemplate('demo-hallway', 'panorama-row', 'Hallway Memories', '2026-10-28T09:12:00.000Z', (s) => ({
      ...s,
      wall: { ...s.wall, widthIn: 168, heightIn: 102, paintId: 'cloud-grey' },
    })),
    fromTemplate('demo-bedroom', 'creative-salon', 'Bedroom Salon', '2026-10-19T20:45:00.000Z', (s) => ({
      ...s,
      wall: { ...s.wall, paintId: 'peach-blush' },
    })),
  ]
}

/** Untrusted (user-editable storage, later the API): rebuild every field or drop the entry. */
function parseSavedDesign(value: unknown): SavedDesign | null {
  if (typeof value !== 'object' || value === null) return null
  const v = value as { [K in keyof SavedDesign]?: unknown }
  if (typeof v.id !== 'string' || !v.id || typeof v.savedAt !== 'string') return null
  if (Number.isNaN(Date.parse(v.savedAt))) return null
  const state = sanitizePlannerState(v.state)
  if (!state) return null
  const title = typeof v.title === 'string' ? v.title.trim().slice(0, 80) : ''
  return {
    id: v.id.slice(0, 64),
    title: title || state.title,
    savedAt: v.savedAt,
    state,
    droppedUploads: v.droppedUploads === true,
  }
}

function parseAll(raw: string | null): SavedDesign[] {
  const parsed: unknown = raw ? JSON.parse(raw) : null
  if (!Array.isArray(parsed)) return seed()
  const seen = new Set<string>()
  return parsed
    .map(parseSavedDesign)
    .filter((d): d is SavedDesign => d !== null && !seen.has(d.id) && !!seen.add(d.id))
    .slice(0, MAX_DESIGNS)
}

function read(): SavedDesign[] {
  if (cache) return cache
  try {
    cache = parseAll(localStorage.getItem(STORAGE_KEY))
  } catch {
    cache = seed()
  }
  return cache
}

function write(next: SavedDesign[]) {
  cache = next
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    // Storage full or blocked: keep the in-memory list for this session.
  }
  listeners.forEach((l) => l())
}

/** Uploaded photos are object URLs, valid only in this tab, so they can't be saved. */
function stripUploads(state: PlannerState): { state: PlannerState; dropped: boolean } {
  let dropped = false
  const frames = state.frames.map((f) => {
    if (f.photo?.kind !== 'upload') return f
    dropped = true
    return { ...f, photo: null }
  })
  return { state: structuredClone({ ...state, frames }), dropped }
}

export const savedDesignsStore = {
  subscribe(listener: () => void) {
    listeners.add(listener)
    // Another tab saved or deleted: re-read on next snapshot.
    const onStorage = (e: StorageEvent) => {
      if (e.key !== STORAGE_KEY && e.key !== null) return
      cache = null
      listener()
    }
    window.addEventListener('storage', onStorage)
    return () => {
      listeners.delete(listener)
      window.removeEventListener('storage', onStorage)
    }
  },

  /** Stable reference between writes (required by useSyncExternalStore). Newest first. */
  getSnapshot(): readonly SavedDesign[] {
    return read()
  },

  save(state: PlannerState, title: string): SavedDesign {
    const { state: clean, dropped } = stripUploads(state)
    const name = title.trim().replace(/\s+/g, ' ').slice(0, 80) || 'Untitled wall'
    const design: SavedDesign = {
      id: `d${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`,
      title: name,
      savedAt: new Date().toISOString(),
      state: { ...clean, title: name },
      droppedUploads: dropped,
    }
    write([design, ...read()].slice(0, MAX_DESIGNS))
    return design
  },

  remove(id: string) {
    write(read().filter((d) => d.id !== id))
  },
}
