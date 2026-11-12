import { describe, expect, it } from 'vitest'
import { postLoginPath } from './redirect'

describe('postLoginPath', () => {
  it('returns to the page the visitor was sent away from', () => {
    expect(postLoginPath({ from: '/memory-wall' })).toBe('/memory-wall')
    expect(postLoginPath({ from: '/memory-wall?design=1' })).toBe('/memory-wall?design=1')
  })

  it('defaults to the planner', () => {
    expect(postLoginPath(null)).toBe('/memory-wall')
    expect(postLoginPath(undefined)).toBe('/memory-wall')
    expect(postLoginPath({})).toBe('/memory-wall')
  })

  it.each([
    'https://evil.example/phish',
    '//evil.example',
    '/\\evil.example',
    'javascript:alert(1)',
    'memory-wall',
    '',
    42,
    { nested: '/x' },
  ])('refuses a crafted target %j (no open redirect)', (from) => {
    expect(postLoginPath({ from })).toBe('/memory-wall')
  })

  it.each(['/login', '/register', '/forgot-password', '/', '/login?x=1', '/register#top'])(
    'never bounces back to an auth page (%s)',
    (from) => {
      expect(postLoginPath({ from })).toBe('/memory-wall')
    },
  )
})
