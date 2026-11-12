import { createContext, useContext } from 'react'
import type { LoginRequest, RegisterRequest, User } from '@/types/api'

/**
 * - `loading`: restoring the session after a page load (the refresh cookie is being exchanged).
 * - `authenticated` / `unauthenticated`: settled.
 */
export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

/** Why the visitor is on the sign-in page without having chosen to be. Shown once, then cleared. */
export type SessionNotice = 'expired' | 'unreachable' | null

export interface AuthContextValue {
  status: AuthStatus
  user: User | null
  notice: SessionNotice
  login: (request: LoginRequest, signal?: AbortSignal) => Promise<User>
  register: (request: RegisterRequest, signal?: AbortSignal) => Promise<User>
  loginWithGoogle: (idToken: string, signal?: AbortSignal) => Promise<User>
  /** Revokes the session on the server, then clears local state. Rejects if the server can't be reached. */
  logout: () => Promise<void>
  clearNotice: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
