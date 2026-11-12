import type {
  AuthResponse,
  ForgotPasswordRequest,
  ForgotPasswordResponse,
  GoogleAuthRequest,
  LoginRequest,
  MeResponse,
  RegisterRequest,
  ResetPasswordRequest,
  ResetPasswordResponse,
  VerifyResetCodeRequest,
  VerifyResetCodeResponse,
} from '@/types/api'
import { api } from './apiClient'
import { endpoints } from './endpoints'

/**
 * Typed wrappers over the auth endpoints (contract §2). They only talk to the API: keeping the
 * access token and the signed-in user is the AuthProvider's job, so these stay trivially testable.
 * Every public call passes `auth: false` so a stale bearer token is never attached to it.
 */
export const authService = {
  register: (body: RegisterRequest, signal?: AbortSignal) =>
    api.post<AuthResponse>(endpoints.auth.register, body, { auth: false, signal }),

  login: (body: LoginRequest, signal?: AbortSignal) =>
    api.post<AuthResponse>(endpoints.auth.login, body, { auth: false, signal }),

  google: (idToken: string, signal?: AbortSignal) =>
    api.post<AuthResponse>(endpoints.auth.google, { id_token: idToken } satisfies GoogleAuthRequest, {
      auth: false,
      signal,
    }),

  /** Revokes the session and clears the refresh cookie. 204. */
  logout: () => api.post<void>(endpoints.auth.logout, undefined, { auth: false, refresh: false }),

  me: (signal?: AbortSignal) => api.get<MeResponse>(endpoints.auth.me, { signal }),

  forgotPassword: (body: ForgotPasswordRequest, signal?: AbortSignal) =>
    api.post<ForgotPasswordResponse>(endpoints.auth.forgotPassword, body, { auth: false, signal }),

  verifyResetCode: (body: VerifyResetCodeRequest, signal?: AbortSignal) =>
    api.post<VerifyResetCodeResponse>(endpoints.auth.verifyResetCode, body, { auth: false, signal }),

  resetPassword: (body: ResetPasswordRequest, signal?: AbortSignal) =>
    api.post<ResetPasswordResponse>(endpoints.auth.resetPassword, body, { auth: false, signal }),
}
