import { describe, expect, it } from 'vitest'
import { ApiError } from '@/services/apiClient'
import { normalizeIndianMobile } from './identifier'
import {
  FULL_NAME_MAX_LENGTH,
  mapRegisterError,
  normalizeFullName,
  PASSWORD_HINT,
  PASSWORD_MAX_LENGTH,
  toRegisterRequest,
  validateRegisterField,
} from './registerValidation'

describe('full name', () => {
  it.each([
    'Aarav Sharma',
    'Zoë O’Brien',
    "D'Souza",
    'Jean-Luc Picard',
    'A. R. Rahman',
    'आरव शर्मा',
    'அருண் குமார்',
    'Li',
  ])('accepts %j', (name) => expect(validateRegisterField('fullName', name)).toBeUndefined())

  it.each([
    ['', /enter your full name/i],
    ['   ', /enter your full name/i],
    ['A', /enter your full name/i],
    ['Aarav123', /letters only/i],
    ['<script>', /letters only/i],
    ['-Aarav', /letters only/i],
    ['a'.repeat(FULL_NAME_MAX_LENGTH + 1), /or fewer/i],
  ])('rejects %j', (name, message) => expect(validateRegisterField('fullName', name)).toMatch(message))

  it('collapses whitespace', () => expect(normalizeFullName('  Aarav   Sharma ')).toBe('Aarav Sharma'))
})

describe('email', () => {
  it('requires a valid address', () => {
    expect(validateRegisterField('email', '')).toMatch(/enter your email/i)
    expect(validateRegisterField('email', 'aarav@')).toMatch(/valid email/i)
    expect(validateRegisterField('email', ' aarav@example.com ')).toBeUndefined()
  })
})

describe('mobile (fixed +91 prefix)', () => {
  it.each(['9876543210', '98765 43210', '098765 43210', '+91 98765 43210', '919876543210'])(
    'accepts %j',
    (v) => {
      expect(validateRegisterField('phone', v)).toBeUndefined()
      expect(normalizeIndianMobile(v)).toBe('+919876543210')
    },
  )

  it.each(['', '12345', '5876543210', '+1 415 555 2671', 'abc'])('rejects %j', (v) => {
    expect(validateRegisterField('phone', v)).toBeDefined()
  })
})

describe('password policy', () => {
  it.each(['short1', 'onlyletters', '1234567890', ''])('rejects %j', (pw) =>
    expect(validateRegisterField('password', pw)).toBeDefined(),
  )
  it('shows the policy hint as the error for weak passwords', () =>
    expect(validateRegisterField('password', 'abc')).toBe(PASSWORD_HINT))
  it.each(['memories85', 'Ünïcödé 2026', 'pass word 1'])('accepts %j', (pw) =>
    expect(validateRegisterField('password', pw)).toBeUndefined(),
  )
  it('caps length', () =>
    expect(validateRegisterField('password', `a1${'x'.repeat(PASSWORD_MAX_LENGTH)}`)).toMatch(/or fewer/i))
})

describe('toRegisterRequest', () => {
  it('normalises name, email and phone; leaves the password untouched', () => {
    expect(
      toRegisterRequest({
        fullName: '  Aarav   Sharma ',
        email: ' Aarav@Example.COM ',
        phone: '98765 43210',
        password: ' pw 12345 ',
      }),
    ).toEqual({
      full_name: 'Aarav Sharma',
      email: 'aarav@example.com',
      phone: '+919876543210',
      password: ' pw 12345 ',
    })
  })
})

describe('mapRegisterError', () => {
  const apiError = (status: number, details: { field: string; issue: string }[] = []) =>
    new ApiError({ status, code: 'X', message: 'server text', details })

  it('maps API field names (full_name, email, phone) onto form fields', () => {
    expect(
      mapRegisterError(
        apiError(422, [
          { field: 'full_name', issue: 'Too short' },
          { field: 'email', issue: 'Already registered' },
        ]),
      ),
    ).toEqual({ fieldErrors: { fullName: 'Too short', email: 'Already registered' } })
  })

  it('explains a duplicate account (409) and suggests signing in', () => {
    expect(mapRegisterError(apiError(409)).formError).toMatch(/already exists.*sign/i)
  })

  it('uses register-specific copy for rate limits and server errors', () => {
    expect(mapRegisterError(apiError(429)).formError).toMatch(/too many attempts/i)
    expect(mapRegisterError(apiError(500)).formError).toMatch(/create your account/i)
  })
})
