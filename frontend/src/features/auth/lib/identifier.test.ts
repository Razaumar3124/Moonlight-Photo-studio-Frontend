import { describe, expect, it } from 'vitest'
import { isEmail, normalizePhone, parseIdentifier } from './identifier'

describe('normalizePhone', () => {
  it.each([
    ['9876543210', '+919876543210'],
    ['98765 43210', '+919876543210'],
    ['98765-43210', '+919876543210'],
    ['(98765) 43210', '+919876543210'],
    ['09876543210', '+919876543210'],
    ['919876543210', '+919876543210'],
    ['+91 98765 43210', '+919876543210'],
    ['+1 415 555 2671', '+14155552671'],
  ])('%s → %s', (input, expected) => {
    expect(normalizePhone(input)).toBe(expected)
  })

  it.each([
    '',
    '12345',
    '5876543210', // Indian mobiles start with 6–9
    '98765432101', // 11 digits, no trunk 0
    '+0123456789', // E.164 can't start with 0
    '+1234567', // too short for E.164
    '+1234567890123456', // too long for E.164
    '९८७६५४३२१०', // non-ASCII digits
    '98765abc10',
  ])('rejects %j', (input) => {
    expect(normalizePhone(input)).toBeNull()
  })
})

describe('isEmail', () => {
  it.each([
    'a@b.co',
    'first.last+tag@sub.example.com',
    '  padded@example.com  ',
    "o'brien@x.org",
    'A@B.CO',
    'x@mail.example.co.in',
  ])('accepts %j', (v) => expect(isEmail(v)).toBe(true))
  it.each([
    '',
    'a@b',
    'a@b.c',
    'a b@c.com',
    '@example.com',
    'user@',
    'a@@b.com',
    'a@b..co',
    'a..b@c.com',
    '.a@b.com',
    'a.@b.com',
    'a@-b.com',
    'a@b-.com',
    'a@b.c-o',
    'user@exa_mple.com',
    '"><script>@x.com',
    '<a@b.com>',
    `${'x'.repeat(65)}@example.com`,
  ])('rejects %j', (v) => expect(isEmail(v)).toBe(false))
})

describe('parseIdentifier', () => {
  it('normalises emails to trimmed lower case', () => {
    expect(parseIdentifier('  Aarav@Example.COM ')).toEqual({ kind: 'email', value: 'aarav@example.com' })
  })

  it('treats anything containing @ as an email attempt (never a phone)', () => {
    expect(parseIdentifier('98765@43210')).toEqual({ kind: 'invalid' })
  })

  it('parses mobile numbers to E.164', () => {
    expect(parseIdentifier('98765 43210')).toEqual({ kind: 'phone', value: '+919876543210' })
  })

  it('treats markup as plain invalid text', () => {
    expect(parseIdentifier('<script>alert(1)</script>')).toEqual({ kind: 'invalid' })
  })
})
