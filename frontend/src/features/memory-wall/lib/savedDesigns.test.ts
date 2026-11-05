// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createInitialState } from './plannerState'

/** Test helper: fail loudly instead of using a non-null assertion. */
function must<T>(value: T | null | undefined): T {
  if (value === null || value === undefined) throw new Error('expected a value')
  return value
}

const KEY = 'moonlight.mock.savedDesigns.v1'

/** Fresh module per test: the store caches what it read. */
async function loadStore() {
  vi.resetModules()
  return (await import('./savedDesigns')).savedDesignsStore
}

beforeEach(() => localStorage.clear())

describe('savedDesignsStore (mock)', () => {
  it('seeds three demo designs when storage is empty', async () => {
    const store = await loadStore()
    expect(store.getSnapshot()).toHaveLength(3)
  })

  it('survives corrupt JSON and tampered entries', async () => {
    localStorage.setItem(KEY, '{not json')
    expect((await loadStore()).getSnapshot()).toHaveLength(3)

    const good = { id: 'a', title: 'Good', savedAt: '2026-11-01T00:00:00Z', state: createInitialState() }
    localStorage.setItem(
      KEY,
      JSON.stringify([
        good,
        { ...good }, // duplicate id
        { ...good, id: 'b', savedAt: 'yesterday' },
        { ...good, id: 'c', state: { wall: { widthIn: 'wide' }, frames: [] } },
        { ...good, id: 'd', title: 42, state: { ...good.state, frames: [{ sizeId: 'bogus' }] } },
        'junk',
      ]),
    )
    const list = (await loadStore()).getSnapshot()
    expect(list.map((d) => d.id)).toEqual(['a', 'd'])
    expect(list[1]?.title).toBe(good.state.title)
    expect(list[1]?.state.frames[0]?.sizeId).toBe('12x16')
  })

  it('drops uploads on save, flags it, and keeps a stable snapshot between writes', async () => {
    const store = await loadStore()
    const state = createInitialState()
    must(state.frames[0]).photo = {
      kind: 'upload',
      url: 'blob:x',
      name: 'me.jpg',
      widthPx: 900,
      heightPx: 900,
    }
    const before = store.getSnapshot()
    expect(store.getSnapshot()).toBe(before)
    const saved = store.save(state, '  My   wall  ')
    expect(saved.title).toBe('My wall')
    expect(saved.droppedUploads).toBe(true)
    expect(saved.state.frames[0]?.photo).toBeNull()
    expect(store.getSnapshot()[0]).toBe(saved)
    expect(state.frames[0]?.photo?.kind).toBe('upload') // caller's state untouched
  })

  it('picks up saves from another tab', async () => {
    const store = await loadStore()
    const listener = vi.fn<() => void>()
    const unsubscribe = store.subscribe(listener)
    expect(store.getSnapshot()).toHaveLength(3)
    localStorage.setItem(KEY, '[]')
    window.dispatchEvent(new StorageEvent('storage', { key: KEY }))
    expect(listener).toHaveBeenCalled()
    expect(store.getSnapshot()).toHaveLength(0)
    unsubscribe()
  })
})
