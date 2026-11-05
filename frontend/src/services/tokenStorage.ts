import type { AuthTokens } from '@/types/api'

/**
 * Persists the JWTs returned by /auth/register and /auth/login.
 *
 * The contract returns tokens in the response body (no httpOnly cookie), so they have to live
 * in JS-readable storage. We use localStorage so a page reload doesn't sign the user out (there is
 * no refresh endpoint yet, see API_ALIGNMENT.md Q2/Q3). The tradeoff: tokens are exposed to XSS.
 * Everything goes through this module, so moving to cookies later is a change in one file.
 */

const STORAGE_KEY = 'moonlight.auth'

interface StoredSession {
  accessToken: string
  refreshToken: string
  /** Epoch ms when the access token expires. */
  expiresAt: number
}

let cache: StoredSession | null | undefined

/** localStorage is user-editable: never trust its shape. */
function isStoredSession(value: unknown): value is StoredSession {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return (
    typeof v.accessToken === 'string' &&
    v.accessToken.length > 0 &&
    typeof v.refreshToken === 'string' &&
    typeof v.expiresAt === 'number' &&
    Number.isFinite(v.expiresAt)
  )
}

function read(): StoredSession | null {
  if (cache !== undefined) return cache
  let raw: string | null = null
  try {
    raw = localStorage.getItem(STORAGE_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : null
    cache = isStoredSession(parsed) ? parsed : null
  } catch {
    cache = null
  }
  // Drop corrupted or tampered entries (bad JSON or wrong shape) so they can't linger.
  if (raw && !cache) {
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // Storage unavailable: nothing to clean up.
    }
  }
  return cache
}

export const tokenStorage = {
  save(tokens: AuthTokens) {
    // A missing/garbled expires_in must not produce NaN (NaN comparisons would never expire).
    const lifetimeSeconds =
      Number.isFinite(tokens.expires_in) && tokens.expires_in > 0 ? tokens.expires_in : 0
    cache = {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      expiresAt: Date.now() + lifetimeSeconds * 1000,
    }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(cache))
    } catch {
      // Storage blocked (private mode etc.) — session stays in memory for this tab.
    }
  },

  /** Returns the access token, or null if missing/expired. */
  getAccessToken(): string | null {
    const session = read()
    if (!session) return null
    if (Date.now() >= session.expiresAt) return null
    return session.accessToken
  },

  /** True if the user signed in at some point, even if the access token has since expired. */
  hasSession(): boolean {
    return read() !== null
  },

  getRefreshToken(): string | null {
    return read()?.refreshToken ?? null
  },

  clear() {
    cache = null
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }
  },
}
