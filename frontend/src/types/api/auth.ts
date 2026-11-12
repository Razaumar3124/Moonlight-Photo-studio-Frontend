/** Contract §2 — Authentication & User Management. */
import type { EntityId, ISODateTime } from './common'

export type UserRole = 'customer' | 'admin' | (string & {})

/** `UserOut`: returned by register, login, Google sign-in and /auth/me (M5 resolved). */
export interface User {
  id: EntityId
  email: string
  full_name: string
  /** E.164, e.g. `+919876543210`. Null for some Google accounts. */
  phone: string | null
  role: UserRole
  is_active: boolean
  created_at: ISODateTime
}

/**
 * Access token only. The refresh token is an httpOnly cookie the browser sends to
 * `/api/v1/auth/*` automatically; it never appears in a response body (API_ALIGNMENT Q2/Q3).
 */
export interface AuthTokens {
  access_token: string
  token_type: 'bearer'
  /** Access-token lifetime in seconds. */
  expires_in: number
}

/** POST /auth/register */
export interface RegisterRequest {
  /** 2–100 characters; letters (any script), spaces, hyphens and apostrophes. */
  full_name: string
  email: string
  /** Indian mobile number: 10 digits or E.164 `+91…` (Q15: India only in v1). */
  phone: string
  /** 8–128 characters, at least one letter and one digit. */
  password: string
}

/**
 * POST /auth/login. Send exactly one of `email`, `phone` (E.164) or `identifier` (either,
 * the server decides). Unknown account and wrong password both return 401 INVALID_CREDENTIALS.
 */
export type LoginRequest =
  | { email: string; phone?: never; identifier?: never; password: string }
  | { phone: string; email?: never; identifier?: never; password: string }
  | { identifier: string; email?: never; phone?: never; password: string }

export interface AuthResponse {
  user: User
  tokens: AuthTokens
}

export type RegisterResponse = AuthResponse
export type LoginResponse = AuthResponse
export type MeResponse = User

/** POST /auth/google — the Google Identity Services credential. */
export interface GoogleAuthRequest {
  id_token: string
}

/* ------------------------------ Password reset ----------------------------- */

/** POST /auth/forgot-password. Same 200 response whether or not the account exists. */
export interface ForgotPasswordRequest {
  email: string
}

export interface ForgotPasswordResponse {
  message: string
  cooldown_seconds: number
}

/** POST /auth/forgot-password/verify. Wrong or expired codes → 422. */
export interface VerifyResetCodeRequest {
  email: string
  /** 6 digits from the email. */
  otp: string
}

export interface VerifyResetCodeResponse {
  reset_token: string
  expires_in_seconds: number
}

/** POST /auth/forgot-password/reset. Revokes every session of the account. */
export interface ResetPasswordRequest {
  reset_token: string
  new_password: string
}

export interface ResetPasswordResponse {
  message: string
}
