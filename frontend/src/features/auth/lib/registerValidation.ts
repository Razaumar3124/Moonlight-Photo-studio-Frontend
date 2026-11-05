import type { FormValues, SubmitErrorResult } from '@/hooks/useForm'
import type { RegisterRequest } from '@/types/api'
import { mapAuthError } from './authErrors'
import { isEmail, normalizeIndianMobile } from './identifier'
import { AUTH_LIMITS } from './limits'

/** Visual order of the form (also the order errors are focused in). */
export const REGISTER_FIELDS = ['fullName', 'email', 'phone', 'password'] as const
export type RegisterField = (typeof REGISTER_FIELDS)[number]
export type RegisterValues = FormValues<RegisterField>

export const REGISTER_INITIAL_VALUES: RegisterValues = { fullName: '', email: '', phone: '', password: '' }

export const FULL_NAME_MAX_LENGTH = AUTH_LIMITS.fullName
export const EMAIL_MAX_LENGTH = AUTH_LIMITS.email
export const PHONE_MAX_LENGTH = AUTH_LIMITS.phone
export const PASSWORD_MIN_LENGTH = AUTH_LIMITS.passwordMin
export const PASSWORD_MAX_LENGTH = AUTH_LIMITS.password

/**
 * Assumed policy until the backend publishes one (API_ALIGNMENT Q19): 8–128 chars, at least one
 * letter and one digit. Shown as a hint under the field so users know it before they fail it.
 */
export const PASSWORD_HINT = `Use at least ${PASSWORD_MIN_LENGTH} characters, including a letter and a number.`

/**
 * Names are hard: allow any script's letters and combining marks (Devanagari, Tamil, accents…)
 * plus spaces, apostrophes, hyphens and dots. Must start with a letter.
 */
const FULL_NAME_RE = /^\p{L}[\p{L}\p{M} .'’-]*$/u

/** Trim and collapse internal whitespace: "  Aarav   Sharma " → "Aarav Sharma". */
export function normalizeFullName(raw: string): string {
  return raw.trim().replace(/\s+/g, ' ')
}

export function validateRegisterField(field: RegisterField, value: string): string | undefined {
  switch (field) {
    case 'fullName': {
      const name = normalizeFullName(value)
      if (!name) return 'Enter your full name.'
      if (name.length < AUTH_LIMITS.fullNameMin) return 'Enter your full name.'
      if (name.length > FULL_NAME_MAX_LENGTH)
        return `Name must be ${FULL_NAME_MAX_LENGTH} characters or fewer.`
      if (!FULL_NAME_RE.test(name)) return 'Use letters only. Spaces, hyphens and apostrophes are fine.'
      return undefined
    }
    case 'email':
      if (!value.trim()) return 'Enter your email address.'
      if (value.trim().length > EMAIL_MAX_LENGTH || !isEmail(value)) return 'Enter a valid email address.'
      return undefined
    case 'phone':
      if (!value.trim()) return 'Enter your mobile number.'
      if (!normalizeIndianMobile(value)) return 'Enter a valid 10-digit mobile number.'
      return undefined
    case 'password':
      if (!value) return 'Create a password.'
      if (value.length < PASSWORD_MIN_LENGTH || !/\p{L}/u.test(value) || !/\d/.test(value))
        return PASSWORD_HINT
      if (value.length > PASSWORD_MAX_LENGTH)
        return `Password must be ${PASSWORD_MAX_LENGTH} characters or fewer.`
      return undefined
  }
}

/** Builds the API payload. Call only after validation passed. */
export function toRegisterRequest(values: RegisterValues): RegisterRequest {
  const phone = normalizeIndianMobile(values.phone)
  if (!phone) throw new Error('toRegisterRequest called with an invalid phone number')
  return {
    full_name: normalizeFullName(values.fullName),
    email: values.email.trim().toLowerCase(),
    phone,
    password: values.password,
  }
}

/** API `details[].field` names → form fields. */
const REGISTER_API_FIELD_MAP: Partial<Record<string, RegisterField>> = {
  full_name: 'fullName',
  email: 'email',
  phone: 'phone',
  password: 'password',
}

export function mapRegisterError(error: unknown): SubmitErrorResult<RegisterField> {
  return mapAuthError(error, REGISTER_API_FIELD_MAP, {
    rejected: 'We couldn’t create your account. Check your details and try again.',
    conflict: 'An account with this email or mobile number already exists. Try signing in instead.',
    rateLimited: 'Too many attempts. Please wait a minute and try again.',
    server: 'We couldn’t create your account right now. Please try again shortly.',
  })
}
