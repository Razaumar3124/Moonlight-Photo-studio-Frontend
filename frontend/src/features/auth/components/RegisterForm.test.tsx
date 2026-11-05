// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as mockAuth from '../lib/mockAuth'
import { LoginForm } from './LoginForm'
import { RegisterForm } from './RegisterForm'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderAt(element: React.ReactNode) {
  const router = createMemoryRouter(
    [
      { path: '/', element },
      { path: '/memory-wall', element: <h1>Planner</h1> },
      { path: '/forgot-password', element: <h1>Forgot</h1> },
    ],
    { initialEntries: ['/'] },
  )
  render(<RouterProvider router={router} />)
  return router
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

  it('sends a normalised payload and navigates on success', async () => {
    const spy = vi.spyOn(mockAuth, 'mockRegister').mockResolvedValue()
    const router = renderAt(<RegisterForm />)
    await userEvent.type(screen.getByLabelText('Full Name'), '  Aarav   Sharma ')
    await userEvent.type(screen.getByLabelText('Email Address'), 'Aarav@Example.com')
    await userEvent.type(screen.getByLabelText(/Mobile Number/), '98765 43210')
    await userEvent.type(screen.getByLabelText('Password', { exact: true }), 'memories85')
    await userEvent.click(screen.getByRole('button', { name: 'Create Account' }))
    expect(spy).toHaveBeenCalledWith(
      {
        full_name: 'Aarav Sharma',
        email: 'aarav@example.com',
        phone: '+919876543210',
        password: 'memories85',
      },
      expect.any(AbortSignal),
    )
    expect(await screen.findByRole('heading', { name: 'Planner' })).toBeTruthy()
    expect(router.state.location.pathname).toBe('/memory-wall')
  })

  it('blocks invalid input without calling the API', async () => {
    const spy = vi.spyOn(mockAuth, 'mockRegister')
    renderAt(<RegisterForm />)
    await userEvent.type(screen.getByLabelText('Email Address'), '"><script>@x.com')
    await userEvent.click(screen.getByRole('button', { name: 'Create Account' }))
    expect(screen.getByText('Enter a valid email address.')).toBeTruthy()
    expect(spy).not.toHaveBeenCalled()
  })

  it('shows "Google sign-in is coming soon" instead of calling anything', async () => {
    renderAt(<RegisterForm />)
    await userEvent.click(screen.getByRole('button', { name: 'Continue with Google' }))
    expect(screen.getByRole('status').textContent).toMatch(/coming soon/)
  })
})

describe('LoginForm', () => {
  it('sends email OR phone (E.164) and navigates on success', async () => {
    const spy = vi.spyOn(mockAuth, 'mockLogin').mockResolvedValue()
    renderAt(<LoginForm />)
    await userEvent.type(screen.getByLabelText('Mobile No. or Email'), '098765 43210')
    await userEvent.type(screen.getByLabelText('Password', { exact: true }), 'pw')
    await userEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(spy).toHaveBeenCalledWith({ phone: '+919876543210', password: 'pw' }, expect.any(AbortSignal))
    expect(await screen.findByRole('heading', { name: 'Planner' })).toBeTruthy()
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
