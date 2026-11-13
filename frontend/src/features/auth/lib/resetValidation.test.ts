import { describe, expect, it } from 'vitest'
import { ApiError } from '@/services/apiClient'
import { mapGoogleError } from './authErrors'
import {
  mapCodeStepError,
  mapEmailStepError,
  mapPasswordStepError,
  sanitizeOtp,
  validateCodeStep,
  validateEmailStep,
  validatePasswordStep,
} from './resetValidation'

const apiError = (status: number, code = 'X', details: { field: string; issue: string }[] = []) =>
  new ApiError({ status, code, message: 'raw server text', details })

describe('sanitizeOtp', () => {
  it.each([
    ['123456', '123456'],
    ['123 456', '123456'],
    ['12-34-56', '123456'],
    ['1234567890', '123456'],
    ['abc', ''],
  ])('%j -> %j', (raw, expected) => expect(sanitizeOtp(raw)).toBe(expected))
})

describe('step validation', () => {
  it('email', () => {
    expect(validateEmailStep('email', '')).toBe('Enter your email address.')
    expect(validateEmailStep('email', 'nope')).toBe('Enter a valid email address.')
    expect(validateEmailStep('email', 'a@example.com')).toBeUndefined()
  })

  it('code', () => {
    expect(validateCodeStep('otp', '')).toMatch(/Enter the 6-digit code/)
    expect(validateCodeStep('otp', '12345')).toBe('The code is 6 digits.')
    expect(validateCodeStep('otp', '123456')).toBeUndefined()
  })

  it('new password follows the registration policy and must be confirmed', () => {
    const values = { password: 'newpass99', confirm: 'newpass99' }
    expect(validatePasswordStep('password', '', values)).toBe('Enter a new password.')
    expect(validatePasswordStep('password', 'short1', values)).toMatch(/at least 8/)
    expect(validatePasswordStep('password', 'onlyletters', values)).toMatch(/letter and a number/)
    expect(validatePasswordStep('password', 'newpass99', values)).toBeUndefined()
    expect(validatePasswordStep('confirm', '', values)).toBe('Re-enter your new password.')
    expect(validatePasswordStep('confirm', 'other', values)).toBe('The two passwords don’t match.')
    expect(validatePasswordStep('confirm', 'newpass99', values)).toBeUndefined()
  })
})

describe('error mapping never shows raw server text', () => {
  it('code step: field detail on 422, generic otherwise', () => {
    expect(
      mapCodeStepError(
        apiError(422, 'VALIDATION_ERROR', [{ field: 'otp', issue: 'Invalid code. 2 attempt(s) left.' }]),
      ),
    ).toEqual({
      fieldErrors: { otp: 'Invalid code. 2 attempt(s) left.' },
    })
    expect(mapCodeStepError(apiError(422)).formError).toMatch(/incorrect or has expired/)
    expect(mapCodeStepError(apiError(429)).formError).toMatch(/Too many attempts/)
    expect(mapCodeStepError(apiError(503)).formError).not.toMatch(/raw server text/)
  })

  it('email step and password step', () => {
    expect(mapEmailStepError(apiError(429)).formError).toMatch(/Too many requests/)
    expect(mapPasswordStepError(apiError(401)).formError).toMatch(/reset session has expired/)
    expect(
      mapPasswordStepError(
        apiError(422, 'VALIDATION_ERROR', [{ field: 'new_password', issue: 'Too common' }]),
      ),
    ).toEqual({ fieldErrors: { password: 'Too common' } })
  })

  it('says clearly when the daily email allowance is used up, and still treats other 503s as a failure', () => {
    expect(mapEmailStepError(apiError(503, 'EMAIL_DAILY_LIMIT_REACHED')).formError).toMatch(
      /daily sending limit was reached.*tomorrow/,
    )
    expect(mapEmailStepError(apiError(503, 'EMAIL_DELIVERY_FAILED')).formError).toMatch(
      /couldn’t send a code right now/,
    )
    expect(mapEmailStepError(apiError(503, 'EMAIL_DAILY_LIMIT_REACHED')).formError).not.toMatch(
      /raw server text/,
    )
  })

  it('unknown thrown values get a neutral message', () => {
    expect(mapEmailStepError(new Error('boom')).formError).toBe('Something went wrong. Please try again.')
    expect(mapGoogleError('boom')).toBe('Something went wrong. Please try again.')
  })
})
