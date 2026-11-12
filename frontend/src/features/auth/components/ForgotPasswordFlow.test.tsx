// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ForgotPasswordFlow } from './ForgotPasswordFlow'

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const error = (status: number, code: string, details: { field: string; issue: string }[] = []) =>
  json(status, { error: { code, message: 'server text', details, timestamp: '' } })

type Handler = (body: Record<string, unknown>) => Response
let routes: Record<string, Handler>
const requests: { path: string; body: Record<string, unknown>; headers: Headers }[] = []

beforeEach(() => {
  routes = {}
  requests.length = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const path = String(url).replace('/api/v1', '')
      const body = init.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {}
      requests.push({ path, body, headers: new Headers(init.headers) })
      const handler = routes[path]
      if (!handler) throw new Error(`Unexpected request ${path}`)
      return handler(body)
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

function renderFlow() {
  const router = createMemoryRouter(
    [
      { path: '/', element: <ForgotPasswordFlow onStepChange={() => undefined} /> },
      { path: '/login', element: <h1>Sign in page</h1> },
    ],
    { initialEntries: ['/'] },
  )
  render(<RouterProvider router={router} />)
  return router
}

const sendCode = async (email = 'Aarav@Example.com') => {
  await userEvent.type(screen.getByLabelText('Email Address'), email)
  await userEvent.click(screen.getByRole('button', { name: 'Send Code' }))
}

describe('password recovery flow', () => {
  it('runs email → code → new password → sign in, sending only what the API needs', async () => {
    routes['/auth/forgot-password'] = () => json(200, { message: 'sent', cooldown_seconds: 60 })
    routes['/auth/forgot-password/verify'] = () =>
      json(200, { reset_token: 'reset-token-abcdef', expires_in_seconds: 600 })
    routes['/auth/forgot-password/reset'] = () => json(200, { message: 'done' })
    const router = renderFlow()

    await sendCode()
    expect(requests[0]).toMatchObject({
      path: '/auth/forgot-password',
      body: { email: 'aarav@example.com' },
    })
    expect(requests[0]?.headers.has('Authorization')).toBe(false)

    // Non-enumerating wording: never "we sent a code to your account".
    expect(await screen.findByText(/If an account exists for/)).toBeTruthy()
    // Pasted/formatted codes are reduced to digits.
    await userEvent.type(screen.getByLabelText('Verification Code'), '12a 34-56')
    expect((screen.getByLabelText('Verification Code') as HTMLInputElement).value).toBe('123456')
    await userEvent.click(screen.getByRole('button', { name: 'Verify Code' }))
    expect(requests[1]).toMatchObject({
      path: '/auth/forgot-password/verify',
      body: { email: 'aarav@example.com', otp: '123456' },
    })

    await userEvent.type(await screen.findByLabelText('New Password', { exact: true }), 'newpass99')
    await userEvent.type(screen.getByLabelText('Confirm Password'), 'newpass99')
    await userEvent.click(screen.getByRole('button', { name: 'Reset Password' }))
    expect(requests[2]).toMatchObject({
      path: '/auth/forgot-password/reset',
      body: { reset_token: 'reset-token-abcdef', new_password: 'newpass99' },
    })
    expect(await screen.findByRole('heading', { name: 'Sign in page' })).toBeTruthy()
    expect(router.state.location.state).toEqual({ passwordReset: true })
  })

  it('validates the email and the code before calling the API', async () => {
    routes['/auth/forgot-password'] = () => json(200, { message: 'sent', cooldown_seconds: 60 })
    renderFlow()
    await userEvent.click(screen.getByRole('button', { name: 'Send Code' }))
    expect(screen.getByText('Enter your email address.')).toBeTruthy()
    expect(requests).toHaveLength(0)

    await sendCode('a@example.com')
    await userEvent.type(await screen.findByLabelText('Verification Code'), '123')
    await userEvent.click(screen.getByRole('button', { name: 'Verify Code' }))
    expect(screen.getByText('The code is 6 digits.')).toBeTruthy()
    expect(requests).toHaveLength(1)
  })

  it('shows the server’s attempts-left message for a wrong code and stays on the step', async () => {
    routes['/auth/forgot-password'] = () => json(200, { message: 'sent', cooldown_seconds: 60 })
    routes['/auth/forgot-password/verify'] = () =>
      error(422, 'VALIDATION_ERROR', [{ field: 'otp', issue: 'Invalid code. 2 attempt(s) left.' }])
    renderFlow()
    await sendCode('a@example.com')
    await userEvent.type(await screen.findByLabelText('Verification Code'), '000000')
    await userEvent.click(screen.getByRole('button', { name: 'Verify Code' }))
    expect(await screen.findByText('Invalid code. 2 attempt(s) left.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Verify Code' })).toBeTruthy()
  })

  it.each([
    [429, 'RATE_LIMIT_EXCEEDED', /Too many attempts/],
    [500, 'INTERNAL_ERROR', /couldn’t check the code/],
  ])('handles a %i while verifying without leaking server text', async (status, code, message) => {
    routes['/auth/forgot-password'] = () => json(200, { message: 'sent', cooldown_seconds: 60 })
    routes['/auth/forgot-password/verify'] = () => error(status, code)
    renderFlow()
    await sendCode('a@example.com')
    await userEvent.type(await screen.findByLabelText('Verification Code'), '123456')
    await userEvent.click(screen.getByRole('button', { name: 'Verify Code' }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(message)
    expect(alert.textContent).not.toMatch(/server text/)
  })

  it('rate-limits the first request politely', async () => {
    routes['/auth/forgot-password'] = () => error(429, 'RATE_LIMIT_EXCEEDED')
    renderFlow()
    await sendCode('a@example.com')
    expect((await screen.findByRole('alert')).textContent).toMatch(/Too many requests/)
  })

  it('throttles resend by the server cooldown, then allows it and invalidates nothing client-side', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let sent = 0
    routes['/auth/forgot-password'] = () => {
      sent += 1
      return json(200, { message: 'sent', cooldown_seconds: 30 })
    }
    renderFlow()
    await sendCode('a@example.com')

    const resend = await screen.findByRole('button', { name: /Resend code in \d+s/ })
    expect((resend as HTMLButtonElement).disabled).toBe(true)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(31_000)
    })
    const ready = screen.getByRole('button', { name: 'Resend code' })
    expect((ready as HTMLButtonElement).disabled).toBe(false)
    await userEvent.click(ready)
    expect(await screen.findByText(/A new code is on its way/)).toBeTruthy()
    expect(sent).toBe(2)
    // Cooldown restarts.
    expect(screen.getByRole('button', { name: /Resend code in \d+s/ })).toBeTruthy()
  })

  it('lets the user change the email address from the code step', async () => {
    routes['/auth/forgot-password'] = () => json(200, { message: 'sent', cooldown_seconds: 60 })
    renderFlow()
    await sendCode('a@example.com')
    await userEvent.click(await screen.findByRole('button', { name: 'Use a different email' }))
    expect(screen.getByRole('button', { name: 'Send Code' })).toBeTruthy()
  })

  it('checks that the two new passwords match and follow the policy before submitting', async () => {
    routes['/auth/forgot-password'] = () => json(200, { message: 'sent', cooldown_seconds: 60 })
    routes['/auth/forgot-password/verify'] = () =>
      json(200, { reset_token: 'reset-token-abcdef', expires_in_seconds: 600 })
    renderFlow()
    await sendCode('a@example.com')
    await userEvent.type(await screen.findByLabelText('Verification Code'), '123456')
    await userEvent.click(screen.getByRole('button', { name: 'Verify Code' }))

    await userEvent.type(await screen.findByLabelText('New Password', { exact: true }), 'short')
    await userEvent.type(screen.getByLabelText('Confirm Password'), 'different1')
    await userEvent.click(screen.getByRole('button', { name: 'Reset Password' }))
    expect(screen.getByText(/at least 8 characters/)).toBeTruthy()
    expect(screen.getByText('The two passwords don’t match.')).toBeTruthy()
    expect(requests.some((r) => r.path.endsWith('/reset'))).toBe(false)
  })

  it('explains an expired reset session and offers a fresh start', async () => {
    routes['/auth/forgot-password'] = () => json(200, { message: 'sent', cooldown_seconds: 60 })
    routes['/auth/forgot-password/verify'] = () =>
      json(200, { reset_token: 'reset-token-abcdef', expires_in_seconds: 600 })
    routes['/auth/forgot-password/reset'] = () => error(401, 'INVALID_TOKEN')
    renderFlow()
    await sendCode('a@example.com')
    await userEvent.type(await screen.findByLabelText('Verification Code'), '123456')
    await userEvent.click(screen.getByRole('button', { name: 'Verify Code' }))
    await userEvent.type(await screen.findByLabelText('New Password', { exact: true }), 'newpass99')
    await userEvent.type(screen.getByLabelText('Confirm Password'), 'newpass99')
    await userEvent.click(screen.getByRole('button', { name: 'Reset Password' }))
    expect((await screen.findByRole('alert')).textContent).toMatch(/reset session has expired/)

    await userEvent.click(screen.getByRole('button', { name: 'Start over' }))
    expect(screen.getByRole('button', { name: 'Send Code' })).toBeTruthy()
  })

  it('never writes the email, code or reset token to browser storage', async () => {
    routes['/auth/forgot-password'] = () => json(200, { message: 'sent', cooldown_seconds: 60 })
    routes['/auth/forgot-password/verify'] = () =>
      json(200, { reset_token: 'reset-token-abcdef', expires_in_seconds: 600 })
    renderFlow()
    await sendCode('a@example.com')
    await userEvent.type(await screen.findByLabelText('Verification Code'), '123456')
    await userEvent.click(screen.getByRole('button', { name: 'Verify Code' }))
    await screen.findByLabelText('New Password', { exact: true })
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })
})
