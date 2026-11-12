// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AuthContextValue } from '@/features/auth/authContext'
import { ApiError } from '@/services/apiClient'
import { fakeAuth, WithAuth } from '@/test/fakeAuth'
import { LoginForm } from './LoginForm'
import { RegisterForm } from './RegisterForm'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderAt(element: React.ReactNode, auth = fakeAuth()) {
  const router = createMemoryRouter(
    [
      { path: '/', element },
      { path: '/forgot-password', element: <h1>Forgot</h1> },
    ],
    { initialEntries: ['/'] },
  )
  render(
    <WithAuth value={auth}>
      <RouterProvider router={router} />
    </WithAuth>,
  )
  return { router, auth }
}

async function fillRegister() {
  await userEvent.type(screen.getByLabelText('Full Name'), 'Aarav Sharma')
  await userEvent.type(screen.getByLabelText('Email Address'), 'a@example.com')
  await userEvent.type(screen.getByLabelText(/Mobile Number/), '9876543210')
  await userEvent.type(screen.getByLabelText('Password', { exact: true }), 'memories85')
  await userEvent.click(screen.getByRole('button', { name: 'Create Account' }))
}

async function fillLogin() {
  await userEvent.type(screen.getByLabelText('Mobile No. or Email'), 'a@example.com')
  await userEvent.type(screen.getByLabelText('Password', { exact: true }), 'pw')
  await userEvent.click(screen.getByRole('button', { name: 'Sign In' }))
}

describe('RegisterForm', () => {
  it('labels every field (incl. the +91 country code for screen readers)', () => {
    renderAt(<RegisterForm />)
    for (const name of ['Full Name', 'Email Address', 'Mobile Number, country code +91', 'Password']) {
      expect(screen.getByLabelText(name)).toBeTruthy()
    }
    const pw = screen.getByLabelText('Password', { exact: true })
    expect(pw.getAttribute('aria-describedby')).toBeTruthy()
    expect(document.getElementById(pw.getAttribute('aria-describedby') ?? '')?.textContent).toMatch(
      /at least 8/,
    )
  })

  it('sends a normalised payload to the auth layer', async () => {
    const { auth } = renderAt(<RegisterForm />)
    await userEvent.type(screen.getByLabelText('Full Name'), '  Aarav   Sharma ')
    await userEvent.type(screen.getByLabelText('Email Address'), 'Aarav@Example.com')
    await userEvent.type(screen.getByLabelText(/Mobile Number/), '98765 43210')
    await userEvent.type(screen.getByLabelText('Password', { exact: true }), 'memories85')
    await userEvent.click(screen.getByRole('button', { name: 'Create Account' }))
    expect(auth.register).toHaveBeenCalledWith(
      {
        full_name: 'Aarav Sharma',
        email: 'aarav@example.com',
        phone: '+919876543210',
        password: 'memories85',
      },
      expect.any(AbortSignal),
    )
  })

  it('blocks invalid input without calling the API', async () => {
    const { auth } = renderAt(<RegisterForm />)
    await userEvent.type(screen.getByLabelText('Email Address'), '"><script>@x.com')
    await userEvent.click(screen.getByRole('button', { name: 'Create Account' }))
    expect(screen.getByText('Enter a valid email address.')).toBeTruthy()
    expect(auth.register).not.toHaveBeenCalled()
  })

  it('maps a duplicate-account conflict to a friendly form error', async () => {
    const auth = fakeAuth({
      register: vi
        .fn<AuthContextValue['register']>()
        .mockRejectedValue(new ApiError({ status: 409, code: 'ACCOUNT_ALREADY_EXISTS', message: 'exists' })),
    })
    renderAt(<RegisterForm />, auth)
    await fillRegister()
    expect((await screen.findByRole('alert')).textContent).toMatch(/already exists/)
  })

  it('maps server field errors onto the matching input', async () => {
    const auth = fakeAuth({
      register: vi.fn<AuthContextValue['register']>().mockRejectedValue(
        new ApiError({
          status: 422,
          code: 'VALIDATION_ERROR',
          message: 'invalid',
          details: [{ field: 'phone', issue: 'Enter a valid 10-digit Indian mobile number' }],
        }),
      ),
    })
    renderAt(<RegisterForm />, auth)
    await fillRegister()
    expect(await screen.findByText('Enter a valid 10-digit Indian mobile number')).toBeTruthy()
  })

  it('offers Google sign-in without the old "coming soon" placeholder', () => {
    renderAt(<RegisterForm />)
    expect(screen.queryByText(/coming soon/i)).toBeNull()
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeTruthy()
  })
})

describe('LoginForm', () => {
  it('sends email OR phone (E.164) to the auth layer', async () => {
    const { auth } = renderAt(<LoginForm />)
    await userEvent.type(screen.getByLabelText('Mobile No. or Email'), '098765 43210')
    await userEvent.type(screen.getByLabelText('Password', { exact: true }), 'pw')
    await userEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(auth.login).toHaveBeenCalledWith(
      { phone: '+919876543210', password: 'pw' },
      expect.any(AbortSignal),
    )
  })

  it.each([
    [401, 'INVALID_CREDENTIALS', /don’t match our records/],
    [429, 'RATE_LIMIT_EXCEEDED', /Too many sign-in attempts/],
    [403, 'ACCOUNT_DISABLED', /disabled/],
    [500, 'INTERNAL_ERROR', /couldn’t sign you in/],
    [0, 'NETWORK_ERROR', /Unable to reach the server/],
  ])('shows a safe message for a %i (%s) response', async (status, code, message) => {
    const auth = fakeAuth({
      login: vi.fn<AuthContextValue['login']>().mockRejectedValue(
        new ApiError({
          status,
          code,
          message:
            status === 0
              ? 'Unable to reach the server. Check your connection and try again.'
              : 'raw server text',
        }),
      ),
    })
    renderAt(<LoginForm />, auth)
    await fillLogin()
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(message)
    expect(alert.textContent).not.toMatch(/raw server text/)
  })

  it('ignores server field details on 401 so the form cannot reveal which accounts exist', async () => {
    const auth = fakeAuth({
      login: vi.fn<AuthContextValue['login']>().mockRejectedValue(
        new ApiError({
          status: 401,
          code: 'INVALID_CREDENTIALS',
          message: 'x',
          details: [{ field: 'email', issue: 'No account with this email' }],
        }),
      ),
    })
    renderAt(<LoginForm />, auth)
    await fillLogin()
    await screen.findByRole('alert')
    expect(screen.queryByText(/No account with this email/)).toBeNull()
  })

  it('links to the forgot-password page', async () => {
    const { router } = renderAt(<LoginForm />)
    await userEvent.click(screen.getByRole('link', { name: 'Forgot Password?' }))
    expect(router.state.location.pathname).toBe('/forgot-password')
  })

  it('password toggle keeps its name and flips aria-pressed + input type', async () => {
    renderAt(<LoginForm />)
    const toggle = screen.getByRole('button', { name: 'Show password' })
    const pw = screen.getByLabelText('Password', { exact: true })
    expect(pw.getAttribute('type')).toBe('password')
    await userEvent.click(toggle)
    expect(toggle.getAttribute('aria-pressed')).toBe('true')
    expect(pw.getAttribute('type')).toBe('text')
  })
})
