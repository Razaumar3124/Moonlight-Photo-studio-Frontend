import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { isApiError, refreshSession, setUnauthorizedHandler } from '@/services/apiClient'
import { authService } from '@/services/authService'
import { tokenStorage } from '@/services/tokenStorage'
import type { AuthResponse, User } from '@/types/api'
import { AuthContext, type AuthContextValue, type AuthStatus, type SessionNotice } from './authContext'

/**
 * The single owner of "who is signed in".
 *
 * - The access token lives in `tokenStorage` (memory only); the refresh token is an httpOnly
 *   cookie JavaScript can't read. Nothing sensitive is written to Web Storage.
 * - On load the session is restored by exchanging the cookie (`/auth/refresh`) and fetching
 *   `/auth/me`; routes wait on `status === 'loading'` so a reload never flashes the sign-in page.
 * - `apiClient` renews access tokens by itself; when that finally fails it calls the handler
 *   below and the route guards send the visitor to sign in.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [user, setUser] = useState<User | null>(null)
  const [notice, setNotice] = useState<SessionNotice>(null)
  const restoreStarted = useRef(false)

  const signIn = useCallback((response: AuthResponse) => {
    tokenStorage.save(response.tokens)
    setUser(response.user)
    setNotice(null)
    setStatus('authenticated')
    return response.user
  }, [])

  const signOutLocally = useCallback((reason: SessionNotice = null) => {
    tokenStorage.clear()
    setUser(null)
    setNotice(reason)
    setStatus('unauthenticated')
  }, [])

  // Restore the session once per page load (a ref, so StrictMode's double effect runs it once).
  useEffect(() => {
    if (restoreStarted.current) return
    restoreStarted.current = true
    void (async () => {
      try {
        if (!(await refreshSession())) return signOutLocally()
        const me = await authService.me()
        setUser(me)
        setStatus('authenticated')
      } catch (error) {
        // Server unreachable: the cookie may still be valid, so say so instead of "expired".
        signOutLocally(isApiError(error) && error.isNetworkError ? 'unreachable' : null)
      }
    })()
  }, [signOutLocally])

  useEffect(() => {
    setUnauthorizedHandler(() => signOutLocally('expired'))
    return () => setUnauthorizedHandler(null)
  }, [signOutLocally])

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      notice,
      login: async (request, signal) => signIn(await authService.login(request, signal)),
      register: async (request, signal) => signIn(await authService.register(request, signal)),
      loginWithGoogle: async (idToken, signal) => signIn(await authService.google(idToken, signal)),
      logout: async () => {
        // If the server can't be reached the refresh cookie stays valid (JS can't clear an
        // httpOnly cookie), so staying "signed in" and reporting the failure is the honest outcome.
        try {
          await authService.logout()
        } catch (error) {
          if (!isApiError(error) || error.status === 0 || error.status >= 500) throw error
        }
        signOutLocally()
      },
      clearNotice: () => setNotice(null),
    }),
    [status, user, notice, signIn, signOutLocally],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
