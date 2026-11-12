import { createElement, type ReactNode } from 'react'
import { vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '@/features/auth/authContext'
import type { User } from '@/types/api'

export const TEST_USER: User = {
  id: '665f1c2e9b1d4a0012345678',
  email: 'aarav@example.com',
  full_name: 'Aarav Sharma',
  phone: '+919876543210',
  role: 'customer',
  is_active: true,
  created_at: '2026-11-12T00:00:00+00:00',
}

/** An AuthContext value whose actions are spies; override what a test cares about. */
export function fakeAuth(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    status: 'unauthenticated',
    user: null,
    notice: null,
    login: vi.fn<AuthContextValue['login']>().mockResolvedValue(TEST_USER),
    register: vi.fn<AuthContextValue['register']>().mockResolvedValue(TEST_USER),
    loginWithGoogle: vi.fn<AuthContextValue['loginWithGoogle']>().mockResolvedValue(TEST_USER),
    logout: vi.fn<AuthContextValue['logout']>().mockResolvedValue(undefined),
    clearNotice: vi.fn<AuthContextValue['clearNotice']>(),
    ...overrides,
  }
}

export function WithAuth({ value, children }: { value: AuthContextValue; children: ReactNode }) {
  return createElement(AuthContext, { value }, children)
}
