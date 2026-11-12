import type { AuthTokens } from '@/types/api'

/**
 * Holds the access token returned by /auth/register, /auth/login, /auth/google and
 * /auth/refresh: **in memory only**, never in localStorage, so an XSS bug can't lift it from
 * storage.
 *
 * The refresh token never reaches JavaScript: the backend keeps it in an httpOnly, SameSite
 * cookie (scoped to `/api/v1/auth`) and rotates it on POST /auth/refresh. After a reload the
 * auth layer restores the session by calling /auth/refresh (the cookie is sent automatically),
 * so nothing needs to survive here.
 */

/** Key used by earlier builds that persisted tokens in localStorage. Removed on load. */
const LEGACY_STORAGE_KEY = 'moonlight.auth'

interface MemorySession {
  accessToken: string
  /** Epoch ms when the access token expires. */
  expiresAt: number
}

let session: MemorySession | null = null

try {
  localStorage.removeItem(LEGACY_STORAGE_KEY)
} catch {
  // Storage unavailable (private mode, non-browser): nothing to clean up.
}

export const tokenStorage = {
  save(tokens: AuthTokens) {
    if (typeof tokens.access_token !== 'string' || !tokens.access_token) {
      session = null
      return
    }
    // A missing/garbled expires_in must not produce NaN (NaN comparisons would never expire).
    const lifetimeSeconds =
      Number.isFinite(tokens.expires_in) && tokens.expires_in > 0 ? tokens.expires_in : 0
    session = { accessToken: tokens.access_token, expiresAt: Date.now() + lifetimeSeconds * 1000 }
  },

  /** Returns the access token, or null if missing/expired. */
  getAccessToken(): string | null {
    if (!session || Date.now() >= session.expiresAt) return null
    return session.accessToken
  },

  /** True if the user signed in during this page's lifetime, even if the token has since expired. */
  hasSession(): boolean {
    return session !== null
  },

  clear() {
    session = null
  },
}
