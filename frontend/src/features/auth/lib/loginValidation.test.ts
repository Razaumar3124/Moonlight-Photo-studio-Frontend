import { describe, expect, it } from 'vitest'
import { ApiError } from '@/services/apiClient'
import {
  IDENTIFIER_MAX_LENGTH,
  mapLoginError,
  PASSWORD_MAX_LENGTH,
  toLoginRequest,
  validateLoginField,
} from './loginValidation'

describe('validateLoginField', () => {
  it('requires an identifier (whitespace-only counts as empty)', () => {
    expect(validateLoginField('identifier', '')).toMatch(/enter your mobile number or email/i)
    expect(validateLoginField('identifier', '   ')).toMatch(/enter your mobile number or email/i)
  })

  it('rejects malformed identifiers and over-long input', () => {
    expect(validateLoginField('identifier', '12345')).toMatch(/valid email/i)
    expect(validateLoginField('identifier', `${'a'.repeat(IDENTIFIER_MAX_LENGTH)}@x.com`)).toMatch(
      /valid email/i,
    )
  })

  it('accepts emails and mobile numbers', () => {
    expect(validateLoginField('identifier', 'a@b.co')).toBeUndefined()
    expect(validateLoginField('identifier', '9876543210')).toBeUndefined()
  })

  it('requires a password but does not enforce a policy on sign-in', () => {
    expect(validateLoginField('password', '')).toMatch(/enter your password/i)
    expect(validateLoginField('password', 'x')).toBeUndefined()
    expect(validateLoginField('password', ' ')).toBeUndefined() // spaces are valid characters
    expect(validateLoginField('password', 'p'.repeat(PASSWORD_MAX_LENGTH + 1))).toMatch(/or fewer/i)
  })
})

describe('toLoginRequest', () => {
  it('sends exactly one of email / phone, password untouched', () => {
    expect(toLoginRequest({ identifier: 'A@B.co', password: ' pw ' })).toEqual({
      email: 'a@b.co',
      password: ' pw ',
    })
    expect(toLoginRequest({ identifier: '9876543210', password: 'pw' })).toEqual({
      phone: '+919876543210',
      password: 'pw',
    })
  })

  it('throws if called with an invalid identifier (programming error)', () => {
    expect(() => toLoginRequest({ identifier: 'nope', password: 'x' })).toThrow(/invalid identifier/)
  })
})

describe('mapLoginError', () => {
  const apiError = (status: number, details: { field: string; issue: string }[] = []) =>
    new ApiError({ status, code: 'X', message: 'server text', details })

  it('keeps credential failures generic, even if the server names a field (no account discovery)', () => {
    const result = mapLoginError(apiError(401, [{ field: 'email', issue: 'No account for this email' }]))
    expect(result.fieldErrors).toBeUndefined()
    expect(result.formError).toMatch(/don’t match our records/)
  })

  it('maps 422 field details onto form fields', () => {
    expect(mapLoginError(apiError(422, [{ field: 'phone', issue: 'Invalid phone' }]))).toEqual({
      fieldErrors: { identifier: 'Invalid phone' },
    })
  })

  it('distinguishes rate limiting, server and network failures', () => {
    expect(mapLoginError(apiError(429)).formError).toMatch(/too many/i)
    expect(mapLoginError(apiError(503)).formError).toMatch(/right now/i)
    const network = new ApiError({ status: 0, code: 'NETWORK_ERROR', message: 'Unable to reach the server.' })
    expect(mapLoginError(network).formError).toBe('Unable to reach the server.')
  })

  it('never shows raw server/exception text for unexpected errors', () => {
    expect(mapLoginError(new Error('stack trace with internals')).formError).toBe(
      'Something went wrong. Please try again.',
    )
    expect(mapLoginError(apiError(500)).formError).not.toContain('server text')
  })
})
