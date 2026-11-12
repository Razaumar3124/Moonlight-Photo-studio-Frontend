// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, Link, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/services/apiClient'
import { tokenStorage } from '@/services/tokenStorage'
import { TEST_USER } from '@/test/fakeAuth'
import { AuthProvider } from './AuthProvider'
import { useAuth } from './authContext'
import { LoginForm } from './components/LoginForm'
import { LoginNotice } from './components/LoginNotice'
import { GuestRoute, ProtectedRoute } from './components/RouteGuards'

/**
 * Integration of AuthProvider + apiClient + route guards against a scripted fake API (`fetch`).
 * Everything except the network is real, so these cover session restoration, redirects,
 * refresh and logout the way the browser experiences them.
 */

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const noContent = () => new Response(null, { status: 204 })
const error = (status: number, code: string) =>
  json(status, { error: { code, message: 'server text', details: [], timestamp: '' } })

const TOKENS = { access_token: 'access-1', token_type: 'bearer', expires_in: 900 }
const SESSION = { user: TEST_USER, tokens: TOKENS }

type Handler = (init: RequestInit) => Response | Promise<Response>
let routes: Record<string, Handler>
const calls: { path: string; init: RequestInit }[] = []

beforeEach(() => {
  calls.length = 0
  routes = {}
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const path = String(url).replace('/api/v1', '')
      calls.push({ path, init })
      const handler = routes[`${init.method ?? 'GET'} ${path}`]
      if (!handler) throw new Error(`Unexpected request: ${init.method ?? 'GET'} ${path}`)
      return handler(init)
    }),
  )
})

afterEach(() => {
  cleanup()
  tokenStorage.clear()
  vi.restoreAllMocks()
  localStorage.clear()
  sessionStorage.clear()
})

function Planner() {
  const { user, logout } = useAuth()
  return (
    <div>
      <h1>Planner for {user?.full_name}</h1>
      <button onClick={() => void logout().catch(() => undefined)}>Sign out</button>
      <button onClick={() => void api.get('/designs').catch(() => undefined)}>Load designs</button>
    </div>
  )
}

function renderApp(initialPath = '/memory-wall') {
  const router = createMemoryRouter(
    [
      {
        path: '/login',
        element: (
          <GuestRoute>
            <h1>Sign in page</h1>
            <LoginNotice />
            <LoginForm />
            <Link to="/forgot-password">forgot</Link>
          </GuestRoute>
        ),
      },
      { path: '/forgot-password', element: <GuestRoute>Forgot</GuestRoute> },
      {
        path: '/memory-wall',
        element: (
          <ProtectedRoute>
            <Planner />
          </ProtectedRoute>
        ),
      },
      {
        path: '/other',
        element: (
          <ProtectedRoute>
            <h1>Other page</h1>
          </ProtectedRoute>
        ),
      },
    ],
    { initialEntries: [initialPath] },
  )
  render(
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>,
  )
  return router
}

function fail(message: string): never {
  throw new Error(message)
}

describe('session restoration', () => {
  it('restores the session from the refresh cookie on reload, without flashing the sign-in page', async () => {
    routes['POST /auth/refresh'] = () => json(200, TOKENS)
    routes['GET /auth/me'] = () => json(200, TEST_USER)
    const router = renderApp('/memory-wall')

    expect(screen.getByRole('status')).toBeTruthy() // loader while restoring
    expect(screen.queryByText('Sign in page')).toBeNull()
    expect(await screen.findByRole('heading', { name: 'Planner for Aarav Sharma' })).toBeTruthy()
    expect(router.state.location.pathname).toBe('/memory-wall')

    // The refresh call is a credentialed POST with the CSRF header and no bearer token.
    const refresh = calls[0] ?? fail('no request')
    expect(refresh.path).toBe('/auth/refresh')
    expect(refresh.init.credentials).toBe('include')
    expect(new Headers(refresh.init.headers).get('X-CSRF-Protection')).toBe('1')
    expect(new Headers(refresh.init.headers).has('Authorization')).toBe(false)
    // /auth/me carries the fresh access token.
    expect(new Headers(calls[1]?.init.headers).get('Authorization')).toBe('Bearer access-1')
  })

  it('sends a signed-out visitor from a protected page to sign in, remembering where they were going', async () => {
    routes['POST /auth/refresh'] = () => error(401, 'INVALID_TOKEN')
    const router = renderApp('/other')
    expect(await screen.findByRole('heading', { name: 'Sign in page' })).toBeTruthy()
    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.state).toEqual({ from: '/other' })

    routes['POST /auth/login'] = () => json(200, SESSION)
    await userEvent.type(screen.getByLabelText('Mobile No. or Email'), 'aarav@example.com')
    await userEvent.type(screen.getByLabelText('Password', { exact: true }), 'memories85')
    await userEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(await screen.findByRole('heading', { name: 'Other page' })).toBeTruthy()
    expect(router.state.location.pathname).toBe('/other')
  })

  it('tells the visitor when the server could not be reached instead of claiming the session expired', async () => {
    routes['POST /auth/refresh'] = () => {
      throw new TypeError('Failed to fetch')
    }
    renderApp('/memory-wall')
    expect(await screen.findByText(/couldn’t reach the server to restore your session/)).toBeTruthy()
  })

  it('keeps signed-in visitors off the auth pages', async () => {
    routes['POST /auth/refresh'] = () => json(200, TOKENS)
    routes['GET /auth/me'] = () => json(200, TEST_USER)
    const router = renderApp('/login')
    expect(await screen.findByRole('heading', { name: /Planner for/ })).toBeTruthy()
    expect(router.state.location.pathname).toBe('/memory-wall')
  })
})

