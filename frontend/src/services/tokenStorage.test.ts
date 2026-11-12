import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createFakeStorage } from '@/test/fakeStorage'

const LEGACY_KEY = 'moonlight.auth'

// tokenStorage keeps state in module scope, so each test gets a fresh module + storage.
async function load(initial: Record<string, string> = {}) {
  const storage = createFakeStorage(initial)
  vi.stubGlobal('localStorage', storage)
  vi.resetModules()
  const { tokenStorage } = await import('./tokenStorage')
  return { tokenStorage, storage }
}

const tokens = { access_token: 'acc', token_type: 'bearer' as const, expires_in: 3600 }

describe('tokenStorage', () => {
  beforeEach(() => {
    vi.useRealTimers()
  })

  it('saves, reads and clears a session in memory only', async () => {
    const { tokenStorage, storage } = await load()
    tokenStorage.save(tokens)
    expect(tokenStorage.getAccessToken()).toBe('acc')
    expect(tokenStorage.hasSession()).toBe(true)
    expect(storage.length).toBe(0) // nothing written to localStorage
    tokenStorage.clear()
    expect(tokenStorage.hasSession()).toBe(false)
    expect(tokenStorage.getAccessToken()).toBeNull()
  })

  it('does not survive a reload (the refresh cookie restores the session instead)', async () => {
    const first = await load()
    first.tokenStorage.save(tokens)
    const second = await load()
    expect(second.tokenStorage.getAccessToken()).toBeNull()
  })

  it('removes tokens persisted by earlier builds', async () => {
    const legacy = JSON.stringify({ accessToken: 'old', refreshToken: 'old-r', expiresAt: 9e15 })
    const { tokenStorage, storage } = await load({ [LEGACY_KEY]: legacy })
    expect(storage.getItem(LEGACY_KEY)).toBeNull()
    expect(tokenStorage.getAccessToken()).toBeNull()
  })

  it('does not return an expired access token but still reports the session', async () => {
    vi.useFakeTimers()
    const { tokenStorage } = await load()
    tokenStorage.save(tokens)
    vi.advanceTimersByTime(3600 * 1000)
    expect(tokenStorage.getAccessToken()).toBeNull()
    expect(tokenStorage.hasSession()).toBe(true)
  })

  it('treats a missing or garbled expires_in as already expired (never "forever")', async () => {
    const { tokenStorage } = await load()
    tokenStorage.save({ ...tokens, expires_in: Number.NaN })
    expect(tokenStorage.getAccessToken()).toBeNull()
  })

  it('ignores an empty or malformed access token', async () => {
    const { tokenStorage } = await load()
    tokenStorage.save({ ...tokens, access_token: '' })
    expect(tokenStorage.hasSession()).toBe(false)
  })

  it('works when storage is unavailable (private mode / blocked)', async () => {
    const throwing = createFakeStorage()
    throwing.removeItem = () => {
      throw new Error('SecurityError')
    }
    vi.stubGlobal('localStorage', throwing)
    vi.resetModules()
    const { tokenStorage } = await import('./tokenStorage')
    expect(() => tokenStorage.save(tokens)).not.toThrow()
    expect(tokenStorage.getAccessToken()).toBe('acc')
  })
})
