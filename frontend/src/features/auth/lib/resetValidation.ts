import type { SubmitErrorResult } from '@/hooks/useForm'
import { mapAuthError } from './authErrors'
import { isEmail } from './identifier'
import { AUTH_LIMITS } from './limits'
import { validateRegisterField } from './registerValidation'

/* Password recovery is three small forms: email → 6-digit code → new password. */

export const OTP_LENGTH = 6

/** Keep only digits, at most six: pasted "123 456" or "123-456" still works. */
export function sanitizeOtp(raw: string): string {
  return raw.replace(/\D/g, '').slice(0, OTP_LENGTH)
}

/* --------------------------------- Step 1 --------------------------------- */

export const EMAIL_STEP_FIELDS = ['email'] as const
export type EmailStepField = (typeof EMAIL_STEP_FIELDS)[number]

export function validateEmailStep(_field: EmailStepField, value: string): string | undefined {
  if (!value.trim()) return 'Enter your email address.'
  if (value.trim().length > AUTH_LIMITS.email || !isEmail(value)) return 'Enter a valid email address.'
  return undefined
}

/** The studio's daily email allowance is used up (the API answers 503 for every address). */
export const EMAIL_LIMIT_MESSAGE =
  'Password reset emails are unavailable right now because the daily sending limit was reached. Please try again tomorrow or contact the studio.'

export function mapEmailStepError(error: unknown): SubmitErrorResult<EmailStepField> {
  return mapAuthError(
    error,
    { email: 'email' },
    {
      rejected: 'We couldn’t send a code. Check the email address and try again.',
      rateLimited: 'Too many requests. Please wait a minute before asking for another code.',
      server: 'We couldn’t send a code right now. Please try again shortly.',
      byCode: { EMAIL_DAILY_LIMIT_REACHED: EMAIL_LIMIT_MESSAGE },
    },
  )
}

/* --------------------------------- Step 2 --------------------------------- */

export const CODE_STEP_FIELDS = ['otp'] as const
export type CodeStepField = (typeof CODE_STEP_FIELDS)[number]

export function validateCodeStep(_field: CodeStepField, value: string): string | undefined {
  if (!value) return 'Enter the 6-digit code from your email.'
  if (!new RegExp(`^\\d{${OTP_LENGTH}}$`).test(value)) return `The code is ${OTP_LENGTH} digits.`
  return undefined
}

export function mapCodeStepError(error: unknown): SubmitErrorResult<CodeStepField> {
  return mapAuthError(
    error,
    { otp: 'otp' },
    {
      rejected: 'That code is incorrect or has expired. Check it, or request a new one.',
      rateLimited: 'Too many attempts. Please wait a few minutes and try again.',
      server: 'We couldn’t check the code right now. Please try again shortly.',
    },
  )
}

/* --------------------------------- Step 3 --------------------------------- */

export const PASSWORD_STEP_FIELDS = ['password', 'confirm'] as const
export type PasswordStepField = (typeof PASSWORD_STEP_FIELDS)[number]

export function validatePasswordStep(
  field: PasswordStepField,
  value: string,
  values: Record<PasswordStepField, string>,
): string | undefined {
  if (field === 'password') {
    return validateRegisterField('password', value)?.replace('Create a password.', 'Enter a new password.')
  }
  if (!value) return 'Re-enter your new password.'
  if (value !== values.password) return 'The two passwords don’t match.'
  return undefined
}

export function mapPasswordStepError(error: unknown): SubmitErrorResult<PasswordStepField> {
  return mapAuthError(
    error,
    { new_password: 'password' },
    {
      rejected: 'This reset session has expired. Please start again to get a new code.',
      rateLimited: 'Too many attempts. Please wait a few minutes and try again.',
      server: 'We couldn’t reset your password right now. Please try again shortly.',
    },
  )
}
