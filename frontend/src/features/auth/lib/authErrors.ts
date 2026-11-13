import type { SubmitErrorResult } from '@/hooks/useForm'
import { isApiError } from '@/services/apiClient'

export interface AuthErrorMessages {
  /** 401/403, or a 4xx without usable field details. */
  rejected: string
  rateLimited: string
  server: string
  /** 409 Conflict without field details (e.g. account already exists). Defaults to `rejected`. */
  conflict?: string
  /** 403 ACCOUNT_DISABLED (the API only says so after a correct password). Defaults to `rejected`. */
  disabled?: string
  /** Messages for specific API error codes (checked before the status-based ones). */
  byCode?: Record<string, string>
}

const UNKNOWN = 'Something went wrong. Please try again.'

/**
 * Shared mapping of a failed auth request (login, register) to form feedback.
 * - 401/403 are always generic: field details are ignored so the form can't be used to discover
 *   accounts.
 * - 400/409/422 field details are mapped onto form fields via `fieldMap` (API name → form field).
 * - Server text is shown only as field-level `details[].issue`; never 5xx bodies or exceptions.
 */
export function mapAuthError<F extends string>(
  error: unknown,
  fieldMap: Partial<Record<string, F>>,
  messages: AuthErrorMessages,
): SubmitErrorResult<F> {
  if (!isApiError(error)) return { formError: UNKNOWN }
  if (error.isNetworkError) return { formError: error.message }
  const coded = messages.byCode?.[error.code]
  if (coded) return { formError: coded }
  if (error.status === 429) return { formError: messages.rateLimited }
  if (error.status >= 500) return { formError: messages.server }
  if (error.code === 'ACCOUNT_DISABLED') return { formError: messages.disabled ?? messages.rejected }
  if (error.status === 401 || error.status === 403) return { formError: messages.rejected }

  const fieldErrors: Partial<Record<F, string>> = {}
  for (const [apiField, issue] of Object.entries(error.fieldErrors)) {
    const field = fieldMap[apiField]
    if (field && !fieldErrors[field]) fieldErrors[field] = issue
  }
  if (Object.keys(fieldErrors).length) return { fieldErrors }
  if (error.status === 409) return { formError: messages.conflict ?? messages.rejected }
  return { formError: messages.rejected }
}

/** Feedback for a failed "Continue with Google" (no form field to attach it to). */
export function mapGoogleError(error: unknown): string {
  if (!isApiError(error)) return UNKNOWN
  if (error.isNetworkError) return error.message
  if (error.code === 'REGISTRATION_LIMIT_REACHED') {
    return 'Too many accounts were created from your network today. Please try again tomorrow or contact the studio.'
  }
  if (error.status === 429) return 'Too many attempts. Please wait a minute and try again.'
  if (error.code === 'GOOGLE_AUTH_NOT_CONFIGURED' || error.status === 503) {
    return 'Google sign-in isn’t available right now. Please use your email or mobile number.'
  }
  if (error.code === 'ACCOUNT_DISABLED') return 'This account has been disabled. Please contact the studio.'
  if (error.status >= 500) return 'We couldn’t sign you in right now. Please try again shortly.'
  return 'We couldn’t verify your Google sign-in. Please try again, or use your email or mobile number.'
}
