// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AuthContextValue } from '../authContext'
import type { GoogleCredentialResponse } from '../lib/googleIdentity'
import type { User } from '@/types/api'
import { TEST_USER } from '@/test/fakeAuth'

const envMock = vi.hoisted(() => ({ googleClientId: 'test-client.apps.googleusercontent.com' }))
vi.mock('@/config/env', () => ({
  env: {
    get googleClientId() {
      return envMock.googleClientId
    },
    apiBaseUrl: '/api/v1',
    isDev: false,
  },
}))

type GoogleCallback = (response: GoogleCredentialResponse) => void
type GoogleId = NonNullable<NonNullable<Window['google']>['accounts']>['id']
let initialize: ReturnType<typeof vi.fn<NonNullable<GoogleId>['initialize']>>
let renderButton: ReturnType<typeof vi.fn<NonNullable<GoogleId>['renderButton']>>
let callback: GoogleCallback | undefined

// googleIdentity keeps module-level state (script promise, initialised client id), so every test
// gets fresh copies of the modules involved (all from the same registry, so instanceof still works).
let GoogleSignIn: typeof import('./GoogleSignIn').GoogleSignIn
let ApiError: typeof import('@/services/apiClient').ApiError
let fakeAuth: typeof import('@/test/fakeAuth').fakeAuth
let WithAuth: typeof import('@/test/fakeAuth').WithAuth

function installGoogle() {
  initialize = vi.fn<NonNullable<GoogleId>['initialize']>((config) => {
    callback = config.callback
  })
  renderButton = vi.fn<NonNullable<GoogleId>['renderButton']>((parent) => {
    const button = document.createElement('div')
    button.setAttribute('data-testid', 'google-rendered-button')
    parent.append(button)
  })
  window.google = { accounts: { id: { initialize, renderButton } } }
}

beforeEach(async () => {
  vi.resetModules()
  ;({ GoogleSignIn } = await import('./GoogleSignIn'))
  ;({ ApiError } = await import('@/services/apiClient'))
  ;({ fakeAuth, WithAuth } = await import('@/test/fakeAuth'))
  envMock.googleClientId = 'test-client.apps.googleusercontent.com'
  callback = undefined
  installGoogle()
})

afterEach(() => {
  cleanup()
  delete window.google
  document.head.querySelectorAll('script[src*="accounts.google.com"]').forEach((el) => el.remove())
  vi.restoreAllMocks()
})

async function renderGoogle(auth = fakeAuth()) {
  render(
    <WithAuth value={auth}>
      <GoogleSignIn />
    </WithAuth>,
  )
  await screen.findByTestId('google-rendered-button')
  return auth
}

describe('GoogleSignIn', () => {
  it('initialises Identity Services once for the configured client and draws Google’s button', async () => {
    await renderGoogle()
    expect(initialize).toHaveBeenCalledTimes(1)
    expect(initialize.mock.calls[0]?.[0]).toMatchObject({
      client_id: 'test-client.apps.googleusercontent.com',
      ux_mode: 'popup',
      auto_select: false,
    })
    expect(renderButton.mock.calls[0]?.[1]).toMatchObject({ text: 'continue_with', type: 'standard', locale: 'en' })
  })

  it('forwards the Google ID token to the auth layer and nothing else', async () => {
    const auth = await renderGoogle()
    await act(async () => {
      void callback?.({ credential: 'google-id-token-jwt' })
    })
    expect(auth.loginWithGoogle).toHaveBeenCalledWith('google-id-token-jwt', expect.any(AbortSignal))
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    expect(document.body.textContent).not.toContain('google-id-token-jwt')
  })

  it('ignores a callback without a credential (user dismissed the popup) and says so', async () => {
    const auth = await renderGoogle()
    await act(async () => {
      void callback?.({})
    })
    expect(auth.loginWithGoogle).not.toHaveBeenCalled()
    expect((await screen.findByRole('alert')).textContent).toMatch(/didn’t return a sign-in/)
  })

  it.each([
    [401, 'INVALID_GOOGLE_TOKEN', /couldn’t verify your Google sign-in/],
    [503, 'GOOGLE_AUTH_NOT_CONFIGURED', /isn’t available right now/],
    [429, 'RATE_LIMIT_EXCEEDED', /Too many attempts/],
    [403, 'ACCOUNT_DISABLED', /disabled/],
    [500, 'INTERNAL_ERROR', /couldn’t sign you in/],
    [0, 'NETWORK_ERROR', /Unable to reach/],
  ])('shows a safe message when POST /auth/google fails with %i (%s)', async (status, code, message) => {
    const auth = fakeAuth({
      loginWithGoogle: vi.fn<AuthContextValue['loginWithGoogle']>().mockRejectedValue(
        new ApiError({
          status,
          code,
          message: status === 0 ? 'Unable to reach the server.' : 'raw server text',
        }),
      ),
    })
    await renderGoogle(auth)
    await act(async () => {
      void callback?.({ credential: 'tok-123456789' })
    })
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(message)
    expect(alert.textContent).not.toMatch(/raw server text|tok-123456789/)
  })

  it('ignores a second credential while one is being exchanged', async () => {
    let finish: () => void = () => undefined
    const auth = fakeAuth({
      loginWithGoogle: vi.fn<AuthContextValue['loginWithGoogle']>(
        () =>
          new Promise<User>((resolve) => {
            finish = () => resolve(TEST_USER)
          }),
      ),
    })
    await renderGoogle(auth)
    await act(async () => {
      void callback?.({ credential: 'first-credential' })
    })
    await act(async () => {
      void callback?.({ credential: 'second-credential' })
    })
    expect(auth.loginWithGoogle).toHaveBeenCalledTimes(1)
    await act(async () => finish())
  })

  it('without a configured client ID shows a disabled button and an honest notice (no network, no script)', async () => {
    envMock.googleClientId = ''
    delete window.google
    render(
      <WithAuth value={fakeAuth()}>
        <GoogleSignIn />
      </WithAuth>,
    )
    const button = screen.getByRole('button', { name: 'Continue with Google' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(screen.getByText(/Google sign-in isn’t available right now/)).toBeTruthy()
    expect(document.head.querySelector('script[src*="accounts.google.com"]')).toBeNull()
  })

  it('falls back gracefully when the Google script cannot load (offline, blocked)', async () => {
    delete window.google
    render(
      <WithAuth value={fakeAuth()}>
        <GoogleSignIn />
      </WithAuth>,
    )
    const script = document.head.querySelector('script[src*="accounts.google.com"]')
    expect(script).not.toBeNull()
    expect((screen.getByRole('button', { name: 'Continue with Google' }) as HTMLButtonElement).disabled).toBe(
      true,
    )
    act(() => {
      script?.dispatchEvent(new Event('error'))
    })
    await waitFor(() => expect(screen.getByText(/Google sign-in isn’t available right now/)).toBeTruthy())
  })
})
