/** Contract §2 — Authentication & User Management. */
import type { EntityId, ISODateTime } from './common'

export type UserRole = 'customer' | (string & {})

/** Full user, as returned by register (§2.1) and /auth/me (§2.3). */
export interface User {
  id: EntityId
  email: string
  full_name: string
  /** E.164, e.g. `+919876543210`. */
  phone: string | null
  role: UserRole
  is_active: boolean
  created_at: ISODateTime
}

/** Login (§2.2) returns a reduced user without `phone` / `created_at` (mismatch M5). */
export type LoginUser = Omit<User, 'phone' | 'created_at'> & Partial<Pick<User, 'phone' | 'created_at'>>

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  /** Access-token lifetime in seconds. */
  expires_in: number
}

/** POST /auth/register */
export interface RegisterRequest {
  email: string
  password: string
  /** Required by the contract but absent from the Register design (mismatch M2). */
  full_name: string
  /** E.164 — the UI's "+91" prefix + local number, concatenated client-side. */
  phone: string
}

/**
 * POST /auth/login. Backend confirmed (2026-11-05) that login will accept email OR mobile number
 * (M1). Exactly one of `email` / `phone` is sent; `phone` is E.164 (`+919876543210`).
 * Field name for phone is assumed to mirror RegisterRequest; confirm when the endpoint ships.
 */
export type LoginRequest =
  { email: string; phone?: never; password: string } | { phone: string; email?: never; password: string }

export interface AuthResponse<TUser = User> {
  user: TUser
  tokens: AuthTokens
}

export type RegisterResponse = AuthResponse<User>
export type LoginResponse = AuthResponse<LoginUser>
export type MeResponse = User
