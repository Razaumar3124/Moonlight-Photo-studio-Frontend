import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createFakeStorage } from '@/test/fakeStorage'
import { NEW_DESIGN, sessionFor } from './designSave'
import { clearDraft, DRAFT_KEY, hasUnsavedChanges, loadDraft, saveDraft } from './plannerDraft'
import { designFingerprint } from './designMapper'
import { createInitialState, plannerReducer } from './plannerState'
import { clearSessionData } from '@/lib/sessionData'

let storage: ReturnType<typeof createFakeStorage>

beforeEach(() => {
  storage = createFakeStorage()
  Object.defineProperty(globalThis, 'sessionStorage', { value: storage, configurable: true })
})
afterEach(() => {
  Reflect.deleteProperty(globalThis, 'sessionStorage')
})

const ID = '665f1c2e9b1d4a00aaaaaaaa'

describe('planner draft', () => {
  it('restores unsaved work and its design session for the same user', () => {
    const state = plannerReducer(createInitialState(), { type: 'wall/setPaint', paintId: 'sand' })
    const session = sessionFor(ID, 3, createInitialState())
    saveDraft('user-1', session, state)
    const draft = loadDraft('user-1')
    expect(draft?.state.wall.paintId).toBe('sand')
    expect(draft?.session).toEqual(session)
  })

  it('belongs to one user: someone else signing in on this tab gets nothing', () => {
    saveDraft('user-1', NEW_DESIGN, createInitialState())
    expect(loadDraft('user-2')).toBeNull()
  })

  it('contains design content only: no tokens, credentials or URLs', () => {
    saveDraft('user-1', NEW_DESIGN, createInitialState())
    const raw = storage.getItem(DRAFT_KEY) ?? ''
    expect(raw).not.toMatch(/token|password|bearer|https?:/i)
  })

  it('rebuilds everything it reads (storage is editable)', () => {
    saveDraft('user-1', NEW_DESIGN, createInitialState())
    const tampered = JSON.parse(storage.getItem(DRAFT_KEY) ?? '{}')
    tampered.state.wall.widthIn = 1e9
    tampered.state.frames[0].sizeId = '../../x'
    tampered.state.frames[0].photo = { kind: 'upload', photoId: 'javascript:alert(1)' }
    tampered.session = { designId: '../../evil', versionNumber: 'x', savedFingerprint: 5 }
    storage.setItem(DRAFT_KEY, JSON.stringify(tampered))
    const draft = loadDraft('user-1')
    expect(draft?.state.wall.widthIn).toBe(480)
    expect(draft?.state.frames[0]?.sizeId).toBe('12x16')
    expect(draft?.state.frames[0]?.photo).toBeNull()
    expect(draft?.session).toEqual(NEW_DESIGN)
  })

  it.each(['not json', '{}', '{"v":2}', 'null', '[]'])('ignores garbage %j', (raw) => {
    storage.setItem(DRAFT_KEY, raw)
    expect(loadDraft('user-1')).toBeNull()
  })

  it('is removed by clearDraft and by a deliberate sign-out', () => {
    saveDraft('user-1', NEW_DESIGN, createInitialState())
    clearDraft()
    expect(storage.getItem(DRAFT_KEY)).toBeNull()
    saveDraft('user-1', NEW_DESIGN, createInitialState())
    clearSessionData()
    expect(storage.getItem(DRAFT_KEY)).toBeNull()
  })

  it('survives unavailable storage', () => {
    Object.defineProperty(globalThis, 'sessionStorage', {
      value: {
        getItem: () => {
          throw new Error('blocked')
        },
        setItem: () => {
          throw new Error('quota')
        },
        removeItem: () => {
          throw new Error('blocked')
        },
      },
      configurable: true,
    })
    expect(() => saveDraft('u', NEW_DESIGN, createInitialState())).not.toThrow()
    expect(loadDraft('u')).toBeNull()
    expect(() => clearDraft()).not.toThrow()
    expect(() => clearSessionData()).not.toThrow()
  })
})

describe('hasUnsavedChanges', () => {
  it('compares against the saved fingerprint, or the initial one for an unsaved design', () => {
    const state = createInitialState()
    const initial = designFingerprint(state)
    expect(hasUnsavedChanges(state, NEW_DESIGN, initial)).toBe(false)
    const changed = plannerReducer(state, { type: 'wall/setPaint', paintId: 'sand' })
    expect(hasUnsavedChanges(changed, NEW_DESIGN, initial)).toBe(true)
    const saved = sessionFor(ID, 1, changed)
    expect(hasUnsavedChanges(changed, saved, initial)).toBe(false)
    expect(
      hasUnsavedChanges(
        plannerReducer(changed, { type: 'wall/setPaint', paintId: 'ivory-mist' }),
        saved,
        initial,
      ),
    ).toBe(true)
    // A restored draft without a saved design is always unsaved.
    expect(hasUnsavedChanges(state, NEW_DESIGN, '')).toBe(true)
  })
})
