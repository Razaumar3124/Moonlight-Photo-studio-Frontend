import type { FormValues, SubmitErrorResult } from '@/hooks/useForm'
import type { LoginRequest } from '@/types/api'
import { mapAuthError } from './authErrors'
import { parseIdentifier } from './identifier'
import { AUTH_LIMITS } from './limits'

export const LOGIN_FIELDS = ['identifier', 'password'] as const
export type LoginField = (typeof LOGIN_FIELDS)[number]
export type LoginValues = FormValues<LoginField>

export const LOGIN_INITIAL_VALUES: LoginValues = { identifier: '', password: '' }

export const IDENTIFIER_MAX_LENGTH = AUTH_LIMITS.email
export const PASSWORD_MAX_LENGTH = AUTH_LIMITS.password

/**
 * Login validates presence and shape only. Password rules are NOT checked here, because
 * revealing the policy on sign-in helps nobody, and older accounts may predate it.
 */
export function validateLoginField(field: LoginField, value: string): string | undefined {
  switch (field) {
    case 'identifier': {
      if (!value.trim()) return 'Enter your mobile number or email.'
      if (value.length > IDENTIFIER_MAX_LENGTH || parseIdentifier(value).kind === 'invalid') {
        return 'Enter a valid email or 10-digit mobile number.'
      }
      return undefined
    }
    case 'password':
      if (!value) return 'Enter your password.'
      if (value.length > PASSWORD_MAX_LENGTH)
        return `Password must be ${PASSWORD_MAX_LENGTH} characters or fewer.`
      return undefined
  }
}

/** Builds the API payload. Call only after validation passed. */
export function toLoginRequest(values: LoginValues): LoginRequest {
  const id = parseIdentifier(values.identifier)
  if (id.kind === 'invalid') throw new Error('toLoginRequest called with an invalid identifier')
  return id.kind === 'email'
    ? { email: id.value, password: values.password }
    : { phone: id.value, password: values.password }
}

/** API `details[].field` names → form fields. */
const LOGIN_API_FIELD_MAP: Partial<Record<string, LoginField>> = {
  email: 'identifier',
  phone: 'identifier',
  password: 'password',
}

/**
 * Maps a failed sign-in to user-facing feedback. Credential failures are deliberately generic
 * (never "no account with this email"); see mapAuthError.
 */
export function mapLoginError(error: unknown): SubmitErrorResult<LoginField> {
  return mapAuthError(error, LOGIN_API_FIELD_MAP, {
    rejected: 'Those details don’t match our records. Check them and try again.',
    rateLimited: 'Too many sign-in attempts. Please wait a minute and try again.',
    server: 'We couldn’t sign you in right now. Please try again shortly.',
  })
}