describe('signing in', () => {
  it('stores the access token in memory only and never in Web Storage', async () => {
    routes['POST /auth/refresh'] = () => error(401, 'INVALID_TOKEN')
    routes['POST /auth/login'] = () => json(200, SESSION)
    routes['GET /designs'] = () => json(200, {})
    renderApp('/login')
    await screen.findByRole('heading', { name: 'Sign in page' })
    await userEvent.type(screen.getByLabelText('Mobile No. or Email'), 'aarav@example.com')
    await userEvent.type(screen.getByLabelText('Password', { exact: true }), 'memories85')
    await userEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    await screen.findByRole('heading', { name: /Planner for/ })

    expect(tokenStorage.getAccessToken()).toBe('access-1')
    expect(JSON.stringify({ ...localStorage })).not.toMatch(/access-1|token/i)
    expect(JSON.stringify({ ...sessionStorage })).not.toMatch(/access-1|token/i)

    const login = calls.find((c) => c.path === '/auth/login') ?? fail('no login request')
    expect(new Headers(login.init.headers).get('X-CSRF-Protection')).toBe('1')
    expect(new Headers(login.init.headers).has('Authorization')).toBe(false)
    expect(JSON.parse(String(login.init.body))).toEqual({
      email: 'aarav@example.com',
      password: 'memories85',
    })
  })
})

describe('session lifetime', () => {
  async function signedIn() {
    routes['POST /auth/refresh'] = () => json(200, TOKENS)
    routes['GET /auth/me'] = () => json(200, TEST_USER)
    const router = renderApp('/memory-wall')
    await screen.findByRole('heading', { name: /Planner for/ })
    return router
  }

  it('renews an expired access token transparently and replays the request', async () => {
    await signedIn()
    let designCalls = 0
    routes['GET /designs'] = () => (++designCalls === 1 ? error(401, 'TOKEN_EXPIRED') : json(200, {}))
    routes['POST /auth/refresh'] = () => json(200, { ...TOKENS, access_token: 'access-2' })
    await userEvent.click(screen.getByRole('button', { name: 'Load designs' }))
    await waitFor(() => expect(tokenStorage.getAccessToken()).toBe('access-2'))
    expect(designCalls).toBe(2)
    expect(screen.getByRole('heading', { name: /Planner for/ })).toBeTruthy()
  })

  it('sends the user to sign in, with a notice, when the session can no longer be renewed', async () => {
    const router = await signedIn()
    routes['GET /designs'] = () => error(401, 'TOKEN_EXPIRED')
    routes['POST /auth/refresh'] = () => error(401, 'TOKEN_REVOKED')
    await userEvent.click(screen.getByRole('button', { name: 'Load designs' }))
    expect(await screen.findByRole('heading', { name: 'Sign in page' })).toBeTruthy()
    expect(router.state.location.pathname).toBe('/login')
    expect(screen.getByText('Your session has ended. Please sign in again.')).toBeTruthy()
    expect(tokenStorage.getAccessToken()).toBeNull()
  })

  it('signs out: revokes on the server with the CSRF header, clears memory, returns to sign in', async () => {
    const router = await signedIn()
    routes['POST /auth/logout'] = () => noContent()
    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in page' })).toBeTruthy()
    expect(router.state.location.pathname).toBe('/login')
    expect(tokenStorage.hasSession()).toBe(false)
    const logout = calls.find((c) => c.path === '/auth/logout') ?? fail('no logout request')
    expect(new Headers(logout.init.headers).get('X-CSRF-Protection')).toBe('1')
    expect(logout.init.credentials).toBe('include')
    // No "session ended" notice after a deliberate sign-out.
    expect(screen.queryByText(/session has ended/)).toBeNull()
  })

  it('stays signed in when sign-out could not reach the server (the cookie would still be valid)', async () => {
    await signedIn()
    routes['POST /auth/logout'] = () => {
      throw new TypeError('Failed to fetch')
    }
    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/auth/logout')).toBe(true))
    expect(screen.getByRole('heading', { name: /Planner for/ })).toBeTruthy()
    expect(tokenStorage.hasSession()).toBe(true)
  })
})
