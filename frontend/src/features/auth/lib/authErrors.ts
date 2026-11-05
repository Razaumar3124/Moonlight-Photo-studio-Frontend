import type { SubmitErrorResult } from '@/hooks/useForm'
import { isApiError } from '@/services/apiClient'

export interface AuthErrorMessages {
  /** 401/403, or a 4xx without usable field details. */
  rejected: string
  rateLimited: string
  server: string
  /** 409 Conflict without field details (e.g. account already exists). Defaults to `rejected`. */
  conflict?: string
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
  if (error.status === 429) return { formError: messages.rateLimited }
  if (error.status >= 500) return { formError: messages.server }
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
